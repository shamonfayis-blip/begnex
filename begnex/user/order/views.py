from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator

from admin_panel.admin_order.models import Order, OrderItem


from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


@login_required(login_url="login")
def order_list_view(request):
    
    search_query = request.GET.get("q", "").strip()
    orders = (
        Order.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at"))

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()
                                        
    paginator = Paginator(orders, 5) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "order/order_list.html",
        {"orders": page_obj, "search_query": search_query},
    )


@login_required(login_url="login")
def order_detail_view(request, order_pk):

    order = get_object_or_404(Order, pk=order_pk, user=request.user)
#status 
    steps = [
        {"code": "pending", "label": "Order Placed", "icon": "fa-receipt"},
        {
            "code": "shipped",
            "label": "Shipped",
            "icon": "fa-truck-ramp-box",
        },
        {
            "code": "out_for_delivery",
            "label": "Out for Delivery",
            "icon": "fa-truck-fast",
        },
        {"code": "delivered", "label": "Delivered", "icon": "fa-circle-check"},
    ]

    current_status = order.status
    current_step_index = 0
    is_cancelled = current_status == "cancelled"
    is_return_requested = current_status == "return_requested"
    is_returned = current_status == "returned"
    is_return_rejected = current_status == "return_rejected"

    if not (is_cancelled or is_return_requested or is_returned or is_return_rejected):
        for idx, step in enumerate(steps):
            if step["code"] == current_status:
                current_step_index = idx
                break

   
    can_cancel = order.status == "pending"
   
    can_return = (
        order.status == "delivered"
        or order.status == "return_requested"
    )

    items = []
    for item in order.items.all():
        item.active_qty = item.quantity - item.cancelled_quantity
        item.return_pending_qty = (
            item.active_qty - item.return_requested_quantity
        )
        item.can_return_item = (
            item.status == "ordered"
            and item.return_pending_qty > 0
            and order.status in ["delivered", "return_requested"]
        )
        items.append(item)

    context = {
        "order": order,
        "items": items,
        "steps": steps,
        "current_step_index": current_step_index,
        "is_cancelled": is_cancelled,
        "is_return_requested": is_return_requested,
        "is_returned": is_returned,
        "is_return_rejected": is_return_rejected,
        "can_cancel": can_cancel,
        "can_return": can_return,
    }
    return render(request, "order/order_detail.html", context)


@login_required(login_url="login")
@require_POST
def cancel_order(request, order_pk):
    
    order = get_object_or_404(Order, pk=order_pk, user=request.user)

    if order.status != "pending":
        messages.error(request, "This order cannot be cancelled.")
        return redirect("user_order_detail", order_pk=order.pk)

    reason = request.POST.get("cancel_reason", "").strip()

    try:
        with transaction.atomic():
            refund_amount = order.total
            order.status = "cancelled"
            order.cancel_reason = reason or "Cancelled by user"
            order.subtotal = 0
            order.discount = 0
            order.shipping_charge = 0
            order.total = 0
            order.save()

            for item in order.items.all():
                if item.status == "ordered":
                    
                    active_qty = item.quantity - item.cancelled_quantity
                    item.cancelled_quantity = item.quantity  # mark all cancelled
                    item.status = "cancelled"
                    item.cancel_reason = reason or "Cancelled by user"
                    item.save()

                    if item.variant and active_qty > 0:
                        item.variant.stock += active_qty
                        item.variant.save()

            # Process refund if order is paid
            if order.payment_status == "paid":
                from user.wallet.utils import refund_to_wallet
                refund_to_wallet(request.user, refund_amount, f"Refund for cancelled Order #{order.order_id}")
                order.payment_status = "refunded"
                order.save()

        messages.success(
            request,
            f"Order #{order.order_id} has been cancelled successfully.",
        )
    except Exception as e:
        messages.error(
            request, f"Error occurred during cancellation: {str(e)}"
        )

    return redirect("user_order_detail", order_pk=order.pk)


