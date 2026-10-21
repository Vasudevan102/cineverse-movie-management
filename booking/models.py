import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from movies.models import Movie

User = get_user_model()

class Theater(models.Model):
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    address = models.TextField()
    total_screens = models.PositiveIntegerField(default=1)
    facilities = models.TextField(blank=True, help_text="e.g. Dolby Atmos, Parking, Food Court, Recliner Seats")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.name} - {self.location}, {self.city}"

class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='shows')
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='shows')
    screen = models.CharField(max_length=50, default="Screen 1")
    show_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_seats = models.PositiveIntegerField(default=100)
    available_seats = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['show_date', 'start_time']
        indexes = [
            models.Index(fields=['show_date', 'theater'], name='show_date_theater_idx'),
            models.Index(fields=['show_date', 'start_time'], name='show_date_start_time_idx'),
        ]

    def clean(self):
        if self.ticket_price is not None and self.ticket_price < 0:
            raise ValidationError({'ticket_price': "Ticket price cannot be negative."})
        if self.available_seats > self.total_seats:
            raise ValidationError({'available_seats': "Available seats cannot exceed total seats."})
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': "End time must be after start time."})

        # Check for schedule conflicts on same theater & screen & date
        if self.theater_id and self.screen and self.show_date and self.start_time and self.end_time:
            conflicts = Show.objects.filter(
                theater=self.theater,
                screen=self.screen,
                show_date=self.show_date,
                is_active=True,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(pk=self.pk)

            if conflicts.exists():
                raise ValidationError("There is a conflicting show schedule in the same screen and theater for this time interval.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.movie.title} at {self.theater.name} ({self.show_date} {self.start_time.strftime('%H:%M')})"

    @property
    def is_past(self):
        show_datetime = timezone.make_aware(timezone.datetime.combine(self.show_date, self.end_time))
        return timezone.now() > show_datetime

    @property
    def booked_seats_count(self):
        return max(0, self.total_seats - self.available_seats)

    @property
    def occupancy_percent(self):
        if not self.total_seats or self.total_seats == 0:
            return 0
        return int((self.booked_seats_count / self.total_seats) * 100)

    @property
    def occupancy_status(self):
        pct = self.occupancy_percent
        if pct >= 90:
            return "🔥 Almost Full"
        elif pct >= 70:
            return "⚡ Filling Fast"
        return "Available"

    @property
    def occupancy_glow_class(self):
        pct = self.occupancy_percent
        if pct >= 90:
            return "occupancy-almost-full"
        elif pct >= 70:
            return "occupancy-filling-fast"
        return "occupancy-available"


class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='bookings')
    booking_reference = models.CharField(max_length=20, unique=True, editable=False)
    selected_seats = models.CharField(max_length=200, blank=True, help_text="e.g. A4, A5")
    number_of_seats = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_PAYMENT')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    watched = models.BooleanField(default=False)

    class Meta:
        ordering = ['-booking_date']
        indexes = [
            models.Index(fields=['booking_date', 'status'], name='booking_date_status_idx'),
            models.Index(fields=['payment_status'], name='booking_payment_status_idx'),
            models.Index(fields=['status'], name='booking_status_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = f"CV-{uuid.uuid4().hex[:8].upper()}"
        if not self.total_amount and self.show:
            self.total_amount = self.show.ticket_price * self.number_of_seats
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.booking_reference} - {self.user.username} ({self.show.movie.title})"

    @property
    def is_completed_or_past(self):
        if self.status == 'COMPLETED':
            return True
        if self.status == 'CONFIRMED' and self.show.is_past:
            return True
        return False


class Payment(models.Model):
    PROVIDER_CHOICES = [
        ('RAZORPAY', 'Razorpay'),
        ('DEMO', 'Demo Gateway'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI (Google Pay / PhonePe / Paytm)'),
        ('CARD', 'Credit / Debit Card'),
        ('NET_BANKING', 'Net Banking'),
        ('WALLET', 'Digital Wallet'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='RAZORPAY')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='UPI')

    # Provider and Transaction Identifiers
    order_id = models.CharField(max_length=100, blank=True, db_index=True, help_text="Razorpay Order ID (e.g. order_xxx)")
    payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Razorpay Payment ID (e.g. pay_xxx)")
    transaction_reference = models.CharField(max_length=50, unique=True, db_index=True)
    signature = models.CharField(max_length=255, blank=True, help_text="HMAC Signature")

    # Financial Breakdown
    currency = models.CharField(max_length=10, default='INR')
    ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    convenience_fee = models.DecimalField(max_digits=8, decimal_places=2, default=30.00)
    taxes = models.DecimalField(max_digits=8, decimal_places=2, default=54.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Status and Diagnostics
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    failure_reason = models.TextField(blank=True)
    error_code = models.CharField(max_length=100, blank=True)

    # Refund Metadata
    refund_id = models.CharField(max_length=100, blank=True, help_text="Razorpay Refund ID")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_status = models.CharField(max_length=30, blank=True)
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['payment_id']),
            models.Index(fields=['status']),
            models.Index(fields=['status', 'created_at'], name='payment_status_created_idx'),
            models.Index(fields=['refund_status', 'refunded_at'], name='payment_refund_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.transaction_reference:
            self.transaction_reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        if not self.user_id and self.booking_id and self.booking.user_id:
            self.user = self.booking.user
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.transaction_reference} ({self.status}) for {self.booking.booking_reference} (₹{self.total_amount})"


class SeatReservation(models.Model):
    STATUS_CHOICES = [
        ('RESERVED', 'Temporarily Reserved'),
        ('BOOKED', 'Confirmed & Booked'),
    ]

    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='seat_reservations')
    seat_number = models.CharField(max_length=10, db_index=True, help_text="e.g. A1, E4")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_reservations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RESERVED')
    reserved_until = models.DateTimeField(null=True, blank=True, db_index=True)
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='seat_reservations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['show', 'seat_number']
        unique_together = ('show', 'seat_number')
        indexes = [
            models.Index(fields=['show', 'status', 'reserved_until']),
            models.Index(fields=['reserved_until']),
        ]

    def __str__(self):
        return f"{self.show.movie.title} @ {self.show.theater.name} - Seat {self.seat_number} ({self.status} by {self.user.username})"

    @property
    def is_expired(self):
        if self.status == 'RESERVED' and self.reserved_until:
            return timezone.now() > self.reserved_until
        return False

    @classmethod
    def release_expired_for_show(cls, show):
        """Releases/purges expired reservations for a given show."""
        now = timezone.now()
        expired = cls.objects.filter(show=show, status='RESERVED', reserved_until__lte=now)
        count = expired.count()
        if count > 0:
            expired.delete()
        return count

    @classmethod
    def release_all_expired(cls):
        """Releases/purges all expired reservations across all shows."""
        now = timezone.now()
        expired = cls.objects.filter(status='RESERVED', reserved_until__lte=now)
        count = expired.count()
        if count > 0:
            expired.delete()
        return count


class Ticket(models.Model):
    """
    Digital ticket linked 1:1 to a confirmed Booking.
    Stores PDF file, QR verification token, and email delivery status.
    """
    EMAIL_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='ticket')
    ticket_number = models.CharField(max_length=30, unique=True, editable=False)
    verification_token = models.CharField(max_length=64, unique=True, editable=False, db_index=True)
    pdf_file = models.FileField(upload_to='tickets/pdf/', blank=True, null=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    email_status = models.CharField(max_length=20, choices=EMAIL_STATUS_CHOICES, default='PENDING', db_index=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_attempts = models.PositiveIntegerField(default=0)
    last_email_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email_status', 'created_at'], name='ticket_email_status_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = f"TKT-{uuid.uuid4().hex[:10].upper()}"
        if not self.verification_token:
            import secrets
            self.verification_token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket {self.ticket_number} for {self.booking.booking_reference}"

    def get_verification_url(self, request=None):
        """Returns the full URL for QR code verification."""
        from django.urls import reverse
        path = reverse('ticket_verify', kwargs={'token': self.verification_token})
        if request:
            return request.build_absolute_uri(path)
        from django.conf import settings
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        return f"{site_url.rstrip('/')}{path}"

