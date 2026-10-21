from django.contrib import admin
from .models import Theater, Show, Booking, Payment, SeatReservation, Ticket

class ShowInline(admin.TabularInline):
    model = Show
    extra = 1
    fields = ('movie', 'screen', 'show_date', 'start_time', 'end_time', 'ticket_price', 'total_seats', 'available_seats', 'is_active')

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'city', 'total_screens', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'location', 'city', 'facilities')
    inlines = [ShowInline]

@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ('movie', 'theater', 'screen', 'show_date', 'start_time', 'ticket_price_in_rupees', 'occupancy_status_display', 'available_seats', 'total_seats', 'is_active')
    list_filter = ('show_date', 'theater__city', 'is_active', 'theater')
    search_fields = ('movie__title', 'theater__name', 'screen')

    @admin.display(description='Price')
    def ticket_price_in_rupees(self, obj):
        return f"₹{obj.ticket_price:.0f}"

    @admin.display(description='Occupancy')
    def occupancy_status_display(self, obj):
        return f"{obj.occupancy_percent}% ({obj.occupancy_status})"

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'user', 'show', 'selected_seats', 'number_of_seats', 'total_in_rupees', 'payment_status', 'status', 'booking_date')
    list_filter = ('status', 'payment_status', 'watched', 'booking_date')
    search_fields = ('booking_reference', 'selected_seats', 'user__username', 'user__email', 'show__movie__title')
    readonly_fields = ('booking_reference', 'booking_date', 'total_amount')

    @admin.display(description='Total Amount')
    def total_in_rupees(self, obj):
        return f"₹{obj.total_amount:.0f}"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_reference',
        'order_id',
        'payment_id',
        'booking',
        'user',
        'provider',
        'payment_method',
        'grand_total_in_rupees',
        'status',
        'refund_status',
        'created_at',
        'verified_at'
    )
    list_filter = ('status', 'provider', 'payment_method', 'refund_status', 'created_at', 'verified_at')
    search_fields = (
        'transaction_reference',
        'order_id',
        'payment_id',
        'refund_id',
        'booking__booking_reference',
        'user__username',
        'user__email'
    )
    readonly_fields = (
        'transaction_reference',
        'order_id',
        'payment_id',
        'signature',
        'refund_id',
        'refunded_at',
        'created_at',
        'updated_at',
        'verified_at'
    )

    @admin.display(description='Total Paid')
    def grand_total_in_rupees(self, obj):
        return f"₹{obj.total_amount:.2f}"

@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ('show', 'seat_number', 'user', 'status', 'reserved_until', 'is_expired_display', 'booking', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('seat_number', 'user__username', 'booking__booking_reference', 'show__movie__title')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Expired?')
    def is_expired_display(self, obj):
        return "Yes" if obj.is_expired else "No"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_number', 'booking', 'email_status',
        'generated_at', 'email_sent_at', 'email_attempts', 'created_at'
    )
    list_filter = ('email_status', 'created_at', 'generated_at')
    search_fields = (
        'ticket_number', 'verification_token',
        'booking__booking_reference', 'booking__user__username', 'booking__user__email'
    )
    readonly_fields = ('ticket_number', 'verification_token', 'created_at', 'updated_at')

