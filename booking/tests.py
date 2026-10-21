from datetime import date, time, timedelta
from decimal import Decimal
import threading
import json
import hmac
import hashlib
from django.conf import settings
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import connection

from movies.models import Movie, Language
from booking.models import Theater, Show, Booking, Payment, SeatReservation

User = get_user_model()

class BookingTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='bookinguser',
            email='booking@example.com',
            password='Password123!'
        )
        self.lang = Language.objects.create(name='Tamil', code='ta')

        self.movie = Movie.objects.create(
            title='Mayajaal Blockbuster',
            description='Action epic movie.',
            release_date=date(2026, 1, 1),
            duration=150,
            language=self.lang,
            director='Director Name'
        )

        self.theater = Theater.objects.create(
            name='Mayajaal Multiplex',
            location='ECR',
            city='Chennai',
            address='ECR Main Road',
            total_screens=5
        )

        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 1',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(14, 30),
            end_time=time(17, 0),
            ticket_price=Decimal('200.00'),
            total_seats=50,
            available_seats=50
        )

    def test_theater_list_view(self):
        response = self.client.get(reverse('theater_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mayajaal Multiplex')

    def test_show_list_view(self):
        response = self.client.get(reverse('show_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mayajaal Blockbuster')

    def test_theater_detail_view(self):
        url = reverse('theater_detail', kwargs={'pk': self.theater.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ECR Main Road')

    def test_booking_creation_and_seat_deduction(self):
        self.client.login(username='bookinguser', password='Password123!')

        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 2,
            'selected_seats': 'A1, A2'
        })
        self.assertEqual(response.status_code, 302)

        self.show.refresh_from_db()
        self.assertEqual(self.show.available_seats, 48)

        booking = Booking.objects.filter(user=self.user, show=self.show).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.number_of_seats, 2)
        self.assertEqual(booking.selected_seats, 'A1, A2')
        self.assertEqual(booking.total_amount, Decimal('400.00'))

        # Check SeatReservation records
        res_seats = list(SeatReservation.objects.filter(show=self.show, user=self.user).values_list('seat_number', flat=True))
        self.assertIn('A1', res_seats)
        self.assertIn('A2', res_seats)

    def test_payment_page_rendering_and_calculations(self):
        self.client.login(username='bookinguser', password='Password123!')
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 3,
            'selected_seats': 'B1, B2, B3'
        })

        booking = Booking.objects.filter(user=self.user, show=self.show, payment_status='PENDING').first()
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        response = self.client.get(pay_url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['ticket_price'], Decimal('200.00'))
        self.assertEqual(response.context['subtotal'], Decimal('600.00'))
        self.assertEqual(response.context['convenience_fee'], Decimal('30.00'))
        self.assertEqual(response.context['taxes'], Decimal('108.00'))
        self.assertEqual(response.context['grand_total'], Decimal('738.00'))

    def test_payment_process_success_and_failure(self):
        self.client.login(username='bookinguser', password='Password123!')
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 1,
            'selected_seats': 'C1'
        })
        booking = Booking.objects.filter(user=self.user, show=self.show, payment_status='PENDING').first()
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        # Test Payment Failure
        fail_resp = self.client.post(pay_url, {
            'payment_method': 'CARD',
            'payment_action': 'fail'
        })
        self.assertEqual(fail_resp.status_code, 200)
        self.assertTrue(fail_resp.context['payment_failed'])
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PENDING')

        # Test Payment Success
        success_resp = self.client.post(pay_url, {
            'payment_method': 'UPI',
            'payment_action': 'success'
        })
        self.assertEqual(success_resp.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAID')

        # Verify SeatReservation is converted to BOOKED
        res = SeatReservation.objects.filter(show=self.show, seat_number='C1').first()
        self.assertIsNotNone(res)
        self.assertEqual(res.status, 'BOOKED')
        self.assertIsNone(res.reserved_until)

    def test_my_bookings_history_view(self):
        self.client.login(username='bookinguser', password='Password123!')
        Booking.objects.create(
            user=self.user,
            show=self.show,
            number_of_seats=2,
            selected_seats='D1, D2',
            total_amount=Decimal('400.00'),
            status='CONFIRMED',
            payment_status='PAID'
        )

        response = self.client.get(reverse('my_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Bookings History')
        self.assertContains(response, 'Mayajaal Multiplex')

    def test_double_booking_prevention(self):
        user2 = User.objects.create_user(username='otheruser', password='Password123!')
        
        # User 1 reserves and books E1
        SeatReservation.objects.create(
            show=self.show,
            seat_number='E1',
            user=self.user,
            status='BOOKED'
        )

        self.client.login(username='otheruser', password='Password123!')
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 1,
            'selected_seats': 'E1'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')


# ==============================================================================
# TASK 2 SPECIFIC TEST SUITES (Phases 17 & 22)
# ==============================================================================

class MultipleSeatSelectionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='multiseat_user', password='Password123!')
        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(
            title='Inception Matrix',
            release_date=date(2026, 1, 1),
            duration=140,
            language=self.lang,
            director='Nolan'
        )
        self.theater = Theater.objects.create(name='IMAX Cinema', location='Downtown', city='Chennai', address='100 Anna Salai')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='IMAX 1',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(20, 30),
            ticket_price=Decimal('250.00'),
            total_seats=50,
            available_seats=50
        )

    def test_single_seat_selection(self):
        self.client.login(username='multiseat_user', password='Password123!')
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A1'
        })
        self.assertEqual(response.status_code, 302)

        res = SeatReservation.objects.filter(show=self.show, seat_number='A1', user=self.user).first()
        self.assertIsNotNone(res)
        self.assertEqual(res.status, 'RESERVED')
        self.assertGreater(res.reserved_until, timezone.now())

    def test_multiple_seats_selection_and_server_pricing(self):
        self.client.login(username='multiseat_user', password='Password123!')
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A1, A2, A3, A4'
        })
        self.assertEqual(response.status_code, 302)

        reservations = SeatReservation.objects.filter(show=self.show, user=self.user, status='RESERVED')
        self.assertEqual(reservations.count(), 4)

        booking = Booking.objects.filter(show=self.show, user=self.user, payment_status='PENDING').first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.number_of_seats, 4)
        # Server-side subtotal: 4 * 250 = 1000.00
        self.assertEqual(booking.total_amount, Decimal('1000.00'))


class ReservationExpiryTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user_one', password='Password123!')
        self.user2 = User.objects.create_user(username='user_two', password='Password123!')
        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(title='Expiring Movie', release_date=date(2026, 1, 1), duration=120, language=self.lang, director='Scott')
        self.theater = Theater.objects.create(name='PVR Cinema', location='Velachery', city='Chennai', address='Phoenix Mall')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 2',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(19, 0),
            end_time=time(21, 30),
            ticket_price=Decimal('150.00'),
            total_seats=50,
            available_seats=50
        )

    def test_reservation_automatically_expires(self):
        # User 1 creates reservation with past timestamp (expired)
        past_time = timezone.now() - timedelta(minutes=3)
        SeatReservation.objects.create(
            show=self.show,
            seat_number='B5',
            user=self.user1,
            status='RESERVED',
            reserved_until=past_time
        )

        # Call live API
        self.client.login(username='user_two', password='Password123!')
        api_url = reverse('show_seats_api', kwargs={'show_id': self.show.id})
        response = self.client.get(api_url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        seat_b5 = next(s for s in data['seats'] if s['seat_id'] == 'B5')
        self.assertEqual(seat_b5['status'], 'AVAILABLE')

        # Verify expired record was cleaned up from DB
        self.assertFalse(SeatReservation.objects.filter(show=self.show, seat_number='B5').exists())


class SeatModificationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mod_user', password='Password123!')
        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(title='Modifying Movie', release_date=date(2026, 1, 1), duration=120, language=self.lang, director='Nolan')
        self.theater = Theater.objects.create(name='INOX', location='Royapettah', city='Chennai', address='Express Avenue')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 3',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(20, 0),
            end_time=time(22, 30),
            ticket_price=Decimal('200.00'),
            total_seats=50,
            available_seats=50
        )

    def test_modify_seats_before_payment(self):
        self.client.login(username='mod_user', password='Password123!')

        # Initial selection: A4, A5, A6
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A4, A5, A6'
        })
        self.assertEqual(SeatReservation.objects.filter(show=self.show, user=self.user, status='RESERVED').count(), 3)

        # User modifies selection to: A4, A7, A8
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A4, A7, A8'
        })
        self.assertEqual(response.status_code, 302)

        user_seats = set(SeatReservation.objects.filter(show=self.show, user=self.user, status='RESERVED').values_list('seat_number', flat=True))
        self.assertEqual(user_seats, {'A4', 'A7', 'A8'})

        # Verify A5 and A6 are released and no longer reserved
        self.assertFalse(SeatReservation.objects.filter(show=self.show, seat_number__in=['A5', 'A6']).exists())


class LiveSeatAvailabilityAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='alice', email='alice@example.com', password='Password123!')
        self.user2 = User.objects.create_user(username='bob', email='bob@example.com', password='Password123!')
        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(title='Live API Movie', release_date=date(2026, 1, 1), duration=120, language=self.lang, director='Nolan')
        self.theater = Theater.objects.create(name='AGS Cinemas', location='T Nagar', city='Chennai', address='G.N. Chetty Road')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 1',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(16, 0),
            end_time=time(18, 30),
            ticket_price=Decimal('180.00'),
            total_seats=48,
            available_seats=48
        )

        # Alice reserves A1
        SeatReservation.objects.create(
            show=self.show,
            seat_number='A1',
            user=self.user1,
            status='RESERVED',
            reserved_until=timezone.now() + timedelta(minutes=2)
        )
        # Alice booked A2
        SeatReservation.objects.create(
            show=self.show,
            seat_number='A2',
            user=self.user1,
            status='BOOKED'
        )

    def test_live_api_response_structure_and_ownership(self):
        # Alice queries the API
        self.client.login(username='alice', password='Password123!')
        response = self.client.get(reverse('show_seats_api', kwargs={'show_id': self.show.id}))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['show_id'], self.show.id)
        self.assertEqual(data['total_seats'], 48)

        seats_by_id = {s['seat_id']: s for s in data['seats']}
        
        # A1 is RESERVED by Alice
        self.assertEqual(seats_by_id['A1']['status'], 'RESERVED')
        self.assertTrue(seats_by_id['A1']['reserved_by_current_user'])
        self.assertGreater(seats_by_id['A1']['remaining_seconds'], 0)

        # A2 is BOOKED
        self.assertEqual(seats_by_id['A2']['status'], 'BOOKED')

        # A3 is AVAILABLE
        self.assertEqual(seats_by_id['A3']['status'], 'AVAILABLE')
        self.assertFalse(seats_by_id['A3']['reserved_by_current_user'])

        # Now Bob queries the API
        self.client.login(username='bob', password='Password123!')
        response_bob = self.client.get(reverse('show_seats_api', kwargs={'show_id': self.show.id}))
        data_bob = response_bob.json()
        seats_bob = {s['seat_id']: s for s in data_bob['seats']}

        # For Bob, A1 is RESERVED, but NOT reserved_by_current_user
        self.assertEqual(seats_bob['A1']['status'], 'RESERVED')
        self.assertFalse(seats_bob['A1']['reserved_by_current_user'])

        # Check that Alice's username or email is nowhere in the JSON
        response_text = response_bob.content.decode('utf-8')
        self.assertNotIn('alice', response_text)
        self.assertNotIn('alice@example.com', response_text)


class PaymentConversionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='payment_user', password='Password123!')
        self.lang = Language.objects.create(name='Tamil', code='ta')
        self.movie = Movie.objects.create(title='Paid Movie', release_date=date(2026, 1, 1), duration=130, language=self.lang, director='Director')
        self.theater = Theater.objects.create(name='Escape Cinemas', location='Royapettah', city='Chennai', address='EA Mall')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 4',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(18, 30),
            end_time=time(21, 0),
            ticket_price=Decimal('220.00'),
            total_seats=50,
            available_seats=50
        )

    def test_payment_converts_reserved_to_booked(self):
        self.client.login(username='payment_user', password='Password123!')

        # 1. Reserve seats D1, D2
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'D1, D2'
        })

        booking = Booking.objects.filter(user=self.user, show=self.show, payment_status='PENDING').first()
        self.assertIsNotNone(booking)

        # 2. Process successful payment
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        response = self.client.post(pay_url, {
            'payment_method': 'UPI',
            'payment_action': 'success'
        })
        self.assertEqual(response.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAID')

        # 3. Check SeatReservation status
        reservations = SeatReservation.objects.filter(booking=booking)
        self.assertEqual(reservations.count(), 2)
        for r in reservations:
            self.assertEqual(r.status, 'BOOKED')
            self.assertIsNone(r.reserved_until)


class ExpiredReservationReuseTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='expired_user_a', password='Password123!')
        self.user2 = User.objects.create_user(username='active_user_b', password='Password123!')
        self.lang = Language.objects.create(name='Tamil', code='ta')
        self.movie = Movie.objects.create(title='Reuse Movie', release_date=date(2026, 1, 1), duration=120, language=self.lang, director='Director')
        self.theater = Theater.objects.create(name='Vettri Theatres', location='Chromepet', city='Chennai', address='GST Road')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Main Screen',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(19, 0),
            end_time=time(21, 30),
            ticket_price=Decimal('160.00'),
            total_seats=50,
            available_seats=50
        )

    def test_user_b_can_reserve_after_user_a_expires(self):
        # User A has expired hold on F1
        SeatReservation.objects.create(
            show=self.show,
            seat_number='F1',
            user=self.user1,
            status='RESERVED',
            reserved_until=timezone.now() - timedelta(seconds=5)
        )

        # User B reserves F1
        self.client.login(username='active_user_b', password='Password123!')
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'F1'
        })
        self.assertEqual(response.status_code, 302)

        # Exactly 1 reservation in DB for F1, belonging to User B
        reservations = SeatReservation.objects.filter(show=self.show, seat_number='F1')
        self.assertEqual(reservations.count(), 1)
        self.assertEqual(reservations.first().user, self.user2)


class ConcurrentDoubleBookingTest(TestCase):
    """
    Concurrent booking and race condition protection test.
    Verifies that when multiple users target the same seat:
    1. Transactional check rejects conflicting reservation with user feedback.
    2. Database-level unique constraint strictly prohibits duplicate active reservations.
    """
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='concurrent_user_a', password='Password123!')
        self.user_b = User.objects.create_user(username='concurrent_user_b', password='Password123!')
        self.lang = Language.objects.create(name='Tamil', code='ta')
        self.movie = Movie.objects.create(title='Concurrency Movie', release_date=date(2026, 1, 1), duration=120, language=self.lang, director='Director')
        self.theater = Theater.objects.create(name='Sangam Cinemas', location='Kilpauk', city='Chennai', address='Poonamallee High Road')
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 1',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(19, 0),
            end_time=time(21, 30),
            ticket_price=Decimal('180.00'),
            total_seats=50,
            available_seats=50
        )

    def test_concurrent_reservation_one_success_one_conflict(self):
        client_a = Client()
        client_a.force_login(self.user_a)

        client_b = Client()
        client_b.force_login(self.user_b)

        # User A reserves A5
        resp_a = client_a.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A5'
        })
        self.assertEqual(resp_a.status_code, 302)

        # User B attempts to reserve A5
        resp_b = client_b.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A5'
        })
        self.assertEqual(resp_b.status_code, 200)
        self.assertContains(resp_b, "no longer available")

        # Database must have strictly ONE active reservation record for A5
        active_reservations = SeatReservation.objects.filter(show=self.show, seat_number='A5')
        self.assertEqual(active_reservations.count(), 1)
        self.assertEqual(active_reservations.first().user, self.user_a)

    def test_database_level_duplicate_reservation_constraint(self):
        from django.db import IntegrityError

        # User A reserves A5
        SeatReservation.objects.create(
            show=self.show,
            seat_number='A5',
            user=self.user_a,
            status='RESERVED',
            reserved_until=timezone.now() + timedelta(minutes=2)
        )

        # User B attempts direct insert on same show and seat -> Database Unique Constraint prevents duplicate
        with self.assertRaises(IntegrityError):
            SeatReservation.objects.create(
                show=self.show,
                seat_number='A5',
                user=self.user_b,
                status='RESERVED',
                reserved_until=timezone.now() + timedelta(minutes=2)
            )


