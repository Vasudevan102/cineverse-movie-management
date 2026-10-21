from datetime import timedelta, date, time
from django.db.models import Count, Q, F, Min, Max, Case, When, Value, IntegerField
from django.utils import timezone
from movies.models import Movie, Genre, Language, MovieView
from booking.models import Booking, Show, Theater

def record_movie_view(request, movie):
    """
    Lightweight recently-viewed tracking for movies.
    - Authenticated users: persist to MovieView model (capped to latest 20 views per user).
    - Anonymous users: store recent movie IDs in session (capped to 20).
    """
    if not movie or not movie.pk:
        return

    if request.user.is_authenticated:
        # Update or create user view record
        MovieView.objects.update_or_create(
            user=request.user,
            movie=movie,
            defaults={'viewed_at': timezone.now()}
        )
        # Enforce 20-entry bounded limit per user
        views_qs = MovieView.objects.filter(user=request.user).order_by('-viewed_at')
        if views_qs.count() > 20:
            excess_ids = list(views_qs.values_list('id', flat=True)[20:])
            if excess_ids:
                MovieView.objects.filter(id__in=excess_ids).delete()
    else:
        # Anonymous session tracking
        recent_ids = request.session.get('recently_viewed_movies', [])
        if movie.id in recent_ids:
            recent_ids.remove(movie.id)
        recent_ids.insert(0, movie.id)
        request.session['recently_viewed_movies'] = recent_ids[:20]
        request.session.modified = True


