from .models import Wishlist


def wishlist_count(request):
    """Inject wishlist_count and wishlist_ids into every template context."""
    if request.user.is_authenticated:
        qs = Wishlist.objects.filter(
            user=request.user,
            product__is_active=True,
            product__is_deleted=False,
            product__category__is_active=True,
            product__category__is_deleted=False,
        )
        return {
            "wishlist_count": qs.count(),
            "wishlist_ids": list(qs.values_list("product_id", flat=True)),
        }
    return {"wishlist_count": 0, "wishlist_ids": []}
