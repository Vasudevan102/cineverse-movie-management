"""
PDF Ticket Generation Service for CineVerse.
Uses ReportLab to create professional cinema tickets with QR verification codes.
"""
import io
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_qr_code_image(data, box_size=6, border=2):
    """Generate QR code as a PIL Image object."""
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def generate_ticket_pdf(ticket, force=False):
    """
    Generate a professional PDF cinema ticket for a given Ticket instance.
    
    Args:
        ticket: booking.models.Ticket instance (must have .booking loaded).
        force: If True, regenerates even if PDF already exists.
    
    Returns:
        bytes: The PDF content as bytes.
    """
    # Idempotent: skip if already generated unless forced
    if not force and ticket.pdf_file and ticket.generated_at:
        try:
            ticket.pdf_file.open('rb')
            content = ticket.pdf_file.read()
            ticket.pdf_file.close()
            return content
        except Exception:
            pass  # PDF file missing, regenerate

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image as RLImage, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    booking = ticket.booking
    show = booking.show
    movie = show.movie
    theater = show.theater
    user = booking.user

    # Get the successful payment record
    payment = booking.payments.filter(status='SUCCESS').order_by('-created_at').first()

    # Build verification URL
    verification_url = ticket.get_verification_url()

    # Generate QR code
    qr_img = generate_qr_code_image(verification_url, box_size=5, border=2)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    # Create PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # Color scheme
    BRAND_RED = HexColor('#E50914')
    DARK_BG = HexColor('#1A1A2E')
    ACCENT_GOLD = HexColor('#FFD700')
    TEXT_GRAY = HexColor('#555555')
    LIGHT_GRAY = HexColor('#F5F5F5')
    MEDIUM_GRAY = HexColor('#999999')

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TicketTitle', parent=styles['Heading1'],
        fontSize=22, textColor=BRAND_RED, spaceAfter=2 * mm,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        'TicketSubtitle', parent=styles['Normal'],
        fontSize=9, textColor=MEDIUM_GRAY, alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    movie_title_style = ParagraphStyle(
        'MovieTitle', parent=styles['Heading2'],
        fontSize=18, textColor=black, spaceAfter=2 * mm,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    detail_label = ParagraphStyle(
        'DetailLabel', parent=styles['Normal'],
        fontSize=8, textColor=MEDIUM_GRAY, fontName='Helvetica',
        spaceAfter=1 * mm,
    )
    detail_value = ParagraphStyle(
        'DetailValue', parent=styles['Normal'],
        fontSize=11, textColor=black, fontName='Helvetica-Bold',
        spaceAfter=3 * mm,
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, textColor=MEDIUM_GRAY, alignment=TA_CENTER,
        spaceAfter=1 * mm,
    )
    section_header_style = ParagraphStyle(
        'SectionHeader', parent=styles['Normal'],
        fontSize=11, textColor=BRAND_RED, fontName='Helvetica-Bold',
        spaceBefore=4 * mm, spaceAfter=2 * mm,
    )

    elements = []

    # -------- HEADER --------
    elements.append(Paragraph('🎬 CINEVERSE', title_style))
    elements.append(Paragraph('Digital Cinema Ticket • Verified Entry Pass', subtitle_style))
    elements.append(HRFlowable(
        width="100%", thickness=1.5, color=BRAND_RED,
        spaceAfter=4 * mm, spaceBefore=1 * mm
    ))

    # -------- MOVIE TITLE --------
    elements.append(Paragraph(movie.title, movie_title_style))

    # Movie metadata line
    meta_parts = []
    if hasattr(movie, 'language') and movie.language:
        meta_parts.append(movie.language.name)
    if movie.duration:
        meta_parts.append(f"{movie.duration} min")
    if movie.age_certificate:
        meta_parts.append(movie.age_certificate)
    if meta_parts:
        meta_line_style = ParagraphStyle(
            'MetaLine', parent=styles['Normal'],
            fontSize=9, textColor=TEXT_GRAY, alignment=TA_CENTER,
            spaceAfter=5 * mm,
        )
        elements.append(Paragraph(' • '.join(meta_parts), meta_line_style))

    elements.append(Spacer(1, 2 * mm))

    # -------- SHOW DETAILS TABLE --------
    elements.append(Paragraph('SHOW DETAILS', section_header_style))

    show_date_str = show.show_date.strftime('%A, %B %d, %Y') if show.show_date else 'N/A'
    show_time_str = show.start_time.strftime('%I:%M %p') if show.start_time else 'N/A'

    detail_data = [
        [
            Paragraph('THEATER', detail_label),
            Paragraph('SCREEN', detail_label),
        ],
        [
            Paragraph(f"{theater.name}", detail_value),
            Paragraph(f"{show.screen}", detail_value),
        ],
        [
            Paragraph('LOCATION', detail_label),
            Paragraph('CITY', detail_label),
        ],
        [
            Paragraph(f"{theater.location}", detail_value),
            Paragraph(f"{theater.city}", detail_value),
        ],
        [
            Paragraph('DATE', detail_label),
            Paragraph('TIME', detail_label),
        ],
        [
            Paragraph(show_date_str, detail_value),
            Paragraph(show_time_str, detail_value),
        ],
    ]

    detail_table = Table(detail_data, colWidths=[doc.width * 0.55, doc.width * 0.45])
    detail_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('BOX', (0, 0), (-1, -1), 0.5, MEDIUM_GRAY),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 3 * mm))

    # -------- BOOKING DETAILS --------
    elements.append(Paragraph('BOOKING INFORMATION', section_header_style))

    seats_display = booking.selected_seats if booking.selected_seats else str(booking.number_of_seats)
    total_amount = f"₹{booking.total_amount:,.2f}" if booking.total_amount else 'N/A'

    booking_data = [
        [
            Paragraph('SEATS', detail_label),
            Paragraph('TOTAL PAID', detail_label),
        ],
        [
            Paragraph(seats_display, detail_value),
            Paragraph(total_amount, detail_value),
        ],
        [
            Paragraph('BOOKING REFERENCE', detail_label),
            Paragraph('CUSTOMER', detail_label),
        ],
        [
            Paragraph(booking.booking_reference, detail_value),
            Paragraph(f"{user.get_full_name() or user.username}", detail_value),
        ],
    ]

    if payment:
        booking_data.extend([
            [
                Paragraph('PAYMENT ID', detail_label),
                Paragraph('TRANSACTION REF', detail_label),
            ],
            [
                Paragraph(payment.payment_id or 'N/A', detail_value),
                Paragraph(payment.transaction_reference or 'N/A', detail_value),
            ],
        ])

    booking_table = Table(booking_data, colWidths=[doc.width * 0.55, doc.width * 0.45])
    booking_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('BOX', (0, 0), (-1, -1), 0.5, MEDIUM_GRAY),
    ]))
    elements.append(booking_table)
    elements.append(Spacer(1, 4 * mm))

    # -------- DIVIDER --------
    elements.append(HRFlowable(
        width="100%", thickness=1, color=MEDIUM_GRAY,
        dash=[3, 3], spaceAfter=4 * mm, spaceBefore=2 * mm
    ))

    # -------- QR CODE & VERIFICATION --------
    elements.append(Paragraph('VERIFICATION', section_header_style))

    # QR Code image
    qr_rl_img = RLImage(qr_buffer, width=35 * mm, height=35 * mm)

    verify_info = Paragraph(
        f'<font size="8" color="#555555">'
        f'Scan QR code or visit:<br/>'
        f'<font color="#E50914"><b>{verification_url}</b></font><br/><br/>'
        f'<b>Ticket No:</b> {ticket.ticket_number}<br/>'
        f'<b>Status:</b> <font color="#00AA00">VERIFIED ✓</font>'
        f'</font>',
        styles['Normal']
    )

    qr_table = Table(
        [[qr_rl_img, verify_info]],
        colWidths=[40 * mm, doc.width - 45 * mm]
    )
    qr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 5 * mm),
    ]))
    elements.append(qr_table)
    elements.append(Spacer(1, 5 * mm))

    # -------- ENTRY INSTRUCTIONS --------
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=MEDIUM_GRAY,
        spaceAfter=3 * mm, spaceBefore=2 * mm
    ))

    instructions_style = ParagraphStyle(
        'Instructions', parent=styles['Normal'],
        fontSize=7.5, textColor=TEXT_GRAY, alignment=TA_CENTER,
        leading=11,
    )
    elements.append(Paragraph(
        '📋 <b>Entry Instructions:</b> Present this ticket (digital or printed) at the cinema entrance. '
        'A valid photo ID matching the booking name may be requested. '
        'Please arrive at least 15 minutes before showtime. '
        'Outside food and beverages may not be permitted. '
        'This ticket is non-transferable.',
        instructions_style
    ))
    elements.append(Spacer(1, 3 * mm))

    # -------- FOOTER --------
    elements.append(Paragraph(
        f'Generated by CineVerse on {timezone.now().strftime("%B %d, %Y at %I:%M %p")} • '
        f'This is a computer-generated document and does not require a physical signature.',
        footer_style
    ))

    # Build PDF
    doc.build(elements)
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    # Save to ticket model
    filename = f"ticket_{ticket.ticket_number}_{booking.booking_reference}.pdf"
    ticket.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    ticket.generated_at = timezone.now()
    ticket.save(update_fields=['pdf_file', 'generated_at'])

    logger.info(f"[PDF_SERVICE] Generated PDF ticket for {booking.booking_reference} ({len(pdf_bytes)} bytes)")
    return pdf_bytes
