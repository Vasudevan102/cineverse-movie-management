from booking.models import Booking
from reviews.models import Review

def can_user_review(user, movie):
    """
    Determines if a user is eligible to write or update a review for a movie,
    and whether they qualify for the 'Verified Viewer' badge.

    Returns dict:
    {
        'can_review': bool,
        'reason': str,
        'is_verified': bool,
        'existing_review': Review object or None
    }
    """
    if not user or not user.is_authenticated:
        return {
            'can_review': False,
            'reason': "You must be logged in to submit a review.",
            'is_verified': False,
            'existing_review': None
        }

    existing_review = Review.objects.filter(user=user, movie=movie).first()

    # Check user bookings for this movie
    user_bookings = Booking.objects.filter(
        user=user,
        show__movie=movie,
        status__in=['CONFIRMED', 'COMPLETED']
    )

    is_verified = False
    for b in user_bookings:
        if b.is_completed_or_past or b.watched:
            is_verified = True
            break

    if not is_verified:
        return {
            'can_review': False,
            'reason': "You must book and watch this movie at a theater before submitting a review.",
            'is_verified': False,
            'existing_review': existing_review
        }

    return {
        'can_review': True,
        'reason': "Eligible to write a review.",
        'is_verified': True,
        'existing_review': existing_review
    }
