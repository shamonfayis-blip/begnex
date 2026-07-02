from django.urls import path

from . import views

urlpatterns = [
    path("", views.cart_view, name="cart"),
    path("api/add/", views.add_to_cart_api, name="add_to_cart_api"),
    path("api/update/", views.update_cart_api, name="update_cart_api"),
    path("api/remove/", views.remove_cart_api, name="remove_cart_api"),
]
