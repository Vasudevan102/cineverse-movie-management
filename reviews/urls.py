from django.urls import path
from . import views

urlpatterns = [
    path('movie/<int:movie_id>/create/', views.review_create_view, name='review_create'),
    path('<int:review_id>/edit/', views.review_edit_view, name='review_edit'),
    path('<int:review_id>/delete/', views.review_delete_view, name='review_delete'),
    path('<int:review_id>/report/', views.review_report_view, name='review_report'),
]
