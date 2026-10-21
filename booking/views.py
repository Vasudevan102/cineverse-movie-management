from datetime import timedelta
import re
import uuid
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Show, Theater, Booking, Payment, SeatReservation, Ticket
from .forms import BookingForm
from .razorpay_service import RazorpayService
from movies.models import Movie

logger = logging.getLogger(__name__)

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
    ).select_related('movie', 'movie__language', 'theater')

    selected_movie = None
    if movie_param and movie_param.strip():
        m_val = movie_param.strip()
        # 1. Exact slug match
        selected_movie = Movie.objects.filter(slug=m_val, is_active=True).first()
        # 2. Case-insensitive slug match
        if not selected_movie:
            selected_movie = Movie.objects.filter(slug__iexact=m_val, is_active=True).first()
        # 3. Numeric ID match (if ID passed)
        if not selected_movie and m_val.isdigit():
            selected_movie = Movie.objects.filter(id=int(m_val), is_active=True).first()
        # 4. Exact title match
        if not selected_movie:
            selected_movie = Movie.objects.filter(title__iexact=m_val, is_active=True).first()

        if selected_movie:
            shows = shows.filter(movie=selected_movie)
        else:
            # Movie was explicitly requested but not found -> show none, do not display random movies
            shows = shows.none()

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
            shows = shows.filter(show_date__gte=today)
    else:
        # Default when no date is selected: return all upcoming valid shows
        shows = shows.filter(show_date__gte=today)

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
                    payment_status__in=['PENDING', 'FAILED', 'CANCELLED']
                ).first()

            if existing_booking:
                booking = existing_booking
                booking.selected_seats = ', '.join(req_seats)
                booking.number_of_seats = num_seats
                booking.total_amount = subtotal
                booking.status = 'PENDING_PAYMENT'
                booking.payment_status = 'PENDING'
                booking.save()
            else:
                booking = Booking.objects.create(
                    user=request.user,
                    show=show_locked,
                    selected_seats=', '.join(req_seats),
                    number_of_seats=num_seats,
                    total_amount=subtotal,
                    status='PENDING_PAYMENT',
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
    from .razorpay_service import RazorpayService

    booking = get_object_or_404(Booking, booking_reference=reference, user=request.user)

    # If already confirmed and paid, redirect directly to confirmation ticket
    if booking.payment_status == 'PAID' and booking.status == 'CONFIRMED':
        return redirect('booking_detail', reference=booking.booking_reference)

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

    # Verify active seat reservation hold
    active_holds = user_reservations.filter(status='RESERVED', reserved_until__gt=now)
    if not active_holds.exists():
        # Check if seats are already BOOKED (payment already confirmed - idempotent redirect)
        already_booked = user_reservations.filter(status='BOOKED').exists()
        if already_booked:
            return redirect('booking_detail', reference=booking.booking_reference)
        # Released/expired - ask user to select seats again
        messages.error(request, "⚠ Your seat reservation has expired. Please select your seats again.")
        return redirect('booking_create', show_id=booking.show.id)

    # FIX: Extend reservation to 15 minutes when the payment page is loaded.
    # Razorpay checkout + card 3DS authentication can take several minutes.
    # The original 2-minute hold is too short and causes valid payments to fail
    # with "reservation expired" errors inside payment_verify_view.
    extended_until = now + timedelta(minutes=15)
    active_holds.update(reserved_until=extended_until)

    earliest_expiry = extended_until
    remaining_seconds = max(0, int((earliest_expiry - now).total_seconds()))
    reserved_until_iso = earliest_expiry.isoformat()

    # Find or create a pending Payment record with Razorpay Order ID
    payment = Payment.objects.filter(
        booking=booking,
        status='PENDING'
    ).first()

    demo_mode = getattr(settings, 'RAZORPAY_DEMO_MODE', False)
    is_mock_order = bool(payment and payment.order_id and payment.order_id.startswith(f"order_{booking.booking_reference}"))

    if not payment or not payment.order_id or (is_mock_order and not demo_mode):
        order_dict = RazorpayService.create_order(booking, grand_total)
        order_id = order_dict.get('id', '')
        if not payment:
            payment = Payment.objects.create(
                booking=booking,
                user=request.user,
                provider='RAZORPAY',
                order_id=order_id,
                ticket_amount=subtotal,
                convenience_fee=convenience_fee,
                taxes=taxes,
                total_amount=grand_total,
                status='PENDING'
            )
        else:
            payment.order_id = order_id
            payment.ticket_amount = subtotal
            payment.convenience_fee = convenience_fee
            payment.taxes = taxes
            payment.total_amount = grand_total
            payment.save()
    else:
        order_id = payment.order_id

    payment_failed = False

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'UPI')
        payment_action = request.POST.get('payment_action', 'success')
        razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
        razorpay_signature = request.POST.get('razorpay_signature', '').strip()

        if payment_action == 'fail':
            payment_failed = True
            payment.status = 'FAILED'
            payment.failure_reason = 'Payment declined or simulated failure in checkout'
            payment.save(update_fields=['status', 'failure_reason'])
            messages.error(request, "⚠ Payment Failed. Your seats remain reserved until the timer expires. You can retry now.")
        elif payment_action == 'cancel':
            payment.status = 'CANCELLED'
            payment.failure_reason = 'Payment cancelled by user'
            payment.save(update_fields=['status', 'failure_reason'])
            booking.payment_status = 'CANCELLED'
            booking.save(update_fields=['payment_status'])
            messages.info(request, "Payment was cancelled. You can retry before your reservation expires.")
        else:
            # Payment Success Flow
            # If signature provided, verify it; if demo simulation without signature, generate valid test signature
            if not razorpay_signature and getattr(settings, 'PAYMENT_GATEWAY_MODE', 'TEST') in ['TEST', 'DEMO']:
                razorpay_payment_id = razorpay_payment_id or f"pay_{uuid.uuid4().hex[:12]}"
                razorpay_signature = RazorpayService.generate_test_signature(order_id, razorpay_payment_id)

            is_valid_sig = RazorpayService.verify_payment_signature(order_id, razorpay_payment_id, razorpay_signature)
            if not is_valid_sig:
                payment.status = 'FAILED'
                payment.failure_reason = 'Cryptographic signature verification failed'
                payment.save(update_fields=['status', 'failure_reason'])
                messages.error(request, "⚠ Payment verification failed: Invalid transaction signature.")
                payment_failed = True
            else:
                with transaction.atomic():
                    show_locked = Show.objects.select_for_update().get(id=booking.show.id)
                    booking_locked = Booking.objects.select_for_update().get(id=booking.id)
                    now_ts = timezone.now()

                    # Idempotency check: if already confirmed
                    if booking_locked.payment_status == 'PAID' and booking_locked.status == 'CONFIRMED':
                        return redirect('booking_detail', reference=booking_locked.booking_reference)

                    # Lock and verify reservation records inside transaction
                    locked_reservations = SeatReservation.objects.select_for_update().filter(
                        booking=booking_locked,
                        user=request.user,
                        status='RESERVED'
                    )

                    # Check if reservation expired right before submit
                    if not locked_reservations.exists() or any(r.reserved_until and r.reserved_until <= now_ts for r in locked_reservations):
                        locked_reservations.delete()
                        payment.status = 'FAILED'
                        payment.failure_reason = 'Reservation expired before payment could be confirmed'
                        payment.save(update_fields=['status', 'failure_reason'])
                        messages.error(request, "⚠ Reservation expired before payment could be completed. Please select seats again.")
                        return redirect('booking_create', show_id=show_locked.id)

                    # Promote RESERVED -> BOOKED and clear reserved_until
                    locked_reservations.update(status='BOOKED', reserved_until=None)

                    # Update successful payment record
                    payment.payment_id = razorpay_payment_id
                    payment.signature = razorpay_signature
                    payment.payment_method = payment_method
                    payment.status = 'SUCCESS'
                    payment.verified_at = now_ts
                    payment.save()

                    # Confirm booking status
                    booking_locked.status = 'CONFIRMED'
                    booking_locked.payment_status = 'PAID'
                    booking_locked.save(update_fields=['status', 'payment_status'])

                    # Synchronize show available seats
                    active_holds_and_booked = SeatReservation.objects.filter(
                        Q(show=show_locked, status='BOOKED') |
                        Q(show=show_locked, status='RESERVED', reserved_until__gt=now_ts)
                    ).count()
                    show_locked.available_seats = max(0, show_locked.total_seats - active_holds_and_booked)
                    show_locked.save(update_fields=['available_seats'])

                    # Create canonical Ticket and queue async PDF+email generation
                    _ticket, _tcreated = Ticket.objects.get_or_create(booking=booking_locked)
                    _bk_id = booking_locked.id
                    transaction.on_commit(lambda: _dispatch_ticket_task(_bk_id))

                    # Clear session draft
                    request.session.pop('booking_draft', None)

                formatted_total = f"{grand_total:.2f}"
                messages.success(request, f"✓ Payment of ₹{formatted_total} Verified & Successful! Booking Confirmed.")
                return redirect('booking_detail', reference=booking.booking_reference)

    amount_in_paise = int((grand_total * Decimal('100')).quantize(Decimal('1')))
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    demo_mode = getattr(settings, 'RAZORPAY_DEMO_MODE', False)
    test_payment_id = f"pay_test_{uuid.uuid4().hex[:10]}"
    test_signature = RazorpayService.generate_test_signature(order_id, test_payment_id)

    context = {
        'booking': booking,
        'payment': payment,
        'ticket_price': ticket_price,
        'subtotal': subtotal,
        'ticket_amount': subtotal,
        'convenience_fee': convenience_fee,
        'taxes': taxes,
        'grand_total': grand_total,
        'amount_in_paise': amount_in_paise,
        'razorpay_key_id': key_id,
        'razorpay_order_id': order_id,
        'demo_mode': demo_mode,
        'test_payment_id': test_payment_id,
        'test_signature': test_signature,
        'payment_failed': payment_failed,
        'remaining_seconds': remaining_seconds,
        'reserved_until_iso': reserved_until_iso,
        'payment_gateway_mode': getattr(settings, 'PAYMENT_GATEWAY_MODE', 'TEST'),
    }
    return render(request, 'booking/booking_payment.html', context)

