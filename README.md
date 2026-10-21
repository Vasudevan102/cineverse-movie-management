# CineVerse — Aurora Glass Cinema Ticket Booking & Movie Management Platform

A premium, full-stack 2026 cinema entertainment application built with **Python 3.11+**, **Django 5.x**, **Bootstrap 5**, and **Aurora Glass UI/UX**.

Designed with **Aurora Glass Cinema Design System**, dynamic backdrop gradient overlays, 3D tilt interactions, atomic double booking prevention (`select_for_update`), verified viewer review authentication, realistic show pricing (₹180–₹350), and digital ticket generation.

---

## 🌟 Key Features

### 🎬 1. Aurora Glass Homepage & Hero Carousel
* **Dynamic Top Auto Carousel**: 6-second auto rotation with smooth `fade + slide` transitions, desktop hover pause/resume, and mobile touch swipe.
* **Cinematic Artwork Overlay**: 3-point backdrop gradient overlay (dark left `#070B18`, center semi-transparent, dark right `#070B18`) for crisp contrast.
* **Floating 3D Posters & Controls**: Perspective mousemove 3D card tilt, circular glass arrows (`‹` & `›`), and active indicator pills (`● ━━━ ○ ○ ○ ○`).
* **Accessible Skip-Link**: Keyboard-accessible skip link (`.skip-to-main`) hidden offscreen by default and visible on `Tab` focus.

### 🏛️ 2. Multi-City Theater & Showtime Schedules
* **Multi-City Support**: Filter showtimes by Indian cities (`Chennai`, `Coimbatore`, `Madurai`, `Trichy`, `Salem`, `Tirunelveli`, `Bengaluru`, `Hyderabad`, `Kochi`, `Mumbai`, `Delhi`, `Pune`, `Kolkata`).
* **Dynamic Pricing Tiers**: Realistic show pricing strictly validated server-side from database (₹180, ₹200, ₹220, ₹250, ₹280, ₹300, ₹350).
* **Occupancy Visualizers**: Color-coded progress bars with glow indicators (High: Purple/Pink, Medium: Cyan, Low: Green).

### 🎟️ 3. Interactive Seat Map & Double Booking Prevention
* **Seat Map Grid**: Cinema screen curve indicator (`SCREEN THIS WAY`) and seat legend (Available ○, Selected ● with purple glow/cyan outline, Booked ✕, Premium ◆ with gold glow).
* **Real-time Price Calculator**: Computes Subtotal, Convenience Fee (₹30), GST & Taxes (18%), and Grand Total in real-time.
* **Atomic Double Booking Locking**: Uses `@transaction.atomic` and `select_for_update()` row-level locking to prevent two users from double-booking the same seat.
* **Session Draft Persistence**: Preserves seat selections when navigating back (`← Back to Seat Selection`).

### 💳 4. Razorpay Payment Gateway & Complete Booking Management (Task 3)
* **Razorpay Payment Integration**: Full integration supporting UPI (Google Pay, PhonePe, Paytm), Credit/Debit Cards, NetBanking (50+ banks), and Wallets.
* **Server-Side Cryptographic Verification**: Direct HMAC-SHA256 signature verification endpoint (`/booking/payment/verify/`) using `RAZORPAY_KEY_SECRET`.
* **Idempotent Webhook Listener**: Asynchronous `@csrf_exempt` webhook endpoint (`/booking/webhook/razorpay/`) with `X-Razorpay-Signature` validation for `payment.captured`, `order.paid`, `payment.failed`, and `refund.processed` events.
* **Payment State Machine**: Strict state tracking for `Payment` (`PENDING`, `SUCCESS`, `FAILED`, `CANCELLED`, `REFUNDED`) and `Booking` (`PENDING_PAYMENT`, `CONFIRMED`, `CANCELLED`, `COMPLETED`).
* **Transactional Seat Locking**: Concurrency-safe transitions ensuring seats transition from `RESERVED` → `BOOKED` atomically inside `with transaction.atomic():`.
* **Payment Failure & Retry Workflow**: Failed or cancelled checkout attempts preserve active seat reservations within the 2-minute window and permit instant retry.
* **Cancellation & Refund Audit Tracking**: Cancelling confirmed bookings releases seats and generates auditable refund records (`refund_id`, `refund_amount`, `refund_status='PROCESSED'`).
* **Digital Cinema Ticket Pass**: QR code graphic, booking reference ID (`CV-XXXXXXXX`), transaction ID, payment ID, movie poster, theater details, seat numbers, and print support.

