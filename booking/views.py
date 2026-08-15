from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from .models import Show, Theater, Booking, Payment
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

        if selected_movie:
            shows = shows.filter(movie=selected_movie)

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

    theaters_cities = Theater.objects.filter(is_active=True).values_list('city', flat=True).distinct()

    context = {
        'shows': shows,
        'selected_movie': selected_movie,
        'cities': sorted(list(set(c for c in theaters_cities if c))),
        'selected_city': city_param,
        'selected_date': date_param,
    }
    return render(request, 'booking/show_list.html', context)

@login_required
def booking_create_view(request, show_id):
    show = get_object_or_404(Show, id=show_id, is_active=True)

    if show.is_past:
        messages.error(request, "This show has already ended and cannot be booked.")
        return redirect('movie_detail', slug=show.movie.slug)

    # Fetch draft selected seats from session if present
    session_draft = request.session.get('booking_draft', {})
    draft_selected_seats = ""
    if session_draft.get('show_id') == show.id:
        draft_selected_seats = session_draft.get('selected_seats', '')

    if request.method == 'POST':
        form = BookingForm(request.POST)
        selected_seats_input = request.POST.get('selected_seats', '').strip()

        if form.is_valid():
            num_seats = form.cleaned_data['number_of_seats']

            with transaction.atomic():
                show_locked = Show.objects.select_for_update().get(id=show.id)

                # Check if user has an existing PENDING booking draft from session
                existing_booking = None
                if session_draft.get('show_id') == show.id and session_draft.get('booking_ref'):
                    existing_booking = Booking.objects.filter(
                        booking_reference=session_draft['booking_ref'],
                        user=request.user,
                        payment_status='PENDING'
                    ).first()

                # Temporarily restore seats for existing pending booking to validate total availability
                effective_available = show_locked.available_seats
                if existing_booking:
                    effective_available += existing_booking.number_of_seats

                if effective_available < num_seats:
                    messages.error(
                        request,
                        f"Sorry! Only {effective_available} seat(s) left for this show."
                    )
                    return render(request, 'booking/booking_form.html', {
                        'show': show_locked,
                        'form': form,
                        'draft_selected_seats': selected_seats_input
                    })

                # Double booking prevention: Check if any requested seats are already confirmed/paid
                if selected_seats_input:
                    req_seats = [s.strip() for s in selected_seats_input.split(',') if s.strip()]
                    paid_bookings = Booking.objects.filter(show=show_locked, payment_status='PAID')
                    if existing_booking:
                        paid_bookings = paid_bookings.exclude(id=existing_booking.id)
                    taken_seats = set()
                    for pb in paid_bookings:
                        if pb.selected_seats:
                            for ts in pb.selected_seats.split(','):
                                taken_seats.add(ts.strip())
                    
                    conflicting = [s for s in req_seats if s in taken_seats]
                    if conflicting:
                        messages.error(
                            request,
                            f"⚠ Seat(s) {', '.join(conflicting)} are no longer available. Please select different seats."
                        )
                        return render(request, 'booking/booking_form.html', {
                            'show': show_locked,
                            'form': form,
                            'draft_selected_seats': selected_seats_input
                        })

                # Update seat inventory: adjust available seats by difference
                if existing_booking:
                    seat_diff = num_seats - existing_booking.number_of_seats
                    show_locked.available_seats -= seat_diff
                else:
                    show_locked.available_seats -= num_seats
                
                if show_locked.available_seats > show_locked.total_seats:
                    show_locked.available_seats = show_locked.total_seats
                show_locked.save()

                ticket_price = Decimal(str(show_locked.ticket_price))
                subtotal = (ticket_price * Decimal(num_seats)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                if existing_booking:
                    booking = existing_booking
                    booking.selected_seats = selected_seats_input or f"{num_seats} Seat(s)"
                    booking.number_of_seats = num_seats
                    booking.total_amount = subtotal
                    booking.save()
                else:
                    booking = Booking.objects.create(
                        user=request.user,
                        show=show_locked,
                        selected_seats=selected_seats_input or f"{num_seats} Seat(s)",
                        number_of_seats=num_seats,
                        total_amount=subtotal,
                        status='CONFIRMED',
                        payment_status='PENDING',
                        watched=False
                    )

                # Save booking draft in session for back navigation
                request.session['booking_draft'] = {
                    'show_id': show.id,
                    'booking_ref': booking.booking_reference,
                    'selected_seats': selected_seats_input,
                    'number_of_seats': num_seats
                }

                return redirect('booking_payment', reference=booking.booking_reference)
    else:
        form = BookingForm()

    context = {
        'show': show,
        'form': form,
        'draft_selected_seats': draft_selected_seats,
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

    payment_failed = False

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'UPI')
        payment_action = request.POST.get('payment_action', 'success')

        if payment_action == 'fail':
            payment_failed = True
            messages.error(request, "⚠ Payment Failed. Your seats have not been permanently booked.")
        else:
            with transaction.atomic():
                show_locked = Show.objects.select_for_update().get(id=booking.show.id)

                # Re-check double booking before final confirmation
                if booking.selected_seats:
                    req_seats = [s.strip() for s in booking.selected_seats.split(',') if s.strip() and not s.strip().endswith('Seat(s)')]
                    if req_seats:
                        paid_bookings = Booking.objects.filter(show=show_locked, payment_status='PAID').exclude(id=booking.id)
                        taken_seats = set()
                        for pb in paid_bookings:
                            if pb.selected_seats:
                                for ts in pb.selected_seats.split(','):
                                    taken_seats.add(ts.strip())
                        
                        conflicting = [s for s in req_seats if s in taken_seats]
                        if conflicting:
                            # Revert temporary seat deduction
                            show_locked.available_seats += booking.number_of_seats
                            if show_locked.available_seats > show_locked.total_seats:
                                show_locked.available_seats = show_locked.total_seats
                            show_locked.save()
                            booking.delete()

                            messages.error(
                                request,
                                f"⚠ Seat(s) {', '.join(conflicting)} were booked by another user. Please select different seats."
                            )
                            return redirect('booking_create', show_id=show_locked.id)

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
                booking.save()

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
            booking.save()

            show = Show.objects.select_for_update().get(id=booking.show.id)
            show.available_seats += booking.number_of_seats
            if show.available_seats > show.total_seats:
                show.available_seats = show.total_seats
            show.save()

            messages.success(request, f"Booking {booking.booking_reference} cancelled. ₹{booking.total_amount} refund initiated.")
            return redirect('my_bookings')

    return render(request, 'booking/booking_cancel_confirm.html', {'booking': booking})
