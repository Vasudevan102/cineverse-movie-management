from datetime import timedelta
import re
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from .models import Show, Theater, Booking, Payment, SeatReservation
from .forms import BookingForm
from movies.models import Movie

def theater_list_view(request):
    city = request.GET.get('city')
    q = request.GET.get('q')

    theaters = Theater.objects.filter(is_active=True)

    if city:
        theaters = theaters.filter(city__iexact=city)

    if q:
        theaters = theaters.filter(
            Q(name__icontains=q) |
            Q(location__icontains=q) |
            Q(city__icontains=q) |
            Q(address__icontains=q) |
            Q(facilities__icontains=q)
        ).distinct()

    today = timezone.now().date()
    theaters = theaters.annotate(
        active_shows_count=Count('shows', filter=Q(shows__is_active=True, shows__show_date__gte=today))
    )

    all_cities = list(Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct())

    context = {
        'theaters': theaters,
        'cities': sorted(all_cities),
        'selected_city': city,
        'search_q': q,
    }
    return render(request, 'booking/theater_list.html', context)

def theater_detail_view(request, pk):
    theater = get_object_or_404(Theater, id=pk, is_active=True)
    today = timezone.now().date()

    shows = Show.objects.filter(
        theater=theater,
        is_active=True,
        show_date__gte=today
    ).select_related('movie', 'movie__language').order_by('movie__title', 'show_date', 'start_time')

    movie_shows_map = {}
    for show in shows:
        movie_shows_map.setdefault(show.movie, []).append(show)

    context = {
        'theater': theater,
        'movie_shows_map': movie_shows_map,
        'total_active_shows': shows.count(),
    }
    return render(request, 'booking/theater_detail.html', context)

def show_list_view(request):
    movie_param = request.GET.get('movie')
    city_param = request.GET.get('city')
    date_param = request.GET.get('date')

    today = timezone.localdate()
    shows = Show.objects.filter(
        is_active=True,
        theater__is_active=True,
        show_date__gte=today
    ).select_related('movie', 'movie__language', 'theater')

    selected_movie = None
    if movie_param and movie_param.strip():
        m_val = movie_param.strip()
        if m_val.isdigit():
            selected_movie = Movie.objects.filter(id=int(m_val)).first()
        if not selected_movie:
            selected_movie = Movie.objects.filter(slug__iexact=m_val).first()
        if not selected_movie:
            selected_movie = Movie.objects.filter(title__iexact=m_val).first()
        if not selected_movie and '-' in m_val:
            base_slug = m_val.split('-')[0]
            selected_movie = Movie.objects.filter(slug__iexact=base_slug).first()
        if not selected_movie:
            selected_movie = Movie.objects.filter(
                Q(slug__icontains=m_val) | Q(title__icontains=m_val)
            ).first()

        if selected_movie:
            shows = shows.filter(movie=selected_movie)
        else:
            shows = shows.filter(
                Q(movie__slug__icontains=m_val) | Q(movie__title__icontains=m_val)
            )

    if city_param and city_param.strip():
        c_val = city_param.strip()
        if c_val.lower() not in ['', 'all', 'all cities', 'all_cities']:
            shows = shows.filter(theater__city__iexact=c_val)

    if date_param and date_param.strip():
        from datetime import datetime as dt
        try:
            parsed_date = dt.strptime(date_param.strip(), '%Y-%m-%d').date()
            shows = shows.filter(show_date=parsed_date)
        except (ValueError, TypeError):
            pass

    shows = shows.order_by('show_date', 'start_time', 'theater__name')

    theaters_cities = Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct()

    context = {
        'shows': shows,
        'selected_movie': selected_movie,
        'cities': sorted(list(set(c for c in theaters_cities if c))),
        'selected_city': city_param,
        'selected_date': date_param,
    }
    return render(request, 'booking/show_list.html', context)