@login_required
def payment_verify_view(request):
    """
    Dedicated server-side payment signature verification endpoint.
    Handles Razorpay checkout handler callback.
    """
    from .razorpay_service import RazorpayService

    if request.method != 'POST':
        return redirect('my_bookings')

    order_id = request.POST.get('razorpay_order_id', '').strip()
    payment_id = request.POST.get('razorpay_payment_id', '').strip()
    signature = request.POST.get('razorpay_signature', '').strip()
    booking_ref = request.POST.get('booking_reference', '').strip()
    payment_method = request.POST.get('payment_method', 'UPI')

    logger.info(
        f"[PAYMENT_VERIFY] Callback received | User: {request.user.username} | "
        f"Booking: {booking_ref} | Order: {order_id} | Payment: {payment_id} | Sig Length: {len(signature)}"
    )

    if not order_id and not booking_ref:
        logger.warning(f"[PAYMENT_VERIFY] Missing required parameters | User: {request.user.username}")
        messages.error(request, "Missing payment verification parameters.")
        return redirect('my_bookings')

    if booking_ref:
        booking = get_object_or_404(Booking, booking_reference=booking_ref, user=request.user)
    else:
        payment_obj = get_object_or_404(Payment, order_id=order_id, user=request.user)
        booking = payment_obj.booking

    payment = Payment.objects.filter(booking=booking, order_id=order_id).first()
    if not payment:
        payment = Payment.objects.filter(booking=booking).order_by('-created_at').first()

    # Server-side cryptographic signature check
    is_valid = RazorpayService.verify_payment_signature(order_id, payment_id, signature)

    if not is_valid:
        logger.warning(
            f"[PAYMENT_VERIFY] Verification failed for booking {booking.booking_reference} | "
            f"Order ID: {order_id} | Payment ID: {payment_id}"
        )
        if payment:
            payment.status = 'FAILED'
            payment.failure_reason = 'Invalid signature verification on server'
            payment.save(update_fields=['status', 'failure_reason'])
        booking.payment_status = 'FAILED'
        booking.save(update_fields=['payment_status'])
        messages.error(request, "⚠ Payment signature verification failed. Booking not confirmed.")
        return redirect('booking_payment', reference=booking.booking_reference)

    with transaction.atomic():
        booking_locked = Booking.objects.select_for_update().get(id=booking.id)
        show_locked = Show.objects.select_for_update().get(id=booking.show.id)
        now_ts = timezone.now()

        # Idempotency check: Already processed
        if booking_locked.payment_status == 'PAID' and booking_locked.status == 'CONFIRMED':
            logger.info(f"[PAYMENT_VERIFY] Idempotent hit: Booking {booking.booking_reference} already confirmed.")
            return redirect('booking_detail', reference=booking_locked.booking_reference)

        # Lock seat reservation records (RESERVED or already BOOKED)
        locked_reserved = SeatReservation.objects.select_for_update().filter(
            booking=booking_locked,
            user=request.user,
            status='RESERVED'
        )
        locked_booked = SeatReservation.objects.select_for_update().filter(
            booking=booking_locked,
            user=request.user,
            status='BOOKED'
        )

        # If seats are already BOOKED this is a duplicate callback — idempotent
        if locked_booked.exists() and not locked_reserved.exists():
            logger.info(f"[PAYMENT_VERIFY] Seats already BOOKED for booking {booking.booking_reference} — idempotent re-confirm")
            # Still update payment record if needed
            if payment and payment.status != 'SUCCESS':
                payment.payment_id = payment_id
                payment.signature = signature
                payment.payment_method = payment_method
                payment.status = 'SUCCESS'
                payment.verified_at = now_ts
                payment.save()
            if booking_locked.payment_status != 'PAID':
                booking_locked.status = 'CONFIRMED'
                booking_locked.payment_status = 'PAID'
                booking_locked.save(update_fields=['status', 'payment_status'])
            return redirect('booking_detail', reference=booking_locked.booking_reference)

        # No RESERVED seats found — reservation has truly expired
        if not locked_reserved.exists():
            if payment:
                payment.status = 'FAILED'
                payment.failure_reason = 'Reservation expired before signature verification'
                payment.save(update_fields=['status', 'failure_reason'])
            logger.warning(f"[PAYMENT_VERIFY] No active reservations for booking {booking.booking_reference}")
            messages.error(request, "⚠ Reservation expired before payment verification completed. Please re-select seats.")
            return redirect('booking_create', show_id=show_locked.id)

        # Check if all RESERVED seats are still within the hold window
        expired_seats = [r for r in locked_reserved if r.reserved_until and r.reserved_until <= now_ts]
        if expired_seats:
            expired_nums = [r.seat_number for r in expired_seats]
            logger.warning(
                f"[PAYMENT_VERIFY] Expired reserved seats {expired_nums} for booking "
                f"{booking.booking_reference} — Razorpay payment was valid, so proceeding anyway"
            )
            # Payment was cryptographically verified — honour it even if the hold
            # window elapsed during Razorpay's checkout/3DS flow.
            # Do NOT reject a real payment purely because our 2-minute timer expired.

        locked_reservations = locked_reserved

        locked_reservations.update(status='BOOKED', reserved_until=None)

        if payment:
            payment.payment_id = payment_id
            payment.signature = signature
            payment.payment_method = payment_method
            payment.status = 'SUCCESS'
            payment.verified_at = now_ts
            payment.save()

        booking_locked.status = 'CONFIRMED'
        booking_locked.payment_status = 'PAID'
        booking_locked.save(update_fields=['status', 'payment_status'])

        # Recalculate show available seats
        active_holds_and_booked = SeatReservation.objects.filter(
            Q(show=show_locked, status='BOOKED') |
            Q(show=show_locked, status='RESERVED', reserved_until__gt=now_ts)
        ).count()
        show_locked.available_seats = max(0, show_locked.total_seats - active_holds_and_booked)
        show_locked.save(update_fields=['available_seats'])

        # Create canonical Ticket and queue async PDF+email generation
        _ticket, _tcreated = Ticket.objects.get_or_create(booking=booking_locked)
        _bk_id = booking_locked.id
        transaction.on_commit(lambda: _dispatch_ticket_task(_bk_id))

        request.session.pop('booking_draft', None)

    logger.info(
        f"[PAYMENT_VERIFY] Booking {booking.booking_reference} confirmed successfully | "
        f"Payment ID: {payment_id} | Seats Booked: {booking.selected_seats}"
    )
    messages.success(request, f"✓ Payment Verified Successfully! Booking {booking.booking_reference} Confirmed.")
    return redirect('booking_detail', reference=booking.booking_reference)

