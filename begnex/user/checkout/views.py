import json
import random
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction

from admin_panel.admin_order.models import Order, OrderItem
from admin_panel.admin_coupon.models import Coupon
from user.address.models import Address
from user.cart.models import Cart
from user.wallet.utils import get_user_wallet
from django.urls import reverse
from django.conf import settings
import razorpay


def generate_unique_order_id():
 
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        order_id = f"ORD-{code}"
        if not Order.objects.filter(order_id=order_id).exists():
            return order_id


def serialize_addresses(user):
   
    addresses = Address.objects.filter(user=user).order_by("-is_default", "-created_at")
    data = []
    for addr in addresses:
        data.append({
            "id": addr.id,
            "name": addr.name,
            "phone_number": addr.phone_number,
            "address_line_1": addr.address_line_1,
            "address_line_2": addr.address_line_2 or "",
            "city": addr.city,
            "state": addr.state,
            "pincode": addr.pincode,
            "country": addr.country,
            "address_type": addr.address_type,
            "is_default": addr.is_default
        })
    return data


@login_required(login_url="login")
def checkout_page(request):
   
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    
    blocked_items = []
    for item in cart.items.all():
        is_inactive = (
            not item.variant.is_active
            or item.variant.is_deleted
            or not item.variant.product.is_active
            or item.variant.product.is_deleted
        )
        is_oos = item.variant.stock < item.quantity
        if is_inactive or is_oos:
            blocked_items.append(item)

    if blocked_items:
        messages.error(request, "Some items in your cart are currently unavailable. Please modify your cart.")
        return redirect("cart")

    subtotal = cart.get_total_price()
    shipping_charge = 0
    total = subtotal + shipping_charge

    addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-created_at")
    today = timezone.now().date()
    active_coupons = Coupon.objects.filter(is_active=True, valid_from__lte=today, valid_until__gte=today)
    wallet = get_user_wallet(request.user)

    context = {
        "cart": cart,
        "items": cart.items.all(),
        "subtotal": subtotal,
        "shipping_charge": shipping_charge,
        "total": total,
        "addresses": addresses,
        "active_coupons": active_coupons,
        "wallet_balance": wallet.balance,
    }
    return render(request, "checkout/checkout.html", context)


@login_required(login_url="login")
@require_POST
def checkout_add_address_api(request):
    """AJAX API to add an address during checkout."""
    name = request.POST.get("name", "").strip()
    phone_number = request.POST.get("phone_number", "").strip()
    address_line_1 = request.POST.get("address_line_1", "").strip()
    address_line_2 = request.POST.get("address_line_2", "").strip()
    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()
    pincode = request.POST.get("pincode", "").strip()
    country = request.POST.get("country", "India").strip()
    address_type = request.POST.get("address_type", "Home").strip()
    is_default = request.POST.get("is_default") in ["on", "true", True]

    if not all([name, phone_number, address_line_1, city, state, pincode]):
        return JsonResponse({"success": False, "message": "All required fields must be filled."})

    try:
        address = Address(
            user=request.user,
            name=name,
            phone_number=phone_number,
            address_line_1=address_line_1,
            address_line_2=address_line_2 or None,
            city=city,
            state=state,
            pincode=pincode,
            country=country,
            address_type=address_type,
            is_default=is_default
        )
        address.save()
        return JsonResponse({"success": True, "addresses": serialize_addresses(request.user)})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required(login_url="login")
@require_POST
def checkout_edit_address_api(request, id):
   
    address = get_object_or_404(Address, id=id, user=request.user)
    name = request.POST.get("name", "").strip()
    phone_number = request.POST.get("phone_number", "").strip()
    address_line_1 = request.POST.get("address_line_1", "").strip()
    address_line_2 = request.POST.get("address_line_2", "").strip()
    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()
    pincode = request.POST.get("pincode", "").strip()
    country = request.POST.get("country", "India").strip()
    address_type = request.POST.get("address_type", "Home").strip()
    is_default = request.POST.get("is_default") in ["on", "true", True]

    if not all([name, phone_number, address_line_1, city, state, pincode]):
        return JsonResponse({"success": False, "message": "All required fields must be filled."})

    try:
        address.name = name
        address.phone_number = phone_number
        address.address_line_1 = address_line_1
        address.address_line_2 = address_line_2 or None
        address.city = city
        address.state = state
        address.pincode = pincode
        address.country = country
        address.address_type = address_type
        address.is_default = is_default
        address.save()
        return JsonResponse({"success": True, "addresses": serialize_addresses(request.user)})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required(login_url="login")
