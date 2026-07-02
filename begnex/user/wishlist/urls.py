from django.urls import path

from . import views

urlpatterns = [
    path("", views.wishlist_view, name="wishlist"),
    path("api/toggle/", views.toggle_wishlist_api, name="toggle_wishlist_api"),
]
