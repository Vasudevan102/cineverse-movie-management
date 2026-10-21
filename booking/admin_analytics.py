"""
CineVerse Admin Analytics Service
High-performance database-level aggregations for the Admin Analytics Dashboard.
Zero Python-level row iteration. Supports 100,000+ booking scale.
"""

from decimal import Decimal
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import (
    Sum, Count, Avg, F, Q, Case, When, FloatField, ExpressionWrapper, Subquery, OuterRef
)
from django.db.models.functions import (
    Coalesce, TruncDate, TruncDay, TruncWeek, TruncMonth, ExtractHour
)
from django.contrib.auth import get_user_model
from .models import Booking, Payment, Show, Theater

User = get_user_model()


def get_date_range(preset='this_month', custom_start_str=None, custom_end_str=None):
    """
    Returns timezone-aware (start_datetime, end_datetime, preset_name, error_msg).
    Presets supported: today, yesterday, this_week, this_month, this_year, custom.
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    preset = (preset or 'this_month').lower().strip()

    if preset == 'today':
        return today_start, now, 'today', None

    elif preset == 'yesterday':
        y_start = today_start - timedelta(days=1)
        y_end = today_start - timedelta(microseconds=1)
        return y_start, y_end, 'yesterday', None

    elif preset == 'this_week':
        week_start = today_start - timedelta(days=now.weekday())
        return week_start, now, 'this_week', None

    elif preset == 'this_month':
        month_start = today_start.replace(day=1)
        return month_start, now, 'this_month', None

    elif preset == 'this_year':
        year_start = today_start.replace(month=1, day=1)
        return year_start, now, 'this_year', None

    elif preset == 'custom':
        if not custom_start_str or not custom_end_str:
            return today_start.replace(day=1), now, 'this_month', "Custom date range requires both start and end dates."
        try:
            d_start = datetime.strptime(custom_start_str.strip(), "%Y-%m-%d").date()
            d_end = datetime.strptime(custom_end_str.strip(), "%Y-%m-%d").date()
            if d_start > d_end:
                return today_start.replace(day=1), now, 'this_month', "Start date cannot be after end date."
            start_aware = timezone.make_aware(datetime.combine(d_start, time.min))
            end_aware = timezone.make_aware(datetime.combine(d_end, time.max))
            return start_aware, end_aware, 'custom', None
        except ValueError:
            return today_start.replace(day=1), now, 'this_month', "Invalid date format. Use YYYY-MM-DD."

    # Default fallback: this_month
    return today_start.replace(day=1), now, 'this_month', None


def get_revenue_metrics(filter_start=None, filter_end=None):
    """
    Computes revenue metrics across all periods (Today, This Week, This Month, This Year, Filtered)
    in a SINGLE optimized aggregate query using conditional Q() filters on Payment.
    Zero Python row loops.
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    f_start = filter_start or month_start
    f_end = filter_end or now

    # Single SQL Query to extract all period totals
    agg = Payment.objects.aggregate(
        # All-Time Lifetime Gross & Refunds
        gross_total=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS')), Decimal('0.00')),
        refund_total=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED')), Decimal('0.00')),

        # Gross Revenues (status='SUCCESS')
        gross_today=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS', created_at__range=(today_start, now))), Decimal('0.00')),
        gross_week=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS', created_at__range=(week_start, now))), Decimal('0.00')),
        gross_month=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS', created_at__range=(month_start, now))), Decimal('0.00')),
        gross_year=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS', created_at__range=(year_start, now))), Decimal('0.00')),
        gross_filtered=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS', created_at__range=(f_start, f_end))), Decimal('0.00')),

        # Processed Refunds (refund_status='PROCESSED')
        refund_today=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED', refunded_at__range=(today_start, now))), Decimal('0.00')),
        refund_week=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED', refunded_at__range=(week_start, now))), Decimal('0.00')),
        refund_month=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED', refunded_at__range=(month_start, now))), Decimal('0.00')),
        refund_year=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED', refunded_at__range=(year_start, now))), Decimal('0.00')),
        refund_filtered=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED', refunded_at__range=(f_start, f_end))), Decimal('0.00')),
    )

    def pack(gross_val, ref_val):
        return {
            'gross': gross_val,
            'refunds': ref_val,
            'net': max(Decimal('0.00'), gross_val - ref_val)
        }

    return {
        'total': pack(agg['gross_total'], agg['refund_total']),
        'today': pack(agg['gross_today'], agg['refund_today']),
        'this_week': pack(agg['gross_week'], agg['refund_week']),
        'this_month': pack(agg['gross_month'], agg['refund_month']),
        'this_year': pack(agg['gross_year'], agg['refund_year']),
        'filtered': pack(agg['gross_filtered'], agg['refund_filtered']),
    }


