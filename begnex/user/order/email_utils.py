"""
Email notification helpers for order cancellation & refund events.
Only fires when the USER cancels an order and a refund is credited to their wallet.
"""

import os
import traceback

from django.conf import settings
from django.core.mail import send_mail


def _from_email():
    return settings.EMAIL_HOST_USER


def _user_display(user):
    full = user.get_full_name()
    return full.strip() if full.strip() else user.username


def _log_email_status(
    event_name, recipient, subject, body, success, error_msg=None, tb=None
):
    try:
        log_path = os.path.join(settings.BASE_DIR, "email_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== {event_name} ===\n")
            f.write(f"Recipient: {recipient}\n")
            f.write(f"Subject: {subject}\n")
            f.write(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}\n")
            f.write(f"EMAIL_HOST: {settings.EMAIL_HOST}\n")
            f.write(f"EMAIL_PORT: {settings.EMAIL_PORT}\n")
            f.write(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}\n")
            if success:
                f.write("Status: SUCCESS\n")
            else:
                f.write(f"Status: FAILED\n")
                f.write(f"Error: {error_msg}\n")
                if tb:
                    f.write(f"Traceback:\n{tb}\n")
            f.write("=" * 40 + "\n\n")
    except Exception:
        pass


def send_order_cancelled_email(user, order, refund_amount):

    recipient = user.email
    if not recipient:
        _log_email_status(
            "FULL ORDER CANCEL",
            "None",
            f"Order #{order.order_id} Cancelled",
            "",
            False,
            "User has no email address",
        )
        return

    name = _user_display(user)
    order_no = order.order_id
    is_paid = refund_amount > 0

    subject = f"Order #{order_no} Cancelled — Begnex"

    if is_paid:
        refund_section = (
            f"\n"
            f"REFUND DETAILS\n"
            f"--------------------------------------\n"
            f"  Refund Amount : ₹{refund_amount:.2f}\n"
            f"  Refunded To   : Your Begnex Wallet\n"
            f"  Status        : Credited Instantly ✓\n\n"
            f"The refund of ₹{refund_amount:.2f} has been added to your\n"
            f"Begnex Wallet balance immediately. You can use it on\n"
            f"your next purchase — no expiry, no hassle.\n"
        )
    else:
        refund_section = (
            f"\nSince this was a Cash on Delivery order, no online\n"
            f"refund is applicable.\n"
        )

    body = (
        f"Hi {name},\n\n"
        f"Your order has been cancelled as requested.\n\n"
        f"ORDER DETAILS\n"
        f"--------------------------------------\n"
        f"  Order ID : #{order_no}\n"
        f"  Status   : Cancelled\n"
        + (f"  Reason   : {order.cancel_reason}\n" if order.cancel_reason else "")
        + f"\n"
        f"{refund_section}\n"
        f"If you have any questions, feel free to contact our support team.\n\n"
        f"Thank you for shopping with Begnex.\n\n"
        f"Warm regards,\n"
        f"Team Begnex\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[recipient],
            fail_silently=False,
        )
        _log_email_status("FULL ORDER CANCEL", recipient, subject, body, True)
    except Exception as e:
        _log_email_status(
            "FULL ORDER CANCEL",
            recipient,
            subject,
            body,
            False,
            str(e),
            traceback.format_exc(),
        )


def send_item_cancelled_email(user, order, item, cancel_qty, refund_amount):

    recipient = user.email
    if not recipient:
        _log_email_status(
            "ITEM CANCEL",
            "None",
            f"Item Cancelled — Order #{order.order_id}",
            "",
            False,
            "User has no email address",
        )
        return

    name = _user_display(user)
    order_no = order.order_id
    is_paid = refund_amount > 0
    unit_label = "unit" if cancel_qty == 1 else "units"

    subject = f"Item Cancellation Confirmed — Order #{order_no} | Begnex"

    if is_paid:
        refund_section = (
            f"\n"
            f"REFUND DETAILS\n"
            f"--------------------------------------\n"
            f"  Refund Amount : ₹{refund_amount:.2f}\n"
            f"  Refunded To   : Your Begnex Wallet\n"
            f"  Status        : Credited Instantly ✓\n\n"
            f"₹{refund_amount:.2f} has been added to your Begnex Wallet\n"
            f"balance right now. You can use it on your next order.\n"
        )
    else:
        refund_section = (
            f"\nSince this was a Cash on Delivery order, no online\n"
            f"refund is applicable for the cancelled item.\n"
        )

    body = (
        f"Hi {name},\n\n"
        f"We've successfully cancelled {cancel_qty} {unit_label} of the\n"
        f"following item from your order.\n\n"
        f"CANCELLED ITEM\n"
        f"--------------------------------------\n"
        f"  Product         : {item.product_name}\n"
        f"  Variant         : {item.variant_name}\n"
        f"  Units Cancelled : {cancel_qty}\n"
        f"  Order ID        : #{order_no}\n"
        + (f"  Reason          : {item.cancel_reason}\n" if item.cancel_reason else "")
        + f"\n"
        f"{refund_section}\n"
        f"The rest of your order remains active and will be\n"
        f"delivered as scheduled.\n\n"
        f"If you have any questions, feel free to contact our support team.\n\n"
        f"Thank you for shopping with Begnex.\n\n"
        f"Warm regards,\n"
        f"Team Begnex\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[recipient],
            fail_silently=False,
        )
        _log_email_status("ITEM CANCEL", recipient, subject, body, True)
    except Exception as e:
        _log_email_status(
            "ITEM CANCEL",
            recipient,
            subject,
            body,
            False,
            str(e),
            traceback.format_exc(),
        )
