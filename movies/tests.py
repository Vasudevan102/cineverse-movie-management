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