def get_dashboard_kpis(start_date, end_date):
    """
    Computes executive KPI cards for the selected period in minimum database trips (3 queries).
    """
    booking_agg = Booking.objects.filter(
        booking_date__range=(start_date, end_date)
    ).aggregate(
        total_bookings=Count('id'),
        confirmed_bookings=Count('id', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])),
        cancelled_bookings=Count('id', filter=Q(status='CANCELLED')),
        tickets_sold=Coalesce(Sum('number_of_seats', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), 0),
        ticket_revenue=Coalesce(Sum('total_amount', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), Decimal('0.00')),
        avg_order_value=Coalesce(Avg('total_amount', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), Decimal('0.00')),
    )

    payment_agg = Payment.objects.filter(
        created_at__range=(start_date, end_date)
    ).aggregate(
        gross_gateway_revenue=Coalesce(Sum('total_amount', filter=Q(status='SUCCESS')), Decimal('0.00')),
        refund_amount=Coalesce(Sum('refund_amount', filter=Q(refund_status='PROCESSED')), Decimal('0.00')),
        refund_count=Count('id', filter=Q(refund_status='PROCESSED')),
    )

    user_agg = User.objects.aggregate(
        total_users=Count('id'),
        new_users=Count('id', filter=Q(date_joined__range=(start_date, end_date)))
    )

    gross_rev = payment_agg['gross_gateway_revenue']
    refund_amt = payment_agg['refund_amount']
    net_rev = max(Decimal('0.00'), gross_rev - refund_amt)

    total_b = booking_agg['total_bookings'] or 1
    cancel_rate = round((booking_agg['cancelled_bookings'] / total_b) * 100, 1)

    return {
        'total_bookings': booking_agg['total_bookings'],
        'confirmed_bookings': booking_agg['confirmed_bookings'],
        'cancelled_bookings': booking_agg['cancelled_bookings'],
        'cancellation_rate': cancel_rate,
        'tickets_sold': booking_agg['tickets_sold'],
        'ticket_revenue': booking_agg['ticket_revenue'],
        'avg_order_value': booking_agg['avg_order_value'],
        'gross_gateway_revenue': gross_rev,
        'refund_amount': refund_amt,
        'refund_count': payment_agg['refund_count'],
        'net_revenue': net_rev,
        'total_revenue': net_rev,
        'total_users': user_agg['total_users'],
        'new_users': user_agg['new_users'],
    }


