from django.urls import path
from . import views

urlpatterns = [
    path("", views.checkout_page, name="checkout_page"),
    path("place-order/", views.place_order, name="place_order"),
    path("success/<int:order_pk>/", views.order_success, name="order_success"),
    path("address/add/", views.checkout_add_address_api, name="checkout_add_address_api"),
    path("address/edit/<int:id>/", views.checkout_edit_address_api, name="checkout_edit_address_api"),
    path("coupon/apply/", views.checkout_apply_coupon_api, name="checkout_apply_coupon_api"),
]