### ⭐ 5. Verified Viewer Reviews & Automatic Rating Summary
* **Authenticity Verification**: Users can ONLY post reviews if they have a confirmed/completed booking for the movie.
* **✓ Verified Viewer Badge**: Automatically assigned to verified ticket holders.
* **Automatic Average Ratings**: Recalculates movie `average_rating` and `total_reviews` instantly on review creation, edit, or deletion.
* **Community Moderation**: Review reporting workflow (`ReviewReport` model) for admin moderation.

### 👑 6. CineVerse Member Gamified Profiles
* **Gamified Tier Levels**: `New Viewer` 🎬, `Movie Explorer` ⭐, `Cinema Fan` 🍿, `Movie Enthusiast` 🔥, `CineVerse Pro` 👑 based on watched movies and reviews.
* **Profile Dashboard**: User stats grid, active booking history, payment status badges, review management, and avatar badge.

### 📊 7. Comprehensive Executive Admin Analytics Dashboard (Task 4)
* **Dedicated Executive Admin Portal**: Accessible at `/admin/dashboard/` and restricted to authorized Django staff (`is_staff=True`) and superusers.
* **Real-time Financial Telemetry**: All-time Total Revenue, Daily Revenue (Today), Weekly Revenue (This Week), Monthly Revenue (This Month), Yearly Revenue (This Year), and Period-Filtered Net Revenue.
* **Strict Revenue Integrity**: Computes gross revenue exclusively from successful payments (`Payment.status == 'SUCCESS'`) minus genuinely processed refunds (`Payment.refund_status == 'PROCESSED'`). Pending, cancelled, or failed transactions are excluded.
* **Interactive Data Visualizations**: Chart.js charts for booking velocity trends, 24-hour peak booking hours distribution, auditorium occupancy comparisons, and daily user registration growth.
* **Advanced Date Filtering**: Presets for `Today`, `Yesterday`, `This Week`, `This Month`, `This Year`, and safe `Custom Date Range` validation (`YYYY-MM-DD`).
* **Streaming CSV Export**: High-performance streaming export at `/admin/dashboard/export/` using `StreamingHttpResponse`, chunked queryset iterator (`chunk_size=2000`), and zero-buffer `EchoBuffer` to scale effortlessly to 100,000+ bookings without Python memory spikes.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.11+, Django 5.x / 6.0
* **Payment Gateway**: Razorpay (HMAC-SHA256 Signature Verification, Webhooks, Orders API)
* **Database**: SQLite3 (Development / Production ready)
* **Frontend**: HTML5, CSS3 (Aurora Glass Cinema Design System), JavaScript ES6, Bootstrap 5, FontAwesome 6
* **Deployment & WSGI**: Gunicorn, WhiteNoise, Vercel Serverless

---

## 🔑 Environment Variables & Payment Configuration

Configure the following environment variables in your `.env` file or hosting provider dashboard:

