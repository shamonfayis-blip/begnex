from django.urls import path
from . import views

urlpatterns = [
    path("details/", views.wallet_details, name="wallet_details"),
    path("add-money/create/", views.create_razorpay_order, name="wallet_create_order"),
    path("add-money/verify/", views.verify_razorpay_payment, name="wallet_verify_payment"),
]
