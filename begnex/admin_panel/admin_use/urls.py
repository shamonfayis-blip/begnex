from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.admin_login_view, name="admin_login"),
    path("dashboard/", views.admin_dashboard_view, name="admin_dashboard"),
    path("logout/", views.admin_logout_view, name="admin_logout"),
    path("users/", views.admin_user_list_view, name="admin_user_list"),
    path(
        "users/toggle-block/<int:user_id>/",
        views.toggle_block_user,
        name="toggle_block_user",
    ),
    path("sales-report/", views.sales_report_view, name="sales_report"),
    path("users/<int:user_id>/", views.admin_user_detail_view, name="admin_user_detail"),
    path("reviews/", views.admin_reviews_view, name="admin_reviews"),
    path("reviews/<int:review_id>/delete/", views.admin_review_delete_view, name="admin_review_delete"),
]
