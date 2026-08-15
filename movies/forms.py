from django import forms
from .models import Genre, Language

class MovieFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-cineverse',
        'placeholder': 'Search movies, directors...'
    }))
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        to_field_name='slug',
        empty_label="All Genres",
        widget=forms.Select(attrs={'class': 'form-select form-select-cineverse'})
    )
    language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        required=False,
        to_field_name='code',
        empty_label="All Languages",
        widget=forms.Select(attrs={'class': 'form-select form-select-cineverse'})
    )
    rating = forms.ChoiceField(
        choices=[('', 'All Ratings'), ('4', '4+ Stars'), ('3', '3+ Stars'), ('2', '2+ Stars')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-cineverse'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('-release_date', 'Newest Releases'),
            ('release_date', 'Oldest Releases'),
            ('-average_rating', 'Highest Rated'),
            ('title', 'Title (A-Z)')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-cineverse'})
    )
