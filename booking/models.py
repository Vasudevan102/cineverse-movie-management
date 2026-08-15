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
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('REFUNDED', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='bookings')
    booking_reference = models.CharField(max_length=20, unique=True, editable=False)
    selected_seats = models.CharField(max_length=200, blank=True, help_text="e.g. A4, A5")
    number_of_seats = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PAID')
    watched = models.BooleanField(default=False)

    class Meta:
        ordering = ['-booking_date']

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
    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI (Google Pay / PhonePe / Paytm)'),
        ('CARD', 'Credit / Debit Card'),
        ('NET_BANKING', 'Net Banking'),
        ('WALLET', 'Digital Wallet'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='UPI')
    transaction_reference = models.CharField(max_length=30, unique=True)
    ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    convenience_fee = models.DecimalField(max_digits=8, decimal_places=2, default=30.00)
    taxes = models.DecimalField(max_digits=8, decimal_places=2, default=54.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.transaction_reference:
            self.transaction_reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.transaction_reference} for {self.booking.booking_reference} (₹{self.total_amount})"
