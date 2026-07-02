from django.urls import path

from . import views

urlpatterns = [
    path("coupons/", views.admin_coupon_list_view, name="admin_coupons"),
    path("coupons/create/", views.admin_coupon_create_view, name="admin_coupon_create"),
    path(
        "coupons/usage-history/",
        views.admin_coupon_usage_history_view,
        name="admin_coupon_usage_history",
    ),
    path(
        "coupons/<int:coupon_id>/delete/",
        views.admin_coupon_delete_view,
        name="admin_coupon_delete",
    ),
    path(
        "coupons/<int:coupon_id>/toggle/",
        views.admin_coupon_toggle_view,
        name="admin_coupon_toggle",
    ),
    path(
        "coupons/<int:coupon_id>/edit/",
        views.admin_coupon_edit_view,
        name="admin_coupon_edit",
    ),
]
