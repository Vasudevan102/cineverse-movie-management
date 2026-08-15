from django import forms
from .models import Review, ReviewReport

class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(5, 0, -1)],
        widget=forms.Select(attrs={'class': 'form-select form-select-cineverse form-select-lg'}),
        help_text="Select rating from 1 to 5 stars"
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-cineverse',
            'rows': 4,
            'placeholder': 'Write your honest review here...'
        }),
        help_text="Share your thoughts about the plot, acting, direction, audio, visual effects, etc."
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']

class ReviewReportForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-cineverse',
            'rows': 3,
            'placeholder': 'Please specify why you are reporting this review (e.g. spoilers, profanity, spam)...'
        })
    )

    class Meta:
        model = ReviewReport
        fields = ['reason']
