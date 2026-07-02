from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import Coupon
from admin_panel.admin_order.models import Order


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_list_view(request):
    coupons = Coupon.objects.all()

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")

    if search_query:
        coupons = coupons.filter(code__icontains=search_query)

    today = timezone.now().date()
    if status_filter == "active":
        coupons = coupons.filter(is_active=True, valid_until__gte=today, valid_from__lte=today)
    elif status_filter == "inactive":
        coupons = coupons.filter(is_active=False)
    elif status_filter == "expired":
        coupons = coupons.filter(valid_until__lt=today)

    paginator = Paginator(coupons, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    total_c = Coupon.objects.count()
    active_coupons = Coupon.objects.filter(is_active=True, valid_until__gte=today, valid_from__lte=today).count()
    expired_coupons = Coupon.objects.filter(valid_until__lt=today).count()
    inactive_coupons = Coupon.objects.filter(is_active=False).count()
    
    


    from django.db.models import Sum
    history_orders = (
        Order.objects.exclude(coupon_code__isnull=True)
        .exclude(coupon_code="")
        .select_related("user")
    )

    history_search = request.GET.get("hq", "").strip()
    history_coupon_filter = request.GET.get("hcoupon", "").strip()

    if history_search:
        history_orders = history_orders.filter(coupon_code__icontains=history_search)
    if history_coupon_filter:
        history_orders = history_orders.filter(coupon_code__iexact=history_coupon_filter)

    history_paginator = Paginator(history_orders, 12)
    history_page_obj = history_paginator.get_page(request.GET.get("hpage"))

    all_used_coupon_codes = (
        Order.objects.exclude(coupon_code__isnull=True)
        .exclude(coupon_code="")
        .values_list("coupon_code", flat=True)
        .distinct()
        .order_by("coupon_code")
    )

    history_total_uses = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code="").count()
    history_total_savings = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code="").aggregate(s=Sum("coupon_discount"))["s"] or 0
    history_unique_coupons = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code="").values("coupon_code").distinct().count()

    
    active_tab = request.GET.get("tab", "coupons")


    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "total_c":total_c,
        "status_filter": status_filter,
        "active_coupons": active_coupons,
        "expired_coupons": expired_coupons,
        "inactive_coupons": inactive_coupons,
        "history_page_obj": history_page_obj,
        "history_search": history_search,
        "history_coupon_filter": history_coupon_filter,
        "all_used_coupon_codes": all_used_coupon_codes,
        "history_total_uses": history_total_uses,
        "history_total_savings": history_total_savings,
        "history_unique_coupons": history_unique_coupons,
        "active_tab": active_tab,
        
    }
    return render(request, "coupons.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_create_view(request):
    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()
        discount_type = request.POST.get("discount_type", "percentage")
        discount_value = request.POST.get("discount_value", "").strip()
        min_order_amount = request.POST.get("min_order_amount", "0").strip()
        max_discount_amount = request.POST.get("max_discount_amount", "").strip()
        usage_limit = request.POST.get("usage_limit", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

       
        if not code:
            errors.append("Coupon code is required.")
        elif len(code) < 3:
            errors.append("Coupon code must be at least 3 characters.")
        elif len(code) > 20:
            errors.append("Coupon code cannot exceed 20 characters.")
        elif not code.replace("_", "").replace("-", "").isalnum():
            errors.append("Coupon code can only contain letters, numbers, hyphens, and underscores.")
        elif Coupon.objects.filter(code=code).exists():
            errors.append(f"Coupon code '{code}' already exists.")

        if not discount_value:
            errors.append("Discount value is required.")
        else:
            try:
                discount_value = float(discount_value)
                if discount_value <= 0:
                    errors.append("Discount value must be greater than 0.")
                if discount_type == "percentage" and discount_value > 100:
                    errors.append("Percentage discount cannot exceed 100%.")
            except ValueError:
                errors.append("Discount value must be a valid number.")

        try:
            min_order_amount = float(min_order_amount) if min_order_amount else 0
            if min_order_amount < 0:
                errors.append("Minimum order amount cannot be negative.")
        except ValueError:
            errors.append("Minimum order amount must be a valid number.")

        if max_discount_amount:
            try:
                max_discount_amount = float(max_discount_amount)
                if max_discount_amount <= 0:
                    errors.append("Maximum discount amount must be greater than 0.")
            except ValueError:
                errors.append("Maximum discount amount must be a valid number.")
        else:
            max_discount_amount = None

        if usage_limit:
            try:
                usage_limit = int(usage_limit)
                if usage_limit < 1:
                    errors.append("Usage limit must be at least 1.")
            except ValueError:
                errors.append("Usage limit must be a whole number.")
        else:
            usage_limit = None

        if not valid_from:
            errors.append("Valid from date is required.")
        if not valid_until:
            errors.append("Valid until date is required.")

        if valid_from and valid_until:
            from datetime import date
            try:
                vf = date.fromisoformat(valid_from)
                vu = date.fromisoformat(valid_until)
                if vu < vf:
                    errors.append("'Valid until' date must be after 'Valid from' date.")
            except ValueError:
                errors.append("Invalid date format.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            Coupon.objects.create(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                min_order_amount=min_order_amount,
                max_discount_amount=max_discount_amount,
                usage_limit=usage_limit,
                valid_from=valid_from,
                valid_until=valid_until,
                is_active=is_active,
            )
            messages.success(request, f"Coupon '{code}' created successfully!")
            return redirect("admin_coupons")

    return redirect("admin_coupons")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_delete_view(request, coupon_id):
    if request.method == "POST":
        coupon = get_object_or_404(Coupon, id=coupon_id)
        code = coupon.code
        coupon.delete()
        messages.success(request, f"Coupon '{code}' deleted successfully.")
    return redirect("admin_coupons")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_toggle_view(request, coupon_id):
    if request.method == "POST":
        coupon = get_object_or_404(Coupon, id=coupon_id)
        coupon.is_active = not coupon.is_active
        coupon.save()
        status = "activated" if coupon.is_active else "deactivated"
        messages.success(request, f"Coupon '{coupon.code}' {status}.")
    return redirect("admin_coupons")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_edit_view(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()
        discount_type = request.POST.get("discount_type", "percentage")
        discount_value = request.POST.get("discount_value", "").strip()
        min_order_amount = request.POST.get("min_order_amount", "0").strip()
        max_discount_amount = request.POST.get("max_discount_amount", "").strip()
        usage_limit = request.POST.get("usage_limit", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

        
        if not code:
            errors.append("Coupon code is required.")
        elif len(code) < 3:
            errors.append("Coupon code must be at least 3 characters.")
        elif len(code) > 20:
            errors.append("Coupon code cannot exceed 20 characters.")
        elif not code.replace("_", "").replace("-", "").isalnum():
            errors.append("Coupon code can only contain letters, numbers, hyphens, and underscores.")
        elif Coupon.objects.filter(code=code).exclude(id=coupon_id).exists():
            errors.append(f"Coupon code '{code}' already exists.")

        if not discount_value:
            errors.append("Discount value is required.")
        else:
            try:
                discount_value = float(discount_value)
                if discount_value <= 0:
                    errors.append("Discount value must be greater than 0.")
                if discount_type == "percentage" and discount_value > 100:
                    errors.append("Percentage discount cannot exceed 100%.")
            except ValueError:
                errors.append("Discount value must be a valid number.")

        try:
            min_order_amount = float(min_order_amount) if min_order_amount else 0
            if min_order_amount < 0:
                errors.append("Minimum order amount cannot be negative.")
        except ValueError:
            errors.append("Minimum order amount must be a valid number.")

        if max_discount_amount:
            try:
                max_discount_amount = float(max_discount_amount)
                if max_discount_amount <= 0:
                    errors.append("Maximum discount amount must be greater than 0.")
            except ValueError:
                errors.append("Maximum discount amount must be a valid number.")
        else:
            max_discount_amount = None

        if usage_limit:
            try:
                usage_limit = int(usage_limit)
                if usage_limit < 1:
                    errors.append("Usage limit must be at least 1.")
            except ValueError:
                errors.append("Usage limit must be a whole number.")
        else:
            usage_limit = None

        if not valid_from:
            errors.append("Valid from date is required.")
        if not valid_until:
            errors.append("Valid until date is required.")

        if valid_from and valid_until:
            from datetime import date
            try:
                vf = date.fromisoformat(valid_from)
                vu = date.fromisoformat(valid_until)
                if vu < vf:
                    errors.append("'Valid until' date must be after 'Valid from' date.")
            except ValueError:
                errors.append("Invalid date format.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            coupon.code = code
            coupon.description = description
            coupon.discount_type = discount_type
            coupon.discount_value = discount_value
            coupon.min_order_amount = min_order_amount
            coupon.max_discount_amount = max_discount_amount
            coupon.usage_limit = usage_limit
            coupon.valid_from = valid_from
            coupon.valid_until = valid_until
            coupon.is_active = is_active
            coupon.save()
            messages.success(request, f"Coupon '{code}' updated successfully!")
            
    return redirect("admin_coupons")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_coupon_usage_history_view(request):
    """Show all orders where a coupon was applied."""
    orders = Order.objects.exclude(coupon_code__isnull=True).exclude(coupon_code="").select_related("user")

   
    search_query = request.GET.get("q", "").strip()
    if search_query:
        orders = orders.filter(coupon_code__icontains=search_query)

    coupon_filter = request.GET.get("coupon", "").strip()
    if coupon_filter:
        orders = orders.filter(coupon_code__iexact=coupon_filter)

    paginator = Paginator(orders, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    
    total_uses = orders.count()
    from django.db.models import Sum, Count
    total_savings = orders.aggregate(s=Sum("coupon_discount"))["s"] or 0
    unique_coupons = orders.values("coupon_code").distinct().count()

    # All distinct coupon codes (for filter dropdown)
    all_coupon_codes = (
        Order.objects.exclude(coupon_code__isnull=True)
        .exclude(coupon_code="")
        .values_list("coupon_code", flat=True)
        .distinct()
        .order_by("coupon_code")
    )

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "coupon_filter": coupon_filter,
        "total_uses": total_uses,
        "total_savings": total_savings,
        "unique_coupons": unique_coupons,
        "all_coupon_codes": all_coupon_codes,
    }
    return render(request, "coupon_usage_history.html", context)
