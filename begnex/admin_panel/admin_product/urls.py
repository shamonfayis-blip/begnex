from django.urls import path

from . import views

urlpatterns = [
    path("products/", views.admin_product_list_view, name="admin_products"),
    path("products/add/", views.admin_product_add_view, name="admin_product_add"),
    path(
        "products/edit/<int:product_id>/",
        views.admin_product_edit_view,
        name="admin_product_edit",
    ),
    path(
        "products/toggle/<int:product_id>/",
        views.admin_product_toggle_view,
        name="admin_product_toggle",
    ),
    path(
        "products/delete/<int:product_id>/",
        views.admin_product_delete_view,
        name="admin_product_delete",
    ),
    # Variant Management URLs
    path(
        "products/<int:product_id>/variants/",
        views.admin_variant_list_view,
        name="admin_variants",
    ),
    path(
        "variants/<int:product_id>/add/",
        views.admin_variant_add_view,
        name="admin_variant_add",
    ),
    path(
        "variants/<int:variant_id>/edit/",
        views.admin_variant_edit_view,
        name="admin_variant_edit",
    ),
    path(
        "variants/<int:variant_id>/delete/",
        views.admin_variant_delete_view,
        name="admin_variant_delete",
    ),
    path(
        "variants/<int:variant_id>/default/",
        views.admin_variant_set_default_view,
        name="admin_variant_set_default",
    ),
]
