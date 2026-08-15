from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from movies.models import Movie
from .models import Review, ReviewReport
from .forms import ReviewForm, ReviewReportForm
from .services import can_user_review

@login_required
def review_create_view(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id, is_active=True)
    status = can_user_review(request.user, movie)

    if not status['can_review']:
        messages.error(request, status['reason'])
        return redirect('movie_detail', slug=movie.slug)

    if status['existing_review']:
        messages.info(request, "You have already reviewed this movie. You can edit your existing review.")
        return redirect('review_edit', review_id=status['existing_review'].id)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.movie = movie
            review.verified_viewer = status['is_verified']
            review.save()

            messages.success(request, "Your review has been submitted successfully!")
            return redirect('movie_detail', slug=movie.slug)
    else:
        form = ReviewForm()

    context = {
        'form': form,
        'movie': movie,
        'is_verified': status['is_verified']
    }
    return render(request, 'reviews/review_form.html', context)

@login_required
def review_edit_view(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    if review.user != request.user:
        messages.error(request, "Unauthorized access! You can only edit your own review.")
        return redirect('movie_detail', slug=review.movie.slug)

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, "Your review has been updated.")
            return redirect('movie_detail', slug=review.movie.slug)
    else:
        form = ReviewForm(instance=review)

    context = {
        'form': form,
        'movie': review.movie,
        'review': review,
        'is_edit': True
    }
    return render(request, 'reviews/review_form.html', context)

@login_required
def review_delete_view(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    if review.user != request.user and not request.user.is_staff:
        messages.error(request, "Unauthorized action!")
        return redirect('movie_detail', slug=review.movie.slug)

    movie_slug = review.movie.slug
    if request.method == 'POST':
        review.delete()
        messages.success(request, "Review deleted successfully.")
        return redirect('movie_detail', slug=movie_slug)

    return render(request, 'reviews/review_confirm_delete.html', {'review': review})

@login_required
def review_report_view(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    existing_report = ReviewReport.objects.filter(review=review, reported_by=request.user).first()
    if existing_report:
        messages.warning(request, "You have already reported this review.")
        return redirect('movie_detail', slug=review.movie.slug)

    if request.method == 'POST':
        form = ReviewReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.review = review
            report.reported_by = request.user
            report.save()

            messages.success(request, "Thank you. The review has been reported for moderator inspection.")
            return redirect('movie_detail', slug=review.movie.slug)
    else:
        form = ReviewReportForm()

    context = {
        'form': form,
        'review': review
    }
    return render(request, 'reviews/review_report.html', context)
