from django.urls import path
from . import views

urlpatterns = [

    path('profile/', views.profile_view, name='profile'),

    path('edit-profile/', views.edit_profile_view, name='edit_profile'),

    path('verify-email-otp/',views.verify_email_otp,name='verify_email_otp'),

    path('change-password/', views.change_password_view, name='change_password'),

]