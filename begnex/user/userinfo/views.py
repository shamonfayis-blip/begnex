import random
import threading
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

User = get_user_model()


def _send_mail_async(subject, body, to_email):
    """Non-blocking email dispatch."""

    def _send():
        send_mail(
            subject,
            body,
            settings.EMAIL_HOST_USER,
            [to_email],
            fail_silently=True,
        )

    threading.Thread(target=_send, daemon=True).start()


@never_cache
@login_required(login_url="login")
def profile_view(request):

    user = request.user

    return render(request, "profile.html", {"user": user})


@never_cache
@login_required(login_url="login")
def edit_profile_view(request):

    user = request.user

    if request.method == "POST":

        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        if phone and (not phone.isdigit() or len(phone) != 10):

            messages.error(request, "Phone number must contain exactly 10 digits.")

            return redirect("edit_profile")
        profile_photo = request.FILES.get("profile_image")
        remove_image = request.POST.get("remove_image") == "true"

        if not full_name or not email:
            messages.error(request, "Name and email are required.")
            return redirect("edit_profile")

        if User.objects.filter(email=email).exclude(id=user.id).exists():
            messages.error(request, "That email is already in use.")
            return redirect("edit_profile")

        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.phone_number = phone

        if remove_image:
            user.profile_photo = None
        elif profile_photo:
            user.profile_photo = profile_photo

        if email != user.email:
            otp = random.randint(100000, 999999)
            request.session["new_email"] = email
            request.session["email_otp"] = str(otp)
            request.session["email_otp_expiry"] = time.time() + 60

            user.save()

            _send_mail_async(
                "Begnex Email Verification",
                f"Your OTP for email change is: {otp}\n\nThis code is valid for 1 minute.",
                email,
            )

            return redirect("verify_email_otp")

        user.email = email
        user.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    return render(request, "edit_profile.html")


@never_cache
@login_required(login_url="login")
def verify_email_otp(request):
    import time

    new_email = request.session.get("new_email")

    if not request.session.get("email_otp"):
        messages.error(request, "No OTP session. Please try again.")
        return redirect("edit_profile")

    otp_expiry = request.session.get("email_otp_expiry", 0)
    if time.time() > otp_expiry:
        request.session.pop("email_otp", None)
        request.session.pop("email_otp_expiry", None)
        messages.error(request, "OTP has expired. Please try again.")
        return redirect("edit_profile")

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        if not entered_otp:
            entered_otp = "".join(
                [request.POST.get(f"otp{i}", "") for i in range(1, 7)]
            )

        session_otp = request.session.get("email_otp")

        if entered_otp == session_otp:
            user = request.user
            user.email = new_email
            user.save()

            request.session.pop("email_otp", None)
            request.session.pop("email_otp_expiry", None)
            request.session.pop("new_email", None)

            messages.success(request, "Email updated successfully.")
            return redirect("profile")

        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return redirect("verify_email_otp")

    return render(
        request,
        "verify_email_otp.html",
        {
            "new_email": new_email,
        },
    )


@never_cache
@login_required(login_url="login")
def change_password_view(request):

    user = request.user

    if request.method == "POST":
        current_password = request.POST.get("current_password", "").strip()
        new_password = request.POST.get("new_password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if not current_password or not new_password or not confirm_password:
            return render(
                request,
                "change_password.html",
                {"error": "All fields are required."},
            )

        if new_password != confirm_password:
            return render(
                request,
                "change_password.html",
                {"error": "New passwords do not match."},
            )

        if len(new_password) < 8:
            return render(
                request,
                "change_password.html",
                {"error": "Password must be at least 8 characters."},
            )

        if not user.check_password(current_password):
            return render(
                request,
                "change_password.html",
                {"error": "Current password is incorrect."},
            )

        user.set_password(new_password)
        user.save()

        update_session_auth_hash(request, user)

        messages.success(request, "Password updated successfully.")
        return redirect("profile")

    return render(request, "change_password.html")
