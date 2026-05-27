from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("user.accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("userinfo/", include("user.userinfo.urls")),
    path("address/", include("user.address.urls")),
    path("begnex-admin/", include("admin_panel.admin_use.urls")),
    path("admin-category/", include("admin_panel.admin_category.urls")),
    path("admin-product/", include("admin_panel.admin_product.urls")),
    path("product/", include("user.product.urls")),
    path("category/", include("user.category.urls")),
    path("cart/", include("user.cart.urls")),
    path("wishlist/", include("user.wishlist.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
