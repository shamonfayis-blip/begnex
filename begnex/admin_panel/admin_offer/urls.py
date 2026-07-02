from django.urls import path

from . import views

urlpatterns = [
    path("offers/", views.admin_offer_list_view, name="admin_offers"),
    path(
        "offers/product/create/",
        views.admin_product_offer_create_view,
        name="admin_product_offer_create",
    ),
    path(
        "offers/category/create/",
        views.admin_category_offer_create_view,
        name="admin_category_offer_create",
    ),
    path(
        "offers/product/<int:offer_id>/edit/",
        views.admin_product_offer_edit_view,
        name="admin_product_offer_edit",
    ),
    path(
        "offers/category/<int:offer_id>/edit/",
        views.admin_category_offer_edit_view,
        name="admin_category_offer_edit",
    ),
    path(
        "offers/product/<int:offer_id>/delete/",
        views.admin_product_offer_delete_view,
        name="admin_product_offer_delete",
    ),
    path(
        "offers/category/<int:offer_id>/delete/",
        views.admin_category_offer_delete_view,
        name="admin_category_offer_delete",
    ),
    path(
        "offers/product/<int:offer_id>/toggle/",
        views.admin_product_offer_toggle_view,
        name="admin_product_offer_toggle",
    ),
    path(
        "offers/category/<int:offer_id>/toggle/",
        views.admin_category_offer_toggle_view,
        name="admin_category_offer_toggle",
    ),
    path("offers/referrals/", views.admin_referrals_view, name="admin_referrals"),
    path(
        "offers/referrals/save/",
        views.admin_referral_offer_save_view,
        name="admin_referral_offer_save",
    ),
]
