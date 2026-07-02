from django.core.paginator import Paginator
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, render

from admin_panel.admin_category.models import Category
from admin_panel.admin_product.models import Product


def category_list_view(request):
    """User-facing categories page — shows all active, non-deleted categories."""
    categories = Category.objects.filter(
        is_deleted=False,
        is_active=True,
    ).order_by("name")

    categories = categories.annotate(
        product_count=Count(
            "products",
            filter=Q(
                products__is_deleted=False,
                products__is_active=True,
            ),
        )
    )

    context = {"categories": categories}
    return render(request, "user_categories.html", context)


def category_detail_view(request, category_id):
    """Show all products in a specific category."""
    category = get_object_or_404(
        Category, id=category_id, is_deleted=False, is_active=True
    )

    products = (
        Product.objects.filter(
            category=category,
            is_deleted=False,
            is_active=True,
        )
        .annotate(
            computed_min_price=Min(
                "variants__price",
                filter=Q(variants__is_active=True, variants__is_deleted=False),
            )
        )
        .order_by("-id")
    )

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "category": category,
        "page_obj": page_obj,
    }
    return render(request, "category_detail.html", context)
