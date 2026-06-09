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
from admin_panel.admin_product.models import Coupon
from user.address.models import Address
from user.cart.models import Cart


def generate_unique_order_id():
    """Generates a unique order code like ORD-XXXXXX."""
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        order_id = f"ORD-{code}"
        if not Order.objects.filter(order_id=order_id).exists():
            return order_id


def serialize_addresses(user):
    """Utility to serialize user addresses for JSON responses."""
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
    """Renders the checkout page if cart items are valid."""
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    # Verify if there are any inactive, deleted, or out of stock items in the cart
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
    shipping_charge = 0 if subtotal >= 1000 else 99
    total = subtotal + shipping_charge

    addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-created_at")
    active_coupons = Coupon.objects.filter(is_active=True, valid_until__gte=timezone.now())

    context = {
        "cart": cart,
        "items": cart.items.all(),
        "subtotal": subtotal,
        "shipping_charge": shipping_charge,
        "total": total,
        "addresses": addresses,
        "active_coupons": active_coupons,
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
    """AJAX API to edit an address during checkout."""
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
    """AJAX API to validate and apply a coupon."""
    try:
        data = json.loads(request.body)
        code = data.get("code", "").strip()
    except json.JSONDecodeError:
        code = request.POST.get("code", "").strip()

    if not code:
        return JsonResponse({"success": False, "message": "Please enter a coupon code."})

    coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
    if not coupon:
        return JsonResponse({"success": False, "message": "Invalid coupon code."})

    if coupon.valid_until and coupon.valid_until < timezone.now():
        return JsonResponse({"success": False, "message": "This coupon has expired."})

    return JsonResponse({
        "success": True,
        "code": coupon.code,
        "discount_percentage": coupon.discount_percentage
    })


@login_required(login_url="login")
@require_POST
def place_order(request):
    """Handles order creation and stock deduction for COD payment."""
    address_id = request.POST.get("address_id")
    coupon_code = request.POST.get("coupon_code", "").strip()

    if not address_id:
        messages.error(request, "Please select or add a shipping address.")
        return redirect("checkout_page")

    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    # Verify stock and active state of items again under atomic transaction
    try:
        with transaction.atomic():
            cart_items = list(cart.items.select_related('variant', 'variant__product').all())
            for item in cart_items:
                # Active verification
                is_active = (
                    item.variant.is_active
                    and not item.variant.is_deleted
                    and item.variant.product.is_active
                    and not item.variant.product.is_deleted
                )
                if not is_active:
                    raise ValueError(f"Product '{item.variant.product.name}' is no longer available.")
                # Stock verification
                if item.variant.stock < item.quantity:
                    raise ValueError(f"Insufficient stock for '{item.variant.product.name} ({item.variant.name})'. Only {item.variant.stock} left.")

            # Calculate price summaries
            subtotal = cart.get_total_price()
            shipping_charge = 0 if subtotal >= 1000 else 99
            discount = 0

            if coupon_code:
                coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
                if coupon and (not coupon.valid_until or coupon.valid_until >= timezone.now()):
                    discount = (subtotal * coupon.discount_percentage) / 100

            total = subtotal + shipping_charge - discount
            total = max(0, total)

            # Generate unique order id
            order_id = generate_unique_order_id()

            # Construct full address string
            addr_lines = [address.address_line_1]
            if address.address_line_2:
                addr_lines.append(address.address_line_2)

            # Create the main Order object
            order = Order.objects.create(
                order_id=order_id,
                user=request.user,
                status="pending",
                payment_method="cod",
                payment_status="unpaid",
                full_name=address.name,
                phone=address.phone_number,
                address_line="\n".join(addr_lines),
                city=address.city,
                state=address.state,
                pincode=address.pincode,
                subtotal=subtotal,
                discount=discount,
                shipping_charge=shipping_charge,
                total=total
            )

            # Create OrderItems and deduct stock
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
                    unit_price=variant.price,
                    subtotal=item.get_subtotal()
                )

            # Clear the cart items
            cart.items.all().delete()

            messages.success(request, f"Order #{order.order_id} placed successfully!")
            return redirect("order_success", order_pk=order.pk)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("checkout_page")
    except Exception as e:
        messages.error(request, f"An error occurred while placing the order: {str(e)}")
        return redirect("checkout_page")


@login_required(login_url="login")
def order_success(request, order_pk):
    """Renders the thank you/success confirmation page."""
    order = get_object_or_404(Order, pk=order_pk, user=request.user)
    return render(request, "checkout/success.html", {"order": order})

