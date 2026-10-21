import hmac
import hashlib
import uuid
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import razorpay  # type: ignore
except ImportError:
    razorpay = None


class RazorpayService:
    """
    Service class handling Razorpay Order Creation, Payment Signature Verification,
    and Webhook Signature Verification.
    """

    @classmethod
    def get_client(cls):
        if razorpay and hasattr(settings, 'RAZORPAY_KEY_ID') and hasattr(settings, 'RAZORPAY_KEY_SECRET'):
            return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        return None

    @classmethod
    def create_order(cls, booking, total_amount_inr, currency='INR'):
        """
        Creates a Razorpay order for the booking with exact server-side amount in paise.
        """
        amount_in_paise = int((Decimal(str(total_amount_inr)) * Decimal('100')).quantize(Decimal('1')))
        receipt_id = booking.booking_reference

        client = cls.get_client()
        demo_mode = getattr(settings, 'RAZORPAY_DEMO_MODE', False)

        logger.info(
            f"[RAZORPAY] Order creation initiated | Booking: {receipt_id} | "
            f"Amount INR: {total_amount_inr} | Amount Paise: {amount_in_paise} | Demo Mode: {demo_mode}"
        )

        if client and not demo_mode:
            try:
                order_data = {
                    'amount': amount_in_paise,
                    'currency': currency,
                    'receipt': receipt_id,
                    'notes': {
                        'booking_reference': booking.booking_reference,
                        'movie_title': booking.show.movie.title,
                        'user_id': str(booking.user_id),
                        'seats': booking.selected_seats,
                    }
                }
                order = client.order.create(data=order_data)
                logger.info(f"[RAZORPAY] Real API order created | Order ID: {order.get('id')} | Receipt: {receipt_id}")
                return order
            except Exception as e:
                logger.warning(
                    f"[RAZORPAY] API order creation failed (Exception: {type(e).__name__}, Message: {e}) | "
                    f"Falling back to local test order representation"
                )

        # Fallback / Demo order
        order_id = f"order_{receipt_id}_{uuid.uuid4().hex[:8]}"
        logger.info(f"[RAZORPAY] Test/Demo order generated | Order ID: {order_id} | Receipt: {receipt_id}")
        return {
            'id': order_id,
            'entity': 'order',
            'amount': amount_in_paise,
            'amount_paid': 0,
            'amount_due': amount_in_paise,
            'currency': currency,
            'receipt': receipt_id,
            'status': 'created',
            'attempts': 0,
            'notes': {
                'booking_reference': booking.booking_reference,
                'movie_title': booking.show.movie.title,
            }
        }

    @classmethod
    def generate_test_signature(cls, razorpay_order_id, razorpay_payment_id):
        """
        Helper utility to generate a valid HMAC signature in TEST / Demo mode.
        """
        secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        return hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

    @classmethod
    def verify_payment_signature(cls, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """
        Cryptographically validates the Razorpay signature sent by client or callback.
        Never trust client input without verification.
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            logger.warning(
                f"[RAZORPAY] Verification missing required parameters | "
                f"Order: {razorpay_order_id} | Payment: {razorpay_payment_id} | Has Sig: {bool(razorpay_signature)}"
            )
            return False

        secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

        # 1. Direct HMAC-SHA256 calculation
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        expected_sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        if hmac.compare_digest(expected_sig, str(razorpay_signature).strip()):
            logger.info(f"[RAZORPAY] Direct HMAC-SHA256 signature verification SUCCEEDED | Order: {razorpay_order_id} | Payment: {razorpay_payment_id}")
            return True

        # 2. Razorpay SDK utility check as fallback if available
        client = cls.get_client()
        if client:
            try:
                client.utility.verify_payment_signature({
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature
                })
                logger.info(f"[RAZORPAY] Razorpay SDK utility verification SUCCEEDED | Order: {razorpay_order_id} | Payment: {razorpay_payment_id}")
                return True
            except Exception as e:
                logger.warning(
                    f"[RAZORPAY] Razorpay SDK utility verification failed (Exception: {type(e).__name__}) | "
                    f"Order: {razorpay_order_id} | Payment: {razorpay_payment_id}"
                )
                return False

        logger.warning(f"[RAZORPAY] HMAC signature verification FAILED (mismatch) | Order: {razorpay_order_id} | Payment: {razorpay_payment_id}")
        return False

    @classmethod
    def verify_webhook_signature(cls, payload_body, signature_header):
        """
        Validates the webhook signature from the X-Razorpay-Signature header.
        """
        if not payload_body or not signature_header:
            return False

        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        if isinstance(payload_body, str):
            payload_bytes = payload_body.encode('utf-8')
        else:
            payload_bytes = payload_body

        expected_sig = hmac.new(webhook_secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        is_valid = hmac.compare_digest(expected_sig, str(signature_header).strip())
        logger.info(f"[RAZORPAY] Webhook signature verification result: {is_valid}")
        return is_valid