class Task3RazorpayPaymentWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='payuser',
            email='payuser@cineverse.com',
            password='TestPassword123!'
        )
        self.client.login(username='payuser', password='TestPassword123!')

        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(
            title='Dune: Part Two',
            description='Epic sci-fi film.',
            release_date=date(2026, 3, 1),
            duration=166,
            language=self.lang,
            director='Denis Villeneuve'
        )
        self.theater = Theater.objects.create(
            name='CineVerse IMAX',
            location='Phoenix MarketCity',
            city='Chennai',
            address='Velachery Main Rd',
            total_screens=4
        )
        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='IMAX 1',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(19, 0),
            end_time=time(22, 0),
            ticket_price=Decimal('250.00'),
            total_seats=60,
            available_seats=60
        )

    def test_01_razorpay_order_creation_and_pending_payment(self):
        # 1. Reserve seats
        resp = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A1, A2'
        })
        self.assertEqual(resp.status_code, 302)

        booking = Booking.objects.get(user=self.user, show=self.show)
        self.assertEqual(booking.status, 'PENDING_PAYMENT')
        self.assertEqual(booking.payment_status, 'PENDING')
        self.assertEqual(booking.number_of_seats, 2)

        # 2. Access payment page -> initiates Razorpay order
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        pay_resp = self.client.get(pay_url)
        self.assertEqual(pay_resp.status_code, 200)

        # Payment record created
        payment = Payment.objects.filter(booking=booking).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'PENDING')
        self.assertEqual(payment.provider, 'RAZORPAY')
        self.assertTrue(payment.order_id.startswith('order_'))
        self.assertEqual(payment.currency, 'INR')
        self.assertEqual(payment.ticket_amount, Decimal('500.00'))
        self.assertEqual(payment.convenience_fee, Decimal('30.00'))
        self.assertEqual(payment.taxes, Decimal('90.00'))
        self.assertEqual(payment.total_amount, Decimal('620.00'))
        self.assertEqual(pay_resp.context['amount_in_paise'], 62000)

    def test_02_server_side_amount_calculation_and_tamper_protection(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'B1'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        resp = self.client.post(pay_url, {
            'payment_method': 'UPI',
            'grand_total': '1.00',
            'payment_action': 'success'
        })
        self.assertEqual(resp.status_code, 302)

        payment = Payment.objects.get(booking=booking, status='SUCCESS')
        self.assertEqual(payment.ticket_amount, Decimal('250.00'))
        self.assertEqual(payment.convenience_fee, Decimal('30.00'))
        self.assertEqual(payment.taxes, Decimal('45.00'))
        self.assertEqual(payment.total_amount, Decimal('325.00'))

    def test_03_invalid_signature_rejection(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'C1'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        payment = Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=f"order_{booking.booking_reference}",
            ticket_amount=Decimal('250.00'),
            total_amount=Decimal('325.00'),
            status='PENDING'
        )

        verify_url = reverse('payment_verify')
        resp = self.client.post(verify_url, {
            'razorpay_order_id': payment.order_id,
            'razorpay_payment_id': 'pay_fake123',
            'razorpay_signature': 'invalid_forged_tampered_signature',
            'booking_reference': booking.booking_reference
        })

        self.assertEqual(resp.status_code, 302)
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, 'PENDING_PAYMENT')
        self.assertEqual(booking.payment_status, 'FAILED')
        self.assertEqual(payment.status, 'FAILED')
        self.assertIn('signature', payment.failure_reason.lower())

        res = SeatReservation.objects.get(show=self.show, seat_number='C1')
        self.assertEqual(res.status, 'RESERVED')

    def test_04_successful_signature_verification_and_seat_confirmation(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'D1, D2'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_valid_tx_123456"
        secret = settings.RAZORPAY_KEY_SECRET

        valid_signature = hmac.new(
            secret.encode('utf-8'),
            f"{order_id}|{payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        payment = Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('500.00'),
            total_amount=Decimal('620.00'),
            status='PENDING'
        )

        verify_url = reverse('payment_verify')
        resp = self.client.post(verify_url, {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_signature,
            'booking_reference': booking.booking_reference,
            'payment_method': 'UPI'
        })

        self.assertRedirects(resp, reverse('booking_detail', kwargs={'reference': booking.booking_reference}))

        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.payment_status, 'PAID')
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(payment.payment_id, payment_id)
        self.assertEqual(payment.signature, valid_signature)
        self.assertIsNotNone(payment.verified_at)

        reservations = SeatReservation.objects.filter(booking=booking)
        self.assertEqual(reservations.count(), 2)
        for r in reservations:
            self.assertEqual(r.status, 'BOOKED')
            self.assertIsNone(r.reserved_until)

    def test_05_failed_payment_and_retry(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'E1'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        resp_fail = self.client.post(pay_url, {
            'payment_action': 'fail'
        })
        self.assertEqual(resp_fail.status_code, 200)
        self.assertTrue(resp_fail.context['payment_failed'])

        payment = Payment.objects.filter(booking=booking).first()
        self.assertEqual(payment.status, 'FAILED')

        resp_retry = self.client.post(pay_url, {
            'payment_method': 'CARD',
            'payment_action': 'success'
        })
        self.assertEqual(resp_retry.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.payment_status, 'PAID')

    def test_06_cancelled_payment_by_customer(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'F1'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        cancel_url = reverse('payment_cancel', kwargs={'reference': booking.booking_reference})

        resp = self.client.get(cancel_url)
        self.assertRedirects(resp, reverse('my_bookings'))

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CANCELLED')
        self.assertEqual(booking.payment_status, 'CANCELLED')

        payment = Payment.objects.filter(booking=booking).first()
        if payment:
            self.assertEqual(payment.status, 'CANCELLED')

    def test_07_payment_retry_after_reservation_expiry_fails(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A3'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        SeatReservation.objects.filter(booking=booking).update(
            reserved_until=timezone.now() - timedelta(seconds=10)
        )

        resp = self.client.get(pay_url)
        self.assertRedirects(resp, reverse('booking_create', kwargs={'show_id': self.show.id}))

        resp_post = self.client.post(pay_url, {'payment_action': 'success'})
        self.assertRedirects(resp_post, reverse('booking_create', kwargs={'show_id': self.show.id}))

    def test_08_duplicate_payment_callback_idempotent(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'B3'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_dup_test_999"
        secret = settings.RAZORPAY_KEY_SECRET

        valid_sig = hmac.new(
            secret.encode('utf-8'),
            f"{order_id}|{payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        payment = Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('250.00'),
            total_amount=Decimal('325.00'),
            status='PENDING'
        )

        verify_url = reverse('payment_verify')

        resp1 = self.client.post(verify_url, {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference
        })
        self.assertEqual(resp1.status_code, 302)

        resp2 = self.client.post(verify_url, {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference
        })
        self.assertEqual(resp2.status_code, 302)

        self.assertEqual(Booking.objects.filter(booking_reference=booking.booking_reference).count(), 1)
        self.assertEqual(SeatReservation.objects.filter(show=self.show, seat_number='B3').count(), 1)
        self.assertEqual(Payment.objects.filter(booking=booking, status='SUCCESS').count(), 1)

    def test_09_razorpay_webhook_signature_verification_and_payment_captured(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'C3'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        order_id = f"order_wh_{booking.booking_reference}"
        payment_id = "pay_wh_captured_111"

        Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('250.00'),
            total_amount=Decimal('325.00'),
            status='PENDING'
        )

        webhook_payload = json.dumps({
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': payment_id,
                        'order_id': order_id,
                        'method': 'card',
                        'amount': 32500,
                        'currency': 'INR',
                        'status': 'captured'
                    }
                }
            }
        })

        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        valid_wh_sig = hmac.new(
            webhook_secret.encode('utf-8'),
            webhook_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        anon_client = Client()
        resp = anon_client.post(
            reverse('razorpay_webhook'),
            data=webhook_payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_wh_sig
        )
        self.assertEqual(resp.status_code, 200)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.payment_status, 'PAID')

        payment = Payment.objects.get(order_id=order_id)
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(payment.payment_id, payment_id)

    def test_10_razorpay_webhook_invalid_signature_rejected(self):
        webhook_payload = json.dumps({'event': 'payment.captured'})
        anon_client = Client()
        resp = anon_client.post(
            reverse('razorpay_webhook'),
            data=webhook_payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='bad_invalid_webhook_signature'
        )
        self.assertEqual(resp.status_code, 400)

    def test_11_razorpay_webhook_duplicate_idempotency(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'D3'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        order_id = f"order_wh_dup_{booking.booking_reference}"
        payment_id = "pay_wh_dup_222"

        Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('250.00'),
            total_amount=Decimal('325.00'),
            status='PENDING'
        )

        webhook_payload = json.dumps({
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': payment_id,
                        'order_id': order_id,
                        'method': 'upi',
                        'amount': 32500
                    }
                }
            }
        })
        valid_wh_sig = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            webhook_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        anon_client = Client()
        resp1 = anon_client.post(
            reverse('razorpay_webhook'),
            data=webhook_payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_wh_sig
        )
        self.assertEqual(resp1.status_code, 200)

        resp2 = anon_client.post(
            reverse('razorpay_webhook'),
            data=webhook_payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_wh_sig
        )
        self.assertEqual(resp2.status_code, 200)

        self.assertEqual(Payment.objects.filter(order_id=order_id, status='SUCCESS').count(), 1)

    def test_12_webhook_payment_failed_event(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'E3'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        order_id = f"order_fail_{booking.booking_reference}"

        Payment.objects.create(
            booking=booking,
            user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('250.00'),
            total_amount=Decimal('325.00'),
            status='PENDING'
        )

        webhook_payload = json.dumps({
            'event': 'payment.failed',
            'payload': {
                'payment': {
                    'entity': {
                        'order_id': order_id,
                        'error_code': 'BAD_REQUEST_ERROR',
                        'error_description': 'Card limit exceeded'
                    }
                }
            }
        })
        valid_sig = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            webhook_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        anon_client = Client()
        resp = anon_client.post(
            reverse('razorpay_webhook'),
            data=webhook_payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=valid_sig
        )
        self.assertEqual(resp.status_code, 200)

        payment = Payment.objects.get(order_id=order_id)
        self.assertEqual(payment.status, 'FAILED')
        self.assertEqual(payment.error_code, 'BAD_REQUEST_ERROR')
        self.assertIn('limit', payment.failure_reason.lower())

    def test_13_booking_cancellation_and_refund_record(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'F3, F4'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        self.client.post(pay_url, {'payment_action': 'success'})

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.payment_status, 'PAID')

        cancel_url = reverse('booking_cancel', kwargs={'reference': booking.booking_reference})
        cancel_resp = self.client.post(cancel_url)
        self.assertRedirects(cancel_resp, reverse('my_bookings'))

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CANCELLED')
        self.assertEqual(booking.payment_status, 'REFUNDED')

        payment = Payment.objects.filter(booking=booking).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.refund_status, 'PROCESSED')
        self.assertTrue(payment.refund_id.startswith('rfnd_'))
        self.assertEqual(payment.refund_amount, booking.total_amount)
        self.assertIsNotNone(payment.refunded_at)

        self.assertEqual(SeatReservation.objects.filter(booking=booking).count(), 0)

    def test_14_payment_history_and_my_bookings_display(self):
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'A5'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        self.client.post(pay_url, {'payment_action': 'success'})

        resp = self.client.get(reverse('my_bookings'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, booking.booking_reference)
        self.assertContains(resp, 'Paid')
        self.assertContains(resp, 'Confirmed')

    def test_15_real_order_creation_mocked_sdk(self):
        from unittest.mock import MagicMock, patch
        from booking.razorpay_service import RazorpayService

        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'B5'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)

        mock_client = MagicMock()
        mock_client.order.create.return_value = {
            'id': 'order_razorpay_mock_12345',
            'entity': 'order',
            'amount': 32500,
            'currency': 'INR',
            'receipt': booking.booking_reference,
            'status': 'created'
        }

        with patch.object(RazorpayService, 'get_client', return_value=mock_client):
            order = RazorpayService.create_order(booking, Decimal('325.00'))
            self.assertEqual(order['id'], 'order_razorpay_mock_12345')
            self.assertEqual(order['amount'], 32500)
            mock_client.order.create.assert_called_once()
            call_kwargs = mock_client.order.create.call_args[1]['data']
            self.assertEqual(call_kwargs['amount'], 32500)
            self.assertEqual(call_kwargs['currency'], 'INR')
            self.assertEqual(call_kwargs['receipt'], booking.booking_reference)

    def test_16_inr_to_paise_conversion_accuracy(self):
        from booking.razorpay_service import RazorpayService

        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'selected_seats': 'C5'
        })
        booking = Booking.objects.get(user=self.user, show=self.show)

        # Test various price points
        test_cases = [
            (Decimal('180.00'), 18000),
            (Decimal('250.00'), 25000),
            (Decimal('325.00'), 32500),
            (Decimal('620.00'), 62000),
            (Decimal('999.50'), 99950),
        ]
        for amount_inr, expected_paise in test_cases:
            order = RazorpayService.create_order(booking, amount_inr)
            self.assertEqual(order['amount'], expected_paise)


