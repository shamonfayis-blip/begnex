from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

User = get_user_model()


@never_cache
def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST': 
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Email and password are required.')
            return redirect('admin_login')

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with that email.')
            return redirect('admin_login')

        user = authenticate(request, username=user_obj.username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')
        elif user is not None and not user.is_staff:
            messages.error(request, 'You do not have admin access.')
            return redirect('admin_login')
        else:
            messages.error(request, 'Incorrect password. Please try again.')
            return redirect('admin_login')

    return render(request, 'admin_use/admin_login.html')


@never_cache
@staff_member_required(login_url='admin_login')
def admin_dashboard_view(request):
    total_users = User.objects.filter(is_staff=False).count()
    return render(request, 'admin_use/admin_dashboard.html', {
        'total_users': total_users,
    })


@never_cache
@staff_member_required(login_url='admin_login')
def admin_user_list_view(request):
    search_query = request.GET.get('q', '').strip()

    users = User.objects.filter(is_staff=False).order_by('-date_joined')

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    paginator = Paginator(users, 5)  # 5 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_use/admin_users.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_users': users.count(),
    })


@never_cache
@staff_member_required(login_url='admin_login')
def toggle_block_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id, is_staff=False)
        user.is_blocked = not user.is_blocked
        user.save()
        action = 'blocked' if user.is_blocked else 'unblocked'
        messages.success(request, f'User "{user.username}" has been {action}.')
    return redirect('admin_user_list')


@never_cache
def admin_logout_view(request):
    logout(request)
    return redirect('admin_login')
