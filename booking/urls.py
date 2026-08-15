from django.urls import path
from . import views

urlpatterns = [
    path('shows/', views.show_list_view, name='show_list'),
    path('theaters/', views.theater_list_view, name='theater_list'),
    path('theaters/<int:pk>/', views.theater_detail_view, name='theater_detail'),
    path('create/<int:show_id>/', views.booking_create_view, name='booking_create'),
    path('payment/<str:reference>/', views.payment_process_view, name='booking_payment'),
    path('my-bookings/', views.my_bookings_view, name='my_bookings'),
    path('detail/<str:reference>/', views.booking_detail_view, name='booking_detail'),
    path('cancel/<str:reference>/', views.booking_cancel_view, name='booking_cancel'),
]