@login_required(login_url="login")
@require_POST
def cancel_order_item(request, item_pk):
   
    item = get_object_or_404(OrderItem, pk=item_pk, order__user=request.user)
    order = item.order

    if order.status != "pending" or item.status != "ordered":
        messages.error(request, "This product cannot be cancelled.")
        return redirect("user_order_detail", order_pk=order.pk)

    reason = request.POST.get("cancel_reason", "").strip()

    active_qty = item.quantity - item.cancelled_quantity

    try:
        cancel_qty = int(request.POST.get("cancel_quantity", active_qty))
    except (ValueError, TypeError):
        cancel_qty = active_qty
    cancel_qty = max(1, min(cancel_qty, active_qty))  #clamp limit

    try:
        with transaction.atomic():
            old_total = order.total
            item.cancelled_quantity += cancel_qty
            item.cancel_reason = reason or "Cancelled by user"

            if item.cancelled_quantity >= item.quantity:
               
                item.status = "cancelled"

            item.save()

            
            if item.variant:
                item.variant.stock += cancel_qty #RESTORE
                item.variant.save()

           
            all_items = order.items.all()
            active_items = [
                i for i in all_items
                if i.quantity - i.cancelled_quantity > 0
            ] 

            if not active_items:
                order.status = "cancelled"
                order.cancel_reason = "All products cancelled"
                order.subtotal = 0
                order.discount = 0
                order.shipping_charge = 0
                order.total = 0
            else:
                
                original_subtotal = sum(
                    i.unit_price * i.quantity for i in all_items
                )
                discount_ratio = (
                    order.discount / original_subtotal
                    if original_subtotal > 0 else 0
                )
                new_subtotal = sum(
                    i.unit_price * (i.quantity - i.cancelled_quantity)
                    for i in active_items
                )
                new_discount = new_subtotal * discount_ratio
                new_shipping = 0

                order.subtotal = new_subtotal
                order.discount = new_discount
                order.shipping_charge = new_shipping
                order.total = max(0, new_subtotal + new_shipping - new_discount)

            order.save()

            # Process refund if order is paid and total decreased
            refund_amount = old_total - order.total
            if refund_amount > 0 and order.payment_status == "paid":
                from user.wallet.utils import refund_to_wallet
                refund_to_wallet(request.user, refund_amount, f"Refund for cancelled units of {item.product_name} in Order #{order.order_id}")
                if not active_items:
                    order.payment_status = "refunded"
                    order.save()

        if cancel_qty == active_qty:
            messages.success(
                request,
                f"All units of '{item.product_name}' cancelled successfully."
            )
        else:
            messages.success(
                request,
                f"{cancel_qty} unit(s) of '{item.product_name}' cancelled. "
                f"{active_qty - cancel_qty} unit(s) remain active."
            )
    except Exception as e:
        messages.error(request, f"Error occurred: {str(e)}")

    return redirect("user_order_detail", order_pk=order.pk)


@login_required(login_url="login")
@require_POST
def return_order(request, order_pk):
    
    order = get_object_or_404(Order, pk=order_pk, user=request.user)

    if order.status != "delivered":
        messages.error(request, "Only delivered orders can be returned.")
        return redirect("user_order_detail", order_pk=order.pk)

    reason = request.POST.get("return_reason", "").strip()
    if not reason:
        messages.error(request, "Reason for return is mandatory.")
        return redirect("user_order_detail", order_pk=order.pk)

    try:
        with transaction.atomic():
            order.status = "return_requested"
            order.return_reason = reason
            order.save()

            for item in order.items.all():
                if item.status == "ordered":
                    active_qty = item.quantity - item.cancelled_quantity
                    item.return_requested_quantity = active_qty
                    item.status = "return_requested"
                    item.return_reason = reason
                    item.save()

        messages.success(
            request,
            f"Return request for Order #{order.order_id} submitted successfully.",
        )
    except Exception as e:
        messages.error(request, f"Error submitting return request: {str(e)}")

    return redirect("user_order_detail", order_pk=order.pk)


@login_required(login_url="login")
@require_POST
def return_order_item(request, item_pk):

    item = get_object_or_404(OrderItem, pk=item_pk, order__user=request.user)

    order = item.order

    if order.status not in ["delivered", "return_requested"] or item.status != "ordered":
        messages.error(request, "This product cannot be returned.")
        return redirect("user_order_detail", order_pk=order.pk)

    reason = request.POST.get("return_reason", "").strip()
    if not reason:
        messages.error(request, "Reason for return is mandatory.")
        return redirect("user_order_detail", order_pk=order.pk)

    
    active_qty = item.quantity - item.cancelled_quantity

    try:
        return_qty = int(request.POST.get("return_quantity", active_qty))
    except (ValueError, TypeError):
        return_qty = active_qty
    return_qty = max(1, min(return_qty, active_qty))  # safe range

    try:
        with transaction.atomic():
            item.return_requested_quantity += return_qty
            item.return_reason = reason

            if item.return_requested_quantity >= active_qty: #full return
                
                item.status = "return_requested"

            item.save()

           
            if order.status == "delivered":
                order.status = "return_requested"
                order.return_reason = f"Return requested for: {item.product_name}"
                order.save()

        if return_qty == active_qty:
            messages.success(
                request,
                f"Return request for all units of '{item.product_name}' submitted."
            )
        else:
            messages.success(
                request,
                f"Return request for {return_qty} unit(s) of "
                f"'{item.product_name}' submitted. "
                f"{active_qty - return_qty} unit(s) remain active."
            )
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

    return redirect("user_order_detail", order_pk=order.pk)


