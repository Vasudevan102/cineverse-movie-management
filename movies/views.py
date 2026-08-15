from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import Movie, Genre, Language
from .forms import MovieFilterForm
from .utils import get_similar_movies, get_trending_movies, get_recently_released_movies
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
    form = MovieFilterForm(request.GET or None)
    movies = Movie.objects.filter(is_active=True).select_related('language').prefetch_related('genres', 'images')

    selected_genre = None
    selected_language = None
    selected_city = request.GET.get('city')

    if selected_city:
        today = timezone.now().date()
        movies = movies.filter(
            shows__theater__city__iexact=selected_city,
            shows__is_active=True,
            shows__show_date__gte=today
        ).distinct()

    if form.is_valid():
        q = form.cleaned_data.get('q')
        if q:
            movies = movies.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(director__icontains=q) |
                Q(cast__name__icontains=q)
            ).distinct()

        genre_obj = form.cleaned_data.get('genre')
        if genre_obj:
            movies = movies.filter(genres=genre_obj)
            selected_genre = genre_obj

        lang_obj = form.cleaned_data.get('language')
        if lang_obj:
            movies = movies.filter(language=lang_obj)
            selected_language = lang_obj

        min_rating = form.cleaned_data.get('rating')
        if min_rating:
            movies = movies.filter(average_rating__gte=float(min_rating))

        sort_by = form.cleaned_data.get('sort_by')
        if sort_by:
            movies = movies.order_by(sort_by)

    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    genres = Genre.objects.all()
    languages = Language.objects.all()
    all_cities = sorted(list(set(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())))

    context = {
        'form': form,
        'page_obj': page_obj,
        'genres': genres,
        'languages': languages,
        'cities': all_cities,
        'selected_genre': selected_genre,
        'selected_language': selected_language,
        'selected_city': selected_city,
    }
    return render(request, 'movies/movie_list.html', context)

def movie_detail_view(request, slug):
    movie = get_object_or_404(Movie, slug=slug, is_active=True)
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
