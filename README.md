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

### 💳 4. Split-Screen Checkout & Demo Payment Gateway
* **Payment Methods**: Instant Indian UPI (GPay, PhonePe, Paytm, BHIM), Credit/Debit Cards, Net Banking, and Wallets.
* **Demo Payment Failure Mode**: Test failure simulator displaying `⚠ Payment Failed` banner with `[Try Again]` and `[← Back to Seats]` actions without creating unconfirmed bookings.
* **Digital Cinema Ticket Pass**: QR code graphic, booking reference ID (`MMS-XXXXXX`), movie poster, theater details, seat numbers, and print support.

### ⭐ 5. Verified Viewer Reviews & Automatic Rating Summary
* **Authenticity Verification**: Users can ONLY post reviews if they have a confirmed/completed booking for the movie.
* **✓ Verified Viewer Badge**: Automatically assigned to verified ticket holders.
* **Automatic Average Ratings**: Recalculates movie `average_rating` and `total_reviews` instantly on review creation, edit, or deletion.
* **Community Moderation**: Review reporting workflow (`ReviewReport` model) for admin moderation.

### 👑 6. CineVerse Member Gamified Profiles
* **Gamified Tier Levels**: `New Viewer` 🎬, `Movie Explorer` ⭐, `Cinema Fan` 🍿, `Movie Enthusiast` 🔥, `CineVerse Pro` 👑 based on watched movies and reviews.
* **Profile Dashboard**: User stats grid, active booking history, review management, and avatar badge.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.11+, Django 5.x
* **Database**: SQLite3 (Development / Production ready)
* **Frontend**: HTML5, CSS3 (Aurora Glass Cinema Design System), JavaScript ES6, Bootstrap 5, FontAwesome 6
* **Deployment & WSGI**: Gunicorn, WhiteNoise, Vercel Serverless

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
```

### Step 4: Run Database Migrations & System Check
```powershell
python manage.py migrate
python manage.py check
```

### Step 5: Run Automated Tests
```powershell
python manage.py test tests
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
   git commit -m "Initial commit of CineVerse application"
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

### Deploying to Vercel via GitHub Integration:
1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New** → **Project**.
3. Import your GitHub repository.
4. Framework Preset: Select **Other** (Vercel automatically detects `vercel.json`).
5. Expand **Environment Variables** and enter the required key-value pairs (do NOT paste raw `.env` content into PowerShell):

| Environment Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `DEBUG` | `False` | Disables debug mode in production |
| `SECRET_KEY` | `replace-with-a-random-secure-secret-key` | Unique production secret key |
| `ALLOWED_HOSTS` | `.vercel.app,127.0.0.1,localhost` | Allowed domain hosts |

6. Click **Deploy**. Vercel will build and launch your application at `https://your-project.vercel.app`.

---

## 🧪 Automated Testing Command

Run the full automated test suite at any time to verify application integrity:

```powershell
python manage.py test tests
```

Output: `Ran 8 tests — OK`
