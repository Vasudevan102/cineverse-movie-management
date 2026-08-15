from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from movies.models import Movie

User = get_user_model()

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(help_text="User review text")
    verified_viewer = models.BooleanField(default=False, help_text="Set automatically based on completed booking")
    is_reported = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'movie')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.movie.update_rating_summary()

    def delete(self, *args, **kwargs):
        movie = self.movie
        super().delete(*args, **kwargs)
        movie.update_rating_summary()

    def __str__(self):
        return f"{self.user.username} review for {self.movie.title} ({self.rating}★)"

class ReviewReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('DISMISSED', 'Dismissed'),
    ]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_reports')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('review', 'reported_by')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == 'PENDING':
            self.review.is_reported = True
            self.review.save(update_fields=['is_reported'])

    def __str__(self):
        return f"Report on {self.review} by {self.reported_by.username}"
