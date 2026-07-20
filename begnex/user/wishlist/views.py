import json

from django.contrib.auth.decorators import login_required
from django.db.models import Min, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from admin_panel.admin_product.models import Product

from .models import Wishlist


@login_required(login_url="login")
def wishlist_view(request):

    wishlist_items = (
        Wishlist.objects.filter(
            user=request.user,
            product__is_active=True,
            product__is_deleted=False,
            product__category__is_active=True,
            product__category__is_deleted=False,
        )
        .select_related("product", "product__category", "variant")
        .prefetch_related("product__variants", "variant__images")
    )

    product_ids = wishlist_items.values_list("product_id", flat=True)
    products_with_price = Product.objects.filter(id__in=product_ids).annotate(
        computed_min_price=Min(
            "variants__price",
            filter=Q(variants__is_active=True, variants__is_deleted=False),
        )
    )
    price_map = {p.id: p.computed_min_price for p in products_with_price}

    items = []
    for wi in wishlist_items:
        wi.product.min_price = price_map.get(wi.product.id)

     
        display_variant = wi.variant 
        if not display_variant:
            
            active_variants = [
                v for v in wi.product.variants.all() if v.is_active and not v.is_deleted
            ]
            display_variant = next(
                (v for v in active_variants if v.is_default),
                active_variants[0] if active_variants else None,
            )

        
        if display_variant:
            wi.display_image = (
                display_variant.images.filter(is_primary=True).first()
                or display_variant.images.first()
            )
            wi.product.default_variant_id = display_variant.id
        else:
            wi.display_image = None
            wi.product.default_variant_id = None

        items.append(wi)

    context = {
        "wishlist_items": items,
        "count": len(items),
    }
    return render(request, "wishlist.html", context)


@login_required(login_url="login")
@require_POST
def toggle_wishlist_api(request):

    try:
        data = json.loads(request.body)
        product_id = data.get("product_id")
        variant_id = data.get("variant_id")  # optional
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "message": "Invalid request."}, status=400
        )

    try:
        product = Product.objects.get(id=product_id, is_deleted=False, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse(
            {"success": False, "message": "Product not found."}, status=404
        )

  
    variant = None
    if variant_id:
        from admin_panel.admin_product.models import ProductVariant
        try:
            variant = ProductVariant.objects.get(
                id=variant_id, product=product, is_deleted=False
            )
        except ProductVariant.DoesNotExist:
            pass

    obj, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={"variant": variant},
    )

    if not created:
        if variant and obj.variant != variant:
           
            obj.variant = variant
            obj.save(update_fields=["variant"])
            count = Wishlist.objects.filter(user=request.user).count()
            return JsonResponse(
                {
                    "success": True,
                    "action": "updated",
                    "wishlist_count": count,
                    "message": "Wishlist variant updated.",
                }
            )
        obj.delete()
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse(
            {
                "success": True,
                "action": "removed",
                "wishlist_count": count,
                "message": "Removed from wishlist.",
            }
        )

    count = Wishlist.objects.filter(user=request.user).count()
    return JsonResponse(
        {
            "success": True,
            "action": "added",
            "wishlist_count": count,
            "message": "Added to wishlist.",
        }
    )