def get_booking_trends(start_date, end_date):
    """
    Returns time-series data for booking volume and revenue using database TruncDate.
    Never loads individual booking rows into memory.
    """
    delta_days = (end_date.date() - start_date.date()).days

    if delta_days <= 35:
        trends = Booking.objects.filter(
            booking_date__range=(start_date, end_date)
        ).annotate(
            period=TruncDate('booking_date')
        ).values('period').annotate(
            total=Count('id'),
            confirmed=Count('id', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            tickets=Coalesce(Sum('number_of_seats', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), 0),
            revenue=Coalesce(Sum('total_amount', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), Decimal('0.00')),
        ).order_by('period')

        chart_labels = [row['period'].strftime("%b %d") for row in trends]
    else:
        trends = Booking.objects.filter(
            booking_date__range=(start_date, end_date)
        ).annotate(
            period=TruncMonth('booking_date')
        ).values('period').annotate(
            total=Count('id'),
            confirmed=Count('id', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            tickets=Coalesce(Sum('number_of_seats', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), 0),
            revenue=Coalesce(Sum('total_amount', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), Decimal('0.00')),
        ).order_by('period')

        chart_labels = [row['period'].strftime("%b %Y") for row in trends]

    chart_total = [row['total'] for row in trends]
    chart_confirmed = [row['confirmed'] for row in trends]
    chart_cancelled = [row['cancelled'] for row in trends]
    chart_revenue = [float(row['revenue']) for row in trends]

    return {
        'labels': chart_labels,
        'total': chart_total,
        'confirmed': chart_confirmed,
        'cancelled': chart_cancelled,
        'revenue': chart_revenue,
        'raw': list(trends),
    }


def get_theater_occupancy(start_date=None, end_date=None, limit=15):
    """
    Calculates occupancy percentage per theater:
    (booked seats / available seat capacity) * 100
    Uses independent subqueries to completely eliminate Cartesian join duplication.
    """
    shows_filter = Q(theater=OuterRef('pk'), is_active=True)
    if start_date and end_date:
        shows_filter &= Q(show_date__range=(start_date.date(), end_date.date()))

    bookings_filter = Q(show__theater=OuterRef('pk'), status__in=['CONFIRMED', 'COMPLETED'])
    if start_date and end_date:
        bookings_filter &= Q(booking_date__range=(start_date, end_date))

    cap_subquery = Show.objects.filter(shows_filter).values('theater').annotate(
        cap=Sum('total_seats')
    ).values('cap')

    shows_cnt_subquery = Show.objects.filter(shows_filter).values('theater').annotate(
        cnt=Count('id')
    ).values('cnt')

    booked_subquery = Booking.objects.filter(bookings_filter).values('show__theater').annotate(
        booked=Sum('number_of_seats')
    ).values('booked')

    rev_subquery = Booking.objects.filter(bookings_filter).values('show__theater').annotate(
        rev=Sum('total_amount')
    ).values('rev')

    occupancy_qs = Theater.objects.filter(is_active=True).annotate(
        total_shows=Coalesce(Subquery(shows_cnt_subquery), 0),
        total_capacity=Coalesce(Subquery(cap_subquery), 0),
        booked_seats=Coalesce(Subquery(booked_subquery), 0),
        revenue=Coalesce(Subquery(rev_subquery), Decimal('0.00')),
    ).annotate(
        occupancy_pct=ExpressionWrapper(
            Case(
                When(total_capacity__gt=0, then=(F('booked_seats') * 100.0) / F('total_capacity')),
                default=0.0,
                output_field=FloatField()
            ),
            output_field=FloatField()
        )
    ).order_by('-occupancy_pct', '-booked_seats')[:limit]

    return list(occupancy_qs)


def get_popular_movies(start_date=None, end_date=None, limit=10):
    """
    Aggregates top movies by tickets sold and box office revenue.
    Booking -> Show -> Movie.
    """
    b_filter = Q(status__in=['CONFIRMED', 'COMPLETED'])
    if start_date and end_date:
        b_filter &= Q(booking_date__range=(start_date, end_date))

    qs = Booking.objects.filter(b_filter).values(
        'show__movie__id',
        'show__movie__title',
        'show__movie__average_rating',
        'show__movie__duration',
    ).annotate(
        booking_count=Count('id'),
        tickets_sold=Coalesce(Sum('number_of_seats'), 0),
        total_revenue=Coalesce(Sum('total_amount'), Decimal('0.00')),
    ).order_by('-tickets_sold', '-total_revenue')[:limit]

    return list(qs)


def get_top_theaters(start_date=None, end_date=None, limit=10):
    """
    Aggregates top performing theaters by box office revenue and tickets sold.
    """
    b_filter = Q(status__in=['CONFIRMED', 'COMPLETED'])
    if start_date and end_date:
        b_filter &= Q(booking_date__range=(start_date, end_date))

    qs = Booking.objects.filter(b_filter).values(
        'show__theater__id',
        'show__theater__name',
        'show__theater__city',
        'show__theater__total_screens',
    ).annotate(
        booking_count=Count('id'),
        tickets_sold=Coalesce(Sum('number_of_seats'), 0),
        total_revenue=Coalesce(Sum('total_amount'), Decimal('0.00')),
    ).order_by('-total_revenue', '-tickets_sold')[:limit]

    return list(qs)


def get_peak_booking_hours(start_date=None, end_date=None):
    """
    Extracts booking hour (0-23) directly inside SQL engine using ExtractHour.
    Returns sorted distribution across 24 hours.
    """
    b_filter = Q()
    if start_date and end_date:
        b_filter &= Q(booking_date__range=(start_date, end_date))

    qs = Booking.objects.filter(b_filter).annotate(
        hour=ExtractHour('booking_date')
    ).values('hour').annotate(
        booking_count=Count('id'),
        confirmed_count=Count('id', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])),
        revenue=Coalesce(Sum('total_amount', filter=Q(status__in=['CONFIRMED', 'COMPLETED'])), Decimal('0.00')),
    ).order_by('hour')

    hour_map = {row['hour']: row for row in qs if row['hour'] is not None}
    hours_data = []
    labels = []
    counts = []
    revenues = []

    for h in range(24):
        h_str = f"{h:02d}:00"
        labels.append(h_str)
        item = hour_map.get(h, {'booking_count': 0, 'confirmed_count': 0, 'revenue': Decimal('0.00')})
        counts.append(item['booking_count'])
        revenues.append(float(item['revenue']))
        hours_data.append({
            'hour': h,
            'time_label': f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}",
            'booking_count': item['booking_count'],
            'revenue': item['revenue'],
        })

    ranked_hours = sorted(hours_data, key=lambda x: x['booking_count'], reverse=True)

    return {
        'labels': labels,
        'counts': counts,
        'revenues': revenues,
        'ranked': ranked_hours[:5],
    }


