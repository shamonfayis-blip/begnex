import random
import re
import threading
import time

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_POST

User = get_user_model()


def _send_mail_async(subject, body, to_email):


    def _send():
        send_mail(
            subject,
            body,
            settings.EMAIL_HOST_USER,
            [to_email],
            fail_silently=True,
        )

    threading.Thread(target=_send, daemon=True).start()


OTP_EXPIRY_SECONDS = 60  


def _build_otp_email(otp, username, expiry_seconds=OTP_EXPIRY_SECONDS):
    
    expiry_minutes = expiry_seconds // 60
    expiry_label = (
        f"{expiry_minutes} minute{'s' if expiry_minutes != 1 else ''}"
        if expiry_seconds >= 60
        else f"{expiry_seconds} seconds"
    )

    return (
        f"Hi {username},\n\n"
        f"Your Begnex verification code is: {otp}\n\n"
        f"This code expires in {expiry_label}.\n"
        f"Do not share it with anyone.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"- The Begnex Team"
    )


def validate_password_strength(password):
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Add at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Add at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Add at least one number"
    return None


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    ref_code = request.GET.get("ref", "").strip()
    if not ref_code:
        ref_code = request.session.get("referrer_code", "")
    else:
        request.session["referrer_code"] = ref_code
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")
        manual_ref_code = request.POST.get("referral_code", "").strip()
        errors = {}
        if not username:
            errors["username"] = "Username is required"
        elif len(username) < 3:
            errors["username"] = "Username must be at least 3 characters"
        elif len(username) > 30:
            errors["username"] = "Username must be at most 30 characters"
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors["username"] = "Username can only contain letters, numbers, and underscores"
        if not email:
            errors["email"] = "Email is required"
        if not password:
            errors["password"] = "Password is required"
        if not confirm:
            errors["confirm_password"] = "Confirm password is required"
        if password and confirm and password != confirm:
            errors["confirm_password"] = "Passwords do not match"
        pw_error = validate_password_strength(password) if password else None
        if pw_error:
            errors["password"] = pw_error
        if username and User.objects.filter(username=username).exists():
            errors["username"] = "Username already exists"
        if email and User.objects.filter(email=email).exists():
            errors["email"] = "Email already exists"
        if manual_ref_code:
            if not User.objects.filter(referral_code=manual_ref_code).exists():
                errors["referral_code"] = "Invalid referral code"
        if errors:
            return render(
                request,
                "signup.html",
                {
                    "errors": errors,
                    "username": username,
                    "email": email,
                    "referral_code": manual_ref_code or ref_code,
                },
            )
        otp = random.randint(100000, 999999)
        request.session["signup_data"] = {
            "username": username,
            "email": email,
            "password": password,
            "referral_code": manual_ref_code,
        }
        request.session["otp"] = str(otp)
        request.session["otp_created_time"] = time.time()
        body = _build_otp_email(otp, username)
        _send_mail_async("Begnex OTP Verification", body, email)
        return redirect("otp_page")
    return render(request, "signup.html", {"referral_code": ref_code})


