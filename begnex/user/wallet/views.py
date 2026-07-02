import json
from decimal import Decimal

import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .utils import get_user_wallet, refund_to_wallet


@login_required(login_url="login")
def wallet_details(request):
    wallet = get_user_wallet(request.user)
    transactions_list = wallet.transactions.all()

    paginator = Paginator(transactions_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "wallet/wallet_details.html",
        {"wallet": wallet, "transactions": page_obj},
    )


@login_required(login_url="login")
@require_POST
def create_razorpay_order(request):
    try:
        data = json.loads(request.body)
        amount = Decimal(data.get("amount", 0))
    except (ValueError, json.JSONDecodeError):
        amount = Decimal(request.POST.get("amount", 0))

    if amount <= 0:
        return JsonResponse(
            {"success": False, "message": "Amount must be greater than zero."}
        )

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    amount_in_paise = int(amount * 100)

    order_data = {"amount": amount_in_paise, "currency": "INR", "payment_capture": 1}

    try:
        order = client.order.create(data=order_data)
        return JsonResponse(
            {
                "success": True,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": settings.RAZORPAY_KEY_ID,
            }
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": f"Failed to create order: {str(e)}"}
        )


@login_required(login_url="login")
@require_POST
def verify_razorpay_payment(request):
    try:
        data = json.loads(request.body)
        payment_id = data.get("razorpay_payment_id")
        order_id = data.get("razorpay_order_id")
        signature = data.get("razorpay_signature")
        amount = Decimal(data.get("amount", 0))
    except (ValueError, json.JSONDecodeError):
        payment_id = request.POST.get("razorpay_payment_id")
        order_id = request.POST.get("razorpay_order_id")
        signature = request.POST.get("razorpay_signature")
        amount = Decimal(request.POST.get("amount", 0))

    if not all([payment_id, order_id, signature, amount]):
        return JsonResponse(
            {"success": False, "message": "Missing payment parameters."}
        )

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    params_dict = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature,
    }

    try:
        client.utility.verify_payment_signature(params_dict)
        refund_to_wallet(
            request.user,
            amount,
            f"Added money to wallet via Razorpay (Ref: {payment_id})",
        )
        return JsonResponse({"success": True})
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse(
            {"success": False, "message": "Signature verification failed."}
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": f"Verification error: {str(e)}"}
        )
