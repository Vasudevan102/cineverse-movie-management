from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from movies.models import Movie, Language, Genre

class MoviesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.lang = Language.objects.create(name='English', code='en')
        self.genre = Genre.objects.create(name='Action', slug='action')

        self.movie = Movie.objects.create(
            title='Inception Thriller',
            description='Mind bending sci-fi thriller.',
            release_date=date(2026, 1, 1),
            duration=148,
            age_certificate='U/A',
            language=self.lang,
            director='Christopher Nolan',
            trailer_url='https://www.youtube.com/watch?v=YoHD9XEInc0'
        )
        self.movie.genres.add(self.genre)

    def test_home_page_rendering(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception Thriller')

    def test_movie_list_view(self):
        response = self.client.get(reverse('movie_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception Thriller')

    def test_movie_detail_view_valid_slug(self):
        url = reverse('movie_detail', kwargs={'slug': self.movie.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Christopher Nolan')

    def test_movie_detail_view_invalid_slug_returns_404(self):
        url = reverse('movie_detail', kwargs={'slug': 'non-existent-movie-slug'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_genre_movies_view(self):
        url = reverse('genre_movies', kwargs={'slug': self.genre.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception Thriller')

    def test_language_movies_view(self):
        url = reverse('language_movies', kwargs={'code': self.lang.code})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception Thriller')

    def test_slug_auto_generation_and_sanitation(self):
        m = Movie.objects.create(
            title='Pushpa 2: The Rule!',
            description='Test movie description.',
            release_date=date(2026, 2, 1),
            duration=165,
            language=self.lang,
            director='Sukumar'
        )
        self.assertTrue(m.slug)
        self.assertNotIn('.', m.slug)
        self.assertNotIn('!', m.slug)

    def test_movie_image_display_url_and_fallback(self):
        from movies.models import MovieImage
        img = MovieImage.objects.create(
            movie=self.movie,
            image_url='https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600',
            image_type='poster',
            is_primary=True
        )
        self.assertEqual(img.display_url, 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600')
        self.assertEqual(self.movie.primary_poster, 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600')

    def test_cast_member_photo_url_display(self):
        from movies.models import CastMember
        member = CastMember.objects.create(
            name='Vijay',
            character_name='Thalapathy',
            photo_url='https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200'
        )
        self.assertEqual(member.display_photo, 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200')

    def test_seed_data_command_idempotency(self):
        from django.core.management import call_command
        call_command('seed_data')
        movie_count_first = Movie.objects.count()
        call_command('seed_data')
        movie_count_second = Movie.objects.count()
        self.assertEqual(movie_count_first, movie_count_second)