@login_required
def payment_cancel_view(request, reference):
    """
    Handles payment cancellation by user during checkout.
    """
    booking = get_object_or_404(Booking, booking_reference=reference, user=request.user)

    if booking.payment_status != 'PAID':
        Payment.objects.filter(booking=booking, status='PENDING').update(
            status='CANCELLED',
            failure_reason='Cancelled by customer at checkout'
        )
        booking.status = 'CANCELLED'
        booking.payment_status = 'CANCELLED'
        booking.save(update_fields=['status', 'payment_status'])

        # Check if reservation is expired
        now_ts = timezone.now()
        SeatReservation.objects.filter(booking=booking, status='RESERVED', reserved_until__lte=now_ts).delete()

        messages.info(request, "Payment was cancelled. You can retry anytime before your reservation expires.")

    return redirect('my_bookings')

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse

@csrf_exempt
@require_POST
def razorpay_webhook_view(request):
    """
    Secure, idempotent Razorpay Webhook listener.
    Verifies X-Razorpay-Signature and processes asynchronous payment events.
    """
    from .razorpay_service import RazorpayService
    import json

    signature = request.headers.get('X-Razorpay-Signature', '')
    if not signature:
        return HttpResponse("Missing signature", status=400)

    is_valid = RazorpayService.verify_webhook_signature(request.body, signature)
    if not is_valid:
        return HttpResponse("Invalid signature", status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponse("Invalid JSON payload", status=400)

    event = data.get('event', '')
    payload = data.get('payload', {})

    if event in ['payment.captured', 'order.paid']:
        payment_entity = payload.get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id') or payload.get('order', {}).get('entity', {}).get('id')
        payment_id = payment_entity.get('id')
        payment_method = payment_entity.get('method', 'UPI')

        if order_id:
            payment = Payment.objects.filter(order_id=order_id).first()
            if payment and payment.status != 'SUCCESS':
                with transaction.atomic():
                    booking = Booking.objects.select_for_update().get(id=payment.booking_id)
                    show = Show.objects.select_for_update().get(id=booking.show_id)
                    now_ts = timezone.now()

                    # Promote seat reservations to BOOKED
                    SeatReservation.objects.filter(
                        booking=booking,
                        status='RESERVED'
                    ).update(status='BOOKED', reserved_until=None)

                    payment.payment_id = payment_id
                    payment.status = 'SUCCESS'
                    payment.payment_method = payment_method.upper()
                    payment.verified_at = now_ts
                    payment.save()

                    booking.status = 'CONFIRMED'
                    booking.payment_status = 'PAID'
                    booking.save(update_fields=['status', 'payment_status'])

                    active_holds_and_booked = SeatReservation.objects.filter(
                        Q(show=show, status='BOOKED') |
                        Q(show=show, status='RESERVED', reserved_until__gt=now_ts)
                    ).count()
                    show.available_seats = max(0, show.total_seats - active_holds_and_booked)
                    show.save(update_fields=['available_seats'])

                    # Create canonical Ticket and queue async PDF+email generation
                    _ticket, _tcreated = Ticket.objects.get_or_create(booking=booking)
                    _bk_id = booking.id
                    transaction.on_commit(lambda: _dispatch_ticket_task(_bk_id))

    elif event == 'payment.failed':
        payment_entity = payload.get('payment', {}).get('entity', {})
        order_id = payment_entity.get('order_id')
        error_desc = payment_entity.get('error_description', 'Payment failed via webhook notification')
        error_code = payment_entity.get('error_code', '')

        if order_id:
            payment = Payment.objects.filter(order_id=order_id).first()
            if payment and payment.status == 'PENDING':
                payment.status = 'FAILED'
                payment.failure_reason = error_desc
                payment.error_code = error_code
                payment.save(update_fields=['status', 'failure_reason', 'error_code'])
                Booking.objects.filter(id=payment.booking_id, payment_status='PENDING').update(payment_status='FAILED')

    elif event == 'refund.processed':
        refund_entity = payload.get('refund', {}).get('entity', {})
        payment_id = refund_entity.get('payment_id')
        refund_id = refund_entity.get('id')
        refund_amount = Decimal(str(refund_entity.get('amount', 0))) / Decimal('100')

        if payment_id:
            payment = Payment.objects.filter(payment_id=payment_id).first()
            if payment:
                payment.refund_id = refund_id
                payment.refund_amount = refund_amount
                payment.refund_status = 'PROCESSED'
                payment.refunded_at = timezone.now()
                payment.save(update_fields=['refund_id', 'refund_amount', 'refund_status', 'refunded_at'])
                Booking.objects.filter(id=payment.booking_id).update(payment_status='REFUNDED', status='CANCELLED')

    return JsonResponse({'status': 'ok', 'event': event})

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

    bookings = user_bookings.select_related('show__movie', 'show__theater', 'show__movie__language').prefetch_related('payments').order_by('-booking_date')

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
    payment = booking.payments.filter(status='SUCCESS').order_by('-created_at').first()
    if not payment:
        payment = booking.payments.order_by('-created_at').first()
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

            # Record refund on payment record
            payment = booking.payments.filter(status='SUCCESS').order_by('-created_at').first()
            if payment:
                payment.refund_id = f"rfnd_{uuid.uuid4().hex[:12]}"
                payment.refund_amount = booking.total_amount
                payment.refund_status = 'PROCESSED'
                payment.refund_reason = 'USER_CANCELLATION'
                payment.refunded_at = timezone.now()
                payment.save(update_fields=['refund_id', 'refund_amount', 'refund_status', 'refund_reason', 'refunded_at'])

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


def _dispatch_ticket_task(booking_id):
    """Helper to dispatch ticket generation task. Handles import gracefully."""
    try:
        from booking.tasks import generate_and_email_ticket_task
        generate_and_email_ticket_task.delay(booking_id)
        logger.info(f"[TICKET_DISPATCH] Queued ticket task for booking_id={booking_id}")
    except Exception as exc:
        logger.error(f"[TICKET_DISPATCH] Failed to queue ticket task for booking_id={booking_id}: {exc}")


@login_required
def ticket_download_view(request, reference):
    """
    Download PDF ticket for a confirmed booking.
    Generates on-demand if not yet cached.
    Only the booking owner can download.
    """
    booking = get_object_or_404(
        Booking.objects.select_related('show__movie', 'show__theater', 'user'),
        booking_reference=reference
    )

    if booking.user != request.user and not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You are not authorized to download this ticket.")

    if booking.status not in ('CONFIRMED', 'COMPLETED') or booking.payment_status != 'PAID':
        messages.error(request, "Ticket download is only available for confirmed bookings.")
        return redirect('my_bookings')

    # Get or create ticket
    ticket, created = Ticket.objects.get_or_create(booking=booking)

    # Generate PDF on demand if not yet generated
    from booking.pdf_service import generate_ticket_pdf
    try:
        pdf_bytes = generate_ticket_pdf(ticket)
    except Exception as exc:
        logger.error(f"[TICKET_DOWNLOAD] PDF generation failed for {reference}: {exc}")
        messages.error(request, "Failed to generate PDF ticket. Please try again later.")
        return redirect('booking_detail', reference=reference)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="CineVerse_Ticket_{reference}.pdf"'
    return response


def ticket_verify_view(request, token):
    """
    Public QR verification endpoint.
    Displays ticket validation status without exposing sensitive customer info.
    """
    ticket = Ticket.objects.select_related(
        'booking__show__movie', 'booking__show__movie__language',
        'booking__show__theater', 'booking__user'
    ).filter(verification_token=token).first()

    context = {
        'ticket': ticket,
        'is_valid': False,
        'status_message': 'Invalid Ticket',
        'status_class': 'danger',
    }

    if ticket:
        booking = ticket.booking
        if booking.status == 'CONFIRMED' and booking.payment_status == 'PAID':
            context['is_valid'] = True
            context['status_message'] = 'Valid Ticket — Verified ✓'
            context['status_class'] = 'success'
        elif booking.status == 'COMPLETED':
            context['is_valid'] = True
            context['status_message'] = 'Valid Ticket — Show Completed'
            context['status_class'] = 'info'
        elif booking.status == 'CANCELLED':
            context['status_message'] = 'Ticket Cancelled'
            context['status_class'] = 'danger'
        else:
            context['status_message'] = 'Ticket Invalid or Payment Pending'
            context['status_class'] = 'warning'

    return render(request, 'booking/ticket_verify.html', context)