@never_cache
def otp_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        entered_otp = "".join([request.POST.get(f"otp{i}", "") for i in range(1, 7)])
        otp_created_time = request.session.get("otp_created_time")
        if not otp_created_time:
            return redirect("signup")
        if time.time() - otp_created_time > 60:
            # Keep signup_data so the user can still Resend OTP
            request.session.pop("otp", None)
            request.session.pop("otp_created_time", None)
            return render(
                request,
                "otp.html",
                {
                    "error": "OTP has expired. Please request a new OTP.",
                    "time_left": 0,
                    "otp_expired": True,
                },
            )
        session_otp = request.session.get("otp")
        signup_data = request.session.get("signup_data")
        if not session_otp or not signup_data:
            return redirect("signup")
        if entered_otp == session_otp:
            parts = signup_data["username"].split()
            user = User.objects.create_user(
                username=signup_data["username"],
                email=signup_data["email"],
                password=signup_data["password"],
                first_name=parts[0],
                last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
            )
            from user.wallet.utils import get_user_wallet, refund_to_wallet
            get_user_wallet(user)
            ref_code = signup_data.get("referral_code")
            if not ref_code:
                ref_code = request.session.get("referrer_code")
            if ref_code:
                try:
                    referrer = User.objects.get(referral_code=ref_code)
                    from admin_panel.admin_offer.models import (ReferralOffer,
                                                                ReferralRecord)
                    active_offer = ReferralOffer.objects.filter(is_active=True).first()
                    referrer_reward = 100.00
                    referee_reward = 50.00
                    if active_offer:
                        referrer_reward = float(active_offer.referrer_reward)
                        referee_reward = float(active_offer.referee_reward)
                    if referee_reward > 0:
                        refund_to_wallet(
                            user,
                            referee_reward,
                            f"Referral signup reward (code {ref_code})",
                        )
                    if referrer_reward > 0:
                        refund_to_wallet(
                            referrer,
                            referrer_reward,
                            f"Referral invite reward (referred {user.username})",
                        )
                    ReferralRecord.objects.create(
                        referrer=referrer,
                        referee=user,
                        referrer_reward_paid=referrer_reward,
                        referee_reward_paid=referee_reward,
                    )
                except User.DoesNotExist:
                    pass
                except Exception as ex:
                    print("Error in referral reward processing:", ex)
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            request.session.pop("otp", None)
            request.session.pop("signup_data", None)
            request.session.pop("otp_created_time", None)
            return redirect("home")
        else:
            elapsed = time.time() - otp_created_time
            time_left = max(0, int(OTP_EXPIRY_SECONDS - elapsed))
            return render(
                request,
                "otp.html",
                {"error": "Invalid OTP. Please try again.", "time_left": time_left},
            )
    list(messages.get_messages(request))
    # If signup_data is missing the user has no active OTP session — send to signup
    if not request.session.get("signup_data"):
        return redirect("signup")
    otp_created_time = request.session.get("otp_created_time")
    if otp_created_time:
        elapsed = time.time() - otp_created_time
        time_left = max(0, int(OTP_EXPIRY_SECONDS - elapsed))
    else:
        time_left = 0
    return render(request, "otp.html", {"time_left": time_left})


@require_POST
def resend_otp(request):
    signup_data = request.session.get("signup_data")
    if not signup_data:
        return redirect("signup")
    otp = random.randint(100000, 999999)
    request.session["otp"] = str(otp)
    request.session["otp_created_time"] = time.time()

    body = _build_otp_email(otp, signup_data["username"])
    _send_mail_async(
        "Begnex OTP Verification",
        body,
        signup_data["email"],
    )

    return redirect("otp_page")


@never_cache
def login_view(request):

    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        context = {"email": email}

        if not email or not password:
            return render(
                request,
                "login.html",
                {**context, "error": "All fields are required"},
            )

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(
                request,
                "login.html",
                {**context, "error": "Invalid email or password"},
            )

        if user_obj.is_blocked:
            return render(
                request,
                "login.html",
                {
                    **context,
                    "error": "Your account has been blocked. Please contact support.",
                },
            )

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return render(
                request,
                "login.html",
                {**context, "error": "Invalid email or password"},
            )

        if user.is_superuser:

            return render(
                request,
                "login.html",
                {**context, "error": "Admin can't access user login"},
            )

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        if remember:
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)

        messages.success(request, "Login successful")
        return redirect("home")

    return render(request, "login.html")


def forgot_password_view(request):

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            user = User.objects.get(email=email)

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(
                reverse("reset_password", kwargs={"uidb64": uid, "token": token})
            )

            _send_mail_async(
                "Begnex Password Reset",
                f"Click this link to reset your password:\n\n{reset_link}",
                email,
            )

            return render(
                request,
                "forgot_password.html",
                {"success": "Password reset link sent to your email."},
            )

        except User.DoesNotExist:
            return render(
                request,
                "forgot_password.html",
                {"error": "Email does not exist"},
            )

    return render(request, "forgot_password.html")


