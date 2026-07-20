import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from admin_panel.admin_product.models import ProductVariant
from user.wishlist.models import Wishlist

from .models import Cart, CartItem

MAX_CART_QUANTITY = 5


def get_or_create_cart(request):

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    else:
        if not request.session.session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(session_id=request.session.session_key)
        return cart


@ensure_csrf_cookie
def cart_view(request):
    cart = get_or_create_cart(request)
    items = (
        cart.items.select_related(
            "variant", "variant__product", "variant__product__category"
        )
        .prefetch_related("variant__images")
        .order_by("created_at")
    )

    has_out_of_stock = False
    valid_items = []

    for item in items:
        v = item.variant

        is_blocked = (
            v.is_deleted
            or not v.is_active
            or v.product.is_deleted
            or not v.product.is_active
            or v.product.category.is_deleted
            or not v.product.category.is_active
        )

        is_out_of_stock = (not is_blocked) and (v.stock == 0)

        is_low_stock = (
            (not is_blocked) and (not is_out_of_stock) and (v.stock < item.quantity)
        )

        item.is_blocked = is_blocked
        item.is_out_of_stock = is_out_of_stock
        item.is_low_stock = is_low_stock
        item.max_allowed = min(MAX_CART_QUANTITY, v.stock) if not is_blocked else 0
        item.stock_remaining = v.stock

        if is_blocked or is_out_of_stock or is_low_stock:
            has_out_of_stock = True

        valid_items.append(item)

    subtotal = sum(
        item.get_subtotal()
        for item in valid_items
        if not item.is_blocked and not item.is_out_of_stock
    )

    context = {
        "cart": cart,
        "items": valid_items,
        "total_price": subtotal,
        "has_out_of_stock": has_out_of_stock,
        "MAX_CART_QUANTITY": MAX_CART_QUANTITY,
    }
    return render(request, "cart.html", context)


@require_POST
def add_to_cart_api(request):

    try:
        data = json.loads(request.body)
        variant_id = data.get("variant_id")
        quantity = int(data.get("quantity", 1))
        if quantity < 1:
            raise ValueError
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "message": "Invalid request data."}, status=400
        )

    variant = get_object_or_404(ProductVariant, id=variant_id)

    if (
        variant.is_deleted
        or not variant.is_active
        or variant.product.is_deleted
        or not variant.product.is_active
        or variant.product.category.is_deleted
        or not variant.product.category.is_active
    ):
        return JsonResponse(
            {"success": False, "message": "This product is currently unavailable."},
            status=400,
        )

    if variant.stock == 0:
        return JsonResponse(
            {"success": False, "message": "This product is out of stock."},
            status=400,
        )

    if variant.stock < quantity:
        return JsonResponse(
            {
                "success": False,
                "message": f"Only {variant.stock} item(s) available in stock.",
            },
            status=400,
        )

    cart = get_or_create_cart(request)

    item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
    new_quantity = quantity if created else item.quantity + quantity

    max_allowed = min(MAX_CART_QUANTITY, variant.stock)

    if new_quantity > max_allowed:
        if created:
            
            item.delete()
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Maximum allowed quantity ({max_allowed}) reached.",
                },
                status=400,
            )
        
        if item.quantity >= max_allowed:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Maximum allowed quantity ({max_allowed}) reached.",
                },
                status=400,
            )
        new_quantity = max_allowed

    item.quantity = new_quantity
    item.save()

    wishlist_removed = False
    wishlist_count = 0
    if request.user.is_authenticated:
        deleted_count, _ = Wishlist.objects.filter(
            user=request.user, product=variant.product
        ).delete()
        wishlist_removed = deleted_count > 0
        wishlist_count = Wishlist.objects.filter(user=request.user).count()

    return JsonResponse(
        {
            "success": True,
            "message": "Added to cart!",
            "cart_item_count": cart.items.count(),
            "wishlist_removed": wishlist_removed,
            "wishlist_count": wishlist_count,
        }
    )


@require_POST
def update_cart_api(request):

    try:
        data = json.loads(request.body)
        item_id = data.get("item_id")
        action = data.get("action")
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "message": "Invalid request data."}, status=400
        )

    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    variant = item.variant

    if action == "increment":

        if variant.stock == 0:
            return JsonResponse(
                {"success": False, "message": "This item is out of stock."},
                status=400,
            )

        max_allowed = min(MAX_CART_QUANTITY, variant.stock)
        if item.quantity >= max_allowed:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Maximum of {max_allowed} units allowed.",
                },
                status=400,
            )
        item.quantity += 1
        item.save()

    elif action == "decrement":
        if item.quantity <= 1:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Minimum quantity is 1. Use ✕ to remove.",
                },
                status=400,
            )
        item.quantity -= 1
        item.save()

    else:
        return JsonResponse(
            {"success": False, "message": "Invalid action."}, status=400
        )

    return JsonResponse(
        {
            "success": True,
            "new_quantity": item.quantity,
            "item_subtotal": str(item.get_subtotal()),
            "cart_total_price": str(cart.get_total_price()),
            "cart_item_count": cart.items.count(),
            "max_allowed": min(MAX_CART_QUANTITY, variant.stock),
        }
    )


@require_POST
def remove_cart_api(request):

    try:
        data = json.loads(request.body)
        item_id = data.get("item_id")
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "message": "Invalid request data."}, status=400
        )

    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Item removed from cart.",
            "cart_total_price": str(cart.get_total_price()),
            "cart_item_count": cart.items.count(),
        }
    )
