from django.urls import path
from . import views

urlpatterns = [
    path("", views.order_list_view, name="order_list"),
    path(
        "<int:order_pk>/",
        views.order_detail_view,
        name="user_order_detail",
    ),
    path(
        "<int:order_pk>/cancel/",
        views.cancel_order,
        name="cancel_order",
    ),
    path(
        "item/<int:item_pk>/cancel/",
        views.cancel_order_item,
        name="cancel_order_item",
    ),
    path(
        "<int:order_pk>/return/",
        views.return_order,
        name="return_order",
    ),
    path(
        "item/<int:item_pk>/return/",
        views.return_order_item,
        name="return_order_item",
    ),
    path(
        "<int:order_pk>/invoice/",
        views.download_invoice,
        name="download_invoice",
    ),
]
