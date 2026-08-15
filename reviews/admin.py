from django.contrib import admin
from .models import Review, ReviewReport

@admin.action(description="Hide selected reviews")
def hide_reviews(modeladmin, request, queryset):
    queryset.update(is_hidden=True)
    for review in queryset:
        review.movie.update_rating_summary()

@admin.action(description="Unhide selected reviews")
def unhide_reviews(modeladmin, request, queryset):
    queryset.update(is_hidden=False)
    for review in queryset:
        review.movie.update_rating_summary()

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('movie', 'user', 'rating', 'verified_viewer', 'is_reported', 'is_hidden', 'created_at')
    list_filter = ('verified_viewer', 'is_reported', 'is_hidden', 'rating', 'created_at')
    search_fields = ('movie__title', 'user__username', 'comment')
    actions = [hide_reviews, unhide_reviews]
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ('review', 'reported_by', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('review__movie__title', 'review__comment', 'reported_by__username', 'reason')
    readonly_fields = ('created_at',)
