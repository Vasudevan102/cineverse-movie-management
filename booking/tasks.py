"""
Asynchronous Celery tasks for CineVerse.
Handles PDF ticket generation and email delivery with retry logic.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_and_email_ticket_task(self, booking_id):
    """
    Asynchronous task: Generate PDF ticket and send booking confirmation email.
    
    Features:
    - Idempotent: Safe to call multiple times for the same booking.
    - Retry: Exponential backoff on SMTP failures (max 3 retries).
    - Non-destructive: A failed email never alters the confirmed booking status.
    
    Args:
        booking_id: Primary key of the Booking instance.
    """
    from booking.models import Booking, Ticket
    from booking.pdf_service import generate_ticket_pdf

    logger.info(f"[TICKET_TASK] Starting for booking_id={booking_id}")

    try:
        booking = Booking.objects.select_related(
            'show__movie', 'show__movie__language',
            'show__theater', 'user'
        ).get(id=booking_id)
    except Booking.DoesNotExist:
        logger.error(f"[TICKET_TASK] Booking {booking_id} not found. Aborting.")
        return

    # Only process confirmed bookings
    if booking.status != 'CONFIRMED' or booking.payment_status != 'PAID':
        logger.warning(
            f"[TICKET_TASK] Booking {booking.booking_reference} is not CONFIRMED/PAID "
            f"(status={booking.status}, payment={booking.payment_status}). Skipping."
        )
        return

    # Get or create the canonical Ticket (idempotent)
    ticket, created = Ticket.objects.get_or_create(booking=booking)
    if created:
        logger.info(f"[TICKET_TASK] Created Ticket {ticket.ticket_number} for {booking.booking_reference}")

    # 1. Generate PDF
    try:
        pdf_bytes = generate_ticket_pdf(ticket)
        logger.info(f"[TICKET_TASK] PDF generated ({len(pdf_bytes)} bytes) for {booking.booking_reference}")
    except Exception as exc:
        logger.error(f"[TICKET_TASK] PDF generation failed for {booking.booking_reference}: {exc}", exc_info=True)
        ticket.last_email_error = f"PDF generation error: {str(exc)}"
        ticket.save(update_fields=['last_email_error'])
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    # 2. Send email with PDF attachment
    if ticket.email_status == 'SENT':
        logger.info(f"[TICKET_TASK] Email already sent for {booking.booking_reference}. Skipping.")
        return

    ticket.email_attempts += 1
    ticket.save(update_fields=['email_attempts'])

    try:
        _send_ticket_email(booking, ticket, pdf_bytes)
        ticket.email_status = 'SENT'
        ticket.email_sent_at = timezone.now()
        ticket.last_email_error = ''
        ticket.save(update_fields=['email_status', 'email_sent_at', 'last_email_error'])
        logger.info(f"[TICKET_TASK] Email sent successfully for {booking.booking_reference} to {booking.user.email}")

    except Exception as exc:
        ticket.email_status = 'FAILED'
        ticket.last_email_error = str(exc)[:500]
        ticket.save(update_fields=['email_status', 'last_email_error'])
        logger.error(
            f"[TICKET_TASK] Email delivery failed for {booking.booking_reference} "
            f"(attempt {ticket.email_attempts}/{self.max_retries + 1}): {exc}"
        )
        # Retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def _send_ticket_email(booking, ticket, pdf_bytes):
    """
    Compose and send the booking confirmation email with PDF attachment.
    
    Uses Django's EmailMessage for attachment support.
    """
    from django.core.mail import EmailMessage
    from django.conf import settings

    user = booking.user
    show = booking.show
    movie = show.movie
    theater = show.theater

    # Get payment info
    payment = booking.payments.filter(status='SUCCESS').order_by('-created_at').first()

    subject = f"🎬 CineVerse Booking Confirmed — {movie.title} | {booking.booking_reference}"

    # Build HTML body
    show_date_str = show.show_date.strftime('%A, %B %d, %Y') if show.show_date else 'N/A'
    show_time_str = show.start_time.strftime('%I:%M %p') if show.start_time else 'N/A'
    seats = booking.selected_seats or str(booking.number_of_seats)
    total = f"₹{booking.total_amount:,.2f}" if booking.total_amount else 'N/A'

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #1a1a2e; color: #ffffff; border-radius: 12px; overflow: hidden;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #e50914, #b20710); padding: 24px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px; letter-spacing: 2px;">🎬 CINEVERSE</h1>
            <p style="margin: 8px 0 0; font-size: 14px; opacity: 0.9;">Booking Confirmation</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 24px;">
            <p style="font-size: 16px; color: #e0e0e0;">Hi {user.get_full_name() or user.username},</p>
            <p style="font-size: 14px; color: #aaa; line-height: 1.6;">
                Your booking has been confirmed! Here are your ticket details:
            </p>
            
            <!-- Movie -->
            <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #e50914;">
                <h2 style="margin: 0 0 8px; font-size: 20px; color: #fff;">{movie.title}</h2>
                <p style="margin: 0; font-size: 13px; color: #999;">
                    {getattr(movie, 'language', None) and movie.language.name or ''} 
                    {' • ' + str(movie.duration) + ' min' if movie.duration else ''}
                    {' • ' + movie.age_certificate if movie.age_certificate else ''}
                </p>
            </div>
            
            <!-- Details Table -->
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin: 16px 0;">
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">📍 Theater</td>
                    <td style="padding: 8px 0; color: #fff; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);"><strong>{theater.name}</strong> ({show.screen})</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">🏙️ Location</td>
                    <td style="padding: 8px 0; color: #fff; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);">{theater.location}, {theater.city}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">📅 Date</td>
                    <td style="padding: 8px 0; color: #ffd700; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);"><strong>{show_date_str}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">⏰ Time</td>
                    <td style="padding: 8px 0; color: #ffd700; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);"><strong>{show_time_str}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">💺 Seats</td>
                    <td style="padding: 8px 0; color: #fff; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);"><strong>{seats}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999; border-bottom: 1px solid rgba(255,255,255,0.1);">💰 Total Paid</td>
                    <td style="padding: 8px 0; color: #00cc66; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1);"><strong>{total}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #999;">🎫 Booking ID</td>
                    <td style="padding: 8px 0; color: #ffd700; text-align: right; font-family: monospace;"><strong>{booking.booking_reference}</strong></td>
                </tr>
            </table>
            
            <!-- Ticket Number -->
            <div style="background: rgba(0,204,102,0.1); border: 1px solid rgba(0,204,102,0.3); border-radius: 8px; padding: 12px; text-align: center; margin: 16px 0;">
                <p style="margin: 0; font-size: 12px; color: #00cc66;">✓ TICKET VERIFIED</p>
                <p style="margin: 4px 0 0; font-size: 16px; color: #fff; font-family: monospace; letter-spacing: 1px;">{ticket.ticket_number}</p>
            </div>
            
            <p style="font-size: 13px; color: #aaa; line-height: 1.6;">
                📎 Your PDF ticket is attached to this email. You can also download it from your 
                <a href="#" style="color: #e50914; text-decoration: none;">My Bookings</a> page.
            </p>
            <p style="font-size: 13px; color: #aaa; line-height: 1.6;">
                Please arrive at least 15 minutes before showtime with a valid photo ID.
            </p>
        </div>
        
        <!-- Footer -->
        <div style="background: rgba(0,0,0,0.3); padding: 16px; text-align: center; font-size: 11px; color: #666;">
            <p style="margin: 0;">This is an automated email from CineVerse. Please do not reply.</p>
            <p style="margin: 4px 0 0;">© {timezone.now().year} CineVerse. All rights reserved.</p>
        </div>
    </div>
    """

    email = EmailMessage(
        subject=subject,
        body=html_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.content_subtype = 'html'

    # Attach PDF ticket
    if pdf_bytes:
        filename = f"CineVerse_Ticket_{booking.booking_reference}.pdf"
        email.attach(filename, pdf_bytes, 'application/pdf')

    email.send(fail_silently=False)
