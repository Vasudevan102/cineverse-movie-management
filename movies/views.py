from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import Movie, Genre, Language
from .forms import MovieFilterForm
from .utils import (
    get_similar_movies,
    get_trending_movies,
    get_recently_released_movies,
    get_personalized_recommendations,
    record_movie_view,
    build_movie_discovery_queryset
)
from reviews.services import can_user_review
from booking.models import Show, Theater

def home_view(request):
    selected_city = request.GET.get('city')
    
    trending_movies = get_trending_movies(limit=8)
    recently_released = get_recently_released_movies(limit=8)
    
    today = timezone.now().date()
    
    if selected_city:
        now_showing = Movie.objects.filter(
            is_active=True,
            shows__theater__city__iexact=selected_city,
            shows__is_active=True,
            shows__show_date__gte=today
        ).select_related('language').prefetch_related('genres', 'images').distinct()[:10]
    else:
        now_showing = Movie.objects.filter(is_active=True).order_by('-average_rating', '-total_reviews')[:10]

    # If city filtering yields no movies, fallback to popular active movies
    if not now_showing.exists():
        now_showing = Movie.objects.filter(is_active=True).order_by('-average_rating', '-total_reviews')[:10]

    # Build deduplicated carousel movies list (6-8 featured movies)
    seen_ids = set()
    carousel_movies = []
    for m in list(now_showing) + list(trending_movies) + list(recently_released):
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            carousel_movies.append(m)
            if len(carousel_movies) >= 8:
                break

    hero_movie = carousel_movies[0] if carousel_movies else None

    genres = Genre.objects.all()
    languages = Language.objects.all()
    all_cities = sorted(list(set(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())))

    context = {
        'carousel_movies': carousel_movies,
        'hero_movie': hero_movie,
        'trending_movies': trending_movies,
        'recently_released': recently_released,
        'now_showing': now_showing,
        'genres': genres,
        'languages': languages,
        'cities': all_cities,
        'selected_city': selected_city,
    }
    return render(request, 'home.html', context)

def movie_list_view(request):
    """
    Feature-rich Movie Discovery view with title search, cumulative multi-facet filters,
    sorting, dynamic match counts, database-backed pagination, and personalized recommendations.
    """
    form = MovieFilterForm(request.GET or None)
    movies = build_movie_discovery_queryset(request.GET, request=request)

    # Dynamic matching movie count (using efficient SQL aggregate)
    match_count = movies.count()

    # Pagination: 12 movies per page
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Personalized recommendations for active user / session
    recommended_movies = get_personalized_recommendations(
        user=request.user,
        session=request.session,
        limit=6
    )

    genres = Genre.objects.all()
    languages = Language.objects.all()
    all_cities = sorted(list(set(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())))
    
    selected_city = request.GET.get('city')
    theaters_qs = Theater.objects.filter(is_active=True)
    if selected_city:
        theaters_qs = theaters_qs.filter(city__iexact=selected_city)
    theaters = theaters_qs.order_by('name')

    # Detect if any active filters are applied (for 'Clear Filters' button display)
    active_filters_applied = any([
        request.GET.get('q'),
        request.GET.get('genre'),
        request.GET.get('language'),
        request.GET.get('city'),
        request.GET.get('theater'),
        request.GET.get('rating'),
        request.GET.get('min_rating'),
        request.GET.get('release_date'),
        request.GET.get('show_time'),
        request.GET.get('sort_by') and request.GET.get('sort_by') != 'popularity',
        request.GET.get('sort') and request.GET.get('sort') != 'popularity',
    ])

    context = {
        'form': form,
        'page_obj': page_obj,
        'match_count': match_count,
        'recommended_movies': recommended_movies,
        'genres': genres,
        'languages': languages,
        'cities': all_cities,
        'theaters': theaters,
        'selected_genre': request.GET.get('genre'),
        'selected_language': request.GET.get('language'),
        'selected_city': selected_city,
        'selected_theater': request.GET.get('theater'),
        'selected_rating': request.GET.get('rating') or request.GET.get('min_rating'),
        'selected_release_date': request.GET.get('release_date'),
        'selected_show_time': request.GET.get('show_time'),
        'selected_sort': request.GET.get('sort') or request.GET.get('sort_by') or 'popularity',
        'search_query': request.GET.get('q', ''),
        'active_filters_applied': active_filters_applied,
    }
    return render(request, 'movies/movie_list.html', context)

def movie_discovery_count_api(request):
    """
    Lightweight AJAX endpoint returning the dynamic count of matching movies
    without loading full movie objects or reloading the page.
    """
    movies = build_movie_discovery_queryset(request.GET, request=request)
    return JsonResponse({'count': movies.count()})

def movie_discovery_theaters_api(request):
    """
    AJAX endpoint returning list of active theaters filtered by selected city.
    """
    city = request.GET.get('city')
    theaters_qs = Theater.objects.filter(is_active=True)
    if city and city.strip():
        theaters_qs = theaters_qs.filter(city__iexact=city.strip())
    
    data = [
        {'id': t.id, 'name': t.name, 'city': t.city, 'location': t.location}
        for t in theaters_qs.order_by('name')
    ]
    return JsonResponse({'theaters': data})

def movie_detail_view(request, slug):
    movie = get_object_or_404(Movie, slug=slug, is_active=True)
    
    # Record viewing history for recommendations
    record_movie_view(request, movie)

    selected_city = request.GET.get('city')
    
    today = timezone.now().date()
    shows_qs = Show.objects.filter(
        movie=movie,
        is_active=True,
        show_date__gte=today
    ).select_related('theater').order_by('show_date', 'start_time')

    if selected_city:
        shows_qs = shows_qs.filter(theater__city__iexact=selected_city)

    reviews = movie.reviews.filter(is_hidden=False).select_related('user').order_by('-created_at')
    review_status = can_user_review(request.user, movie)
    similar_movies = get_similar_movies(movie, limit=6)
    all_cities = sorted(list(set(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())))

    context = {
        'movie': movie,
        'shows': shows_qs,
        'reviews': reviews,
        'review_status': review_status,
        'similar_movies': similar_movies,
        'selected_city': selected_city,
        'cities': all_cities,
    }
    return render(request, 'movies/movie_detail.html', context)

def genre_movies_view(request, slug):
    genre = get_object_or_404(Genre, slug=slug)
    movies = Movie.objects.filter(genres=genre, is_active=True).distinct()
    
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'genre': genre,
        'page_obj': page_obj,
    }
    return render(request, 'movies/genre_movies.html', context)

def language_movies_view(request, code):
    language = get_object_or_404(Language, code=code)
    movies = Movie.objects.filter(language=language, is_active=True)
    
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'language': language,
        'page_obj': page_obj,
    }
    return render(request, 'movies/language_movies.html', context)
