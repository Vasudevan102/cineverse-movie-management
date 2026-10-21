from django import forms
from .models import Genre, Language
from booking.models import Theater

class MovieFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-cineverse',
            'placeholder': 'Search movies by title, actors, directors...',
            'id': 'filter-search-input',
            'aria-label': 'Search movies'
        })
    )
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        to_field_name='slug',
        empty_label="All Genres",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-genre-select',
            'aria-label': 'Filter by genre'
        })
    )
    language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        required=False,
        to_field_name='code',
        empty_label="All Languages",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-language-select',
            'aria-label': 'Filter by language'
        })
    )
    city = forms.CharField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-city-select',
            'aria-label': 'Filter by city'
        })
    )
    theater = forms.CharField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-theater-select',
            'aria-label': 'Filter by theater'
        })
    )
    rating = forms.ChoiceField(
        choices=[
            ('', 'All Ratings'),
            ('4.5', '4.5+ Stars'),
            ('4', '4+ Stars'),
            ('3', '3+ Stars'),
            ('2', '2+ Stars')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-rating-select',
            'aria-label': 'Filter by minimum rating'
        })
    )
    release_date = forms.ChoiceField(
        choices=[
            ('', 'All Releases'),
            ('recent', 'New & Recent (Last 60 Days)'),
            ('upcoming', 'Coming Soon / Upcoming'),
            ('past_year', 'Released in Past Year')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-release-select',
            'aria-label': 'Filter by release date'
        })
    )
    show_time = forms.ChoiceField(
        choices=[
            ('', 'All Show Times'),
            ('morning', '🌅 Morning (6 AM – 12 PM)'),
            ('afternoon', '☀️ Afternoon (12 PM – 5 PM)'),
            ('evening', '🌆 Evening (5 PM – 9 PM)'),
            ('night', '🌙 Night (9 PM – 6 AM)')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-showtime-select',
            'aria-label': 'Filter by show timing'
        })
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('popularity', '🔥 Popularity (Bookings)'),
            ('newest', '📅 Newest Releases'),
            ('-average_rating', '⭐ Highest Rated'),
            ('price_asc', '🏷️ Ticket Price: Low to High'),
            ('price_desc', '🏷️ Ticket Price: High to Low'),
            ('title', '🔤 Title (A–Z)')
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-cineverse',
            'id': 'filter-sort-select',
            'aria-label': 'Sort movies'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate dynamic city choices
        cities = sorted(list(set(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())))
        self.fields['city'].widget.choices = [('', 'All Cities')] + [(c, c) for c in cities]
        
        # Populate theaters based on selected city if provided in data
        city_val = None
        if self.data:
            city_val = self.data.get('city')
        theaters_qs = Theater.objects.filter(is_active=True)
        if city_val:
            theaters_qs = theaters_qs.filter(city__iexact=city_val)
        self.fields['theater'].widget.choices = [('', 'All Theaters')] + [(t.id, f"{t.name} ({t.city})") for t in theaters_qs]