@login_required(login_url="login")
def download_invoice(request, order_pk):

    order = get_object_or_404(Order, pk=order_pk, user=request.user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Invoice_{order.order_id}.pdf"'
    )

   
    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#0F121C')
    )

    normal_style = ParagraphStyle(
        'InvoiceNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4A4A4A')
    )

    bold_style = ParagraphStyle(
        'InvoiceBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F121C')
    )


    story.append(Paragraph("BEGNEX INVOICE", title_style))
    story.append(Spacer(1, 15))


    meta_data = [
        [
            Paragraph(f"<b>Order ID:</b> #{order.order_id}", normal_style),
            Paragraph(
                f"<b>Date:</b> "
                f"{order.created_at.strftime('%d %b %Y, %I:%M %p')}",
                normal_style,
            )
        ],
        [
            Paragraph(f"<b>Payment Method:</b> {order.get_payment_method_display()}",
                      normal_style),
            Paragraph(
                f"<b>Payment Status:</b> "
                f"{order.get_payment_status_display()}",
                normal_style,
            )
        ],
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))


    addr_lines = order.address_line.split('\n')
    addr_html = (
        f"<b>Deliver To:</b><br/>"
        f"{order.full_name}<br/>"
        f"{'<br/>'.join(addr_lines)}<br/>"
        f"{order.city}, {order.state} - {order.pincode}<br/>"
        f"Phone: {order.phone}"
    )
    addr_data = [[Paragraph(addr_html, normal_style)]]
    addr_table = Table(addr_data, colWidths=[520])
    addr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F4F5F7')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 20))


    table_data = [
        [
            Paragraph("<b>Product Name</b>", bold_style),
            Paragraph("<b>Variant</b>", bold_style),
            Paragraph("<b>SKU</b>", bold_style),
            Paragraph("<b>Qty</b>", bold_style),
            Paragraph("<b>Unit Price</b>", bold_style),
            Paragraph("<b>Subtotal</b>", bold_style)
        ]
    ]

    for item in order.items.all():
        name_p = item.product_name
        if item.status != "ordered":
            name_p += f" ({item.get_status_display()})"

        table_data.append([
            Paragraph(name_p, normal_style),
            Paragraph(item.variant_name, normal_style),
            Paragraph(item.sku or "-", normal_style),
            Paragraph(str(item.quantity), normal_style),
            Paragraph(f"INR {item.unit_price}", normal_style),
            Paragraph(f"INR {item.subtotal}", normal_style)
        ])

    items_table = Table(table_data, colWidths=[180, 80, 80, 30, 75, 75])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ECEFF1')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#CFD8DC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))

    
    totals_data = [
        [
            Paragraph("", normal_style),
            Paragraph("<b>Items Subtotal:</b>", normal_style),
            Paragraph(f"INR {order.subtotal}", normal_style),
        ],
        [
            Paragraph("", normal_style),
            Paragraph("<b>Shipping Charge:</b>", normal_style),
            Paragraph(
                "FREE" if order.shipping_charge == 0
                else f"INR {order.shipping_charge}",
                normal_style,
            ),
        ],
    ]
    if order.discount > 0:
        totals_data.append([
            Paragraph("", normal_style),
            Paragraph("<b>Discount:</b>", normal_style),
            Paragraph(f"-INR {order.discount}", normal_style),
        ])

    totals_data.append([
        Paragraph("", normal_style),
        Paragraph("<b>Grand Total:</b>", bold_style),
        Paragraph(f"INR {order.total}", bold_style),
    ])

    totals_table = Table(totals_data, colWidths=[320, 100, 100])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_table)


    doc.build(story)
    return response
