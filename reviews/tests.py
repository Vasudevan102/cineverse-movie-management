from datetime import date, time
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from movies.models import Movie, Language
from booking.models import Theater, Show, Booking
from reviews.models import Review, ReviewReport
from reviews.services import can_user_review

User = get_user_model()

class ReviewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='Password123!'
        )
        self.lang = Language.objects.create(name='Hindi', code='hi')

        self.movie = Movie.objects.create(
            title='Stree Blockbuster',
            description='Horror comedy film.',
            release_date=date(2026, 1, 1),
            duration=130,
            language=self.lang,
            director='Amar Kaushik'
        )

        self.theater = Theater.objects.create(
            name='PVR Cinema',
            location='Connaught Place',
            city='Delhi',
            address='CP Plaza',
            total_screens=3
        )

        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 2',
            show_date=date(2026, 8, 20),
            start_time=time(19, 0),
            end_time=time(21, 30),
            ticket_price=Decimal('220.00'),
            total_seats=50,
            available_seats=50
        )

    def test_unverified_viewer_review_permission_blocked(self):
        perm = can_user_review(self.user, self.movie)
        self.assertFalse(perm['can_review'])

    def test_verified_viewer_review_permission_allowed(self):
        Booking.objects.create(
            user=self.user,
            show=self.show,
            number_of_seats=1,
            total_amount=Decimal('220.00'),
            status='COMPLETED'
        )

        perm = can_user_review(self.user, self.movie)
        self.assertTrue(perm['can_review'])
        self.assertTrue(perm['is_verified'])

    def test_review_creation_and_rating_averaging(self):
        Booking.objects.create(
            user=self.user,
            show=self.show,
            number_of_seats=1,
            total_amount=Decimal('220.00'),
            status='COMPLETED'
        )

        self.client.login(username='reviewer', password='Password123!')
        url = reverse('review_create', kwargs={'movie_id': self.movie.id})
        response = self.client.post(url, {
            'rating': 5,
            'comment': 'Fantastic movie experience!'
        })
        self.assertEqual(response.status_code, 302)

        self.movie.refresh_from_db()
        self.assertEqual(self.movie.average_rating, Decimal('5.00'))
        self.assertEqual(self.movie.total_reviews, 1)

    def test_review_report_workflow(self):
        user2 = User.objects.create_user(username='flagger', password='Password123!')
        Booking.objects.create(user=self.user, show=self.show, number_of_seats=1, total_amount=Decimal('220.00'), status='COMPLETED')

        review = Review.objects.create(
            user=self.user,
            movie=self.movie,
            rating=5,
            comment='Superb film',
            verified_viewer=True
        )

        self.client.login(username='flagger', password='Password123!')
        url = reverse('review_report', kwargs={'review_id': review.id})
        response = self.client.post(url, {
            'reason': 'SPAM',
            'details': 'Inappropriate content.'
        })
        self.assertEqual(response.status_code, 302)

        self.assertTrue(ReviewReport.objects.filter(review=review, reported_by=user2).exists())
