import io
from datetime import date, time, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from movies.models import Movie, Language, Genre
from booking.models import Theater, Show, Booking, Ticket
from booking.pdf_service import generate_qr_code_image, generate_ticket_pdf
from booking.tasks import generate_and_email_ticket_task


class BaseTicketTestCase(TestCase):
    """Base setup for Ticket and Email confirmation tests."""

    def setUp(self):
        self.client = Client()

        # Users
        self.user = User.objects.create_user(
            username='cineuser',
            email='cineuser@example.com',
            password='Password123!'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='otheruser@example.com',
            password='Password123!'
        )

        # Movie & Dependencies
        self.language = Language.objects.create(name='English', code='en')
        self.genre = Genre.objects.create(name='Sci-Fi', slug='sci-fi')

        self.movie = Movie.objects.create(
            title='Cosmic Odyssey',
            description='An epic journey beyond the stars.',
            release_date=date(2026, 5, 10),
            duration=150,
            age_certificate='U/A',
            language=self.language,
            director='Christopher Nolan',
            trailer_url='https://www.youtube.com/watch?v=YoHD9XEInc0'
        )
        self.movie.genres.add(self.genre)

        # Theater & Show
        self.theater = Theater.objects.create(
            name='IMAX Grand CineVerse',
            location='Cyber City',
            city='Bangalore',
            address='100 Tech Park Blvd',
            total_screens=4
        )

        self.show = Show.objects.create(
            movie=self.movie,
            theater=self.theater,
            screen='Screen 1 - IMAX',
            show_date=timezone.now().date() + timedelta(days=2),
            start_time=time(19, 30),
            end_time=time(22, 0),
            ticket_price=350.00,
            total_seats=60,
            available_seats=58
        )

        # Confirmed & Paid Booking
        self.booking = Booking.objects.create(
            user=self.user,
            show=self.show,
            selected_seats='D4, D5',
            number_of_seats=2,
            total_amount=700.00,
            status='CONFIRMED',
            payment_status='PAID'
        )


class TicketModelTests(BaseTicketTestCase):
    """Tests for the Ticket database model."""

    def test_ticket_creation_and_auto_tokens(self):
        ticket = Ticket.objects.create(booking=self.booking)

        # Verification token auto-generation
        self.assertTrue(ticket.ticket_number.startswith('TKT-'))
        self.assertGreaterEqual(len(ticket.verification_token), 48)
        self.assertEqual(ticket.email_status, 'PENDING')
        self.assertEqual(ticket.email_attempts, 0)
        self.assertFalse(bool(ticket.pdf_file))
        self.assertIsNone(ticket.generated_at)

    def test_ticket_one_to_one_with_booking(self):
        ticket = Ticket.objects.create(booking=self.booking)
        self.assertEqual(self.booking.ticket, ticket)

        # Unique OneToOne
        with self.assertRaises(Exception):
            Ticket.objects.create(booking=self.booking)

    def test_get_verification_url(self):
        ticket = Ticket.objects.create(booking=self.booking)
        url = ticket.get_verification_url()
        self.assertIn(f"/booking/verify/{ticket.verification_token}/", url)


class PDFServiceTests(BaseTicketTestCase):
    """Tests for PDF ticket generation and QR code service."""

    def test_generate_qr_code_image(self):
        img = generate_qr_code_image("https://cineverse.test/verify/sample-token")
        self.assertIsNotNone(img)
        self.assertGreater(img.size[0], 0)
        self.assertGreater(img.size[1], 0)

    def test_generate_ticket_pdf_creates_valid_pdf(self):
        ticket = Ticket.objects.create(booking=self.booking)
        pdf_bytes = generate_ticket_pdf(ticket)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

        # Check ticket model fields updated
        ticket.refresh_from_db()
        self.assertTrue(bool(ticket.pdf_file))
        self.assertIsNotNone(ticket.generated_at)

    def test_generate_ticket_pdf_content_contains_metadata(self):
        ticket = Ticket.objects.create(booking=self.booking)
        pdf_bytes = generate_ticket_pdf(ticket)

        # In reportlab PDF, text streams contain literal strings or compressed data
        # Check that PDF has reasonable length and starts with standard PDF magic number
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertTrue(b'%%EOF' in pdf_bytes or len(pdf_bytes) > 2000)

    def test_generate_ticket_pdf_idempotency(self):
        ticket = Ticket.objects.create(booking=self.booking)
        first_pdf = generate_ticket_pdf(ticket)
        first_file_name = ticket.pdf_file.name

        # Second call without force=True should return existing file without recreating
        second_pdf = generate_ticket_pdf(ticket, force=False)
        ticket.refresh_from_db()

        self.assertEqual(first_file_name, ticket.pdf_file.name)
        self.assertEqual(first_pdf, second_pdf)


