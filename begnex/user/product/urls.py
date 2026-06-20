from django.urls import path

from . import views

urlpatterns = [
    path("", views.shop_view, name="shop"),
    path(
        "suggestions/",
        views.search_suggestions_view,
        name="search_suggestions",
    ),
    path(
        "product/<int:product_id>/",
        views.product_detail_view,
        name="product_detail",
    ),
    path(
        "product/<int:product_id>/review/",
        views.submit_review,
        name="submit_review",
    ),
    path(
        "product/<int:product_id>/review/delete/",
        views.delete_review,
        name="delete_review",
    ),
]
