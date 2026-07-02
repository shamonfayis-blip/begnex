from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("otp/", views.otp_page, name="otp_page"),
    path("login/", views.login_view, name="login"),
    path("", views.home_view, name="home"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path(
        "reset-password/<uidb64>/<token>/",
        views.reset_password_view,
        name="reset_password",
    ),
    path("logout/", views.logout_view, name="logout_view"),
    path("referrals/", views.user_referrals_view, name="user_referrals"),
    path("about/", views.about_view, name="about"),
]