@require_POST
def checkout_apply_coupon_api(request):
    try:
        data = json.loads(request.body)
        code = data.get("code", "").strip()
        cart_subtotal = float(data.get("subtotal", 0) or 0)
    except json.JSONDecodeError:
        code = request.POST.get("code", "").strip()
        cart_subtotal = 0

    if not code:
        return JsonResponse({"success": False, "message": "Please enter a coupon code."})

    today = timezone.now().date()
    coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
    if not coupon:
        return JsonResponse({"success": False, "message": "Invalid or inactive coupon code."})

    if today < coupon.valid_from or today > coupon.valid_until:
        return JsonResponse({"success": False, "message": "This coupon has expired or is not yet active."})

    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return JsonResponse({"success": False, "message": "This coupon has reached its usage limit."})

    if cart_subtotal > 0 and coupon.min_order_amount > 0:
        if float(coupon.min_order_amount) > cart_subtotal:
            return JsonResponse({
                "success": False,
                "message": f"Minimum order amount of \u20b9{coupon.min_order_amount:.0f} required for this coupon."
            })

    
    from decimal import Decimal
    subtotal_dec = Decimal(str(cart_subtotal))
    if coupon.discount_type == "percentage":
        discount = (subtotal_dec * coupon.discount_value) / 100
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
    else:
        discount = min(coupon.discount_value, subtotal_dec)

    return JsonResponse({
        "success": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "discount_amount": float(discount),
        "min_order_amount": float(coupon.min_order_amount),
        "message": f"Coupon applied! You save \u20b9{discount:.2f}"
    })


@login_required(login_url="login")
@require_POST
def place_order(request):
    address_id = request.POST.get("address_id")
    coupon_code = request.POST.get("coupon_code", "").strip()
    payment_method = request.POST.get("payment_method", "cod").strip().lower()

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

    if not address_id:
        if is_ajax:
            return JsonResponse({"success": False, "message": "Please select or add a shipping address."})
        messages.error(request, "Please select or add a shipping address.")
        return redirect("checkout_page")

    if payment_method not in ["cod", "wallet"]:
        if is_ajax:
            return JsonResponse({"success": False, "message": "Please complete the payment via the checkout page for online orders."})
        messages.error(request, "Please complete the payment via the checkout page for online orders.")
        return redirect("checkout_page")

    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        if is_ajax:
            return JsonResponse({"success": False, "message": "Your cart is empty."})
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    try:
        with transaction.atomic():
            cart_items = list(cart.items.select_related('variant', 'variant__product').all())
            for item in cart_items:
                is_active = (
                    item.variant.is_active
                    and not item.variant.is_deleted
                    and item.variant.product.is_active
                    and not item.variant.product.is_deleted
                )
                if not is_active:
                    raise ValueError(f"Product '{item.variant.product.name}' is no longer available.")
                
                if item.variant.stock < item.quantity:
                    raise ValueError(f"Insufficient stock for '{item.variant.product.name} ({item.variant.name})'. Only {item.variant.stock} left.")

            subtotal = cart.get_total_price()
            shipping_charge = 0
            discount = 0

            coupon_obj = None
            if coupon_code:
                today = timezone.now().date()
                coupon_obj = Coupon.objects.filter(
                    code__iexact=coupon_code,
                    is_active=True,
                    valid_from__lte=today,
                    valid_until__gte=today
                ).first()
                if coupon_obj:
                    if coupon_obj.discount_type == "percentage":
                        discount = (subtotal * coupon_obj.discount_value) / 100
                        if coupon_obj.max_discount_amount:
                            discount = min(discount, coupon_obj.max_discount_amount)
                    else:
                        discount = min(coupon_obj.discount_value, subtotal)

            total = subtotal + shipping_charge - discount
            total = max(0, total)

            order_id = generate_unique_order_id()

            if payment_method == "wallet":
                from user.wallet.utils import pay_using_wallet
                try:
                    pay_using_wallet(request.user, total, f"Payment for Order #{order_id}")
                except ValueError as e:
                    raise ValueError(f"Wallet payment failed: {str(e)}")

            addr_lines = [address.address_line_1]
            if address.address_line_2:
                addr_lines.append(address.address_line_2)

            order = Order.objects.create(
                order_id=order_id,
                user=request.user,
                status="pending",
                payment_method=payment_method,
                payment_status="paid" if payment_method == "wallet" else "unpaid",
                full_name=address.name,
                phone=address.phone_number,
                address_line="\n".join(addr_lines),
                city=address.city,
                state=address.state,
                pincode=address.pincode,
                coupon_code=coupon_obj.code if coupon_obj else None,
                coupon_discount=discount if coupon_obj else 0,
                subtotal=subtotal,
                discount=discount,
                shipping_charge=shipping_charge,
                total=total
            )

            for item in cart_items:
                variant = item.variant
                variant.stock -= item.quantity
                variant.save()

                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    sku=variant.sku,
                    quantity=item.quantity,
                    unit_price=variant.get_discounted_price(),
                    subtotal=item.get_subtotal()
                )

            cart.items.all().delete()

            if coupon_obj:
                coupon_obj.used_count += 1
                coupon_obj.save(update_fields=["used_count"])

            if is_ajax:
                from django.urls import reverse
                return JsonResponse({
                    "success": True,
                    "order_id": order.order_id,
                    "amount_display": f"{total:,.2f}",
                    "payment_method": payment_method,
                    "redirect_url": reverse("user_order_detail", kwargs={"order_pk": order.pk})
                })

            messages.success(request, f"Order #{order.order_id} placed successfully!")
            return redirect("user_order_detail", order_pk=order.pk)

    except ValueError as e:
        if is_ajax:
            return JsonResponse({"success": False, "message": str(e)})
        messages.error(request, str(e))
        return redirect("checkout_page")
    except Exception as e:
        if is_ajax:
            return JsonResponse({"success": False, "message": f"An error occurred while placing the order: {str(e)}"})
        messages.error(request, f"An error occurred while placing the order: {str(e)}")
        return redirect("checkout_page")