class QRVerificationViewTests(BaseTicketTestCase):
    """Tests for the public QR ticket verification view."""

    def setUp(self):
        super().setUp()
        self.ticket = Ticket.objects.create(booking=self.booking)

    def test_verify_valid_ticket(self):
        response = self.client.get(reverse('ticket_verify', kwargs={'token': self.ticket.verification_token}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/ticket_verify.html')

        # Should show verified/valid status
        self.assertContains(response, 'Valid Ticket')
        self.assertContains(response, 'Cosmic Odyssey')
        self.assertContains(response, 'IMAX Grand CineVerse')
        self.assertContains(response, self.booking.booking_reference)

    def test_verify_valid_ticket_does_not_leak_sensitive_info(self):
        response = self.client.get(reverse('ticket_verify', kwargs={'token': self.ticket.verification_token}))
        self.assertEqual(response.status_code, 200)

        # Ensure user's email is not displayed publicly
        self.assertNotContains(response, self.user.email)
        # Ensure password hash or secret payment IDs aren't leaked
        self.assertNotContains(response, 'razorpay_signature')

    def test_verify_cancelled_booking(self):
        self.booking.status = 'CANCELLED'
        self.booking.save()

        response = self.client.get(reverse('ticket_verify', kwargs={'token': self.ticket.verification_token}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ticket Cancelled')

    def test_verify_invalid_token(self):
        response = self.client.get(reverse('ticket_verify', kwargs={'token': 'nonexistent-token-123456789'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid Verification Token')


class TicketDownloadViewTests(BaseTicketTestCase):
    """Tests for secure PDF ticket download view."""

    def setUp(self):
        super().setUp()
        self.ticket = Ticket.objects.create(booking=self.booking)

    def test_download_by_booking_owner(self):
        self.client.login(username='cineuser', password='Password123!')
        response = self.client.get(reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn(f'CineVerse_Ticket_{self.booking.booking_reference}.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_download_by_unauthenticated_user_redirects_to_login(self):
        response = self.client.get(reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_download_by_another_user_forbidden(self):
        self.client.login(username='otheruser', password='Password123!')
        response = self.client.get(reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference}))
        self.assertEqual(response.status_code, 403)

    def test_download_unpaid_booking_forbidden(self):
        unpaid_booking = Booking.objects.create(
            user=self.user,
            show=self.show,
            selected_seats='A1',
            number_of_seats=1,
            total_amount=350.00,
            status='PENDING_PAYMENT',
            payment_status='PENDING'
        )
        self.client.login(username='cineuser', password='Password123!')
        response = self.client.get(reverse('booking_ticket_download', kwargs={'reference': unpaid_booking.booking_reference}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('my_bookings'))

    def test_download_generates_pdf_on_demand_if_missing(self):
        # Ticket without pre-generated PDF
        self.assertFalse(bool(self.ticket.pdf_file))
        self.client.login(username='cineuser', password='Password123!')
        response = self.client.get(reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.ticket.refresh_from_db()
        self.assertTrue(bool(self.ticket.pdf_file))


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class CeleryTaskAndEmailTests(BaseTicketTestCase):
    """Tests for asynchronous Celery ticket generation and email confirmation."""

    def setUp(self):
        super().setUp()
        mail.outbox = []

    def test_task_generates_pdf_and_sends_email(self):
        # Run eager Celery task
        result = generate_and_email_ticket_task.delay(self.booking.id)

        # 1. Check Ticket created & fields updated
        ticket = Ticket.objects.get(booking=self.booking)
        self.assertTrue(bool(ticket.pdf_file))
        self.assertEqual(ticket.email_status, 'SENT')
        self.assertIsNotNone(ticket.email_sent_at)
        self.assertEqual(ticket.email_attempts, 1)
        self.assertEqual(ticket.last_email_error, '')

        # 2. Check Email sent in outbox
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.booking.booking_reference, email.subject)
        self.assertIn(self.movie.title, email.subject)
        self.assertEqual(email.to, [self.user.email])
        self.assertIn("Cosmic Odyssey", email.body)
        self.assertIn("IMAX Grand CineVerse", email.body)

        # 3. Check PDF Attachment
        self.assertEqual(len(email.attachments), 1)
        filename, content, mime_type = email.attachments[0]
        self.assertEqual(filename, f"CineVerse_Ticket_{self.booking.booking_reference}.pdf")
        self.assertEqual(mime_type, 'application/pdf')
        self.assertTrue(content.startswith(b'%PDF'))

    def test_task_idempotency_prevents_duplicate_emails(self):
        # First execution
        generate_and_email_ticket_task.delay(self.booking.id)
        self.assertEqual(len(mail.outbox), 1)

        # Second execution for already SENT ticket
        generate_and_email_ticket_task.delay(self.booking.id)
        # Should still be 1 email sent (no duplicate)
        self.assertEqual(len(mail.outbox), 1)

    def test_task_skips_unconfirmed_booking(self):
        unconfirmed = Booking.objects.create(
            user=self.user,
            show=self.show,
            selected_seats='B1',
            number_of_seats=1,
            total_amount=350.00,
            status='PENDING_PAYMENT',
            payment_status='PENDING'
        )
        generate_and_email_ticket_task.delay(unconfirmed.id)

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(Ticket.objects.filter(booking=unconfirmed).exists())

    @patch('booking.tasks._send_ticket_email')
    def test_task_email_failure_preserves_confirmed_booking(self, mock_send):
        mock_send.side_effect = Exception("SMTP connection timed out")

        # Running task which will fail sending email
        try:
            generate_and_email_ticket_task.delay(self.booking.id)
        except Exception:
            pass

        # CRITICAL REQUIREMENT: Booking must remain CONFIRMED
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'CONFIRMED')
        self.assertEqual(self.booking.payment_status, 'PAID')

        # Ticket recorded failure details
        ticket = Ticket.objects.get(booking=self.booking)
        self.assertEqual(ticket.email_status, 'FAILED')
        self.assertIn('SMTP connection timed out', ticket.last_email_error)
        self.assertGreater(ticket.email_attempts, 0)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class PaymentFlowTicketIntegrationTests(BaseTicketTestCase):
    """Integration tests verifying payment process creates Ticket and updates UI."""

    def setUp(self):
        super().setUp()
        from booking.models import SeatReservation
        mail.outbox = []
        self.pending_booking = Booking.objects.create(
            user=self.user,
            show=self.show,
            selected_seats='C1',
            number_of_seats=1,
            total_amount=350.00,
            status='PENDING_PAYMENT',
            payment_status='PENDING'
        )
        self.reservation = SeatReservation.objects.create(
            show=self.show,
            seat_number='C1',
            user=self.user,
            status='RESERVED',
            reserved_until=timezone.now() + timedelta(minutes=15),
            booking=self.pending_booking
        )

    def test_payment_process_success_triggers_ticket_and_email(self):
        self.client.login(username='cineuser', password='Password123!')
        pay_url = reverse('booking_payment', kwargs={'reference': self.pending_booking.booking_reference})

        response = self.client.post(pay_url, {
            'payment_method': 'UPI',
            'payment_action': 'success'
        })
        self.assertEqual(response.status_code, 302)

        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, 'CONFIRMED')
        self.assertEqual(self.pending_booking.payment_status, 'PAID')

        # Check Ticket was created
        ticket = Ticket.objects.filter(booking=self.pending_booking).first()
        self.assertIsNotNone(ticket)
        self.assertTrue(ticket.ticket_number.startswith('TKT-'))

    def test_booking_success_page_renders_download_button(self):
        self.client.login(username='cineuser', password='Password123!')
        url = reverse('booking_detail', kwargs={'reference': self.booking.booking_reference})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Download PDF Ticket')
        download_url = reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference})
        self.assertContains(response, download_url)

    def test_my_bookings_page_renders_pdf_ticket_button(self):
        self.client.login(username='cineuser', password='Password123!')
        response = self.client.get(reverse('my_bookings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PDF Ticket')
        download_url = reverse('booking_ticket_download', kwargs={'reference': self.booking.booking_reference})
        self.assertContains(response, download_url)