def get_cancellation_metrics(start_date=None, end_date=None):
    """
    Computes total cancelled bookings, cancellation rate, and cancelled amount.
    """
    b_filter = Q()
    if start_date and end_date:
        b_filter &= Q(booking_date__range=(start_date, end_date))

    stats = Booking.objects.filter(b_filter).aggregate(
        total_bookings=Count('id'),
        cancelled_bookings=Count('id', filter=Q(status='CANCELLED')),
        post_payment_cancelled=Count('id', filter=Q(status='CANCELLED', payment_status='REFUNDED')),
        checkout_abandoned=Count('id', filter=Q(status='CANCELLED', payment_status='CANCELLED')),
        cancelled_amount=Coalesce(Sum('total_amount', filter=Q(status='CANCELLED')), Decimal('0.00')),
    )

    total = stats['total_bookings'] or 1
    stats['cancellation_rate'] = round((stats['cancelled_bookings'] / total) * 100, 2)
    return stats


def get_refund_metrics(start_date=None, end_date=None):
    """
    Computes refund count, refund amount, and refund rate using Payment model refund fields.
    """
    p_filter = Q(refund_status='PROCESSED')
    if start_date and end_date:
        p_filter &= (
            Q(refunded_at__range=(start_date, end_date)) |
            (Q(refunded_at__isnull=True) & Q(created_at__range=(start_date, end_date)))
        )

    stats = Payment.objects.filter(p_filter).aggregate(
        refund_count=Count('id'),
        refund_amount=Coalesce(Sum('refund_amount'), Decimal('0.00')),
    )

    succ_filter = Q(status='SUCCESS')
    if start_date and end_date:
        succ_filter &= Q(created_at__range=(start_date, end_date))

    total_success = Payment.objects.filter(succ_filter).count() or 1
    stats['refund_rate'] = round((stats['refund_count'] / total_success) * 100, 2)
    return stats


def get_user_growth(start_date=None, end_date=None):
    """
    Aggregates user registration growth by day/month using TruncDate on User.date_joined.
    """
    u_filter = Q()
    if start_date and end_date:
        u_filter &= Q(date_joined__range=(start_date, end_date))

    trends = User.objects.filter(u_filter).annotate(
        period=TruncDate('date_joined')
    ).values('period').annotate(
        registrations=Count('id')
    ).order_by('period')

    labels = [row['period'].strftime("%b %d") for row in trends]
    counts = [row['registrations'] for row in trends]

    return {
        'labels': labels,
        'counts': counts,
        'total_in_period': sum(counts),
        'raw': list(trends),
    }
