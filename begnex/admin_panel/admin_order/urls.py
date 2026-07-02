from django.urls import path

from . import views

urlpatterns = [
    path("orders/", views.admin_order_list_view, name="admin_orders"),
    path(
        "orders/<int:order_id>/",
        views.admin_order_detail_view,
        name="admin_order_detail",
    ),
    path(
        "orders/<int:order_id>/update-status/",
        views.admin_order_update_status_view,
        name="admin_order_update_status",
    ),
]
