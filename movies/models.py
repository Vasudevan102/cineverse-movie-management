import re
from django.db import models
from django.utils.text import slugify

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="e.g. en, ta, hi, te, ml, kn")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class CastMember(models.Model):
    name = models.CharField(max_length=100)
    character_name = models.CharField(max_length=100, help_text="Role or character played in movie")
    biography = models.TextField(blank=True)
    photo = models.ImageField(upload_to='cast/', blank=True, null=True)
    photo_url = models.URLField(max_length=500, blank=True, null=True, help_text="Remote photo URL")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} as {self.character_name}"

    @property
    def display_photo(self):
        if self.photo_url:
            return self.photo_url
        if self.photo:
            try:
                return self.photo.url
            except Exception:
                pass
        return None

class Movie(models.Model):
    AGE_CERTIFICATE_CHOICES = [
        ('U', 'U - Universal (All Ages)'),
        ('U/A', 'U/A - Parental Guidance Required'),
        ('A', 'A - Adults Only (18+)'),
    ]

    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    release_date = models.DateField()
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    age_certificate = models.CharField(max_length=5, choices=AGE_CERTIFICATE_CHOICES, default='U/A')
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, related_name='movies')
    genres = models.ManyToManyField(Genre, related_name='movies')
    cast = models.ManyToManyField(CastMember, related_name='movies', blank=True)
    director = models.CharField(max_length=100)
    trailer_url = models.URLField(help_text="YouTube URL e.g. https://www.youtube.com/watch?v=VIDEO_ID or https://youtu.be/VIDEO_ID")
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-release_date', 'title']

    def save(self, *args, **kwargs):
        if not self.slug or re.search(r'[^a-zA-Z0-9_-]', self.slug):
            raw_slug = self.slug or self.title or 'movie'
            raw_slug = raw_slug.replace('.', '-')
            base_slug = slugify(raw_slug)
            if not base_slug:
                base_slug = 'movie'
            base_slug = re.sub(r'[^a-zA-Z0-9_-]', '', base_slug)
            slug = base_slug
            count = 1
            while Movie.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{count}"
                count += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def formatted_duration(self):
        hours = self.duration // 60
        mins = self.duration % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    @property
    def youtube_video_id(self):
        if not self.trailer_url:
            return None
        pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
        match = re.search(pattern, self.trailer_url)
        return match.group(1) if match else None

    @property
    def youtube_embed_url(self):
        video_id = self.youtube_video_id
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
        return None

    @property
    def primary_poster(self):
        primary_image = self.images.filter(is_primary=True, image_type='poster').first() or self.images.filter(is_primary=True).first()
        if primary_image and primary_image.display_url:
            return primary_image.display_url
        first_poster = self.images.filter(image_type='poster').first() or self.images.first()
        if first_poster and first_poster.display_url:
            return first_poster.display_url
        return None

    @property
    def backdrop_url(self):
        backdrop_image = self.images.filter(image_type='backdrop').first()
        if backdrop_image and backdrop_image.display_url:
            return backdrop_image.display_url
        return self.primary_poster

    @property
    def genre_theme_class(self):
        first_genre = self.genres.first()
        if not first_genre:
            return "theme-action"
        name = first_genre.name.lower()
        if "action" in name or "adventure" in name:
            return "theme-action"
        elif "sci-fi" in name or "fantasy" in name:
            return "theme-scifi"
        elif "horror" in name or "thriller" in name or "crime" in name:
            return "theme-horror"
        elif "romance" in name or "drama" in name:
            return "theme-romance"
        elif "comedy" in name or "family" in name or "animation" in name:
            return "theme-comedy"
        return "theme-action"

    def update_rating_summary(self):
        from django.db.models import Avg, Count
        summary = self.reviews.filter(is_hidden=False).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        self.average_rating = round(summary['avg_rating'] or 0.0, 2)
        self.total_reviews = summary['count'] or 0
        self.save(update_fields=['average_rating', 'total_reviews'])

    @property
    def rating_breakdown(self):
        from django.db.models import Count
        total = self.total_reviews or 1
        counts = self.reviews.filter(is_hidden=False).values('rating').annotate(count=Count('id'))
        count_map = {item['rating']: item['count'] for item in counts}
        
        breakdown = []
        for star in range(5, 0, -1):
            star_count = count_map.get(star, 0)
            pct = int(round((star_count / total) * 100)) if self.total_reviews > 0 else 0
            breakdown.append({
                'star': star,
                'count': star_count,
                'percent': pct
            })
        return breakdown


class MovieImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('poster', 'Poster'),
        ('backdrop', 'Backdrop'),
        ('gallery', 'Gallery'),
    ]

    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='posters/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Remote image URL (e.g. TMDB or CDN)")
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES, default='poster')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            MovieImage.objects.filter(movie=self.movie, is_primary=True, image_type=self.image_type).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.image_type.capitalize()} for {self.movie.title} ({'Primary' if self.is_primary else 'Gallery'})"

    @property
    def display_url(self):
        if self.image_url:
            return self.image_url
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        return None
