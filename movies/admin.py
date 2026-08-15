from django.contrib import admin
from .models import Language, Genre, CastMember, Movie, MovieImage

class MovieImageInline(admin.TabularInline):
    model = MovieImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'uploaded_at')
    readonly_fields = ('uploaded_at',)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(CastMember)
class CastMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'character_name')
    search_fields = ('name', 'character_name')

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('title', 'language', 'release_date', 'duration', 'age_certificate', 'average_rating', 'total_reviews', 'is_active')
    list_filter = ('is_active', 'age_certificate', 'language', 'genres')
    search_fields = ('title', 'director', 'description')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('genres', 'cast')
    inlines = [MovieImageInline]
    readonly_fields = ('average_rating', 'total_reviews', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Details', {
            'fields': ('title', 'slug', 'description', 'director', 'is_active')
        }),
        ('Classification & Language', {
            'fields': ('release_date', 'duration', 'age_certificate', 'language', 'genres', 'cast')
        }),
        ('Media & Trailer', {
            'fields': ('trailer_url',)
        }),
        ('Rating Summary', {
            'fields': ('average_rating', 'total_reviews', 'created_at', 'updated_at')
        }),
    )

@admin.register(MovieImage)
class MovieImageAdmin(admin.ModelAdmin):
    list_display = ('movie', 'caption', 'is_primary', 'uploaded_at')
    list_filter = ('is_primary', 'uploaded_at')
    search_fields = ('movie__title', 'caption')