| Environment Variable | Default / Recommended Value | Description |
| :--- | :--- | :--- |
| `DEBUG` | `True` (Dev) / `False` (Prod) | Enables or disables debug mode |
| `SECRET_KEY` | `django-insecure-local-dev-key` | Django application cryptographic secret |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost,.vercel.app` | Host domain whitelist |
| `RAZORPAY_KEY_ID` | `rzp_test_cineverse_key` | Razorpay public key ID |
| `RAZORPAY_KEY_SECRET` | `cineverse_razorpay_secret_key` | Razorpay private key secret (Keep secret!) |
| `RAZORPAY_WEBHOOK_SECRET` | `cineverse_webhook_secret_key` | Razorpay webhook verification secret |
| `PAYMENT_GATEWAY_MODE` | `TEST` (Options: `LIVE`, `TEST`, `DEMO`) | Operational mode for payment flows |
| `RAZORPAY_DEMO_MODE` | `False` (Options: `True`, `False`) | Explicit flag for simulated demo fallback |

---

## 💻 Local Windows Setup (PowerShell Guide)

> [!IMPORTANT]
> **CRITICAL FOR POWERSHELL USERS**:
> **DO NOT** paste `.env` key-value pairs (such as `DEBUG=False` or `SECRET_KEY=...`) directly into your PowerShell terminal prompt! Doing so will cause a PowerShell `ParserError`.
> Environment variables must be placed inside a `.env` file using a text editor (like VS Code) or configured in your hosting platform's Environment Variables dashboard.

### Step 1: Open PowerShell & Create Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Create Local `.env` File
Create an empty `.env` file in PowerShell:
```powershell
New-Item .env -ItemType File
```
Then open `.env` in VS Code (`code .env`) or Notepad and enter the following settings:
```ini
DEBUG=True
SECRET_KEY=django-insecure-local-dev-key
ALLOWED_HOSTS=127.0.0.1,localhost
RAZORPAY_KEY_ID=rzp_test_cineverse_key
RAZORPAY_KEY_SECRET=cineverse_razorpay_secret_key
RAZORPAY_WEBHOOK_SECRET=cineverse_webhook_secret_key
PAYMENT_GATEWAY_MODE=TEST
```

### Step 4: Run Database Migrations & System Check
```powershell
python manage.py migrate
python manage.py check
```

### Step 5: Run Automated Tests
```powershell
python manage.py test
```

### Step 6: Start Local Development Server
```powershell
python manage.py runserver
```
Open `http://127.0.0.1:8000/` in your web browser.

---

## 🐙 GitHub Setup

1. Initialize Git repository locally (if not already initialized):
   ```powershell
   git init
   git add .
   git commit -m "feat: complete Task 3 Razorpay payment workflow and booking management"
   ```
2. Create a new repository on GitHub.
3. Push local codebase to GitHub:
   ```powershell
   git remote add origin https://github.com/your-username/your-repository-name.git
   git branch -M main
   git push -u origin main
   ```

---

## 🌐 Vercel Deployment Guide

CineVerse is configured for Vercel deployment using Vercel Python Serverless (`@vercel/python`) via `vercel.json` and `movie_management/wsgi.py`.

> [!WARNING]
> **DATABASE CONSIDERATIONS FOR VERCEL**:
> Vercel functions are **serverless and ephemeral**. The default `db.sqlite3` database on Vercel is read-only when deployed.
> - **For Demo/Read-Only Hosting on Vercel**: Commit your populated `db.sqlite3` database to GitHub so pre-loaded movies, showtimes, and theaters display seamlessly on Vercel.
> - **For Full Production (Persistent Bookings & Writes)**: Connect a cloud PostgreSQL database (such as Supabase, Neon, or Vercel Postgres) by setting a `DATABASE_URL` environment variable.

---

## 📊 Task 4: Executive Admin Analytics Dashboard

