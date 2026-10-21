from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, time, timedelta
from decimal import Decimal
from movies.models import Movie, Language, Genre
from booking.models import Theater, Show
from django.contrib.auth import get_user_model
User = get_user_model()

class MovieNavigationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='flowtester',
            email='flow@example.com',
            password='Password123!'
        )

        self.lang = Language.objects.create(name='English', code='en')
        self.genre_sci_fi = Genre.objects.create(name='Sci-Fi', slug='sci-fi')
        self.genre_action = Genre.objects.create(name='Action', slug='action')

        # Movie 1: Interstellar
        self.movie_interstellar = Movie.objects.create(
            title='Interstellar',
            slug='interstellar',
            description='A team of explorers travel through a wormhole in space.',
            release_date=date(2014, 11, 7),
            duration=169,
            age_certificate='U/A',
            language=self.lang,
            director='Christopher Nolan',
            is_active=True
        )
        self.movie_interstellar.genres.add(self.genre_sci_fi)

        # Movie 2: Vikram
        self.movie_vikram = Movie.objects.create(
            title='Vikram',
            slug='vikram',
            description='A special investigator is assigned a case of serial killings.',
            release_date=date(2022, 6, 3),
            duration=175,
            age_certificate='U/A',
            language=self.lang,
            director='Lokesh Kanagaraj',
            is_active=True
        )
        self.movie_vikram.genres.add(self.genre_action)

        # Theaters
        self.theater_chennai = Theater.objects.create(
            name='CineVerse Luxe Chennai',
            location='Velachery, Phoenix Marketcity',
            city='Chennai',
            total_screens=5,
            is_active=True
        )

        self.theater_coimbatore = Theater.objects.create(
            name='CineVerse IMAX Coimbatore',
            location='Avinashi Road, Brookefields',
            city='Coimbatore',
            total_screens=4,
            is_active=True
        )

        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.day_after = self.today + timedelta(days=2)

        # Shows for Interstellar in Chennai
        self.show_interstellar_chennai_1 = Show.objects.create(
            movie=self.movie_interstellar,
            theater=self.theater_chennai,
            screen='Screen 1',
            show_date=self.tomorrow,
            start_time=time(14, 30),
            end_time=time(17, 30),
            ticket_price=Decimal('250.00'),
            total_seats=100,
            available_seats=90,
            is_active=True
        )

        # Shows for Interstellar in Coimbatore
        self.show_interstellar_cbe_1 = Show.objects.create(
            movie=self.movie_interstellar,
            theater=self.theater_coimbatore,
            screen='IMAX Screen',
            show_date=self.tomorrow,
            start_time=time(18, 0),
            end_time=time(21, 0),
            ticket_price=Decimal('350.00'),
            total_seats=150,
            available_seats=140,
            is_active=True
        )

        self.show_interstellar_cbe_date2 = Show.objects.create(
            movie=self.movie_interstellar,
            theater=self.theater_coimbatore,
            screen='IMAX Screen',
            show_date=self.day_after,
            start_time=time(18, 0),
            end_time=time(21, 0),
            ticket_price=Decimal('350.00'),
            total_seats=150,
            available_seats=140,
            is_active=True
        )

        # Shows for Vikram in Chennai
        self.show_vikram_chennai_1 = Show.objects.create(
            movie=self.movie_vikram,
            theater=self.theater_chennai,
            screen='Screen 2',
            show_date=self.tomorrow,
            start_time=time(19, 0),
            end_time=time(22, 0),
            ticket_price=Decimal('200.00'),
            total_seats=120,
            available_seats=110,
            is_active=True
        )

    def test_01_movie_card_links_to_detail_page(self):
        """Movie card on /movies/ links to /movies/<slug>/ using Django URL reversing."""
        response = self.client.get(reverse('movie_list'))
        self.assertEqual(response.status_code, 200)

        interstellar_detail_url = reverse('movie_detail', kwargs={'slug': 'interstellar'})
        vikram_detail_url = reverse('movie_detail', kwargs={'slug': 'vikram'})

        self.assertContains(response, f'href="{interstellar_detail_url}"')
        self.assertContains(response, f'href="{vikram_detail_url}"')

    def test_02_movie_detail_view_retrieves_exact_movie_by_slug(self):
        """Movie detail view loads the exact selected movie by slug and not a random movie."""
        url_interstellar = reverse('movie_detail', kwargs={'slug': 'interstellar'})
        res_interstellar = self.client.get(url_interstellar)
        self.assertEqual(res_interstellar.status_code, 200)
        self.assertEqual(res_interstellar.context['movie'].slug, 'interstellar')
        self.assertEqual(res_interstellar.context['movie'].title, 'Interstellar')
        self.assertContains(res_interstellar, 'Christopher Nolan')

        url_vikram = reverse('movie_detail', kwargs={'slug': 'vikram'})
        res_vikram = self.client.get(url_vikram)
        self.assertEqual(res_vikram.status_code, 200)
        self.assertEqual(res_vikram.context['movie'].slug, 'vikram')
        self.assertEqual(res_vikram.context['movie'].title, 'Vikram')
        self.assertContains(res_vikram, 'Lokesh Kanagaraj')

    def test_03_book_tickets_button_passes_selected_movie_slug(self):
        """Book tickets button on movie detail page passes ?movie=<movie-slug>."""
        url = reverse('movie_detail', kwargs={'slug': 'interstellar'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        expected_book_url = reverse('show_list') + '?movie=interstellar'
        self.assertContains(response, expected_book_url)

    def test_04_showtimes_view_filters_strictly_for_selected_movie(self):
        """Showtimes page for Interstellar contains only Interstellar shows, not Vikram."""
        url = reverse('show_list') + '?movie=interstellar'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_movie'].slug, 'interstellar')

        # Heading must show selected movie
        self.assertContains(response, 'Showing showtimes for')
        self.assertContains(response, 'Interstellar')

        # Shows must belong only to Interstellar
        shows = list(response.context['shows'])
        self.assertGreater(len(shows), 0)
        for show in shows:
            self.assertEqual(show.movie.slug, 'interstellar')

        # Must not contain Vikram shows
        self.assertNotContains(response, 'Vikram')

    def test_05_showtimes_view_filters_strictly_for_vikram(self):
        """Showtimes page for Vikram contains only Vikram shows, not Interstellar."""
        url = reverse('show_list') + '?movie=vikram'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_movie'].slug, 'vikram')

        self.assertContains(response, 'Showing showtimes for')
        self.assertContains(response, 'Vikram')

        shows = list(response.context['shows'])
        self.assertGreater(len(shows), 0)
        for show in shows:
            self.assertEqual(show.movie.slug, 'vikram')

        self.assertNotContains(response, 'Interstellar')

    def test_06_city_filter_works_with_selected_movie(self):
        """Interstellar + Chennai shows only Chennai Interstellar shows."""
        # Interstellar + Chennai
        url_chennai = reverse('show_list') + '?movie=interstellar&city=Chennai'
        res_chennai = self.client.get(url_chennai)
        self.assertEqual(res_chennai.status_code, 200)
        shows_chennai = list(res_chennai.context['shows'])
        self.assertEqual(len(shows_chennai), 1)
        self.assertEqual(shows_chennai[0].theater.city, 'Chennai')
        self.assertEqual(shows_chennai[0].movie.slug, 'interstellar')

        # Interstellar + Coimbatore
        url_cbe = reverse('show_list') + '?movie=interstellar&city=Coimbatore'
        res_cbe = self.client.get(url_cbe)
        self.assertEqual(res_cbe.status_code, 200)
        shows_cbe = list(res_cbe.context['shows'])
        self.assertEqual(len(shows_cbe), 2)
        for show in shows_cbe:
            self.assertEqual(show.theater.city, 'Coimbatore')
            self.assertEqual(show.movie.slug, 'interstellar')

        # Interstellar + All Cities
        url_all = reverse('show_list') + '?movie=interstellar&city='
        res_all = self.client.get(url_all)
        self.assertEqual(res_all.status_code, 200)
        shows_all = list(res_all.context['shows'])
        self.assertEqual(len(shows_all), 3)

    def test_07_date_filter_works_correctly(self):
        """Filtering by date returns only that date; empty date returns upcoming shows."""
        # Filter by specific date (tomorrow)
        date_str = self.tomorrow.strftime('%Y-%m-%d')
        url_date = reverse('show_list') + f'?movie=interstellar&date={date_str}'
        res_date = self.client.get(url_date)
        self.assertEqual(res_date.status_code, 200)
        shows_date = list(res_date.context['shows'])
        self.assertEqual(len(shows_date), 2)
        for s in shows_date:
            self.assertEqual(s.show_date, self.tomorrow)

        # Filter by day after tomorrow
        date2_str = self.day_after.strftime('%Y-%m-%d')
        url_date2 = reverse('show_list') + f'?movie=interstellar&date={date2_str}'
        res_date2 = self.client.get(url_date2)
        self.assertEqual(res_date2.status_code, 200)
        shows_date2 = list(res_date2.context['shows'])
        self.assertEqual(len(shows_date2), 1)
        self.assertEqual(shows_date2[0].show_date, self.day_after)

        # Empty date does not remove shows
        url_empty_date = reverse('show_list') + '?movie=interstellar&date='
        res_empty = self.client.get(url_empty_date)
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(len(res_empty.context['shows']), 3)

    def test_08_show_to_seat_link_passes_exact_show_id(self):
        """Clicking Select Seats passes the exact show.id to booking_create."""
        url = reverse('show_list') + '?movie=interstellar'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that links to booking_create with show_id are present
        expected_create_url = reverse('booking_create', kwargs={'show_id': self.show_interstellar_chennai_1.id})
        self.assertContains(response, expected_create_url)

        # Test loading the seat selection page for that exact show
        self.client.login(username='flowtester', password='Password123!')
        res_seats = self.client.get(expected_create_url)
        self.assertEqual(res_seats.status_code, 200)
        self.assertEqual(res_seats.context['show'].id, self.show_interstellar_chennai_1.id)
        self.assertEqual(res_seats.context['show'].movie.title, 'Interstellar')

    def test_09_complete_e2e_flow_interstellar_and_vikram(self):
        """End-to-end simulation of movie selection, detail view, showtimes, filtering, and seat selection."""
        # 1. User visits /movies/
        res_movies = self.client.get(reverse('movie_list'))
        self.assertEqual(res_movies.status_code, 200)

        # 2. User clicks Interstellar card -> /movies/interstellar/
        res_detail = self.client.get(reverse('movie_detail', kwargs={'slug': 'interstellar'}))
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.context['movie'].title, 'Interstellar')

        # 3. User clicks Book Tickets -> /booking/shows/?movie=interstellar
        res_shows = self.client.get(reverse('show_list') + '?movie=interstellar')
        self.assertEqual(res_shows.status_code, 200)
        self.assertContains(res_shows, 'Showing showtimes for')
        self.assertContains(res_shows, 'Interstellar')

        # 4. User filters by Chennai -> /booking/shows/?movie=interstellar&city=Chennai
        res_chennai = self.client.get(reverse('show_list') + '?movie=interstellar&city=Chennai')
        self.assertEqual(res_chennai.status_code, 200)
        shows = list(res_chennai.context['shows'])
        self.assertEqual(len(shows), 1)
        selected_show = shows[0]
        self.assertEqual(selected_show.theater.city, 'Chennai')
        self.assertEqual(selected_show.movie.title, 'Interstellar')

        # 5. User clicks Select Seats -> /booking/create/<show_id>/
        self.client.login(username='flowtester', password='Password123!')
        res_seat = self.client.get(reverse('booking_create', kwargs={'show_id': selected_show.id}))
        self.assertEqual(res_seat.status_code, 200)
        self.assertEqual(res_seat.context['show'].id, selected_show.id)

        # Independent test for Vikram:
        res_vikram_detail = self.client.get(reverse('movie_detail', kwargs={'slug': 'vikram'}))
        self.assertEqual(res_vikram_detail.status_code, 200)
        self.assertEqual(res_vikram_detail.context['movie'].title, 'Vikram')

        res_vikram_shows = self.client.get(reverse('show_list') + '?movie=vikram&city=Chennai')
        self.assertEqual(res_vikram_shows.status_code, 200)
        vikram_shows = list(res_vikram_shows.context['shows'])
        self.assertEqual(len(vikram_shows), 1)
        self.assertEqual(vikram_shows[0].movie.title, 'Vikram')