def show_seats_api_view(request, show_id):
    """
    Live Seat Availability JSON API.
    Returns per-seat status (AVAILABLE, RESERVED, BOOKED), user ownership, and remaining seconds.
    Never exposes private user identity.
    """
    show = get_object_or_404(Show, id=show_id, is_active=True)

    # Release any expired reservations for this show
    SeatReservation.release_expired_for_show(show)

    now = timezone.now()
    active_reservations = SeatReservation.objects.filter(show=show)
    reservation_map = {res.seat_number: res for res in active_reservations}

    seats_data = []
    # Grid layout: Rows A-D (Standard), Rows E-F (Premium), numbers 1-8
    all_rows = [('A', 'standard'), ('B', 'standard'), ('C', 'standard'), ('D', 'standard'), ('E', 'premium'), ('F', 'premium')]

    available_count = 0
    reserved_count = 0
    booked_count = 0

    user_id = request.user.id if request.user.is_authenticated else None

    for row, seat_type in all_rows:
        for num in range(1, 9):
            seat_id = f"{row}{num}"
            res = reservation_map.get(seat_id)

            if not res or (res.status == 'RESERVED' and res.reserved_until and res.reserved_until <= now):
                status = 'AVAILABLE'
                is_mine = False
                reserved_until_str = None
                remaining_sec = 0
                available_count += 1
            elif res.status == 'BOOKED':
                status = 'BOOKED'
                is_mine = (res.user_id == user_id) if user_id else False
                reserved_until_str = None
                remaining_sec = 0
                booked_count += 1
            else:
                status = 'RESERVED'
                is_mine = (res.user_id == user_id) if user_id else False
                remaining_sec = max(0, int((res.reserved_until - now).total_seconds()))
                reserved_until_str = res.reserved_until.isoformat() if res.reserved_until else None
                reserved_count += 1

            seats_data.append({
                'seat_id': seat_id,
                'row': row,
                'number': num,
                'seat_type': seat_type,
                'status': status,
                'reserved_by_current_user': is_mine,
                'reserved_until': reserved_until_str,
                'remaining_seconds': remaining_sec,
            })

    return JsonResponse({
        'show_id': show.id,
        'movie_title': show.movie.title,
        'theater_name': show.theater.name,
        'total_seats': len(seats_data),
        'available_count': available_count,
        'reserved_count': reserved_count,
        'booked_count': booked_count,
        'server_time': now.isoformat(),
        'seats': seats_data
    })