### 1. Dashboard URL & Access Permissions
- **Dashboard Interface**: [`/admin/dashboard/`](http://127.0.0.1:8000/admin/dashboard/)
- **Streaming CSV Export**: [`/admin/dashboard/export/`](http://127.0.0.1:8000/admin/dashboard/export/)
- **Django Admin Console**: [`/admin/`](http://127.0.0.1:8000/admin/)

#### Access Control Rules
- **Protected by `@staff_member_required(login_url='admin:login')`**.
- **Superusers & Staff (`is_staff=True`)**: Full access to analytics dashboard, time-series charts, and streaming CSV export.
- **Anonymous Users**: Automatically denied and redirected (HTTP 302) to Django admin authentication login (`/admin/login/?next=/admin/dashboard/`).
- **Normal Authenticated Users**: Denied access (HTTP 302 redirected to admin login or HTTP 403 Forbidden). No business analytics or financials are exposed through public URLs.

#### How to Create an Admin User
Run the standard Django superuser creation command in PowerShell:
```powershell
python manage.py createsuperuser
```
Follow the interactive prompts:
```
Username: admin
Email address: admin@cineverse.com
Password: **********
Password (again): **********
Superuser created successfully.
```
Then log in at `http://127.0.0.1:8000/admin/login/` and navigate to `/admin/dashboard/`.

---

### 2. Analytics Metric Definitions & Formulas
| Metric | Definition & Computation Formula |
| :--- | :--- |
| **Total Revenue** | All-time lifetime net revenue: `Sum(Payment.total_amount WHERE status='SUCCESS') - Sum(Payment.refund_amount WHERE refund_status='PROCESSED')`. |
| **Daily Revenue** | Net revenue received during current calendar day (`00:00:00` to current time). |
| **Weekly Revenue** | Net revenue from Monday of the current week to current time. |
| **Monthly Revenue** | Net revenue from the 1st day of the current calendar month to current time. |
| **Yearly Revenue** | Net revenue from January 1st of current calendar year to current time. |
| **Period Net Revenue** | Net gateway revenue for the selected date window or preset. |
| **Booking Trends** | Time-series aggregation grouped by `TruncDate('booking_date')` (<= 35 days) or `TruncMonth('booking_date')` (> 35 days) returning total, confirmed, cancelled counts, and revenue. |
| **Theater Occupancy %** | Formula: `(Booked Seats ÷ Available Seat Capacity) × 100`. Uses independent subqueries on `Show.total_seats` and `Booking.number_of_seats` to eliminate Cartesian join bloat. |
| **Most Booked Movies** | Top 10 movies ranked by `tickets_sold` (`Sum(number_of_seats)`) and box office yield. |
| **Top-Performing Theaters**| Top 10 venues ranked by total ticket sales volume and gross revenue. |
| **Peak Booking Hours** | Distribution across 24 hourly buckets computed via SQL engine `ExtractHour('booking_date')`. |
| **Cancellation Statistics**| Total cancelled bookings, cancellation rate (`(cancelled ÷ total) × 100`), post-payment vs draft cancellations, and value lost. |
| **Refund Statistics** | Count and total amount of processed refunds (`Payment.refund_status='PROCESSED'`) and refund rate (`(refund_count ÷ successful_payments) × 100`). |
| **User Growth** | Daily user account registrations aggregated via `TruncDate('date_joined')`. |

---

### 3. Database Indexes Added (Migration `0005`)
To guarantee sub-second execution on high-volume production tables (100,000+ bookings), compound and single-column indexes were added in `booking/migrations/0005_booking_booking_date_status_idx_and_more.py`:
- `Booking`:
  - `booking_date_status_idx`: `Index(fields=['booking_date', 'status'])` — accelerates date-range slicing with status filtering.
  - `booking_payment_status_idx`: `Index(fields=['payment_status'])` — speeds payment condition checks.
  - `booking_status_idx`: `Index(fields=['status'])` — optimizes cancellation and confirmation counts.
- `Payment`:
  - `payment_status_created_idx`: `Index(fields=['status', 'created_at'])` — optimizes multi-period revenue sums.
  - `payment_refund_idx`: `Index(fields=['refund_status', 'refunded_at'])` — speeds refund tracking aggregations.
- `Show`:
  - `show_date_theater_idx`: `Index(fields=['show_date', 'theater'])` — optimizes theater capacity subqueries.

---

### 4. ORM Optimization Techniques
- **Zero Python Row Loops**: All metrics are aggregated inside the database engine using `Sum`, `Count`, `Avg`, `Coalesce`, and `Case(When(...))`.
- **Single-Query Multi-Period Aggregation**: `get_revenue_metrics()` executes 1 single SQL query to simultaneously extract Today, This Week, This Month, This Year, All-Time, and Custom Filtered totals using conditional `filter=Q(...)` inside `Sum()`.
- **Cartesian Join Prevention**: Theater occupancy calculation uses independent correlated `Subquery` expressions rather than multi-table joins, preventing row multiplications.
- **Selective Query Pre-fetching**: For CSV exports, `select_related('user', 'show__movie', 'show__theater')` is used to load all foreign key relations in a single join, eliminating N+1 query loops.
- **Fixed Query Ceiling**: The entire dashboard renders in **<= 15 database queries** regardless of whether there are 100 or 100,000 bookings in the database.

---

### 5. Memory-Efficient Streaming CSV Export
- **Route**: `/admin/dashboard/export/?preset=this_month`
- **Architecture**: Utilizes Django's `StreamingHttpResponse` coupled with an `EchoBuffer` pseudo file interface and `QuerySet.iterator(chunk_size=2000)`.
- **Memory Footprint**: Memory consumption remains constant (`O(1)` memory overhead) because rows are fetched in 2,000-row database cursor batches and streamed immediately over the HTTP response stream rather than accumulating in Python RAM.

---

### 6. Responsive Viewport Adaptations
The dashboard is styled using the CineVerse Aurora Glass design system and optimized with custom CSS media queries for all required viewports:
- **375px & 390px (Mobile)**: Compact KPI cards, stacked filter controls, full-width date inputs, 230px–250px chart heights, and horizontally scrollable tables.
- **768px (Tablet)**: 2-column KPI grid with balanced gutters and touch padding.
- **1024px (Laptop / Tablet Landscape)**: Optimized grid columns and 300px chart heights.
- **1440px+ (Large Desktop / Ultra-wide)**: Expanded container width, 350px chart heights, and enhanced glassmorphic backdrop elevations.

---

---

## 🔍 Task 5: Movie Discovery with Search, Filters & Personalized Recommendations

### 1. Overview & Discovery Architecture
The Movie Discovery module (`/movies/`) offers a cinema discovery hub with multi-facet cumulative filtering, title search, dynamic matching movie counts, deterministic personalized recommendations, and high-performance ORM optimization.

### 2. URL & Query Parameter Specifications
All discovery states can be bookmarked and shared via standard GET parameters:
| Parameter | Description | Supported Values / Format |
| :--- | :--- | :--- |
| `q` | Movie title search (case-insensitive & partial) | String e.g. `?q=avatar` |
| `genre` | Genre filter | Genre slug e.g. `action`, `sci-fi`, `comedy` |
| `language` | Audio language filter | Language code e.g. `en`, `ta`, `hi`, `te` |
| `city` | Cinema city filter | City string e.g. `Chennai`, `Coimbatore`, `Bengaluru` |
| `theater` | Theater venue filter | Theater ID e.g. `1`, `2` (auto-syncs with selected city) |
| `release_date` | Release timing preset | `recent` (last 60 days), `upcoming`, `past_year` |
| `release_from` / `release_to` | Custom release date boundaries | `YYYY-MM-DD` |
| `rating` / `min_rating` | Minimum average rating | `4.5`, `4`, `3`, `2` |
| `show_time` | Show schedule timing window | `morning` (6 AM–12 PM), `afternoon` (12 PM–5 PM), `evening` (5 PM–9 PM), `night` (9 PM–6 AM) |
| `sort` / `sort_by` | Ordering criteria | `popularity` (booking count), `newest` (`-release_date`), `rating` (`-average_rating`), `price_asc` (cheapest ticket first), `price_desc`, `title` (A–Z) |
| `page` | Pagination page number | Integer e.g. `?page=2` (page size: 12) |

### 3. Cumulative Multi-Facet Filters
- **Cumulative Conjunction**: All filters combine via logical AND (`.filter(...)`) to allow complex criteria (e.g. Action + English + Chennai + 4★ Rating + Evening Showtimes).
- **Active Show Verification**: When `city`, `theater`, or `show_time` filters are applied, only movies with active, future show schedules matching the exact criteria are returned.
- **Dynamic Theaters Sync**: Changing the city filter asynchronously fetches matching theaters via `/movies/api/theaters/?city=...`.
- **One-Click Chips Removal**: Active criteria render as interactive badge chips with instant removal links.

### 4. Dynamic Matching Movie Count & APIs
- **Dynamic Count Indicator**: Displayed prominently in the discovery header (`X movies found`) with loading spinner.
- **AJAX Match Count API**: `/movies/api/count/?...` returns JSON `{"count": N}` using `QuerySet.count()` without full-page reloads.
- **AJAX Theaters API**: `/movies/api/theaters/?city=...` returns active venues for the selected city.

### 5. Personalized "Recommended for You" Engine
- **Signal 1: Booking History**: Analyzes confirmed and completed user ticket bookings (`Booking.objects.filter(status__in=['CONFIRMED', 'COMPLETED'])`).
- **Signal 2: Recently Viewed Movies**: Analyzes user exploration behavior tracked in `MovieView` (for logged-in users) and session history (for guests).
- **Ranking Formula**:
  1. Extract preferred genre IDs and language IDs from interaction seeds.
  2. Candidate pool: active movies excluding already-booked titles.
  3. Ranked by: `genre_score` (number of shared genres) → `lang_match` (language alignment) → `booking_count` (popularity) → `average_rating` → `release_date`.
  4. Cold-Start / Backfill: Gracefully backfills with trending and top-rated movies for new visitors or users with low activity.

### 6. Lightweight Recently Viewed Movie Tracking
- **Authenticated Users**: Persisted to `MovieView` model with unique constraint `('user', 'movie')` and composite index `Index(fields=['user', '-viewed_at'])`. Automatically capped to the 20 most recent entries per user.
- **Anonymous Users**: Stored in `request.session['recently_viewed_movies']` with a 20-entry FIFO limit.

### 7. Database Indexing & ORM Performance
- **Indexes Added**:
  - `Movie`: `db_index=True` on `release_date`, `average_rating`, `is_active`, plus compound indexes `['is_active', '-release_date']` and `['is_active', '-average_rating']`.
  - `MovieView`: Compound index `['user', '-viewed_at']`.
  - `Show`: Compound index `['show_date', 'start_time']`.
- **Zero N+1 Queries**: Discovery view employs `select_related('language')`, `prefetch_related('genres', 'images')`, and prefetch-aware property accessors on `Movie.primary_poster` and `Movie.backdrop_url`.
- **Query Count**: The full discovery page renders in **<= 10 database queries** (count, pagination, genres, languages, cities, and recommendations).

---

---

## 🎟️ Task 6: Automated PDF Ticket Generation + Asynchronous Email Confirmation

### 1. Overview & Architecture
Task 6 implements an enterprise-grade automated digital ticket generation and email confirmation engine for CineVerse:
- **Asynchronous & Non-blocking**: Ticket generation and email delivery execute completely out-of-band via **Celery** backed by **Redis**, ensuring the user's payment checkout flow finishes in under 200ms without blocking on PDF rendering or SMTP network latency.
- **Transactional Dispatch**: Uses Django's `transaction.on_commit()` to guarantee that Celery tasks are only queued after the database transaction successfully commits.
- **Fail-Safe Booking State**: If email delivery fails, the booking strictly remains **CONFIRMED** and paid. Failures are logged, tracked in the `Ticket` model, and retried automatically.

```
Payment Success (Razorpay / Gateway)
       │
       ▼
with transaction.atomic():
  • Promote SeatReservation to BOOKED
  • Set Booking.status = CONFIRMED, payment_status = PAID
  • Create Ticket (ticket_number, verification_token)
  • transaction.on_commit(lambda: generate_and_email_ticket_task.delay(booking_id))
       │
       ▼
Celery Worker (Async Task Execution)
  ├── 1. Generate professional PDF with ReportLab & QR code
  ├── 2. Save PDF file to Ticket.pdf_file (media/tickets/pdf/)
  ├── 3. Compose HTML confirmation email with PDF attachment
  └── 4. Send via SMTP with exponential backoff (retries: 60s, 120s, 240s)
```

### 2. Digital Ticket Model (`booking.Ticket`)
A dedicated `Ticket` model linked 1:1 to `Booking` manages digital ticket state:
- `booking`: OneToOneField to `Booking` with cascade deletion.
- `ticket_number`: Unique identifier formatted as `TKT-XXXXXXXXXX`.
- `verification_token`: Cryptographically secure 64-character token (`secrets.token_urlsafe(48)`), uniquely indexed for rapid public QR verification lookups.
- `pdf_file`: FileField storing generated PDF artifacts in `tickets/pdf/`.
- `email_status`: State tracker (`PENDING`, `SENT`, `FAILED`).
- `email_attempts`: Counter tracking delivery attempts (capped at 4 total: 1 initial + 3 retries).
- `last_email_error`: Detailed diagnostic message if delivery encounters SMTP issues.
- `get_verification_url()`: Computes the canonical public verification URL for QR embedding.

### 3. ReportLab PDF Ticket Generator (`booking.pdf_service`)
High-fidelity, printable PDF ticket generated dynamically via **ReportLab**:
- **Design & Typography**: High-contrast modern layout with CineVerse brand header (`#E50914` accent), dark table headers, and clean metadata alignment.
- **Embedded Dynamic QR Code**: Generated via `qrcode` library using error correction level `M`, pointing directly to the ticket's verification URL (`/booking/verify/<token>/`).
- **Comprehensive Details**: Movie title, language, duration, age rating, theater name, auditorium screen, city, formatted show date/time, booked seat numbers, convenience fee, GST breakdown, total amount paid, booking reference, payment ID, and attendee name.
- **Security & Instructions**: Entry policy notice, ID requirement reminder, and cryptographic authenticity hash notice.
- **Strict Idempotency**: Cached PDF files are reused on subsequent requests unless explicit `force=True` regeneration is requested.

### 4. Celery Task & Exponential Backoff (`booking.tasks`)
- **Shared Task**: `@shared_task(bind=True, max_retries=3, default_retry_delay=60)`
- **Exponential Backoff**: Subsequent retries back off exponentially (`countdown = 60 * 2^retries` → 60s, 120s, 240s).
- **Delivery Idempotency**: If `ticket.email_status == 'SENT'`, the task safely skips sending duplicate emails.
- **HTML + Plaintext Template**: Formatted responsive email featuring show details, QR validation link, and PDF attachment.

### 5. Secure Ticket Download & Public QR Verification
- **Authenticated Download Endpoint** (`/booking/ticket/<reference>/download/`):
  - Requires user authentication (`@login_required`).
  - Strict ownership check: Only the booking owner or staff can download the PDF (returns `403 Forbidden` for unauthorized users).
  - On-Demand Fallback: If the PDF hasn't finished asynchronous generation, it is generated synchronously on the fly.
  - Returns `application/pdf` with `Content-Disposition: attachment; filename="CineVerse_Ticket_<ref>.pdf"`.
- **Public QR Verification Endpoint** (`/booking/verify/<token>/`):
  - Accessible without login (used by cinema gate scanners and patrons).
  - Resolves ticket solely by the unguessable 64-character verification token.
  - Displays validation status badge (Valid ✓, Cancelled ✕, Show Completed, or Invalid Token).
  - Shows movie, theater, showtime, and seat details **without exposing sensitive customer PII or card secrets**.

### 6. User Interface Integration
- **Booking Success Page** (`booking_success.html`): Prominent **"Download PDF Ticket"** action button alongside existing "Print Ticket" and "View My Bookings" buttons.
- **My Bookings History** (`my_bookings.html`): Quick **"PDF Ticket"** download button available on all confirmed and paid booking cards.
- **Django Admin**: `TicketAdmin` registration with status filters (`email_status`), search capabilities, and audit timestamps.

### 7. Celery & Email Configuration
Add the following to your `.env` or development settings:
```ini
# Celery & Redis Configuration
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# Email Delivery Configuration (Gmail SMTP or Console Backend)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=CineVerse Cinema <no-reply@cineverse.com>
```

#### Running Celery in Development
```powershell
# 1. Start Redis Server (or via Docker)
docker run -p 6379:6379 redis:alpine

# 2. Start Celery Worker
celery -A movie_management worker -l info -P solo
```

---

## 🧪 Automated Testing Command

Run the comprehensive automated test suite verifying Tasks 1 through 6:

```powershell
# Run Task 6 PDF Ticket & Email test suite (23 tests)
python manage.py test tests.test_ticket_and_email

# Run Task 5 Movie Discovery test suite (31 tests)
python manage.py test tests.test_movie_discovery

# Run all tests across the entire application (98 tests)
python manage.py test tests
```

Output: `Ran 98 tests in ~74s — OK (0 failures)`