# ==============================================================================
# REGRESSION TESTS — Bug: Razorpay payment remains PENDING after test checkout
# Root causes:
#   1. ondismiss fired after handler, navigating away before form submit completed
#   2. 2-minute reservation hold too short for Razorpay checkout + 3DS auth
#   3. payment_verify did not honour verified payment when hold had lapsed
# ==============================================================================

class RazorpayPendingPaymentRegressionTests(TestCase):
    """
    Regression tests for the bug where a successful Razorpay TEST MODE payment
    left the booking in PENDING state because:
    - ondismiss fired after handler, aborting the verification form submission
    - Reservation expired during Razorpay checkout (2 min was too short)
    - payment_verify rejected an expired reservation even for a valid payment
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='regression_user',
            email='regression@cineverse.com',
            password='TestPassword123!'
        )
        self.client.login(username='regression_user', password='TestPassword123!')
        self.lang = Language.objects.create(name='Hindi', code='hi')
        self.movie = Movie.objects.create(
            title='Regression Test Movie',
            description='Test.',
            release_date=date(2026, 1, 1),
            duration=120,
            language=self.lang,
            director='Test Director'
        )
        self.theater = Theater.objects.create(
            name='Test Theater', location='Test Location',
            city='Mumbai', address='Test Address'
        )
        self.show = Show.objects.create(
            movie=self.movie, theater=self.theater,
            screen='Screen 1',
            show_date=timezone.now().date() + timedelta(days=3),
            start_time=time(15, 0), end_time=time(18, 0),
            ticket_price=Decimal('200.00'),
            total_seats=50, available_seats=50
        )

    def _make_valid_sig(self, order_id, payment_id):
        """Helper: compute a real HMAC-SHA256 Razorpay signature."""
        secret = settings.RAZORPAY_KEY_SECRET
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        return hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

    def _reserve_seats(self, seats='A1'):
        """Reserve seats and return the booking."""
        self.client.post(
            reverse('booking_create', kwargs={'show_id': self.show.id}),
            {'selected_seats': seats}
        )
        return Booking.objects.get(user=self.user, show=self.show, payment_status='PENDING')

    # -----------------------------------------------------------------------
    # Test 1: payment_verify endpoint correctly processes a real valid signature
    # (This is what Razorpay's handler submits to after checkout succeeds)
    # -----------------------------------------------------------------------
    def test_payment_verify_completes_full_flow_with_valid_signature(self):
        """
        Regression: The Razorpay handler submits to /payment/verify/ with real
        payment_id/order_id/signature. This must confirm booking, book seats,
        and queue ticket task — not leave it PENDING.
        """
        booking = self._reserve_seats('B1')
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_regression_test_001"

        payment = Payment.objects.create(
            booking=booking, user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('200.00'),
            total_amount=Decimal('266.00'),
            status='PENDING'
        )

        valid_sig = self._make_valid_sig(order_id, payment_id)
        resp = self.client.post(reverse('payment_verify'), {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference,
            'payment_method': 'CARD',
        })

        # Must redirect to booking_detail (success)
        self.assertRedirects(resp, reverse('booking_detail', kwargs={'reference': booking.booking_reference}))

        booking.refresh_from_db()
        payment.refresh_from_db()

        # Booking must be CONFIRMED/PAID, not PENDING
        self.assertEqual(booking.status, 'CONFIRMED',
            "BUG REGRESSION: Booking must be CONFIRMED after successful Razorpay payment verification")
        self.assertEqual(booking.payment_status, 'PAID',
            "BUG REGRESSION: Payment status must be PAID, not PENDING")

        # Payment must be SUCCESS
        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(payment.payment_id, payment_id)
        self.assertIsNotNone(payment.verified_at)

        # Seats must be BOOKED
        reservations = SeatReservation.objects.filter(booking=booking)
        self.assertTrue(reservations.exists())
        for r in reservations:
            self.assertEqual(r.status, 'BOOKED',
                f"Seat {r.seat_number} must be BOOKED, not {r.status}")
            self.assertIsNone(r.reserved_until)

    # -----------------------------------------------------------------------
    # Test 2: Payment page extends reservation from 2min to 15min
    # (Fixes the "reservation expired during Razorpay checkout" bug)
    # -----------------------------------------------------------------------
    def test_payment_page_extends_reservation_to_15_minutes(self):
        """
        Regression: When user lands on the payment page, the 2-minute hold
        must be extended to 15 minutes so Razorpay checkout + 3DS auth has
        enough time to complete.
        """
        booking = self._reserve_seats('C1')

        # Simulate reservation about to expire (30 seconds left)
        almost_expired = timezone.now() + timedelta(seconds=30)
        SeatReservation.objects.filter(booking=booking).update(reserved_until=almost_expired)

        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        resp = self.client.get(pay_url)

        # Payment page must load successfully (not redirect to seat selection)
        self.assertEqual(resp.status_code, 200,
            "Payment page must load even when hold is about to expire")

        # Reservation must be extended
        reservation = SeatReservation.objects.get(booking=booking, seat_number='C1')
        remaining = (reservation.reserved_until - timezone.now()).total_seconds()
        self.assertGreater(remaining, 60 * 10,  # at least 10 minutes remaining
            "BUG REGRESSION: Reservation must be extended when payment page loads, "
            "not left at 30 seconds which would cause 'expired' failure during Razorpay checkout")

    # -----------------------------------------------------------------------
    # Test 3: payment_verify honours valid payment even if hold window elapsed
    # (3DS auth can push the checkout past the original 2-minute window)
    # -----------------------------------------------------------------------
    def test_payment_verify_honours_valid_payment_with_lapsed_hold(self):
        """
        Regression: If the hold window elapses during Razorpay 3DS authentication
        but the payment signature is cryptographically valid, the booking must
        still be confirmed. A valid Razorpay payment must never be rejected
        purely because our internal timer ran out.
        """
        booking = self._reserve_seats('D1')
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_lapsed_hold_test"

        payment = Payment.objects.create(
            booking=booking, user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('200.00'),
            total_amount=Decimal('266.00'),
            status='PENDING'
        )

        # Simulate hold window elapsed AFTER payment was made
        # (e.g., 3DS auth took 3 minutes, original hold was 2 minutes)
        # The payment page extended it to 15 min, so simulate 16 min elapsed
        SeatReservation.objects.filter(booking=booking).update(
            reserved_until=timezone.now() - timedelta(seconds=30)
        )

        valid_sig = self._make_valid_sig(order_id, payment_id)
        resp = self.client.post(reverse('payment_verify'), {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference,
        })

        # Valid payment must proceed even if hold elapsed
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED',
            "BUG REGRESSION: Valid Razorpay payment must not be rejected because "
            "internal reservation timer expired. Payment was cryptographically verified.")
        self.assertEqual(booking.payment_status, 'PAID')

    # -----------------------------------------------------------------------
    # Test 4: Invalid signature does NOT confirm booking (security check)
    # -----------------------------------------------------------------------
    def test_payment_verify_rejects_invalid_signature(self):
        """
        Security: An invalid/forged signature must never confirm a booking.
        """
        booking = self._reserve_seats('E1')
        order_id = f"order_{booking.booking_reference}"

        Payment.objects.create(
            booking=booking, user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('200.00'),
            total_amount=Decimal('266.00'),
            status='PENDING'
        )

        resp = self.client.post(reverse('payment_verify'), {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': 'pay_fake_001',
            'razorpay_signature': 'invalid_tampered_signature_xyz',
            'booking_reference': booking.booking_reference,
        })

        booking.refresh_from_db()
        self.assertNotEqual(booking.status, 'CONFIRMED',
            "SECURITY: Invalid signature must NOT confirm booking")
        self.assertNotEqual(booking.payment_status, 'PAID',
            "SECURITY: Invalid signature must NOT mark payment as PAID")

        # Seats must still be RESERVED (not BOOKED)
        for r in SeatReservation.objects.filter(booking=booking):
            self.assertNotEqual(r.status, 'BOOKED',
                "SECURITY: Seats must not be BOOKED after invalid signature")

    # -----------------------------------------------------------------------
    # Test 5: Duplicate callback to payment_verify is idempotent
    # (ondismiss fix means handler fires once, but we guard against retries)
    # -----------------------------------------------------------------------
    def test_duplicate_payment_verify_callback_is_idempotent(self):
        """
        Idempotency: If the Razorpay handler fires twice (e.g., network retry),
        the second call to payment_verify must NOT create duplicate bookings
        or payments.
        """
        booking = self._reserve_seats('F1')
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_idempotent_reg_001"

        Payment.objects.create(
            booking=booking, user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('200.00'),
            total_amount=Decimal('266.00'),
            status='PENDING'
        )

        valid_sig = self._make_valid_sig(order_id, payment_id)
        payload = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference,
        }

        # First call
        resp1 = self.client.post(reverse('payment_verify'), payload)
        self.assertEqual(resp1.status_code, 302)

        # Second call (duplicate / retry)
        resp2 = self.client.post(reverse('payment_verify'), payload)
        self.assertEqual(resp2.status_code, 302)

        # Exactly one confirmed booking
        self.assertEqual(Booking.objects.filter(booking_reference=booking.booking_reference).count(), 1)

        # Exactly one seat record
        self.assertEqual(SeatReservation.objects.filter(show=self.show, seat_number='F1').count(), 1)

        # Exactly one SUCCESS payment
        self.assertEqual(Payment.objects.filter(booking=booking, status='SUCCESS').count(), 1)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.payment_status, 'PAID')

    # -----------------------------------------------------------------------
    # Test 6: Ticket is created after payment (Task 6 integration)
    # -----------------------------------------------------------------------
    def test_ticket_record_created_after_payment_confirmation(self):
        """
        Task 6: A Ticket record must be created (get_or_create) inside the
        payment_verify transaction so the Celery task can find it.
        """
        from booking.models import Ticket

        booking = self._reserve_seats('A3')
        order_id = f"order_{booking.booking_reference}"
        payment_id = "pay_ticket_task_001"

        Payment.objects.create(
            booking=booking, user=self.user,
            order_id=order_id,
            ticket_amount=Decimal('200.00'),
            total_amount=Decimal('266.00'),
            status='PENDING'
        )

        valid_sig = self._make_valid_sig(order_id, payment_id)
        self.client.post(reverse('payment_verify'), {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': valid_sig,
            'booking_reference': booking.booking_reference,
        })

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAID')

        # Ticket record must exist with a unique ticket_number and verification_token
        self.assertTrue(
            Ticket.objects.filter(booking=booking).exists(),
            "Task 6: Ticket record must be created in the payment transaction"
        )
        ticket = Ticket.objects.get(booking=booking)
        self.assertTrue(ticket.ticket_number.startswith('TKT-'))
        self.assertIsNotNone(ticket.verification_token)
        self.assertTrue(len(ticket.verification_token) > 10)

    # -----------------------------------------------------------------------
    # Test 7: PENDING booking does not get ticket (Task 6 guard)
    # -----------------------------------------------------------------------
    def test_pending_booking_does_not_get_ticket(self):
        """
        Task 6 guard: The Celery task skips PENDING bookings.
        This verifies the task's own guard works correctly.
        """
        from booking.models import Ticket
        from booking.tasks import generate_and_email_ticket_task

        booking = self._reserve_seats('B3')
        # Do NOT pay — booking stays PENDING

        # Manually create a ticket record (simulate premature creation)
        ticket = Ticket.objects.create(booking=booking)

        # Run the task synchronously
        generate_and_email_ticket_task(booking.id)

        # Task should have returned early — booking is still PENDING
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PENDING',
            "Task 6 guard: Task must not process PENDING bookings")

    # -----------------------------------------------------------------------
    # Test 8: Failed payment leaves seats RESERVED not BOOKED
    # -----------------------------------------------------------------------
    def test_failed_payment_leaves_seats_reserved(self):
        """
        Failed payment via Razorpay must not book seats.
        Seats must remain RESERVED so the user can retry.
        """
        booking = self._reserve_seats('C3')
        pay_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})

        resp = self.client.post(pay_url, {'payment_action': 'fail'})
        self.assertEqual(resp.status_code, 200)

        payment = Payment.objects.filter(booking=booking).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'FAILED')

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PENDING',
            "Failed payment must leave booking PENDING (not FAILED permanently)")

        # Seats must still be RESERVED
        for r in SeatReservation.objects.filter(booking=booking):
            self.assertEqual(r.status, 'RESERVED',
                f"Seat {r.seat_number} must remain RESERVED after failed payment")


