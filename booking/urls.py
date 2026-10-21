from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    path('shows/', views.show_list_view, name='show_list'),
    path('theaters/', views.theater_list_view, name='theater_list'),
    path('theaters/<int:pk>/', views.theater_detail_view, name='theater_detail'),
    path('create/<int:show_id>/', views.booking_create_view, name='booking_create'),
    path('seats/<int:show_id>/', views.booking_create_view, name='booking_seats'),
    path('book/<int:show_id>/', views.booking_create_view, name='booking_create_alias'),
    path('show/<int:show_id>/seats/', views.show_seats_api_view, name='show_seats_api'),
    path('api/shows/<int:show_id>/seats/', views.show_seats_api_view, name='show_seats_api_alt'),
    path('payment/verify/', views.payment_verify_view, name='payment_verify'),
    path('payment/cancel/<str:reference>/', views.payment_cancel_view, name='payment_cancel'),
    path('payment/<str:reference>/', views.payment_process_view, name='booking_payment'),
    path('webhook/razorpay/', views.razorpay_webhook_view, name='razorpay_webhook'),
    path('my-bookings/', views.my_bookings_view, name='my_bookings'),
    path('detail/<str:reference>/', views.booking_detail_view, name='booking_detail'),
    path('cancel/<str:reference>/', views.booking_cancel_view, name='booking_cancel'),
    path('ticket/<str:reference>/download/', views.ticket_download_view, name='booking_ticket_download'),
    path('verify/<str:token>/', views.ticket_verify_view, name='ticket_verify'),
    path('admin-dashboard/', admin_views.admin_dashboard_view, name='booking_admin_dashboard'),
    path('admin-dashboard/export-csv/', admin_views.admin_dashboard_export_csv_view, name='booking_admin_dashboard_export'),
]

