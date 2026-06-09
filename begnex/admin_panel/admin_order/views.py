from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from .models import Order


@never_cache
@staff_member_required(login_url="admin_login")
def admin_order_list_view(request):


    total_orders    = Order.objects.count()

    total_revenue   = Order.objects.filter(status="delivered").aggregate(rev=Sum("total"))["rev"] or 0

    pending_orders  = Order.objects.filter(status="pending").count()
    returned_orders = Order.objects.filter(status="cancelled").count()


    search_query  = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    sort_option   = request.GET.get("sort", "newest")

    orders = Order.objects.select_related("user").prefetch_related("items")

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(full_name__icontains=search_query)
        )

    if status_filter:
        orders = orders.filter(status=status_filter)

    
    if sort_option == "oldest":
        orders = orders.order_by("created_at")
    elif sort_option == "total_high":
        orders = orders.order_by("-total")
    elif sort_option == "total_low":
        orders = orders.order_by("total")
    else: 
        orders = orders.order_by("-created_at")



    paginator   = Paginator(orders, 5)
    page_obj    = paginator.get_page(request.GET.get("page"))

    context = {
        "total_orders":    total_orders,
        "total_revenue":   total_revenue,
        "pending_orders":  pending_orders,
        "returned_orders": returned_orders,
        "page_obj":        page_obj,
        "search_query":    search_query,
        "status_filter":   status_filter,
        "sort_option":     sort_option,
        "status_choices":  Order.STATUS_CHOICES,
    }
    return render(request, "orders.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "order_detail.html", {"order": order})


@never_cache
@staff_member_required(login_url="admin_login")
def admin_order_update_status_view(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get("status", "")

        
        allowed_transitions = {
            "pending": ["shipped", "cancelled"],
            "shipped": ["out_for_delivery", "cancelled"],
            "out_for_delivery": ["delivered", "cancelled"],
            "return_requested": ["returned"],
            "delivered": [],
            "cancelled": [],
            "returned": [],
        }

        current = order.status
        allowed = allowed_transitions.get(current, [])

        if new_status == current:
            
            pass
        elif new_status in allowed:
            order.status = new_status

            if new_status == "delivered":
                order.payment_status = "paid"
            elif new_status == "returned":
                order.payment_status = "refunded"
            order.save()
            messages.success(
                request,
                f"Order #{order.order_id} updated to "
                f"{order.get_status_display()}."
            )
        else:
            status_labels = dict(Order.STATUS_CHOICES)
            cur_label = order.get_status_display()
            new_label = status_labels.get(new_status, new_status)
            messages.error(
                request,
                f"Cannot transition status from '{cur_label}' "
                f"to '{new_label}'."
            )
   
    next_url = request.POST.get("next", "admin_orders")
    if next_url == "detail":
        return redirect("admin_order_detail", order_id=order_id)
    return redirect("admin_orders")
