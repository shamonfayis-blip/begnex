import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from admin_panel.admin_category.models import Category
from admin_panel.admin_product.models import Product, ProductVariant, Review, Coupon


def shop_view(request):
    search_query = request.GET.get("q", "").strip()
    
   
    category_filters = request.GET.getlist("category")
    category_filters = [c.strip() for c in category_filters if c.strip()]
    
    sort = request.GET.get("sort", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    products = Product.objects.filter(
        is_deleted=False,
        is_active=True,
        category__is_deleted=False,
        category__is_active=True,
    )

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(material__icontains=search_query)
        )

    if category_filters:
        products = products.filter(category_id__in=category_filters)

    
    products = products.annotate(
        computed_min_price=Min( "variants__price",filter=Q(variants__is_active=True, variants__is_deleted=False)
        )
    )

    if min_price:
        try:
            products = products.filter(computed_min_price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(computed_min_price__lte=float(max_price))
        except ValueError:
            pass

    if sort == "a_z":
        products = products.order_by("name")
    elif sort == "z_a":
        products = products.order_by("-name")
    elif sort == "price_low":
        products = products.order_by("computed_min_price")
    elif sort == "price_high":
        products = products.order_by("-computed_min_price")
    else:
        products = products.order_by("-id")

    categories = Category.objects.filter(is_deleted=False, is_active=True)

    paginator = Paginator(products, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    has_filters = bool(search_query or category_filters or min_price or max_price or sort)

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "category_filters": category_filters,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "has_filters": has_filters,
    }

    return render(request, "shop.html", context)


def product_detail_view(request, product_id):
    
    product = Product.objects.filter(id=product_id, is_deleted=False, is_active=True, category__is_deleted=False, category__is_active=True).first()
    if not product:
        messages.error(request, "Sorry, this product is currently unavailable or out of stock.")
        return redirect('shop')

    variants = ProductVariant.objects.filter(
        product=product, is_deleted=False, is_active=True
    ).prefetch_related("images")

    default_variant = variants.filter(is_default=True).first()
    if not default_variant:
        default_variant = variants.first()

   
    variants_data = []
    for v in variants:
        parts = v.name.split("/")
        color = parts[0].strip() if parts else ""
        size = parts[1].strip() if len(parts) > 1 else ""
        images = [
            {"url": img.image.url, "is_primary": img.is_primary}
            for img in v.images.all()
        ]
        variants_data.append(
            {
                "id": v.id,
                "name": v.name,
                "color": color,
                "size": size,
                "sku": v.sku,
                "price": str(v.price),
                "stock": v.stock,
                "is_default": v.is_default,
                "images": images,
            }
        )

    
    related_products = Product.objects.filter(
        category=product.category, is_deleted=False, is_active=True
    ).exclude(id=product.id).order_by("-id")[:4]

  
    now = timezone.now()
    active_coupons = Coupon.objects.filter(
        is_active=True
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))

    reviews = product.reviews.all().order_by("-created_at")

    context = {
        "product": product,
        "variants": variants,
        "default_variant": default_variant,
        "variants_data": variants_data,
        "related_products": related_products,
        "active_coupons": active_coupons,
        "reviews": reviews,
    }

    return render(request, "product_detail.html", context)