def get_personalized_recommendations(user=None, session=None, limit=6, current_movie_id=None):
    """
    Generates personalized "Recommended for You" movie list based on:
    1. User's confirmed/completed booking history (strongest intent signal).
    2. Recently viewed movies (exploration intent signal).
    
    Scoring & Ranking Formula:
    - Candidate movies are active and exclude already booked movies and currently viewed movie.
    - Ranked by shared genre count, language match, booking count (popularity), average rating, and recency.
    - If user has no history (cold-start) or recommendations < limit, gracefully backfills with trending/top-rated movies.
    - Zero fake random numbers; 100% ORM-driven and deterministic.
    """
    booked_movie_ids = []
    viewed_movie_ids = []

    if user and user.is_authenticated:
        # 1. Booked movies
        booked_movie_ids = list(
            Booking.objects.filter(user=user, status__in=['CONFIRMED', 'COMPLETED'])
            .values_list('show__movie_id', flat=True)
            .distinct()
        )
        # 2. Recently viewed movies
        viewed_movie_ids = list(
            MovieView.objects.filter(user=user)
            .order_by('-viewed_at')
            .values_list('movie_id', flat=True)[:10]
        )
    elif session:
        # Anonymous recent views from session
        viewed_movie_ids = list(session.get('recently_viewed_movies', []))[:10]

    # Exclude already-booked movies (to encourage new discoveries) and current movie
    exclude_ids = set(booked_movie_ids)
    if current_movie_id:
        exclude_ids.add(current_movie_id)

    seed_movie_ids = list(set(booked_movie_ids + viewed_movie_ids))
    recommendations = []

    if seed_movie_ids:
        # Extract preferred genres & languages from user's seed history
        preferred_genre_ids = list(
            Genre.objects.filter(movies__id__in=seed_movie_ids)
            .values_list('id', flat=True)
            .distinct()
        )
        preferred_language_ids = list(
            Movie.objects.filter(id__in=seed_movie_ids, language__isnull=False)
            .values_list('language_id', flat=True)
            .distinct()
        )

        candidates = Movie.objects.filter(is_active=True).exclude(id__in=exclude_ids)

        genre_filter = Q(genres__in=preferred_genre_ids) if preferred_genre_ids else Q(pk__in=[])

        candidates = candidates.annotate(
            genre_score=Count('genres', filter=genre_filter, distinct=True),
            booking_count=Count('shows__bookings', filter=Q(shows__bookings__status__in=['CONFIRMED', 'COMPLETED']), distinct=True),
            lang_match=Case(
                When(language_id__in=preferred_language_ids, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).filter(
            Q(genre_score__gt=0) | Q(lang_match=1)
        ).order_by(
            '-genre_score',
            '-lang_match',
            '-booking_count',
            '-average_rating',
            '-release_date'
        ).distinct()

        recommendations = list(
            candidates.select_related('language').prefetch_related('genres', 'images')[:limit]
        )

    # Cold-start / Backfill with trending and top-rated active movies
    if len(recommendations) < limit:
        needed = limit - len(recommendations)
        current_rec_ids = exclude_ids | {m.id for m in recommendations}
        
        fallback = Movie.objects.filter(is_active=True).exclude(id__in=current_rec_ids).annotate(
            booking_count=Count('shows__bookings', filter=Q(shows__bookings__status__in=['CONFIRMED', 'COMPLETED']), distinct=True)
        ).order_by(
            '-booking_count',
            '-average_rating',
            '-release_date'
        ).select_related('language').prefetch_related('genres', 'images')[:needed]

        recommendations.extend(list(fallback))

    return recommendations[:limit]


def get_similar_movies(movie, limit=6):
    """
    Recommends movies similar to the given movie based on:
    1. Shared genres (highest weight)
    2. Same language (bonus match)
    3. Rating and release date
    """
    genre_ids = movie.genres.values_list('id', flat=True)
    
    similar = Movie.objects.filter(is_active=True).exclude(id=movie.id)
    
    similar = similar.annotate(
        genre_matches=Count('genres', filter=Q(genres__in=genre_ids), distinct=True),
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
        booking_count=Count('shows__bookings', filter=Q(shows__bookings__status__in=['CONFIRMED', 'COMPLETED']), distinct=True)
    ).order_by('-booking_count', '-average_rating', '-release_date')[:limit]


def get_recently_released_movies(limit=6):
    """
    Returns latest released active movies.
    """
    return Movie.objects.filter(is_active=True).order_by('-release_date', '-created_at')[:limit]


def build_movie_discovery_queryset(params, request=None):
    """
    Constructs an optimized Django QuerySet for the Movie Discovery page supporting:
    - Search (title search, partial match, case-insensitive)
    - Cumulative filters (Genre, Language, City, Theater, Release Date, Min Rating, Show Timing)
    - Sorting (Popularity, Newest, Rating, Ticket Price asc/desc, Title)
    """
    movies = Movie.objects.filter(is_active=True)
    today = timezone.now().date()

    # 1. Search Query (title search, partial and case-insensitive)
    q = (params.get('q') or '').strip()
    if q:
        movies = movies.filter(title__icontains=q)

    # 2. Genre Filter (by slug or id)
    genre = params.get('genre')
    if genre:
        if str(genre).isdigit():
            movies = movies.filter(genres__id=int(genre))
        else:
            movies = movies.filter(genres__slug=genre)

    # 3. Language Filter (by code or id)
    language = params.get('language')
    if language:
        if str(language).isdigit():
            movies = movies.filter(language__id=int(language))
        else:
            movies = movies.filter(language__code=language)

    # 4. Rating Filter (min rating)
    rating = params.get('rating') or params.get('min_rating')
    if rating:
        try:
            min_r = float(rating)
            movies = movies.filter(average_rating__gte=min_r)
        except (ValueError, TypeError):
            pass

    # 5. City Filter
    city = params.get('city')
    if city and city.strip():
        movies = movies.filter(
            shows__theater__city__iexact=city.strip(),
            shows__is_active=True,
            shows__show_date__gte=today
        )

    # 6. Theater Filter
    theater = params.get('theater')
    if theater:
        try:
            theater_id = int(theater)
            movies = movies.filter(
                shows__theater_id=theater_id,
                shows__is_active=True,
                shows__show_date__gte=today
            )
        except (ValueError, TypeError):
            pass

    # 7. Release Date Filter
    release_date_filter = params.get('release_date')
    if release_date_filter == 'recent':
        movies = movies.filter(
            release_date__gte=today - timedelta(days=60),
            release_date__lte=today
        )
    elif release_date_filter == 'upcoming':
        movies = movies.filter(release_date__gt=today)
    elif release_date_filter == 'past_year':
        movies = movies.filter(release_date__gte=today - timedelta(days=365))
    
    # Custom release date range if provided
    release_from = params.get('release_from')
    release_to = params.get('release_to')
    if release_from:
        try:
            movies = movies.filter(release_date__gte=release_from)
        except Exception:
            pass
    if release_to:
        try:
            movies = movies.filter(release_date__lte=release_to)
        except Exception:
            pass

    # 8. Show Timing Filter (morning, afternoon, evening, night)
    show_time = params.get('show_time')
    if show_time == 'morning':
        movies = movies.filter(
            shows__start_time__gte=time(6, 0),
            shows__start_time__lte=time(11, 59, 59),
            shows__is_active=True,
            shows__show_date__gte=today
        )
    elif show_time == 'afternoon':
        movies = movies.filter(
            shows__start_time__gte=time(12, 0),
            shows__start_time__lte=time(16, 59, 59),
            shows__is_active=True,
            shows__show_date__gte=today
        )
    elif show_time == 'evening':
        movies = movies.filter(
            shows__start_time__gte=time(17, 0),
            shows__start_time__lte=time(20, 59, 59),
            shows__is_active=True,
            shows__show_date__gte=today
        )
    elif show_time == 'night':
        movies = movies.filter(
            Q(shows__start_time__gte=time(21, 0)) | Q(shows__start_time__lte=time(5, 59, 59)),
            shows__is_active=True,
            shows__show_date__gte=today
        )

    # 9. Sorting
    sort_by = params.get('sort') or params.get('sort_by') or 'popularity'

    if sort_by in ['popularity', '-popularity']:
        movies = movies.annotate(
            booking_count=Count('shows__bookings', filter=Q(shows__bookings__status__in=['CONFIRMED', 'COMPLETED']), distinct=True)
        ).order_by('-booking_count', '-average_rating', '-release_date')
    elif sort_by in ['newest', '-release_date']:
        movies = movies.order_by('-release_date', '-created_at')
    elif sort_by in ['oldest', 'release_date']:
        movies = movies.order_by('release_date', 'title')
    elif sort_by in ['rating', '-average_rating']:
        movies = movies.order_by('-average_rating', '-total_reviews')
    elif sort_by in ['price_asc', 'price', 'ticket_price']:
        movies = movies.annotate(
            min_price=Min('shows__ticket_price', filter=Q(shows__is_active=True, shows__show_date__gte=today))
        ).order_by(F('min_price').asc(nulls_last=True), '-average_rating')
    elif sort_by in ['price_desc', '-ticket_price']:
        movies = movies.annotate(
            max_price=Max('shows__ticket_price', filter=Q(shows__is_active=True, shows__show_date__gte=today))
        ).order_by(F('max_price').desc(nulls_last=True), '-average_rating')
    elif sort_by == 'title':
        movies = movies.order_by('title')
    else:
        movies = movies.order_by('-release_date', 'title')

    # Apply ORM query optimization: select_related, prefetch_related, distinct
    return movies.select_related('language').prefetch_related('genres', 'images').distinct()