@login_required(login_url="login")
@require_POST
def initiate_razorpay_payment(request):
    
    address_id = request.POST.get("address_id")
    coupon_code = request.POST.get("coupon_code", "").strip()
    
    if not address_id:
        return JsonResponse({"success": False, "message": "Please select or add a shipping address."})

    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        return JsonResponse({"success": False, "message": "Your cart is empty."})

    try:
       
        cart_items = list(cart.items.select_related('variant', 'variant__product').all())
        for item in cart_items:
            is_active = (
                item.variant.is_active
                and not item.variant.is_deleted
                and item.variant.product.is_active
                and not item.variant.product.is_deleted
            )
            if not is_active:
                return JsonResponse({"success": False, "message": f"Product '{item.variant.product.name}' is no longer available."})
            
            if item.variant.stock < item.quantity:
                return JsonResponse({"success": False, "message": f"Insufficient stock for '{item.variant.product.name} ({item.variant.name})'. Only {item.variant.stock} left."})

        subtotal = cart.get_total_price()
        shipping_charge = 0
        discount = 0

        if coupon_code:
            today = timezone.now().date()
            coupon = Coupon.objects.filter(
                code__iexact=coupon_code,
                is_active=True,
                valid_from__lte=today,
                valid_until__gte=today
            ).first()
            if coupon:
                if coupon.discount_type == "percentage":
                    discount = (subtotal * coupon.discount_value) / 100
                    if coupon.max_discount_amount:
                        discount = min(discount, coupon.max_discount_amount)
                else:
                    discount = min(coupon.discount_value, subtotal)

        total = subtotal + shipping_charge - discount
        total = max(0, total)

       
        receipt_id = f"rcpt_{request.user.id}_{int(timezone.now().timestamp())}"[:40]

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        from decimal import Decimal
        amount_paise = int((total * Decimal('100')).to_integral_value())
        
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_id,
            "payment_capture": 1,
            "notes": {
                "user_id": request.user.id,
                "address_id": address_id,
                "coupon_code": coupon_code
            }
        })

        return JsonResponse({
            "success": True,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order['id'],
            "amount": amount_paise,
            "user_name": request.user.username,
            "user_email": request.user.email,
            "user_phone": address.phone_number,
            "address_id": address_id,
            "coupon_code": coupon_code
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": f"An error occurred while creating payment: {str(e)}"})


@login_required(login_url="login")
@require_POST
def verify_razorpay_payment(request):
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON."})

    payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")
    address_id = data.get("address_id")
    coupon_code = data.get("coupon_code", "").strip()

    if not all([payment_id, razorpay_order_id, signature, address_id]):
        return JsonResponse({"success": False, "message": "Missing payment parameters."})

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }

    try:
        
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({"success": False, "message": "Payment signature verification failed."})
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Verification error: {str(e)}"})

    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        try:
            rz_order = client.order.fetch(razorpay_order_id)
            amount_paid = rz_order['amount'] / 100
            from decimal import Decimal
            from user.wallet.utils import refund_to_wallet
            refund_to_wallet(request.user, Decimal(str(amount_paid)), f"Refund for empty cart payment (Ref: {razorpay_order_id})")
            return JsonResponse({"success": False, "message": "Your cart is empty. Payment has been refunded to your wallet."})
        except Exception:
            return JsonResponse({"success": False, "message": "Your cart is empty. Order could not be created. Please contact support."})

    try:
        with transaction.atomic():
            cart_items = list(cart.items.select_related('variant', 'variant__product').all())
            
           
            for item in cart_items:
                is_active = (
                    item.variant.is_active
                    and not item.variant.is_deleted
                    and item.variant.product.is_active
                    and not item.variant.product.is_deleted
                )
                if not is_active:
                    raise ValueError(f"Product '{item.variant.product.name}' is no longer available.")
                
                if item.variant.stock < item.quantity:
                    raise ValueError(f"Insufficient stock for '{item.variant.product.name} ({item.variant.name})'. Only {item.variant.stock} left.")

            subtotal = cart.get_total_price()
            shipping_charge = 0
            discount = 0

            coupon_obj = None
            if coupon_code:
                today = timezone.now().date()
                coupon_obj = Coupon.objects.filter(
                    code__iexact=coupon_code,
                    is_active=True,
                    valid_from__lte=today,
                    valid_until__gte=today
                ).first()
                if coupon_obj:
                    if coupon_obj.discount_type == "percentage":
                        discount = (subtotal * coupon_obj.discount_value) / 100
                        if coupon_obj.max_discount_amount:
                            discount = min(discount, coupon_obj.max_discount_amount)
                    else:
                        discount = min(coupon_obj.discount_value, subtotal)

            total = subtotal + shipping_charge - discount
            total = max(0, total)

           
            order_id = generate_unique_order_id()

            addr_lines = [address.address_line_1]
            if address.address_line_2:
                addr_lines.append(address.address_line_2)

            
            order = Order.objects.create(
                order_id=order_id,
                user=request.user,
                status="pending",
                payment_method="online",
                payment_status="paid",
                full_name=address.name,
                phone=address.phone_number,
                address_line="\n".join(addr_lines),
                city=address.city,
                state=address.state,
                pincode=address.pincode,
                coupon_code=coupon_obj.code if coupon_obj else None,
                coupon_discount=discount if coupon_obj else 0,
                subtotal=subtotal,
                discount=discount,
                shipping_charge=shipping_charge,
                total=total,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=payment_id,
                razorpay_signature=signature
            )

          
            for item in cart_items:
                variant = item.variant
                variant.stock -= item.quantity
                variant.save()

                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    sku=variant.sku,
                    quantity=item.quantity,
                    unit_price=variant.get_discounted_price(),
                    subtotal=item.get_subtotal()
                )

          
            cart.items.all().delete()

            
            if coupon_obj:
                coupon_obj.used_count += 1
                coupon_obj.save(update_fields=["used_count"])

            messages.success(request, f"Order #{order.order_id} placed successfully!")
            return JsonResponse({
                "success": True,
                "order_id": order.order_id,
                "redirect_url": reverse("user_order_detail", kwargs={"order_pk": order.pk})
            })

    except ValueError as e:
        try:
            rz_order = client.order.fetch(razorpay_order_id)
            amount_paid = rz_order['amount'] / 100
            from decimal import Decimal
            from user.wallet.utils import refund_to_wallet
            refund_to_wallet(request.user, Decimal(str(amount_paid)), f"Refund for failed order: {str(e)}")
            return JsonResponse({"success": False, "message": f"Order failed: {str(e)}. Payment has been refunded to your wallet."})
        except Exception:
            return JsonResponse({"success": False, "message": f"Order failed: {str(e)}. Please contact support with Payment ID: {payment_id}."})
    except Exception as e:
        try:
            rz_order = client.order.fetch(razorpay_order_id)
            amount_paid = rz_order['amount'] / 100
            from decimal import Decimal
            from user.wallet.utils import refund_to_wallet
            refund_to_wallet(request.user, Decimal(str(amount_paid)), f"Refund for failed order: {str(e)}")
            return JsonResponse({"success": False, "message": f"An error occurred: {str(e)}. Payment has been refunded to your wallet."})
        except Exception:
            return JsonResponse({"success": False, "message": f"An error occurred: {str(e)}. Please contact support with Payment ID: {payment_id}."})


@login_required(login_url="login")
@require_POST
def checkout_delete_address_api(request, id):
  
    address = get_object_or_404(Address, id=id, user=request.user)
    try:
        address.delete()
        return JsonResponse({"success": True, "addresses": serialize_addresses(request.user)})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

