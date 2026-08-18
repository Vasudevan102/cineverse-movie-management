from datetime import date, time, timedelta
from decimal import Decimal
import threading
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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
            show_date=date(2026, 8, 25),
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





