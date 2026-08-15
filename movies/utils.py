from django.db.models import Count, Q, F, FloatField, ExpressionWrapper
from django.utils import timezone
from movies.models import Movie

def get_similar_movies(movie, limit=6):
    """
    Recommends movies similar to the given movie based on:
    1. Shared genres (highest weight)
    2. Same language (bonus match)
    3. Rating and release date
    """
    genre_ids = movie.genres.values_list('id', flat=True)
    
    similar = Movie.objects.filter(is_active=True).exclude(id=movie.id)
    
    # Annotate with match scores
    similar = similar.annotate(
        genre_matches=Count('genres', filter=Q(genres__in=genre_ids)),
        language_match=Q(language=movie.language)
    ).filter(
        Q(genre_matches__gt=0) | Q(language_match=True)
    ).order_by(
        '-genre_matches',
        '-language_match',
        '-average_rating',
        '-release_date'
    ).distinct()[:limit]

    return similar

def get_trending_movies(limit=6):
    """
    Returns trending movies calculated using booking count and average rating.
    """
    return Movie.objects.filter(is_active=True).annotate(
        booking_count=Count('shows__bookings', filter=Q(shows__bookings__status__in=['CONFIRMED', 'COMPLETED']))
    ).order_by('-booking_count', '-average_rating', '-release_date')[:limit]

def get_recently_released_movies(limit=6):
    """
    Returns latest released active movies.
    """
    return Movie.objects.filter(is_active=True).order_by('-release_date', '-created_at')[:limit]
