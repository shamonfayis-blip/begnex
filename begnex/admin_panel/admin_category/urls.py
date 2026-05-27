from django.urls import path

from . import views

urlpatterns = [
    path(
        "categories/", views.admin_category_list_view, name="admin_categories"
    ),
    path(
        "categories/add/",
        views.admin_category_add_view,
        name="admin_category_add",
    ),
    path(
        "categories/edit/<int:category_id>/",
        views.admin_category_edit_view,
        name="admin_category_edit",
    ),
    path(
        "categories/toggle/<int:category_id>/",
        views.admin_category_toggle_view,
        name="admin_category_toggle",
    ),
    path(
        "categories/delete/<int:category_id>/",
        views.admin_category_delete_view,
        name="admin_category_delete",
    ),
]
