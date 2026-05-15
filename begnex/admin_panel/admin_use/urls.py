from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login_view, name='admin_login'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('logout/', views.admin_logout_view, name='admin_logout'),
    path('users/', views.admin_user_list_view, name='admin_user_list'),
    path('users/toggle-block/<int:user_id>/', views.toggle_block_user, name='toggle_block_user'),
]
