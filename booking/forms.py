from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    number_of_seats = forms.IntegerField(
        min_value=1,
        max_value=20,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-cineverse form-control-lg text-center',
            'min': 1,
            'max': 20
        })
    )

    class Meta:
        model = Booking
        fields = ['number_of_seats']