@never_cache
def reset_password_view(request, uidb64, token):

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "Invalid or expired reset link.")
        return redirect("login")

    messages.success(request, "Please enter your new password.")

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if not password or not confirm:
            return render(
                request,
                "reset_password.html",
                {"error": "All fields are required"},
            )

        if password != confirm:
            return render(
                request,
                "reset_password.html",
                {"error": "Passwords do not match"},
            )

        pw_error = validate_password_strength(password)
        if pw_error:
            return render(request, "reset_password.html", {"error": pw_error})

        if user.check_password(password):
            return render(
                request,
                "reset_password.html",
                {"error": "New password cannot be same as old password"},
            )

        user.set_password(password)
        user.save()

        messages.success(request, "Password reset successful. Please login.")
        return redirect("login")

    return render(request, "reset_password.html")


@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def home_view(request):
    from admin_panel.admin_offer.models import ReferralOffer
    from admin_panel.admin_product.models import Product

    latest_products = Product.objects.filter(
        is_deleted=False,
        is_active=True,
        category__is_deleted=False,
        category__is_active=True,
    ).order_by("-id")[:3]

    # cart_count, wishlist_ids, wishlist_count are injected by context processors
    referral_offer = ReferralOffer.objects.filter(is_active=True).first()

    context = {
        "latest_products": latest_products,
        "referral_offer": referral_offer,
    }
    return render(request, "home.html", context)


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        email = None
        if user and user.email:
            email = user.email
        elif sociallogin.account and sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get("email")

        if email:
            User = get_user_model()
            try:
                db_user = User.objects.get(email__iexact=email)
                if db_user.is_blocked:
                    messages.error(
                        request,
                        "Your account has been blocked. Please contact support.",
                    )
                    raise ImmediateHttpResponse(redirect("login"))
            except User.DoesNotExist:
                pass

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

       
        from user.wallet.utils import get_user_wallet, refund_to_wallet

        get_user_wallet(user)

     
        ref_code = request.session.get("referrer_code")
        if ref_code:
            try:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                referrer = User.objects.get(referral_code=ref_code)

                
                from admin_panel.admin_offer.models import (ReferralOffer,
                                                            ReferralRecord)

                if not ReferralRecord.objects.filter(referee=user).exists():
                    active_offer = ReferralOffer.objects.filter(is_active=True).first()

                    referrer_reward = 100.00
                    referee_reward = 50.00
                    if active_offer:
                        referrer_reward = float(active_offer.referrer_reward)
                        referee_reward = float(active_offer.referee_reward)

                    if referee_reward > 0:
                        refund_to_wallet(
                            user,
                            referee_reward,
                            f"Referral signup reward via Google (code {ref_code})",
                        )
                    if referrer_reward > 0:
                        refund_to_wallet(
                            referrer,
                            referrer_reward,
                            f"Referral invite reward via Google (referred {user.username})",
                        )

                    ReferralRecord.objects.create(
                        referrer=referrer,
                        referee=user,
                        referrer_reward_paid=referrer_reward,
                        referee_reward_paid=referee_reward,
                    )
            except User.DoesNotExist:
                pass
            except Exception as ex:
                print("Error in social login referral reward processing:", ex)
        return user


@never_cache
@login_required(login_url="login")
def user_referrals_view(request):
    user = request.user

    if not user.referral_code:
        user.save()

    from admin_panel.admin_offer.models import ReferralOffer, ReferralRecord

    active_offer = ReferralOffer.objects.filter(is_active=True).first()

    referrer_reward = 100.00
    referee_reward = 50.00
    if active_offer:
        referrer_reward = float(active_offer.referrer_reward)
        referee_reward = float(active_offer.referee_reward)

   
    referral_history = (
        ReferralRecord.objects.filter(referrer=user)
        .select_related("referee")
        .order_by("-created_at")
    )

    context = {
        "user": user,
        "referrer_reward": referrer_reward,
        "referee_reward": referee_reward,
        "is_active": active_offer.is_active if active_offer else True,
        "referral_history": referral_history,
    }
    return render(request, "referrals_page.html", context)


def about_view(request):
    return render(request, "about.html")