@login_required
def booking_create_view(request, show_id):
    show = get_object_or_404(Show, id=show_id, is_active=True)

    if show.is_past:
        messages.error(request, "This show has already ended and cannot be booked.")
        return redirect('movie_detail', slug=show.movie.slug)

    # Release expired reservations for this show
    SeatReservation.release_expired_for_show(show)

    now = timezone.now()
    user_active_reservations = SeatReservation.objects.filter(
        show=show,
        user=request.user,
        status='RESERVED',
        reserved_until__gt=now
    ).order_by('seat_number')

    draft_selected_seats = ", ".join([r.seat_number for r in user_active_reservations])

    # Calculate remaining seconds of user's active hold
    user_remaining_seconds = 0
    user_reserved_until_iso = ""
    if user_active_reservations.exists():
        earliest_expiry = min(r.reserved_until for r in user_active_reservations)
        user_remaining_seconds = max(0, int((earliest_expiry - now).total_seconds()))
        user_reserved_until_iso = earliest_expiry.isoformat()

    if request.method == 'POST':
        selected_seats_input = request.POST.get('selected_seats', '').strip()
        req_seats = [s.strip().upper() for s in selected_seats_input.split(',') if s.strip() and not s.strip().endswith('Seat(s)')]

        if not req_seats:
            num_input = request.POST.get('number_of_seats')
            try:
                num_int = int(num_input)
            except (ValueError, TypeError):
                num_int = 0

            if num_int > 0:
                num_int = min(10, num_int)
                all_possible_seats = [f"{row}{num}" for row in "ABCDEF" for num in range(1, 9)]
                active_taken = set(SeatReservation.objects.filter(
                    show=show,
                    reserved_until__gt=now
                ).exclude(user=request.user).values_list('seat_number', flat=True))
                active_booked = set(SeatReservation.objects.filter(
                    show=show,
                    status='BOOKED'
                ).values_list('seat_number', flat=True))
                taken = active_taken | active_booked
                available_candidates = [s for s in all_possible_seats if s not in taken]
                req_seats = available_candidates[:num_int]

        if not req_seats:
            messages.error(request, "Please select at least 1 seat to proceed.")
            return render(request, 'booking/booking_form.html', {
                'show': show,
                'draft_selected_seats': selected_seats_input,
                'user_remaining_seconds': user_remaining_seconds,
                'user_reserved_until_iso': user_reserved_until_iso,
            })


        if len(req_seats) > 10:
            messages.error(request, "You can select a maximum of 10 seats per booking.")
            return render(request, 'booking/booking_form.html', {
                'show': show,
                'draft_selected_seats': selected_seats_input,
                'user_remaining_seconds': user_remaining_seconds,
                'user_reserved_until_iso': user_reserved_until_iso,
            })

        # Validate seat formats (must match A1-F8)
        valid_seat_pattern = re.compile(r'^[A-F][1-8]$')
        invalid_seats = [s for s in req_seats if not valid_seat_pattern.match(s)]
        if invalid_seats:
            messages.error(request, f"Invalid seat identifier(s): {', '.join(invalid_seats)}")
            return render(request, 'booking/booking_form.html', {
                'show': show,
                'draft_selected_seats': selected_seats_input,
                'user_remaining_seconds': user_remaining_seconds,
                'user_reserved_until_iso': user_reserved_until_iso,
            })

        num_seats = len(req_seats)

        with transaction.atomic():
            show_locked = Show.objects.select_for_update().get(id=show.id)

            # 1. Clean up any expired reservations on this show
            now_ts = timezone.now()
            SeatReservation.objects.filter(
                show=show_locked,
                status='RESERVED',
                reserved_until__lte=now_ts
            ).delete()

            # 2. Lock requested seats in database
            locked_existing = SeatReservation.objects.select_for_update().filter(
                show=show_locked,
                seat_number__in=req_seats
            )

            # 3. Check for any conflicts (booked or actively reserved by another user)
            conflicts = []
            for r in locked_existing:
                if r.status == 'BOOKED':
                    conflicts.append(r.seat_number)
                elif r.status == 'RESERVED' and r.user != request.user and r.reserved_until and r.reserved_until > now_ts:
                    conflicts.append(r.seat_number)

            if conflicts:
                messages.error(
                    request,
                    f"⚠ Seat(s) {', '.join(sorted(conflicts))} are no longer available. Please select different seats."
                )
                return render(request, 'booking/booking_form.html', {
                    'show': show_locked,
                    'draft_selected_seats': selected_seats_input,
                    'user_remaining_seconds': user_remaining_seconds,
                    'user_reserved_until_iso': user_reserved_until_iso,
                })

            # 4. Seat Modification: Release seats previously reserved by this user that are NOT in req_seats
            SeatReservation.objects.filter(
                show=show_locked,
                user=request.user,
                status='RESERVED'
            ).exclude(seat_number__in=req_seats).delete()

            # 5. Set 2-minute temporary hold
            reserved_until = now_ts + timedelta(minutes=2)

            for seat_no in req_seats:
                SeatReservation.objects.update_or_create(
                    show=show_locked,
                    seat_number=seat_no,
                    defaults={
                        'user': request.user,
                        'status': 'RESERVED',
                        'reserved_until': reserved_until,
                    }
                )

            # 6. Recalculate price server-side
            ticket_price = Decimal(str(show_locked.ticket_price))
            subtotal = (ticket_price * Decimal(num_seats)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # 7. Create or update Booking record
            session_draft = request.session.get('booking_draft', {})
            existing_booking = None
            if session_draft.get('show_id') == show.id and session_draft.get('booking_ref'):
                existing_booking = Booking.objects.filter(
                    booking_reference=session_draft['booking_ref'],
                    user=request.user,
                    payment_status='PENDING'
                ).first()

            if existing_booking:
                booking = existing_booking
                booking.selected_seats = ', '.join(req_seats)
                booking.number_of_seats = num_seats
                booking.total_amount = subtotal
                booking.save()
            else:
                booking = Booking.objects.create(
                    user=request.user,
                    show=show_locked,
                    selected_seats=', '.join(req_seats),
                    number_of_seats=num_seats,
                    total_amount=subtotal,
                    status='CONFIRMED',
                    payment_status='PENDING',
                    watched=False
                )

            # Associate all reserved seat records with this booking
            SeatReservation.objects.filter(
                show=show_locked,
                user=request.user,
                status='RESERVED',
                seat_number__in=req_seats
            ).update(booking=booking)

            # Synchronize available_seats count on show
            active_holds_and_booked = SeatReservation.objects.filter(
                Q(show=show_locked, status='BOOKED') |
                Q(show=show_locked, status='RESERVED', reserved_until__gt=now_ts)
            ).count()
            show_locked.available_seats = max(0, show_locked.total_seats - active_holds_and_booked)
            show_locked.save(update_fields=['available_seats'])

            # Store in session
            request.session['booking_draft'] = {
                'show_id': show.id,
                'booking_ref': booking.booking_reference,
                'selected_seats': ', '.join(req_seats),
                'number_of_seats': num_seats,
                'reserved_until': reserved_until.isoformat()
            }

            return redirect('booking_payment', reference=booking.booking_reference)

    context = {
        'show': show,
        'draft_selected_seats': draft_selected_seats,
        'user_remaining_seconds': user_remaining_seconds,
        'user_reserved_until_iso': user_reserved_until_iso,
    }
    return render(request, 'booking/booking_form.html', context)

@login_required
def payment_process_view(request, reference):
    booking = get_object_or_404(Booking, booking_reference=reference, user=request.user)

    # Server-side validation and recalculation of prices using Decimal (never trust client)
    ticket_price = Decimal(str(booking.show.ticket_price))
    seats_count = Decimal(booking.number_of_seats)
    subtotal = (ticket_price * seats_count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    convenience_fee = Decimal('30.00')
    taxes = (subtotal * Decimal('0.18')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    grand_total = subtotal + convenience_fee + taxes

    if booking.total_amount != subtotal:
        booking.total_amount = subtotal
        booking.save(update_fields=['total_amount'])

    # Clean up expired reservations on this show
    SeatReservation.release_expired_for_show(booking.show)

    now = timezone.now()
    user_reservations = SeatReservation.objects.filter(booking=booking, user=request.user)

    # If booking is still PENDING, verify active 2-minute reservation hold
    if booking.payment_status == 'PENDING':
        active_holds = user_reservations.filter(status='RESERVED', reserved_until__gt=now)
        if not active_holds.exists():
            # Released/expired
            messages.error(request, "⚠ Your 2-minute seat reservation has expired. Please select your seats again.")
            return redirect('booking_create', show_id=booking.show.id)

        earliest_expiry = min(r.reserved_until for r in active_holds)
        remaining_seconds = max(0, int((earliest_expiry - now).total_seconds()))
        reserved_until_iso = earliest_expiry.isoformat()
    else:
        remaining_seconds = 0
        reserved_until_iso = ""

    payment_failed = False

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'UPI')
        payment_action = request.POST.get('payment_action', 'success')

        if payment_action == 'fail':
            payment_failed = True
            messages.error(request, "⚠ Payment Failed. Your seats remain reserved until the timer expires.")
        else:
            with transaction.atomic():
                show_locked = Show.objects.select_for_update().get(id=booking.show.id)
                now_ts = timezone.now()

                # Lock and verify reservation records inside transaction
                locked_reservations = SeatReservation.objects.select_for_update().filter(
                    booking=booking,
                    user=request.user,
                    status='RESERVED'
                )

                # Check if reservation expired right before submit
                if not locked_reservations.exists() or any(r.reserved_until and r.reserved_until <= now_ts for r in locked_reservations):
                    locked_reservations.delete()
                    messages.error(request, "⚠ Reservation expired before payment could be completed. Please select seats again.")
                    return redirect('booking_create', show_id=show_locked.id)

                # Promote RESERVED -> BOOKED and clear reserved_until
                locked_reservations.update(status='BOOKED', reserved_until=None)

                # Create successful payment record
                Payment.objects.create(
                    booking=booking,
                    payment_method=payment_method,
                    ticket_amount=subtotal,
                    convenience_fee=convenience_fee,
                    taxes=taxes,
                    total_amount=grand_total,
                    status='SUCCESS'
                )

                # Confirm booking status
                booking.payment_status = 'PAID'
                booking.save(update_fields=['payment_status'])

                # Synchronize show available seats
                active_holds_and_booked = SeatReservation.objects.filter(
                    Q(show=show_locked, status='BOOKED') |
                    Q(show=show_locked, status='RESERVED', reserved_until__gt=now_ts)
                ).count()
                show_locked.available_seats = max(0, show_locked.total_seats - active_holds_and_booked)
                show_locked.save(update_fields=['available_seats'])

                # Clear session draft
                request.session.pop('booking_draft', None)

            formatted_total = f"{grand_total:.2f}"
            messages.success(request, f"✓ Payment of ₹{formatted_total} Successful! Booking Confirmed.")
            return redirect('booking_detail', reference=booking.booking_reference)

    context = {
        'booking': booking,
        'ticket_price': ticket_price,
        'subtotal': subtotal,
        'ticket_amount': subtotal,
        'convenience_fee': convenience_fee,
        'taxes': taxes,
        'grand_total': grand_total,
        'payment_failed': payment_failed,
        'remaining_seconds': remaining_seconds,
        'reserved_until_iso': reserved_until_iso,
    }
    return render(request, 'booking/booking_payment.html', context)

@login_required
def my_bookings_view(request):
    status_filter = request.GET.get('status')
    q = request.GET.get('q')

    today = timezone.now().date()
    user_bookings = Booking.objects.filter(user=request.user)

    counts = {
        'all': user_bookings.count(),
        'upcoming': user_bookings.filter(status='CONFIRMED', show__show_date__gte=today).count(),
        'completed': user_bookings.filter(status='COMPLETED').count(),
        'cancelled': user_bookings.filter(status='CANCELLED').count(),
        'watched': user_bookings.filter(watched=True).count(),
    }

    bookings = user_bookings.select_related('show__movie', 'show__theater', 'show__movie__language').order_by('-booking_date')

    if status_filter == 'upcoming':
        bookings = bookings.filter(status='CONFIRMED', show__show_date__gte=today)
    elif status_filter == 'completed':
        bookings = bookings.filter(status='COMPLETED')
    elif status_filter == 'cancelled':
        bookings = bookings.filter(status='CANCELLED')
    elif status_filter == 'watched':
        bookings = bookings.filter(watched=True)

    if q:
        bookings = bookings.filter(
            Q(show__movie__title__icontains=q) |
            Q(booking_reference__icontains=q) |
            Q(show__theater__name__icontains=q) |
            Q(show__theater__city__icontains=q)
        ).distinct()

    context = {
        'bookings': bookings,
        'selected_status': status_filter,
        'search_q': q,
        'counts': counts,
    }
    return render(request, 'booking/my_bookings.html', context)

@login_required
def booking_detail_view(request, reference):
    booking = get_object_or_404(Booking, booking_reference=reference, user=request.user)
    payment = booking.payments.filter(status='SUCCESS').first()
    return render(request, 'booking/booking_success.html', {'booking': booking, 'payment': payment})

@login_required
def booking_cancel_view(request, reference):
    booking = get_object_or_404(Booking, booking_reference=reference, user=request.user)

    if booking.status == 'CANCELLED':
        messages.info(request, "This booking has already been cancelled.")
        return redirect('my_bookings')

    if booking.show.is_past:
        messages.error(request, "Past shows cannot be cancelled.")
        return redirect('my_bookings')

    if request.method == 'POST':
        with transaction.atomic():
            booking.status = 'CANCELLED'
            booking.payment_status = 'REFUNDED'
            booking.save(update_fields=['status', 'payment_status'])

            show = Show.objects.select_for_update().get(id=booking.show.id)

            # Delete/release all seat reservations associated with this booking
            SeatReservation.objects.filter(booking=booking).delete()

            now_ts = timezone.now()
            active_holds_and_booked = SeatReservation.objects.filter(
                Q(show=show, status='BOOKED') |
                Q(show=show, status='RESERVED', reserved_until__gt=now_ts)
            ).count()
            show.available_seats = max(0, show.total_seats - active_holds_and_booked)
            show.save(update_fields=['available_seats'])

            messages.success(request, f"Booking {booking.booking_reference} cancelled. ₹{booking.total_amount} refund initiated.")
            return redirect('my_bookings')

    return render(request, 'booking/booking_cancel_confirm.html', {'booking': booking})

