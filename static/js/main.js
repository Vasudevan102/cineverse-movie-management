/* ============================================================
   CineVerse — Client Interactions, City Persistence & Seat Picker
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ----------------------------------------------------------
    // 1. City Selector & LocalStorage Persistence
    // ----------------------------------------------------------
    const cityButtons = document.querySelectorAll('.select-city-btn');
    const navCityName = document.getElementById('nav-city-name');
    const mobileCityLabels = document.querySelectorAll('.mobile-city-label');
    const citySearchInput = document.getElementById('city-search-input');
    const defaultCity = "Chennai";

    const urlParams = new URLSearchParams(window.location.search);
    let currentCity = urlParams.get('city');

    if (currentCity) {
        localStorage.setItem('cineverse_city', currentCity);
    } else {
        const storedCity = localStorage.getItem('cineverse_city');
        if (storedCity) {
            currentCity = storedCity;
            if (window.location.pathname === '/' && !urlParams.has('city')) {
                const newUrl = new URL(window.location.href);
                newUrl.searchParams.set('city', currentCity);
                window.history.replaceState({}, '', newUrl);
            }
        } else {
            currentCity = defaultCity;
            localStorage.setItem('cineverse_city', defaultCity);
        }
    }

    if (navCityName) {
        navCityName.textContent = currentCity;
    }
    mobileCityLabels.forEach(function (el) {
        el.textContent = currentCity;
    });

    cityButtons.forEach(function (btn) {
        if (btn.getAttribute('data-city').toLowerCase() === currentCity.toLowerCase()) {
            btn.classList.add('active');
        }
    });

    cityButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const selected = this.getAttribute('data-city');
            localStorage.setItem('cineverse_city', selected);
            
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('city', selected);
            window.location.href = currentUrl.toString();
        });
    });

    if (citySearchInput) {
        citySearchInput.addEventListener('input', function () {
            const query = this.value.trim().toLowerCase();
            cityButtons.forEach(function (btn) {
                const cityName = btn.getAttribute('data-city').toLowerCase();
                const parentCol = btn.closest('.col-6, .col-sm-4, .col-md-3');
                if (cityName.includes(query)) {
                    if (parentCol) parentCol.style.display = '';
                } else {
                    if (parentCol) parentCol.style.display = 'none';
                }
            });
        });
    }

    // ----------------------------------------------------------
    // 2. Top Auto-Changing Movie Carousel Handler
    // ----------------------------------------------------------
    const carouselContainer = document.getElementById('heroCarousel');
    const slides = document.querySelectorAll('.hero-carousel-slide');
    const dots = document.querySelectorAll('.hero-carousel-dot');
    const prevBtn = document.querySelector('.hero-carousel-control.prev-btn');
    const nextBtn = document.querySelector('.hero-carousel-control.next-btn');

    if (carouselContainer && slides.length > 1) {
        let currentSlide = 0;
        let slideTimer = null;
        const slideIntervalMs = 6000; // 6 seconds auto change

        function showSlide(index) {
            if (index < 0) index = slides.length - 1;
            if (index >= slides.length) index = 0;
            currentSlide = index;

            slides.forEach((slide, i) => {
                slide.classList.toggle('active', i === currentSlide);
            });

            dots.forEach((dot, i) => {
                dot.classList.toggle('active', i === currentSlide);
            });
        }

        function nextSlide() {
            showSlide(currentSlide + 1);
        }

        function prevSlide() {
            showSlide(currentSlide - 1);
        }

        function startAutoPlay() {
            if (!slideTimer) {
                slideTimer = setInterval(nextSlide, slideIntervalMs);
            }
        }

        function stopAutoPlay() {
            if (slideTimer) {
                clearInterval(slideTimer);
                slideTimer = null;
            }
        }

        // Controls Event Listeners
        if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopAutoPlay(); startAutoPlay(); });
        if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopAutoPlay(); startAutoPlay(); });

        dots.forEach((dot) => {
            dot.addEventListener('click', function () {
                const targetIdx = parseInt(this.getAttribute('data-target-slide'), 10);
                if (!isNaN(targetIdx)) {
                    showSlide(targetIdx);
                    stopAutoPlay();
                    startAutoPlay();
                }
            });
        });

        // Pause on hover (Desktop)
        carouselContainer.addEventListener('mouseenter', stopAutoPlay);
        carouselContainer.addEventListener('mouseleave', startAutoPlay);

        // Touch Swipe (Mobile)
        let touchStartX = 0;
        let touchEndX = 0;

        carouselContainer.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        carouselContainer.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            const diffX = touchEndX - touchStartX;
            if (Math.abs(diffX) > 40) {
                if (diffX < 0) nextSlide();
                else prevSlide();
                stopAutoPlay();
                startAutoPlay();
            }
        }, { passive: true });

        // Keyboard Navigation
        carouselContainer.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') { nextSlide(); stopAutoPlay(); startAutoPlay(); }
            else if (e.key === 'ArrowLeft') { prevSlide(); stopAutoPlay(); startAutoPlay(); }
        });

        // Initialize Auto Play
        startAutoPlay();
    }

    // ----------------------------------------------------------
    // 3. Smart Seat Selection, Live Polling & 2-Minute Hold Timer
    // ----------------------------------------------------------
    const seatButtons = document.querySelectorAll('#visual-seat-grid .seat-btn');
    const visualGrid = document.getElementById('visual-seat-grid');
    const selectedSeatsInput = document.getElementById('selected_seats_input');
    const numberOfSeatsInput = document.getElementById('id_number_of_seats');
    const selectedSeatsDisplay = document.getElementById('selected-seats-display');
    const selectedCountDisplay = document.getElementById('selected-count-display');
    const ticketSubtotalEl = document.getElementById('ticket-subtotal');
    const convenienceFeeEl = document.getElementById('convenience-fee');
    const taxesFeeEl = document.getElementById('taxes-fee');
    const totalPriceDisplay = document.getElementById('total-calculated-price');
    const unitPriceEl = document.getElementById('unit-ticket-price');
    const confirmSeatsBtn = document.getElementById('confirm-seats-btn');

    // Helper: format seconds into MM:SS
    function formatTimer(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    // A. Payment Page 2-Minute Countdown Timer
    const paymentTimerBanner = document.getElementById('payment-timer-banner');
    const paymentCountdownDisplay = document.getElementById('payment-countdown-display');
    if (paymentTimerBanner && paymentCountdownDisplay) {
        let remainingSec = parseInt(paymentTimerBanner.getAttribute('data-remaining'), 10) || 120;
        const redirectUrl = paymentTimerBanner.getAttribute('data-redirect');

        function updatePaymentTimer() {
            if (remainingSec <= 0) {
                paymentCountdownDisplay.textContent = "00:00";
                paymentTimerBanner.classList.remove('border-warning');
                paymentTimerBanner.classList.add('border-danger', 'bg-danger', 'bg-opacity-25');
                const submitBtn = document.querySelector('#payment-gateway-form button[type="submit"]');
                if (submitBtn) submitBtn.disabled = true;
                alert("⚠ Your 2-minute seat reservation has expired. Returning to seat selection.");
                if (redirectUrl) {
                    window.location.href = redirectUrl;
                }
                return;
            }
            paymentCountdownDisplay.textContent = formatTimer(remainingSec);
            remainingSec -= 1;
        }

        updatePaymentTimer();
        setInterval(updatePaymentTimer, 1000);
    }

    // B. Seat Selection Page 2-Minute Timer Banner
    const seatTimerBanner = document.getElementById('reservation-timer-banner');
    const countdownTimerDisplay = document.getElementById('countdown-timer-display');
    if (seatTimerBanner && countdownTimerDisplay) {
        let seatRemainingSec = parseInt(seatTimerBanner.getAttribute('data-remaining'), 10) || 0;
        if (seatRemainingSec > 0) {
            function updateSeatHoldTimer() {
                if (seatRemainingSec <= 0) {
                    countdownTimerDisplay.textContent = "00:00";
                    seatTimerBanner.classList.add('d-none');
                    return;
                }
                countdownTimerDisplay.textContent = formatTimer(seatRemainingSec);
                seatRemainingSec -= 1;
            }
            updateSeatHoldTimer();
            setInterval(updateSeatHoldTimer, 1000);
        }
    }

    // C. Multi-Seat Selection & Live Polling
    if (seatButtons.length > 0 && unitPriceEl) {
        const unitPrice = parseFloat(unitPriceEl.getAttribute('data-price')) || 180;
        const convenienceFee = 30;
        let selectedSeats = [];

        // Check if pre-selected / draft seats exist
        if (selectedSeatsInput && selectedSeatsInput.value.trim() !== '') {
            const preSelectedStr = selectedSeatsInput.value.trim();
            selectedSeats = preSelectedStr.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0 && !s.includes('SEAT'));
            selectedSeats.forEach(seatId => {
                const btn = document.querySelector(`#visual-seat-grid .seat-btn[data-seat-id="${seatId}"]`);
                if (btn && !btn.classList.contains('seat-booked') && !btn.classList.contains('seat-reserved')) {
                    btn.classList.remove('seat-available');
                    btn.classList.add('seat-selected');
                }
            });
            updateCalculations();
        }

        function updateCalculations() {
            const seatCount = selectedSeats.length;
            const subtotal = seatCount * unitPrice;
            const taxes = seatCount > 0 ? (subtotal * 0.18) : 0;
            const grandTotal = seatCount > 0 ? (subtotal + convenienceFee + taxes) : 0;

            if (selectedSeatsInput) selectedSeatsInput.value = selectedSeats.join(', ');
            if (numberOfSeatsInput) numberOfSeatsInput.value = seatCount > 0 ? seatCount : 1;

            if (selectedSeatsDisplay) {
                selectedSeatsDisplay.textContent = seatCount > 0 ? selectedSeats.join(', ') : 'None';
            }
            if (selectedCountDisplay) {
                selectedCountDisplay.textContent = seatCount;
            }

            if (ticketSubtotalEl) ticketSubtotalEl.textContent = '₹' + subtotal.toFixed(0);
            if (convenienceFeeEl) convenienceFeeEl.textContent = seatCount > 0 ? ('₹' + convenienceFee.toFixed(0)) : '₹0';
            if (taxesFeeEl) taxesFeeEl.textContent = seatCount > 0 ? ('₹' + Math.round(taxes)) : '₹0';

            if (totalPriceDisplay) {
                totalPriceDisplay.textContent = '₹' + Math.round(grandTotal);
            }

            if (confirmSeatsBtn) {
                confirmSeatsBtn.disabled = (seatCount === 0 || seatCount > 10);
            }
        }

        // Seat Click Handler
        seatButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (this.classList.contains('seat-booked') || this.classList.contains('seat-reserved')) {
                    return;
                }

                const seatId = this.getAttribute('data-seat-id').toUpperCase();

                if (this.classList.contains('seat-selected')) {
                    // Deselect seat
                    this.classList.remove('seat-selected', 'seat-mine');
                    this.classList.add('seat-available');
                    selectedSeats = selectedSeats.filter(id => id !== seatId);
                } else {
                    // Select seat (limit to 10 max)
                    if (selectedSeats.length >= 10) {
                        alert("You can select a maximum of 10 seats per booking.");
                        return;
                    }
                    this.classList.remove('seat-available');
                    this.classList.add('seat-selected');
                    if (!selectedSeats.includes(seatId)) {
                        selectedSeats.push(seatId);
                    }
                }

                updateCalculations();
            });
        });

        // D. Live Seat Availability Polling
        if (visualGrid) {
            const pollUrl = visualGrid.getAttribute('data-poll-url');
            if (pollUrl) {
                function pollSeatAvailability() {
                    fetch(pollUrl, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    })
                    .then(res => {
                        if (!res.ok) throw new Error("API response error");
                        return res.json();
                    })
                    .then(data => {
                        if (data && data.seats) {
                            data.seats.forEach(seat => {
                                const btn = document.querySelector(`#visual-seat-grid .seat-btn[data-seat-id="${seat.seat_id}"]`);
                                if (!btn) return;

                                const isPremium = seat.seat_type === 'premium';
                                const premiumBorderClass = isPremium ? 'border-warning' : '';

                                if (seat.status === 'BOOKED') {
                                    btn.className = `seat-btn seat-icon seat-booked ${premiumBorderClass}`;
                                    btn.disabled = true;
                                    if (selectedSeats.includes(seat.seat_id)) {
                                        selectedSeats = selectedSeats.filter(s => s !== seat.seat_id);
                                        updateCalculations();
                                    }
                                } else if (seat.status === 'RESERVED') {
                                    if (seat.reserved_by_current_user) {
                                        // Reserved by the active logged-in user
                                        btn.className = `seat-btn seat-icon seat-selected seat-mine ${premiumBorderClass}`;
                                        btn.disabled = false;
                                        if (!selectedSeats.includes(seat.seat_id)) {
                                            selectedSeats.push(seat.seat_id);
                                            updateCalculations();
                                        }
                                    } else {
                                        // Reserved by someone else
                                        btn.className = `seat-btn seat-icon seat-reserved ${premiumBorderClass}`;
                                        btn.disabled = true;
                                        if (selectedSeats.includes(seat.seat_id)) {
                                            selectedSeats = selectedSeats.filter(s => s !== seat.seat_id);
                                            updateCalculations();
                                        }
                                    }
                                } else {
                                    // AVAILABLE
                                    if (selectedSeats.includes(seat.seat_id)) {
                                        btn.className = `seat-btn seat-icon seat-selected ${premiumBorderClass}`;
                                        btn.disabled = false;
                                    } else {
                                        btn.className = `seat-btn seat-icon seat-available ${premiumBorderClass}`;
                                        btn.disabled = false;
                                    }
                                }
                            });

                            // Dynamically update available count & occupancy if present
                            const availEl = document.getElementById('available-seats-display');
                            if (availEl && data.available_count !== undefined) {
                                availEl.textContent = data.available_count;
                            }
                            const bookedEl = document.getElementById('booked-seats-display');
                            if (bookedEl && data.booked_count !== undefined) {
                                bookedEl.textContent = data.booked_count;
                            }
                        }
                    })
                    .catch(() => {
                        // Silent catch on network blip
                    });
                }

                // Poll every 3.5 seconds
                setInterval(pollSeatAvailability, 3500);
            }
        }
    }


    // ----------------------------------------------------------
    // 3. Auto-dismiss Flash Alerts
    // ----------------------------------------------------------
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                if (bsAlert) bsAlert.close();
            } catch (e) { /* silent catch */ }
        }, 5000);
    });

    // ----------------------------------------------------------
    // 4. Compact Navbar on Scroll
    // ----------------------------------------------------------
    const navbar = document.querySelector('.navbar-cineverse');
    if (navbar) {
        const scrollThreshold = 40;
        function handleScroll() {
            if (window.scrollY > scrollThreshold) {
                navbar.classList.add('navbar-scrolled');
            } else {
                navbar.classList.remove('navbar-scrolled');
            }
        }
        window.addEventListener('scroll', handleScroll, { passive: true });
        handleScroll();
    }

    // ----------------------------------------------------------
    // 5. Image Fallback Error Handler
    // ----------------------------------------------------------
    document.querySelectorAll('img').forEach(function (img) {
        img.addEventListener('error', function () {
            this.style.display = 'none';
        });
    });

    // ----------------------------------------------------------
    // 6. Dynamic Width Elements Handler (Progress & Rating Bars)
    // ----------------------------------------------------------
    document.querySelectorAll('[data-width]').forEach(function (el) {
        el.style.width = el.getAttribute('data-width');
    });

    // ----------------------------------------------------------
    // 7. Subtle 3D Card Tilt Effect
    // ----------------------------------------------------------
    const tiltCards = document.querySelectorAll('.hero-poster-wrapper, .movie-card-modern');
    tiltCards.forEach(function (card) {
        card.addEventListener('mousemove', function (e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            const rotateX = (-y / rect.height) * 8;
            const rotateY = (x / rect.width) * 8;
            this.style.transform = `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-6px) scale(1.02)`;
        });
        card.addEventListener('mouseleave', function () {
            this.style.transform = '';
        });
    });

});

