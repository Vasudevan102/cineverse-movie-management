from django.urls import path
from . import views

urlpatterns = [
    path('', views.movie_list_view, name='movie_list'),
    path('<slug:slug>/', views.movie_detail_view, name='movie_detail'),
    path('genre/<slug:slug>/', views.genre_movies_view, name='genre_movies'),
    path('language/<str:code>/', views.language_movies_view, name='language_movies'),
]
