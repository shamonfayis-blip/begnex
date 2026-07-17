from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from admin_panel.admin_category.models import Category
from admin_panel.admin_coupon.models import Coupon
from admin_panel.admin_order.models import Order
from admin_panel.admin_product.models import Product, ProductVariant, Review


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
        computed_min_price=Min(
            "variants__price",
            filter=Q(variants__is_active=True, variants__is_deleted=False),
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

    has_filters = bool(
        search_query or category_filters or min_price or max_price or sort
    )

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


def search_suggestions_view(request):
    from django.http import JsonResponse

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []})

    products = Product.objects.filter(
        is_deleted=False,
        is_active=True,
        category__is_deleted=False,
        category__is_active=True,
    ).filter(
        Q(name__icontains=query)
        | Q(category__name__icontains=query)
        | Q(material__icontains=query)
    )[
        :6
    ]

    results = []
    for product in products:
        primary_image = product.get_primary_image()
        image_url = primary_image.image.url if primary_image else None

        price = product.get_price()
        discounted_price = product.get_discounted_price()
        pct = product.get_active_offer_percentage()

        results.append(
            {
                "id": product.id,
                "name": product.name,
                "category": product.category.name,
                "image_url": image_url,
                "price": float(price) if price else None,
                "discounted_price": (
                    float(discounted_price) if discounted_price else None
                ),
                "discount_percentage": pct,
            }
        )

    return JsonResponse({"results": results})


def product_detail_view(request, product_id):
    product = Product.objects.filter(
        id=product_id,
        is_deleted=False,
        is_active=True,
        category__is_deleted=False,
        category__is_active=True,
    ).first()
    if not product:
        messages.error(
            request, "Sorry, this product is currently unavailable or out of stock."
        )
        return redirect("shop")

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
                "discounted_price": str(v.get_discounted_price()),
                "discount_percentage": v.product.get_active_offer_percentage(),
                "stock": v.stock,
                "is_default": v.is_default,
                "images": images,
            }
        )

    related_products = (
        Product.objects.filter(
            category=product.category, is_deleted=False, is_active=True
        )
        .exclude(id=product.id)
        .order_by("-id")[:4]
    )

    today = timezone.now().date()
    active_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=today,
        valid_until__gte=today,
    )

    reviews = product.reviews.select_related("user").order_by("-created_at")

    # Average rating
    avg_data = reviews.aggregate(avg=Avg("rating"))
    avg_rating = round(avg_data["avg"] or 0, 1)
    avg_rating_int = round(avg_data["avg"] or 0)

    # Review permission for current user
    user_can_review = False
    user_review = None

    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        if not user_review:
            has_delivered = Order.objects.filter(
                user=request.user,
                status="delivered",
                items__variant__product=product,
            ).exists()
            user_can_review = has_delivered

    context = {
        "product": product,
        "variants": variants,
        "default_variant": default_variant,
        "variants_data": variants_data,
        "related_products": related_products,
        "active_coupons": active_coupons,
        "reviews": reviews,
        "avg_rating": avg_rating,
        "avg_rating_int": avg_rating_int,
        "user_can_review": user_can_review,
        "user_review": user_review,
    }

    return render(request, "product_detail.html", context)


@login_required(login_url="login")
@require_POST
def submit_review(request, product_id):
    """Submit or update a product review. Only for users with a delivered order."""
    product = get_object_or_404(
        Product, id=product_id, is_deleted=False, is_active=True
    )

    # Verify the user has a delivered order containing this product
    has_delivered = Order.objects.filter(
        user=request.user,
        status="delivered",
        items__variant__product=product,
    ).exists()

    if not has_delivered:
        messages.error(
            request, "You can only review products you have purchased and received."
        )
        return redirect("product_detail", product_id=product_id)

    try:
        rating = int(request.POST.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    if rating < 1 or rating > 5:
        messages.error(request, "Please select a valid rating between 1 and 5 stars.")
        return redirect("product_detail", product_id=product_id)

    comment = request.POST.get("comment", "").strip()

    # Prevent editing an existing review
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.error(request, "You have already reviewed this product.")
        return redirect("product_detail", product_id=product_id)

    Review.objects.create(
        product=product, user=request.user, rating=rating, comment=comment
    )
    messages.success(request, "Thank you! Your review has been posted.")

    return redirect("product_detail", product_id=product_id)


@login_required(login_url="login")
@require_POST
def delete_review(request, product_id):
    """Delete the current user's review for a product."""
    product = get_object_or_404(
        Product, id=product_id, is_deleted=False, is_active=True
    )
    Review.objects.filter(product=product, user=request.user).delete()
    messages.success(request, "Your review has been deleted.")
    return redirect("product_detail", product_id=product_id)
