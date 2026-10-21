"""
Comprehensive Automated Test Suite for Task 4: Admin Analytics Dashboard
Validates:
1. Admin dashboard access
2. Normal user denied
3. Unauthenticated user redirected
4. Revenue calculation
5. Booking trend
6. Theater occupancy
7. Most booked movies
8. Top theaters
9. Peak booking hours
10. Cancellation statistics
11. Refund statistics
12. User growth
13. Today filter
14. Week filter
15. Month filter
16. Year filter
17. Custom date range
18. Invalid date range
19. CSV export headers
20. CSV export content
21. CSV streaming behavior
22. Query count
23. Index/migration correctness
24. Large dataset simulation
"""

import csv
import json
from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import connection
from movies.models import Movie, Language, Genre
from booking.models import Theater, Show, Booking, Payment
from booking import admin_analytics

User = get_user_model()


class AdminDashboardAnalyticsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # 1. Users
        cls.admin_user = User.objects.create_superuser(
            username='admin_tester',
            email='admin@test.com',
            password='AdminPassword123!'
        )
        cls.staff_user = User.objects.create_user(
            username='staff_tester',
            email='staff@test.com',
            password='StaffPassword123!',
            is_staff=True
        )
        cls.normal_user = User.objects.create_user(
            username='normal_tester',
            email='normal@test.com',
            password='NormalPassword123!'
        )

        # 2. Language & Genre
        cls.lang, _ = Language.objects.get_or_create(code="en", defaults={"name": "English"})
        cls.genre, _ = Genre.objects.get_or_create(slug="action", defaults={"name": "Action"})

        # 3. Movies
        cls.movie_a = Movie.objects.create(
            title="Apex Action",
            slug="apex-action",
            description="High octane action movie",
            release_date=datetime(2026, 1, 1).date(),
            duration=120,
            language=cls.lang,
            director="Director One",
            average_rating=4.5
        )
        cls.movie_b = Movie.objects.create(
            title="Silent Echoes",
            slug="silent-echoes",
            description="Mystery drama",
            release_date=datetime(2026, 1, 1).date(),
            duration=110,
            language=cls.lang,
            director="Director Two",
            average_rating=4.0
        )

        # 4. Theaters
        cls.theater_a = Theater.objects.create(
            name="Apex Multiplex",
            location="Downtown",
            city="Mumbai",
            total_screens=2,
            is_active=True
        )
        cls.theater_b = Theater.objects.create(
            name="CineStar Plaza",
            location="Suburbs",
            city="Chennai",
            total_screens=1,
            is_active=True
        )

        # 5. Shows
        cls.now = timezone.now()
        cls.show_a = Show.objects.create(
            movie=cls.movie_a,
            theater=cls.theater_a,
            screen="Screen 1",
            show_date=cls.now.date(),
            start_time=datetime.strptime("18:00", "%H:%M").time(),
            end_time=datetime.strptime("20:30", "%H:%M").time(),
            ticket_price=Decimal("200.00"),
            total_seats=100,
            available_seats=95,
            is_active=True
        )
        cls.show_b = Show.objects.create(
            movie=cls.movie_b,
            theater=cls.theater_b,
            screen="Screen 1",
            show_date=cls.now.date(),
            start_time=datetime.strptime("21:00", "%H:%M").time(),
            end_time=datetime.strptime("23:15", "%H:%M").time(),
            ticket_price=Decimal("150.00"),
            total_seats=80,
            available_seats=78,
            is_active=True
        )

        # 6. Bookings & Payments
        cls.booking_1 = Booking.objects.create(
            user=cls.normal_user,
            show=cls.show_a,
            booking_reference="BK-TEST-001",
            selected_seats="A1, A2",
            number_of_seats=2,
            total_amount=Decimal("400.00"),
            status='CONFIRMED',
            payment_status='PAID',
            booking_date=cls.now - timedelta(hours=2)
        )
        cls.payment_1 = Payment.objects.create(
            booking=cls.booking_1,
            user=cls.normal_user,
            provider='RAZORPAY',
            payment_method='UPI',
            order_id="order_test_001",
            payment_id="pay_test_001",
            transaction_reference="TXN-TEST-001",
            ticket_amount=Decimal("400.00"),
            convenience_fee=Decimal("30.00"),
            taxes=Decimal("72.00"),
            total_amount=Decimal("502.00"),
            status='SUCCESS',
            created_at=cls.now - timedelta(hours=2),
            verified_at=cls.now - timedelta(hours=2)
        )

        cls.booking_2 = Booking.objects.create(
            user=cls.normal_user,
            show=cls.show_a,
            booking_reference="BK-TEST-002",
            selected_seats="B1",
            number_of_seats=1,
            total_amount=Decimal("200.00"),
            status='CONFIRMED',
            payment_status='PAID',
            booking_date=cls.now - timedelta(hours=1)
        )
        cls.payment_2 = Payment.objects.create(
            booking=cls.booking_2,
            user=cls.normal_user,
            provider='RAZORPAY',
            payment_method='CARD',
            order_id="order_test_002",
            payment_id="pay_test_002",
            transaction_reference="TXN-TEST-002",
            ticket_amount=Decimal("200.00"),
            convenience_fee=Decimal("30.00"),
            taxes=Decimal("36.00"),
            total_amount=Decimal("266.00"),
            status='SUCCESS',
            created_at=cls.now - timedelta(hours=1),
            verified_at=cls.now - timedelta(hours=1)
        )

        cls.booking_3 = Booking.objects.create(
            user=cls.normal_user,
            show=cls.show_b,
            booking_reference="BK-TEST-003",
            selected_seats="C1, C2",
            number_of_seats=2,
            total_amount=Decimal("300.00"),
            status='CANCELLED',
            payment_status='REFUNDED',
            booking_date=cls.now - timedelta(hours=3)
        )
        cls.payment_3 = Payment.objects.create(
            booking=cls.booking_3,
            user=cls.normal_user,
            provider='RAZORPAY',
            payment_method='UPI',
            order_id="order_test_003",
            payment_id="pay_test_003",
            transaction_reference="TXN-TEST-003",
            ticket_amount=Decimal("300.00"),
            convenience_fee=Decimal("30.00"),
            taxes=Decimal("54.00"),
            total_amount=Decimal("384.00"),
            status='SUCCESS',
            refund_status='PROCESSED',
            refund_amount=Decimal("300.00"),
            refund_reason='USER_CANCELLATION',
            refunded_at=cls.now - timedelta(hours=1),
            created_at=cls.now - timedelta(hours=3),
            verified_at=cls.now - timedelta(hours=3)
        )

        cls.booking_4 = Booking.objects.create(
            user=cls.normal_user,
            show=cls.show_b,
            booking_reference="BK-TEST-004",
            selected_seats="D1",
            number_of_seats=1,
            total_amount=Decimal("150.00"),
            status='PENDING_PAYMENT',
            payment_status='PENDING',
            booking_date=cls.now - timedelta(minutes=15)
        )
        cls.payment_4 = Payment.objects.create(
            booking=cls.booking_4,
            user=cls.normal_user,
            provider='RAZORPAY',
            payment_method='UPI',
            order_id="order_test_004",
            transaction_reference="TXN-TEST-004",
            ticket_amount=Decimal("150.00"),
            convenience_fee=Decimal("30.00"),
            taxes=Decimal("27.00"),
            total_amount=Decimal("207.00"),
            status='PENDING',
            created_at=cls.now - timedelta(minutes=15)
        )

    def setUp(self):
        self.client = Client()

    def test_admin_dashboard_access_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Analytics Dashboard")

    def test_admin_dashboard_access_superuser(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Analytics Dashboard")
        self.assertContains(response, "Total Revenue")
        self.assertContains(response, "Daily Revenue")

    def test_normal_user_denied(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_revenue_calculation(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        kpis = admin_analytics.get_dashboard_kpis(start_date, end_date)
        
        self.assertEqual(kpis['gross_gateway_revenue'], Decimal('1152.00'))
        self.assertEqual(kpis['refund_amount'], Decimal('300.00'))
        self.assertEqual(kpis['net_revenue'], Decimal('852.00'))
        self.assertEqual(kpis['total_revenue'], Decimal('852.00'))
        self.assertEqual(kpis['ticket_revenue'], Decimal('600.00'))

    def test_daily_weekly_monthly_yearly_revenue(self):
        rev = admin_analytics.get_revenue_metrics()
        self.assertIn('total', rev)
        self.assertIn('today', rev)
        self.assertIn('this_week', rev)
        self.assertIn('this_month', rev)
        self.assertIn('this_year', rev)

        # Net revenues must account for successful payments and processed refunds
        self.assertEqual(rev['total']['net'], Decimal('852.00'))
        self.assertEqual(rev['today']['net'], Decimal('852.00'))
        self.assertEqual(rev['this_week']['net'], Decimal('852.00'))
        self.assertEqual(rev['this_month']['net'], Decimal('852.00'))
        self.assertEqual(rev['this_year']['net'], Decimal('852.00'))


    def test_booking_trend(self):
        start_date = self.now - timedelta(days=2)
        end_date = self.now + timedelta(days=1)
        trends = admin_analytics.get_booking_trends(start_date, end_date)
        self.assertGreater(len(trends['labels']), 0)
        self.assertGreaterEqual(sum(trends['confirmed']), 2)

    def test_theater_occupancy(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        occupancy = admin_analytics.get_theater_occupancy(start_date, end_date)
        self.assertGreater(len(occupancy), 0)
        t_a = next(t for t in occupancy if t.id == self.theater_a.id)
        # 3 seats booked out of 100 capacity = 3.0%
        self.assertAlmostEqual(t_a.occupancy_pct, 3.0, places=1)

    def test_most_booked_movies(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        movies = admin_analytics.get_popular_movies(start_date, end_date)
        self.assertGreater(len(movies), 0)
        top_movie = movies[0]
        self.assertEqual(top_movie['show__movie__title'], "Apex Action")
        self.assertEqual(top_movie['tickets_sold'], 3)
        self.assertEqual(top_movie['total_revenue'], Decimal("600.00"))

    def test_top_theaters(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        theaters = admin_analytics.get_top_theaters(start_date, end_date)
        self.assertGreater(len(theaters), 0)
        top_th = theaters[0]
        self.assertEqual(top_th['show__theater__name'], "Apex Multiplex")
        self.assertEqual(top_th['total_revenue'], Decimal("600.00"))

    def test_peak_booking_hours(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        peak = admin_analytics.get_peak_booking_hours(start_date, end_date)
        self.assertEqual(len(peak['labels']), 24)
        self.assertGreater(len(peak['ranked']), 0)

    def test_cancellation_statistics(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        canc = admin_analytics.get_cancellation_metrics(start_date, end_date)
        self.assertEqual(canc['total_bookings'], 4)
        self.assertEqual(canc['cancelled_bookings'], 1)
        self.assertEqual(canc['cancellation_rate'], 25.0)
        self.assertEqual(canc['cancelled_amount'], Decimal("300.00"))

    def test_refund_statistics(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        refs = admin_analytics.get_refund_metrics(start_date, end_date)
        self.assertEqual(refs['refund_count'], 1)
        self.assertEqual(refs['refund_amount'], Decimal("300.00"))

    def test_user_growth(self):
        start_date = self.now - timedelta(days=1)
        end_date = self.now + timedelta(days=1)
        growth = admin_analytics.get_user_growth(start_date, end_date)
        self.assertGreater(len(growth['labels']), 0)
        self.assertGreaterEqual(growth['total_in_period'], 3)

    def test_today_filter(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard') + '?preset=today')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_preset'], 'today')

    def test_week_filter(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard') + '?preset=this_week')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_preset'], 'this_week')

    def test_month_filter(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard') + '?preset=this_month')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_preset'], 'this_month')

    def test_year_filter(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard') + '?preset=this_year')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_preset'], 'this_year')

    def test_custom_date_range(self):
        self.client.force_login(self.staff_user)
        start = (self.now - timedelta(days=5)).strftime("%Y-%m-%d")
        end = self.now.strftime("%Y-%m-%d")
        res = self.client.get(f"{reverse('admin_dashboard')}?preset=custom&start_date={start}&end_date={end}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_preset'], 'custom')
        self.assertIsNone(res.context['date_error'])

    def test_invalid_date_range(self):
        self.client.force_login(self.staff_user)
        start = self.now.strftime("%Y-%m-%d")
        end = (self.now - timedelta(days=5)).strftime("%Y-%m-%d")
        res = self.client.get(f"{reverse('admin_dashboard')}?preset=custom&start_date={start}&end_date={end}")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.context['date_error'])
        self.assertIn("Start date cannot be after end date", res.context['date_error'])

    def test_csv_export_headers(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard_export') + '?preset=this_year')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get('Content-Type'), 'text/csv')
        self.assertIn('attachment; filename="cineverse_bookings_', res.get('Content-Disposition'))

    def test_csv_export_content(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard_export') + '?preset=this_year')
        content = "".join([chunk.decode('utf-8') for chunk in res.streaming_content])
        self.assertIn("Booking Reference,User,Movie,Theater,City,Show Date,Show Time,Seats,Seat Count,Total Amount (INR),Payment Status,Booking Status,Created At", content)
        self.assertIn("BK-TEST-001", content)
        self.assertIn("Apex Action", content)
        self.assertIn("Apex Multiplex", content)

    def test_csv_streaming_behavior(self):
        self.client.force_login(self.staff_user)
        res = self.client.get(reverse('admin_dashboard_export') + '?preset=this_year')
        self.assertTrue(res.streaming)
        chunks = list(res.streaming_content)
        self.assertGreater(len(chunks), 1)

    def test_query_count(self):
        self.client.force_login(self.staff_user)
        # Dashboard query efficiency assertion
        with self.assertNumQueries(15):
            response = self.client.get(reverse('admin_dashboard') + '?preset=this_year')
            self.assertEqual(response.status_code, 200)

    def test_index_and_migration_correctness(self):
        booking_indexes = [idx.name for idx in Booking._meta.indexes]
        self.assertIn('booking_date_status_idx', booking_indexes)
        self.assertIn('booking_payment_status_idx', booking_indexes)
        
        payment_indexes = [idx.name for idx in Payment._meta.indexes]
        self.assertIn('payment_status_created_idx', payment_indexes)
        self.assertIn('payment_refund_idx', payment_indexes)

        show_indexes = [idx.name for idx in Show._meta.indexes]
        self.assertIn('show_date_theater_idx', show_indexes)

    def test_large_dataset_simulation(self):
        curr_now = timezone.now()
        bulk_b = []
        for i in range(200):
            bulk_b.append(
                Booking(
                    user=self.normal_user,
                    show=self.show_a,
                    booking_reference=f"BK-SIM-{i:04d}",
                    selected_seats="A1",
                    number_of_seats=1,
                    total_amount=Decimal("200.00"),
                    status='CONFIRMED',
                    payment_status='PAID'
                )
            )
        Booking.objects.bulk_create(bulk_b)
        # Verify large scale query executes cleanly in database
        kpis = admin_analytics.get_dashboard_kpis(curr_now - timedelta(days=1), curr_now + timedelta(minutes=5))
        self.assertGreaterEqual(kpis['total_bookings'], 200)
