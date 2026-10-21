"""
CineVerse Admin Analytics Dashboard Views
Provides executive analytics, KPI cards, visual charts, and streaming CSV export.
Protected by Django staff permissions.
"""

import csv
import json
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import StreamingHttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .models import Booking
from . import admin_analytics


class EchoBuffer:
    """An object that implements just the write method of the file-like interface for streaming CSV."""
    def write(self, value):
        return value


@staff_member_required(login_url='admin:login')
def admin_dashboard_view(request):
    """
    Main executive analytics dashboard view.
    Restricted to Django staff / administrators.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("Access Denied: Staff permissions required.")

    preset = request.GET.get('preset', 'this_month')
    start_str = request.GET.get('start_date', '')
    end_str = request.GET.get('end_date', '')

    start_date, end_date, active_preset, date_error = admin_analytics.get_date_range(
        preset=preset,
        custom_start_str=start_str,
        custom_end_str=end_str
    )

    # 1. Executive Summary KPIs & Revenue
    kpis = admin_analytics.get_dashboard_kpis(start_date, end_date)
    revenue_metrics = admin_analytics.get_revenue_metrics(start_date, end_date)

    # 2. Time-series Booking Trends
    booking_trends = admin_analytics.get_booking_trends(start_date, end_date)

    # 3. Theater Occupancy & Performance
    theater_occupancy = admin_analytics.get_theater_occupancy(start_date, end_date, limit=15)
    top_theaters = admin_analytics.get_top_theaters(start_date, end_date, limit=10)

    # 4. Popular Movies
    popular_movies = admin_analytics.get_popular_movies(start_date, end_date, limit=10)

    # 5. Peak Booking Hours
    peak_hours = admin_analytics.get_peak_booking_hours(start_date, end_date)

    # 6. Cancellation & Refund Statistics
    cancellations = admin_analytics.get_cancellation_metrics(start_date, end_date)
    refunds = admin_analytics.get_refund_metrics(start_date, end_date)

    # 7. User Growth Trends
    user_growth = admin_analytics.get_user_growth(start_date, end_date)

    # Safe JSON payloads for interactive charts
    chart_trends_json = json.dumps({
        'labels': booking_trends['labels'],
        'total': booking_trends['total'],
        'confirmed': booking_trends['confirmed'],
        'cancelled': booking_trends['cancelled'],
        'revenue': booking_trends['revenue'],
    }, cls=DjangoJSONEncoder)

    chart_peak_hours_json = json.dumps({
        'labels': peak_hours['labels'],
        'counts': peak_hours['counts'],
        'revenues': peak_hours['revenues'],
    }, cls=DjangoJSONEncoder)

    chart_user_growth_json = json.dumps({
        'labels': user_growth['labels'],
        'counts': user_growth['counts'],
    }, cls=DjangoJSONEncoder)

    chart_occupancy_json = json.dumps({
        'labels': [t.name[:18] for t in theater_occupancy[:8]],
        'rates': [round(t.occupancy_pct, 1) for t in theater_occupancy[:8]],
    }, cls=DjangoJSONEncoder)

    context = {
        'title': 'Executive Analytics Dashboard',
        'kpis': kpis,
        'revenue': revenue_metrics,
        'booking_trends': booking_trends,
        'theater_occupancy': theater_occupancy,
        'top_theaters': top_theaters,
        'popular_movies': popular_movies,
        'peak_hours': peak_hours,
        'cancellations': cancellations,
        'refunds': refunds,
        'user_growth': user_growth,
        'active_preset': active_preset,
        'start_date': start_date,
        'end_date': end_date,
        'start_date_str': start_date.strftime('%Y-%m-%d'),
        'end_date_str': end_date.strftime('%Y-%m-%d'),
        'date_error': date_error,
        'chart_trends_json': chart_trends_json,
        'chart_peak_hours_json': chart_peak_hours_json,
        'chart_user_growth_json': chart_user_growth_json,
        'chart_occupancy_json': chart_occupancy_json,
    }

    return render(request, 'admin/dashboard.html', context)


@staff_member_required(login_url='admin:login')
def admin_dashboard_export_csv_view(request):
    """
    Streams booking reports in CSV format for the selected date range.
    Optimized for large datasets (100,000+ rows) via StreamingHttpResponse and iterator.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("Access Denied: Staff permissions required.")

    preset = request.GET.get('preset', 'this_month')
    start_str = request.GET.get('start_date', '')
    end_str = request.GET.get('end_date', '')

    start_date, end_date, _, date_error = admin_analytics.get_date_range(
        preset=preset,
        custom_start_str=start_str,
        custom_end_str=end_str
    )

    if date_error:
        return HttpResponseBadRequest(f"Export Error: {date_error}")

    # Query with select_related to avoid N+1 query overhead
    bookings_qs = Booking.objects.filter(
        booking_date__range=(start_date, end_date)
    ).select_related(
        'user',
        'show__movie',
        'show__theater'
    ).order_by('-booking_date')

    pseudo_buffer = EchoBuffer()
    writer = csv.writer(pseudo_buffer)

    def row_generator():
        # Header row
        yield writer.writerow([
            'Booking Reference',
            'User',
            'Movie',
            'Theater',
            'City',
            'Show Date',
            'Show Time',
            'Seats',
            'Seat Count',
            'Total Amount (INR)',
            'Payment Status',
            'Booking Status',
            'Created At',
        ])

        # Stream row chunks from cursor
        for b in bookings_qs.iterator(chunk_size=2000):
            show = b.show
            movie_title = show.movie.title if show and show.movie else "N/A"
            theater_name = show.theater.name if show and show.theater else "N/A"
            city = show.theater.city if show and show.theater else "N/A"
            show_date = show.show_date.strftime("%Y-%m-%d") if show and show.show_date else "N/A"
            show_time = show.start_time.strftime("%H:%M") if show and show.start_time else "N/A"
            user_name = b.user.username if b.user else "Anonymous"

            yield writer.writerow([
                b.booking_reference,
                user_name,
                movie_title,
                theater_name,
                city,
                show_date,
                show_time,
                b.selected_seats,
                b.number_of_seats,
                f"{b.total_amount:.2f}",
                b.payment_status,
                b.status,
                b.booking_date.strftime("%Y-%m-%d %H:%M:%S"),
            ])

    filename = f"cineverse_bookings_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    response = StreamingHttpResponse(row_generator(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
