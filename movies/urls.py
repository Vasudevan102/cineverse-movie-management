from django.urls import path
from . import views

urlpatterns = [
    path('', views.movie_list_view, name='movie_list'),
    path('api/count/', views.movie_discovery_count_api, name='movie_discovery_count_api'),
    path('api/theaters/', views.movie_discovery_theaters_api, name='movie_discovery_theaters_api'),
    path('genre/<slug:slug>/', views.genre_movies_view, name='genre_movies'),
    path('language/<str:code>/', views.language_movies_view, name='language_movies'),
    path('<slug:slug>/', views.movie_detail_view, name='movie_detail'),
]
