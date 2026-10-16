from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from .models import Order


@never_cache
@staff_member_required(login_url="admin_login")
def admin_order_list_view(request):

    total_orders = Order.objects.count()

    total_revenue = (
        Order.objects.filter(status="delivered").aggregate(rev=Sum("total"))["rev"] or 0
    )

    pending_orders = Order.objects.filter(status="pending").count()
    returned_orders = Order.objects.filter(status="cancelled").count()

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    sort_option = request.GET.get("sort", "newest")

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

    paginator = Paginator(orders, 5)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "pending_orders": pending_orders,
        "returned_orders": returned_orders,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "sort_option": sort_option,
        "status_choices": Order.STATUS_CHOICES,
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
            "return_requested": ["returned", "return_rejected"],
            "delivered": [],
            "cancelled": [],
            "returned": [],
            "return_rejected": [],
        }

        current = order.status
        allowed = list(allowed_transitions.get(current, []))

        
        has_pending_items = any(
            (i.return_requested_quantity > 0 or i.status == "return_requested")
            for i in order.items.all()
        )
        if has_pending_items or current == "return_requested":
            if "returned" not in allowed:
                allowed.append("returned")
            if "return_rejected" not in allowed:
                allowed.append("return_rejected")

        if new_status == current and not has_pending_items:
            pass
        elif new_status in allowed:
            order.status = new_status

            if new_status == "cancelled":
                reason = request.POST.get("reason", "").strip() or "Cancelled by Admin"
                order.cancel_reason = reason

                with transaction.atomic():
                    for item in order.items.all():
                        active_qty = item.quantity - item.cancelled_quantity
                        if active_qty > 0:
                            item.cancelled_quantity = item.quantity
                            item.status = "cancelled"
                            item.cancel_reason = reason
                            item.save()
                            if item.variant:
                                item.variant.stock += active_qty
                                item.variant.save()

                    if order.payment_status == "paid":
                        from user.wallet.utils import refund_to_wallet

                        refund_to_wallet(
                            order.user,
                            order.total,
                            f"Refund for cancelled Order #{order.order_id} (Admin)",
                        )
                        order.payment_status = "refunded"

            elif new_status == "delivered":
                order.payment_status = "paid"
                
                from django.utils import timezone as _tz
                if not order.delivered_at:
                    order.delivered_at = _tz.now()

            elif new_status == "returned":
                reason = request.POST.get("reason", "").strip()
                if reason:
                    order.return_reason = reason

                with transaction.atomic():
                    refund_total = 0
                    all_items = list(order.items.all())
                    
                   
                    returning_items = [
                        i for i in all_items
                        if i.return_requested_quantity > 0 or i.status == "return_requested"
                    ]

                    discount_ratio = (
                        order.discount / order.subtotal if order.subtotal > 0 else 0
                    )

                    returned_subtotal = 0
                    total_returned_qty = 0

                    for item in returning_items:
                        qty_to_return = item.return_requested_quantity
                        if qty_to_return <= 0:
                            qty_to_return = max(0, item.quantity - item.cancelled_quantity - item.returned_quantity)

                        if qty_to_return <= 0:
                            continue

                     
                        item.returned_quantity += qty_to_return
                        item.return_requested_quantity = 0

                      
                        total_active = item.quantity - item.cancelled_quantity
                        if item.returned_quantity >= total_active:
                            item.status = "returned"
                        else:
                            item.status = "ordered"

                        if reason:
                            item.return_reason = reason
                        item.save()

                        if item.variant:
                            item.variant.stock += qty_to_return
                            item.variant.save()

                        effective_price = item.unit_price * (1 - discount_ratio)
                        item_refund = qty_to_return * effective_price
                        refund_total += item_refund
                        total_returned_qty += qty_to_return
                        returned_subtotal += item.unit_price * qty_to_return

                    all_active_returned = all(
                        (i.quantity - i.cancelled_quantity - i.returned_quantity) <= 0
                        for i in all_items
                    )

                    if all_active_returned and order.shipping_charge > 0:
                        refund_total += order.shipping_charge

                    refund_total = round(refund_total, 2)

                    if refund_total > 0 and order.payment_status in ["paid", "partial_refund"]:
                        from user.wallet.utils import refund_to_wallet

                        refund_to_wallet(
                            order.user,
                            refund_total,
                            f"Refund for {total_returned_qty} returned item(s) in Order #{order.order_id}",
                        )

                    
                    new_subtotal = max(0, order.subtotal - returned_subtotal)
                    new_discount = round(new_subtotal * discount_ratio, 2)
                    new_shipping = 0 if all_active_returned else order.shipping_charge
                    new_total = max(0, new_subtotal + new_shipping - new_discount)

                    order.subtotal = new_subtotal
                    order.discount = new_discount
                    order.shipping_charge = new_shipping
                    order.total = new_total

                    has_active_items = any(
                        (i.quantity - i.cancelled_quantity - i.returned_quantity) > 0
                        for i in all_items
                    )
                    if has_active_items:
                        # Partial return — order continues as delivered, payment stays paid
                        order.status = "delivered"
                        order.payment_status = "paid"
                    else:
                        order.status = "returned"
                        order.payment_status = "refunded"

            elif new_status == "return_rejected":
                reason = request.POST.get("reason", "").strip()
                if reason:
                    order.return_reason = f"Rejected: {reason}"

                with transaction.atomic():
                    for item in order.items.all():
                        if item.status == "return_requested" or item.return_requested_quantity > 0:
                            item.return_requested_quantity = 0
                            total_active = item.quantity - item.cancelled_quantity
                            if item.returned_quantity >= total_active and total_active > 0:
                                item.status = "returned"
                            elif item.returned_quantity > 0:
                                item.status = "ordered"
                            else:
                                item.status = "return_rejected"
                            if reason:
                                item.return_reason = f"Rejected: {reason}"
                            item.save()

                    all_items = list(order.items.all())
                    has_active_items = any(
                        (i.quantity - i.cancelled_quantity - i.returned_quantity) > 0
                        for i in all_items
                    )
                    if has_active_items:
                        order.status = "delivered"
                    else:
                        order.status = "return_rejected"

            order.save()
            messages.success(
                request,
                f"Order #{order.order_id} updated to {order.get_status_display()}.",
            )
        else:
            status_labels = dict(Order.STATUS_CHOICES)
            cur_label = order.get_status_display()
            new_label = status_labels.get(new_status, new_status)
            messages.error(
                request,
                f"Cannot transition status from '{cur_label}' " f"to '{new_label}'.",
            )

    next_url = request.POST.get("next", "admin_orders")
    if next_url == "detail":
        return redirect("admin_order_detail", order_id=order_id)
    return redirect("admin_orders")
