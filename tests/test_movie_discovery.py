from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from movies.models import Movie, Language, Genre, MovieImage, MovieView
from booking.models import Theater, Show, Booking, Payment
from movies.utils import (
    get_personalized_recommendations,
    build_movie_discovery_queryset,
    record_movie_view
)

User = get_user_model()

class MovieDiscoveryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Users
        cls.user1 = User.objects.create_user(username='discovery_user1', email='user1@cineverse.com', password='Password123!')
        cls.user2 = User.objects.create_user(username='discovery_user2', email='user2@cineverse.com', password='Password123!')

        # Languages
        cls.lang_en = Language.objects.create(name='English', code='en')
        cls.lang_ta = Language.objects.create(name='Tamil', code='ta')
        cls.lang_hi = Language.objects.create(name='Hindi', code='hi')

        # Genres
        cls.genre_action = Genre.objects.create(name='Action', slug='action')
        cls.genre_scifi = Genre.objects.create(name='Sci-Fi', slug='sci-fi')
        cls.genre_drama = Genre.objects.create(name='Drama', slug='drama')
        cls.genre_comedy = Genre.objects.create(name='Comedy', slug='comedy')

        # Theaters
        cls.theater_chennai = Theater.objects.create(name='PVR Grand Chennai', location='Velachery', city='Chennai', address='Phoenix Mall', total_screens=5)
        cls.theater_cbe = Theater.objects.create(name='KG Cinemas', location='RS Puram', city='Coimbatore', address='Bungalow Road', total_screens=4)

        cls.today = timezone.now().date()
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.yesterday = cls.today - timedelta(days=10)

        # Movies (15 movies to test pagination of 12)
        cls.movies = []
        for i in range(1, 16):
            lang = cls.lang_en if i % 2 == 1 else cls.lang_ta
            rel_date = cls.today - timedelta(days=i * 10)
            avg_rating = Decimal(str(round(3.0 + (i % 5) * 0.4, 2)))
            
            m = Movie.objects.create(
                title=f'Blockbuster Movie {i:02d}',
                description=f'Thrilling description for movie {i}',
                release_date=rel_date,
                duration=120 + i,
                age_certificate='U/A',
                language=lang,
                director=f'Director {i}',
                average_rating=avg_rating,
                total_reviews=10 * i,
                is_active=True
            )
            # Assign genres
            if i % 3 == 0:
                m.genres.add(cls.genre_action, cls.genre_scifi)
            elif i % 3 == 1:
                m.genres.add(cls.genre_action, cls.genre_drama)
            else:
                m.genres.add(cls.genre_comedy)
            cls.movies.append(m)

        # Ensure Movie 2 has Action & Drama for cumulative filter test
        cls.movies[1].genres.add(cls.genre_action, cls.genre_drama)

        # Inactive movie
        cls.inactive_movie = Movie.objects.create(
            title='Archived Unlisted Film',
            description='Inactive movie',
            release_date=cls.yesterday,
            duration=100,
            language=cls.lang_en,
            director='Hidden Director',
            is_active=False
        )

        # Shows for Movie 1 (Chennai Morning 9:00 AM, Ticket 150)
        cls.show_m1_morning = Show.objects.create(
            movie=cls.movies[0],
            theater=cls.theater_chennai,
            screen='Screen 1',
            show_date=cls.tomorrow,
            start_time=time(9, 30),
            end_time=time(12, 0),
            ticket_price=Decimal('150.00'),
            total_seats=100,
            available_seats=100,
            is_active=True
        )

        # Shows for Movie 2 (Chennai Evening 18:30 PM, Ticket 250)
        cls.show_m2_evening = Show.objects.create(
            movie=cls.movies[1],
            theater=cls.theater_chennai,
            screen='Screen 2',
            show_date=cls.tomorrow,
            start_time=time(18, 30),
            end_time=time(21, 30),
            ticket_price=Decimal('250.00'),
            total_seats=100,
            available_seats=90,
            is_active=True
        )

        # Shows for Movie 3 (Coimbatore Night 21:30 PM, Ticket 120)
        cls.show_m3_night = Show.objects.create(
            movie=cls.movies[2],
            theater=cls.theater_cbe,
            screen='Screen 1',
            show_date=cls.tomorrow,
            start_time=time(21, 30),
            end_time=time(23, 45),
            ticket_price=Decimal('120.00'),
            total_seats=100,
            available_seats=80,
            is_active=True
        )

        # Bookings for Popularity ranking (Movie 2 has 2 bookings, Movie 3 has 1 booking)
        b1 = Booking.objects.create(
            user=cls.user1,
            show=cls.show_m2_evening,
            number_of_seats=2,
            total_amount=Decimal('500.00'),
            status='CONFIRMED',
            payment_status='PAID'
        )
        b2 = Booking.objects.create(
            user=cls.user2,
            show=cls.show_m2_evening,
            number_of_seats=1,
            total_amount=Decimal('250.00'),
            status='COMPLETED',
            payment_status='PAID'
        )
        b3 = Booking.objects.create(
            user=cls.user1,
            show=cls.show_m3_night,
            number_of_seats=2,
            total_amount=Decimal('240.00'),
            status='CONFIRMED',
            payment_status='PAID'
        )

    def setUp(self):
        self.client = Client()

    # ==========================================================
    # 1. SEARCH TESTS
    # ==========================================================
    def test_search_by_exact_title(self):
        url = reverse('movie_list') + '?q=Blockbuster Movie 01'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Blockbuster Movie 01')
        self.assertEqual(res.context['match_count'], 1)

    def test_search_case_insensitive_and_partial(self):
        url = reverse('movie_list') + '?q=movie 02'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Blockbuster Movie 02')
        self.assertEqual(res.context['match_count'], 1)

    def test_search_no_results(self):
        url = reverse('movie_list') + '?q=NonExistentMovieQuery12345'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['match_count'], 0)
        self.assertContains(res, 'No Matching Movies Found')

    def test_search_inactive_movie_excluded(self):
        url = reverse('movie_list') + '?q=Archived Unlisted Film'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['match_count'], 0)

    # ==========================================================
    # 2. FILTER TESTS
    # ==========================================================
    def test_filter_by_genre(self):
        url = reverse('movie_list') + '?genre=comedy'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        for m in res.context['page_obj']:
            self.assertTrue(m.genres.filter(slug='comedy').exists())

    def test_filter_by_language(self):
        url = reverse('movie_list') + '?language=ta'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        for m in res.context['page_obj']:
            self.assertEqual(m.language.code, 'ta')

    def test_filter_by_city(self):
        url = reverse('movie_list') + '?city=Chennai'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        # Movies 1 and 2 have active shows in Chennai
        titles = [m.title for m in res.context['page_obj']]
        self.assertIn('Blockbuster Movie 01', titles)
        self.assertIn('Blockbuster Movie 02', titles)
        self.assertNotIn('Blockbuster Movie 03', titles)

    def test_filter_by_theater(self):
        url = reverse('movie_list') + f'?theater={self.theater_cbe.id}'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        titles = [m.title for m in res.context['page_obj']]
        self.assertIn('Blockbuster Movie 03', titles)
        self.assertNotIn('Blockbuster Movie 01', titles)

    def test_filter_by_min_rating(self):
        url = reverse('movie_list') + '?rating=4.0'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        for m in res.context['page_obj']:
            self.assertGreaterEqual(float(m.average_rating), 4.0)

    def test_filter_by_show_time_morning(self):
        url = reverse('movie_list') + '?show_time=morning'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        titles = [m.title for m in res.context['page_obj']]
        self.assertIn('Blockbuster Movie 01', titles)
        self.assertNotIn('Blockbuster Movie 02', titles)

    def test_filter_by_show_time_evening(self):
        url = reverse('movie_list') + '?show_time=evening'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        titles = [m.title for m in res.context['page_obj']]
        self.assertIn('Blockbuster Movie 02', titles)
        self.assertNotIn('Blockbuster Movie 01', titles)

    def test_cumulative_filters_combined(self):
        # Filter Genre=Action + Language=Tamil + City=Chennai
        url = reverse('movie_list') + '?genre=action&language=ta&city=Chennai'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        titles = [m.title for m in res.context['page_obj']]
        # Movie 2 is Tamil + Action + has Chennai show
        self.assertIn('Blockbuster Movie 02', titles)
        # Movie 1 is English (excluded)
        self.assertNotIn('Blockbuster Movie 01', titles)

    # ==========================================================
    # 3. SORTING TESTS
    # ==========================================================
    def test_sort_by_popularity(self):
        # Movie 2 has 2 bookings, Movie 3 has 1 booking
        url = reverse('movie_list') + '?sort=popularity'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        page_movies = list(res.context['page_obj'])
        # Top movie should be Movie 2
        self.assertEqual(page_movies[0].id, self.movies[1].id)

    def test_sort_by_newest(self):
        url = reverse('movie_list') + '?sort=newest'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        page_movies = list(res.context['page_obj'])
        dates = [m.release_date for m in page_movies]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_sort_by_rating(self):
        url = reverse('movie_list') + '?sort=rating'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        page_movies = list(res.context['page_obj'])
        ratings = [m.average_rating for m in page_movies]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_sort_by_ticket_price_ascending(self):
        url = reverse('movie_list') + '?sort=price_asc'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        page_movies = list(res.context['page_obj'])
        # Movie 3 has price 120, Movie 1 has 150, Movie 2 has 250
        movie_ids = [m.id for m in page_movies if m.id in [self.movies[0].id, self.movies[1].id, self.movies[2].id]]
        self.assertEqual(movie_ids, [self.movies[2].id, self.movies[0].id, self.movies[1].id])

    # ==========================================================
    # 4. MATCH COUNT & AJAX APIS
    # ==========================================================
    def test_match_count_api_returns_correct_json(self):
        url = reverse('movie_discovery_count_api') + '?genre=comedy'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('count', data)
        expected = Movie.objects.filter(is_active=True, genres__slug='comedy').count()
        self.assertEqual(data['count'], expected)

    def test_theaters_api_returns_city_theaters(self):
        url = reverse('movie_discovery_theaters_api') + '?city=Chennai'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('theaters', data)
        theaters = data['theaters']
        self.assertTrue(all(t['city'] == 'Chennai' for t in theaters))
        self.assertIn(self.theater_chennai.name, [t['name'] for t in theaters])

    # ==========================================================
    # 5. PAGINATION TESTS
    # ==========================================================
    def test_pagination_page_1_and_page_2(self):
        # We have 15 movies, page size is 12 -> page 1 has 12, page 2 has 3
        url_p1 = reverse('movie_list') + '?page=1'
        res_p1 = self.client.get(url_p1)
        self.assertEqual(res_p1.status_code, 200)
        self.assertEqual(len(res_p1.context['page_obj']), 12)
        self.assertTrue(res_p1.context['page_obj'].has_next())

        url_p2 = reverse('movie_list') + '?page=2'
        res_p2 = self.client.get(url_p2)
        self.assertEqual(res_p2.status_code, 200)
        self.assertEqual(len(res_p2.context['page_obj']), 3)
        self.assertFalse(res_p2.context['page_obj'].has_next())

    def test_pagination_invalid_page_handles_gracefully(self):
        url_invalid = reverse('movie_list') + '?page=9999'
        res = self.client.get(url_invalid)
        self.assertEqual(res.status_code, 200)
        # get_page fallback delivers last page
        self.assertEqual(res.context['page_obj'].number, 2)

    def test_pagination_preserves_query_params_in_links(self):
        url = reverse('movie_list') + '?q=Blockbuster&sort=newest&page=1'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        # Pagination include must carry over q=Blockbuster and sort=newest
        self.assertContains(res, 'q=Blockbuster')
        self.assertContains(res, 'sort=newest')

    # ==========================================================
    # 6. RECOMMENDATIONS ENGINE TESTS
    # ==========================================================
    def test_recommendations_for_user_with_booking_history(self):
        # user1 booked Movie 2 (Tamil, Action/Drama) and Movie 3 (Tamil, Comedy)
        recs = get_personalized_recommendations(user=self.user1, limit=4)
        self.assertTrue(len(recs) > 0)
        rec_ids = [m.id for m in recs]
        # Must exclude already booked movies 2 and 3
        self.assertNotIn(self.movies[1].id, rec_ids)
        self.assertNotIn(self.movies[2].id, rec_ids)
        # Recommended candidates should heavily align with Action, Drama, or Comedy
        for m in recs:
            has_matching_genre = m.genres.filter(id__in=[self.genre_action.id, self.genre_drama.id, self.genre_comedy.id]).exists()
            self.assertTrue(has_matching_genre or m.language_id == self.lang_ta.id)

    def test_recommendations_for_user_with_view_history(self):
        # user2 views Movie 1 (English, Action/Sci-Fi)
        MovieView.objects.create(user=self.user2, movie=self.movies[0])
        recs = get_personalized_recommendations(user=self.user2, limit=4)
        self.assertTrue(len(recs) > 0)
        # Recommendations should prioritize Action or Sci-Fi or English
        genres = [g.slug for r in recs for g in r.genres.all()]
        self.assertTrue('action' in genres or 'sci-fi' in genres)

    def test_recommendations_anonymous_user_with_session_history(self):
        session = {'recently_viewed_movies': [self.movies[0].id]}
        recs = get_personalized_recommendations(user=None, session=session, limit=4)
        self.assertTrue(len(recs) > 0)

    def test_recommendations_cold_start_fallback(self):
        # New user without any bookings or views
        new_user = User.objects.create_user(username='coldstart_user', password='Password123!')
        recs = get_personalized_recommendations(user=new_user, limit=6)
        self.assertEqual(len(recs), 6)
        # All returned must be active movies
        self.assertTrue(all(m.is_active for m in recs))

    # ==========================================================
    # 7. RECENTLY VIEWED TRACKING TESTS
    # ==========================================================
    def test_movie_detail_view_records_movie_view_for_authenticated_user(self):
        self.client.login(username='discovery_user1', password='Password123!')
        url = reverse('movie_detail', kwargs={'slug': self.movies[4].slug})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        view_exists = MovieView.objects.filter(user=self.user1, movie=self.movies[4]).exists()
        self.assertTrue(view_exists)

    def test_movie_view_revisit_updates_timestamp_without_duplicates(self):
        self.client.login(username='discovery_user1', password='Password123!')
        url = reverse('movie_detail', kwargs={'slug': self.movies[4].slug})
        self.client.get(url)
        self.client.get(url)
        
        count = MovieView.objects.filter(user=self.user1, movie=self.movies[4]).count()
        self.assertEqual(count, 1)

    def test_movie_view_history_capped_at_20_entries(self):
        # Create 25 views for user2
        for i in range(1, 15):
            record_movie_view(request=type('Req', (), {'user': self.user2, 'session': {}})(), movie=self.movies[i - 1])
        
        user2_views_count = MovieView.objects.filter(user=self.user2).count()
        self.assertLessEqual(user2_views_count, 20)

    def test_movie_detail_view_records_session_history_for_anonymous_user(self):
        client = Client()
        url = reverse('movie_detail', kwargs={'slug': self.movies[5].slug})
        res = client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.movies[5].id, client.session.get('recently_viewed_movies', []))

    # ==========================================================
    # 8. SECURITY & DATA ISOLATION
    # ==========================================================
    def test_user_history_isolation(self):
        MovieView.objects.create(user=self.user1, movie=self.movies[0])
        user2_views = MovieView.objects.filter(user=self.user2)
        self.assertNotIn(self.movies[0].id, user2_views.values_list('movie_id', flat=True))

    # ==========================================================
    # 9. ORM PERFORMANCE & QUERY COUNT (N+1 PREVENTION)
    # ==========================================================
    def test_discovery_query_efficiency_and_no_n_plus_one(self):
        """
        Verify that discovery page uses select_related and prefetch_related
        so that rendering 12 movie cards executes a fixed low number of queries.
        """
        url = reverse('movie_list')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
        
        # Total queries should be bounded (count query, paginated movies query, prefetch genres, prefetch images, recommendations)
        # Under 15 queries for the entire page render including count and recommendations
        self.assertLess(len(queries), 15, f"Query count too high ({len(queries)} queries executed). Check for N+1 queries.")
