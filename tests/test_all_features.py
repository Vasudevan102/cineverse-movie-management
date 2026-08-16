from datetime import date, time
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from movies.models import Movie, Language, Genre, CastMember
from booking.models import Theater, Show, Booking
from reviews.models import Review, ReviewReport
from reviews.services import can_user_review
from movies.utils import get_similar_movies

class MovieManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.user1 = User.objects.create_user(username='john', email='john@example.com', password='password123')
        self.user2 = User.objects.create_user(username='jane', email='jane@example.com', password='password123')

        # Language & Genre
        self.lang_en = Language.objects.create(name='English', code='en')
        self.genre_action = Genre.objects.create(name='Action', slug='action')
        self.genre_scifi = Genre.objects.create(name='Sci-Fi', slug='sci-fi')

        # Movie 1
        self.movie1 = Movie.objects.create(
            title='Inception Matrix',
            description='Mind bending thriller in virtual worlds.',
            release_date=date(2026, 1, 1),
            duration=140,
            age_certificate='U/A',
            language=self.lang_en,
            director='Nolan',
            trailer_url='https://www.youtube.com/watch?v=YoHD9XEInc0'
        )
        self.movie1.genres.add(self.genre_action, self.genre_scifi)

        # Movie 2
        self.movie2 = Movie.objects.create(
            title='Cyber Runner',
            description='Futuristic sci-fi action runner.',
            release_date=date(2026, 2, 1),
            duration=120,
            age_certificate='A',
            language=self.lang_en,
            director='Scott',
            trailer_url='https://www.youtube.com/watch?v=YoHD9XEInc0'
        )
        self.movie2.genres.add(self.genre_scifi)

        # Theater & Show
        self.theater = Theater.objects.create(
            name='Star Cinema',
            location='Main St',
            city='Boston',
            address='100 Main St',
            total_screens=2
        )
        self.show = Show.objects.create(
            movie=self.movie1,
            theater=self.theater,
            screen='Screen 1',
            show_date=date(2026, 8, 20),
            start_time=time(18, 0),
            end_time=time(20, 30),
            ticket_price=10.00,
            total_seats=50,
            available_seats=50
        )

    def test_user_authentication(self):
        # Registration test for unauthenticated user
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'ComplexPass123!@#',
            'password2': 'ComplexPass123!@#'
        })
        self.assertEqual(User.objects.filter(username='newuser').count(), 1)

        # Login test
        login_success = self.client.login(username='john', password='password123')
        self.assertTrue(login_success)

    def test_movie_listing_and_detail(self):
        response = self.client.get(reverse('movie_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception Matrix')

        response_detail = self.client.get(reverse('movie_detail', kwargs={'slug': self.movie1.slug}))
        self.assertEqual(response_detail.status_code, 200)
        self.assertContains(response_detail, 'Nolan')

    def test_booking_and_seat_deduction(self):
        self.client.login(username='john', password='password123')

        # Book 2 seats
        response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 2
        })
        self.assertEqual(response.status_code, 302) # Redirects to booking_detail

        # Check seats reduced
        self.show.refresh_from_db()
        self.assertEqual(self.show.available_seats, 48)

        # Check booking created
        booking = Booking.objects.filter(user=self.user1, show=self.show).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.number_of_seats, 2)
        self.assertEqual(booking.total_amount, 20.00)

    def test_verified_viewer_review_permission(self):
        # Without booking, user cannot review
        review_perm_before = can_user_review(self.user1, self.movie1)
        self.assertFalse(review_perm_before['can_review'])

        # Create completed booking for user1
        booking = Booking.objects.create(
            user=self.user1,
            show=self.show,
            number_of_seats=1,
            total_amount=10.00,
            status='COMPLETED'
        )

        review_perm_after = can_user_review(self.user1, self.movie1)
        self.assertTrue(review_perm_after['can_review'])
        self.assertTrue(review_perm_after['is_verified'])

    def test_review_creation_and_rating_averaging(self):
        # Create booking for user1
        Booking.objects.create(user=self.user1, show=self.show, number_of_seats=1, total_amount=10.00, status='COMPLETED')

        # User 1 submits 5 star review
        self.client.login(username='john', password='password123')
        self.client.post(reverse('review_create', kwargs={'movie_id': self.movie1.id}), {
            'rating': 5,
            'comment': 'Awesome movie!'
        })

        self.movie1.refresh_from_db()
        self.assertEqual(self.movie1.average_rating, 5.00)
        self.assertEqual(self.movie1.total_reviews, 1)

    def test_recommendation_algorithm_excludes_current_movie(self):
        recommendations = get_similar_movies(self.movie1, limit=6)
        self.assertNotIn(self.movie1, recommendations)
        self.assertIn(self.movie2, recommendations)

    def test_payment_page_rendering_and_recalculations(self):
        from decimal import Decimal
        self.client.login(username='john', password='password123')

        # Test seat counts: 1, 2, 3, 4
        for seats in [1, 2, 3, 4]:
            response = self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
                'number_of_seats': seats,
                'selected_seats': ','.join([f"A{i}" for i in range(1, seats + 1)])
            })
            self.assertEqual(response.status_code, 302)
            booking = Booking.objects.filter(user=self.user1, show=self.show, payment_status='PENDING').first()
            self.assertIsNotNone(booking)

            # Get payment page
            payment_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
            pay_resp = self.client.get(payment_url)
            self.assertEqual(pay_resp.status_code, 200)

            # Check context monetary values
            expected_ticket_price = Decimal('10.00')
            expected_subtotal = expected_ticket_price * Decimal(seats)
            expected_convenience = Decimal('30.00')
            expected_taxes = (expected_subtotal * Decimal('0.18')).quantize(Decimal('0.01'))
            expected_grand_total = expected_subtotal + expected_convenience + expected_taxes

            self.assertEqual(pay_resp.context['ticket_price'], expected_ticket_price)
            self.assertEqual(pay_resp.context['subtotal'], expected_subtotal)
            self.assertEqual(pay_resp.context['convenience_fee'], expected_convenience)
            self.assertEqual(pay_resp.context['taxes'], expected_taxes)
            self.assertEqual(pay_resp.context['grand_total'], expected_grand_total)

    def test_payment_success_and_failure_flow(self):
        self.client.login(username='john', password='password123')
        self.client.post(reverse('booking_create', kwargs={'show_id': self.show.id}), {
            'number_of_seats': 2,
            'selected_seats': 'B1, B2'
        })
        booking = Booking.objects.filter(user=self.user1, show=self.show, payment_status='PENDING').first()

        # Simulate Payment Failure
        payment_url = reverse('booking_payment', kwargs={'reference': booking.booking_reference})
        fail_resp = self.client.post(payment_url, {
            'payment_method': 'UPI',
            'payment_action': 'fail'
        })
        self.assertEqual(fail_resp.status_code, 200)
        self.assertTrue(fail_resp.context['payment_failed'])
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PENDING')

        # Simulate Payment Success
        success_resp = self.client.post(payment_url, {
            'payment_method': 'UPI',
            'payment_action': 'success'
        })
        self.assertEqual(success_resp.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAID')

        # Check detail page status code 200
        detail_resp = self.client.get(reverse('booking_detail', kwargs={'reference': booking.booking_reference}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'Payment Successful!')

    def test_show_list_query_by_movie(self):
        # Create movie Vikram
        vikram = Movie.objects.create(
            title='Vikram',
            slug='vikram',
            description='Action thriller',
            release_date=date(2022, 6, 3),
            duration=175,
            age_certificate='U/A',
            language=self.lang_en,
            director='Lokesh'
        )
        Show.objects.create(
            movie=vikram,
            theater=self.theater,
            screen='Screen 2',
            show_date=date.today(),
            start_time=time(20, 0),
            end_time=time(23, 0),
            ticket_price=200.00,
            total_seats=100,
            available_seats=100
        )

        response = self.client.get(reverse('show_list') + '?movie=vikram')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'No Shows Available')
        self.assertContains(response, 'Vikram')

