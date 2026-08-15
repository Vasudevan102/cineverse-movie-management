from datetime import date, time
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from movies.models import Movie, Language
from booking.models import Theater, Show, Booking, Payment

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
        Booking.objects.create(
            user=self.user,
            show=self.show,
            number_of_seats=1,
            selected_seats='E1',
            total_amount=Decimal('200.00'),
            status='CONFIRMED',
            payment_status='PAID'
        )

        self.client.login(username='otheruser', password='Password123!')
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 1,
            'selected_seats': 'E1'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')
