import random
import time

import re
import threading

from django.shortcuts import render, redirect

from django.contrib.auth import authenticate, login, logout

from django.contrib.auth import get_user_model

from django.views.decorators.cache import never_cache, cache_control

from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from django.contrib.auth.decorators import login_required

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

from django.urls import reverse

User = get_user_model()



def _send_mail_async(subject, body, to_email):
    """Send email in a background daemon thread so views never block."""
    def _send():
        send_mail(subject, body, settings.EMAIL_HOST_USER, [to_email], fail_silently=True)
    threading.Thread(target=_send, daemon=True).start()


def validate_password_strength(password):
    if len(password) < 8:
        return 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return 'Add at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return 'Add at least one lowercase letter'
    if not re.search(r'\d', password):
        return 'Add at least one number'
    return None


def signup_view(request):

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm_password', '')

        errors = {}

        if not username:
            errors['username'] = 'Username is required'
        if not email:
            errors['email'] = 'Email is required'
        if not password:
            errors['password'] = 'Password is required'
        if not confirm:
            errors['confirm_password'] = 'Confirm password is required'

        if password and confirm and password != confirm:
            errors['confirm_password'] = 'Passwords do not match'

        pw_error = validate_password_strength(password) if password else None
        if pw_error:
            errors['password'] = pw_error

        if username and User.objects.filter(username=username).exists():
            errors['username'] = 'Username already exists'
        if email and User.objects.filter(email=email).exists():
            errors['email'] = 'Email already exists'

        if errors:
            return render(request, 'signup.html', {
                'errors': errors, 'username': username, 'email': email
            })

        otp = random.randint(100000, 999999)
        request.session['signup_data'] = {
            'username': username, 'email': email, 'password': password,
        }
        request.session['otp'] = str(otp)
        request.session['otp_created_time'] = time.time()

        _send_mail_async('Begnex OTP Verification', f'Your OTP is {otp}', email)

        messages.success(request, 'OTP sent successfully')
        return redirect('otp_page')

    return render(request, 'signup.html')


@never_cache
def otp_page(request):

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        entered_otp = ''.join([request.POST.get(f'otp{i}', '') for i in range(1, 7)])

        otp_created_time = request.session.get('otp_created_time')
        if not otp_created_time:
            return redirect('signup')

        if time.time() - otp_created_time > 60:
            request.session.pop('otp', None)
            request.session.pop('signup_data', None)
            request.session.pop('otp_created_time', None)
            return render(request, 'otp.html', {'error': 'OTP expired. Please sign up again.'})

        session_otp = request.session.get('otp')
        signup_data = request.session.get('signup_data')

        if not session_otp or not signup_data:
            return redirect('signup')

        if entered_otp == session_otp:
            parts = signup_data['username'].split()
            user = User.objects.create_user(
                username   = signup_data['username'],
                email      = signup_data['email'],
                password   = signup_data['password'],
                first_name = parts[0],
                last_name  = ' '.join(parts[1:]) if len(parts) > 1 else '',
            )
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            request.session.pop('otp', None)
            request.session.pop('signup_data', None)
            request.session.pop('otp_created_time', None)

            return redirect('home')
        else:
            return render(request, 'otp.html', {'error': 'Invalid OTP. Please try again.'})

    return render(request, 'otp.html')


def resend_otp(request):
    signup_data = request.session.get('signup_data')
    if not signup_data:
        return redirect('signup')

    otp = random.randint(100000, 999999)
    request.session['otp'] = str(otp)
    request.session['otp_created_time'] = time.time()

    _send_mail_async('Begnex OTP Verification', f'Your new OTP is {otp}', signup_data['email'])

    messages.success(request, 'New OTP sent successfully')
    return redirect('otp_page')



@never_cache
def login_view(request):

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember')

        context = {'email': email}

        if not email or not password:
            return render(request, 'login.html', {**context, 'error': 'All fields are required'})

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'login.html', {**context, 'error': 'Invalid email or password'})

        # ── Blocked check ──
        if user_obj.is_blocked:
            return render(request, 'login.html', {
                **context,
                'error': 'Your account has been blocked. Please contact support.'
            })

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return render(request, 'login.html', {
                **context,
                'error': 'Invalid email or password'
            })

    
        if user.is_superuser:

            return render(request, 'login.html', {
                **context,
                'error': "Admin can't access user login"
            })

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        if remember:
            request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            request.session.set_expiry(0)

        messages.success(request, 'Login successful')
        return redirect('home')

    return render(request, 'login.html')



def forgot_password_view(request):

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()

        try:
            user = User.objects.get(email=email)

            token = default_token_generator.make_token(user)
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            reset_link = request.build_absolute_uri(
                reverse('reset_password', kwargs={'uidb64': uid, 'token': token})
            )

            _send_mail_async(
                'Begnex Password Reset',
                f'Click this link to reset your password:\n\n{reset_link}',
                email
            )

            return render(request, 'forgot_password.html', {
                'success': 'Password reset link sent to your email.'
            })

        except User.DoesNotExist:
            return render(request, 'forgot_password.html', {'error': 'Email does not exist'})

    return render(request, 'forgot_password.html')



@never_cache
def reset_password_view(request, uidb64, token):

    try:
        uid  = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('login')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm_password', '')

        if not password or not confirm:
            return render(request, 'reset_password.html', {'error': 'All fields are required'})

        if password != confirm:
            return render(request, 'reset_password.html', {'error': 'Passwords do not match'})

        pw_error = validate_password_strength(password)
        if pw_error:
            return render(request, 'reset_password.html', {'error': pw_error})

        if user.check_password(password):
            return render(request, 'reset_password.html', {
                'error': 'New password cannot be same as old password'
            })

        user.set_password(password)
        user.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'Password reset successful')
        return redirect('profile')

    return render(request, 'reset_password.html')



@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required(login_url='login')
def home_view(request):
    return render(request, 'home.html')



def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')
