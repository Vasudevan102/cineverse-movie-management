from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegisterForm, UserProfileForm
from booking.models import Booking
from reviews.models import Review

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to MovieSpace, {user.username}! Your account was created successfully.")
            return redirect('home')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next') or 'home'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Error updating profile.")
    else:
        form = UserProfileForm(instance=request.user)

    user_bookings = Booking.objects.filter(user=request.user).select_related('show__movie', 'show__theater')
    user_reviews = Review.objects.filter(user=request.user).select_related('movie')

    movies_watched_count = user_bookings.filter(status='CONFIRMED').count()
    reviews_count = user_reviews.count()

    if movies_watched_count >= 10:
        member_level = "CineVerse Pro"
        member_badge = "👑"
    elif movies_watched_count >= 6:
        member_level = "Movie Enthusiast"
        member_badge = "🔥"
    elif movies_watched_count >= 3:
        member_level = "Cinema Fan"
        member_badge = "🍿"
    elif movies_watched_count >= 1:
        member_level = "Movie Explorer"
        member_badge = "⭐"
    else:
        member_level = "New Viewer"
        member_badge = "🎬"

    context = {
        'form': form,
        'bookings': user_bookings,
        'reviews': user_reviews,
        'movies_watched_count': movies_watched_count,
        'reviews_count': reviews_count,
        'member_level': member_level,
        'member_badge': member_badge,
    }
    return render(request, 'accounts/profile.html', context)
