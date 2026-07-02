from django.urls import path

from . import views

urlpatterns = [
    path("categories/", views.category_list_view, name="categories"),
    path(
        "categories/<int:category_id>/",
        views.category_detail_view,
        name="category_detail",
    ),
]
