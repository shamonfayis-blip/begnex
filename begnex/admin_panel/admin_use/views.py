from datetime import date, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

User = get_user_model()


@never_cache
def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin_dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return redirect("admin_login")

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with that email.")
            return redirect("admin_login")

        user = authenticate(
            request, username=user_obj.username, password=password
        )

        if user is not None and user.is_staff:
            login(request, user)
            return redirect("admin_dashboard")
        elif user is not None and not user.is_staff:
            messages.error(request, "You do not have admin access.")
            return redirect("admin_login")
        else:
            messages.error(request, "Incorrect password. Please try again.")
            return redirect("admin_login")

    return render(request, "admin_use/admin_login.html")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_dashboard_view(request):
    from admin_panel.admin_order.models import Order, OrderItem
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import date, timedelta
    from django.db.models.functions import TruncDate, TruncMonth

    total_users = User.objects.filter(is_staff=False).count()
    
   
    active_orders = Order.objects.exclude(status="cancelled")
    
    total_revenue = active_orders.aggregate(r=Sum("total"))["r"] or 0
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    
    
    chart_filter = request.GET.get("chart_filter", "monthly") # yearly, monthly, weekly
    today = timezone.now().date()
    
    labels = []
    values = []
    
    if chart_filter == "weekly":
      
        start_date = today - timedelta(days=6)
        daily_stats = (
            active_orders.filter(created_at__date__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("total"))
            .order_by("day")
        )
        daily_map = {row["day"]: row["total"] for row in daily_stats}
        for i in range(7):
            d = start_date + timedelta(days=i)
            labels.append(d.strftime("%a")) # Mon, Tue, etc.
            values.append(float(daily_map.get(d, 0) or 0))
            
    elif chart_filter == "monthly":
        
        start_date = today - timedelta(days=29)
        daily_stats = (
            active_orders.filter(created_at__date__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("total"))
            .order_by("day")
        )
        daily_map = {row["day"]: row["total"] for row in daily_stats}
        for i in range(30):
            d = start_date + timedelta(days=i)
            labels.append(d.strftime("%d %b"))
            values.append(float(daily_map.get(d, 0) or 0))
            
    elif chart_filter == "yearly":
       
        start_date = date(today.year - 1, today.month, 1)
        monthly_stats = (
            active_orders.filter(created_at__date__gte=start_date)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Sum("total"))
            .order_by("month")
        )
        monthly_map = {row["month"]: row["total"] for row in monthly_stats}
        for i in range(12):
            m = (today.month - 11 + i - 1) % 12 + 1
            y = today.year if m <= today.month else today.year - 1
            d = date(y, m, 1)
            labels.append(d.strftime("%b %y"))
            values.append(float(monthly_map.get(d, 0) or 0))

    best_products = (
        OrderItem.objects.exclude(order__status="cancelled")
        .values("product_name", "variant__product__category__name")
        .annotate(qty=Sum("quantity"), rev=Sum("subtotal"))
        .order_by("-qty")[:10]
    )
   
    best_categories = (
        OrderItem.objects.exclude(order__status="cancelled")
        .values("variant__product__category__name")
        .annotate(qty=Sum("quantity"), rev=Sum("subtotal"))
        .order_by("-qty")[:10]
    )
    
    
    recent_activity = []
    recent_orders = Order.objects.order_by("-created_at")[:5]
    for o in recent_orders:
        recent_activity.append({
            "title": f"Order #{o.order_id} placed",
            "subtitle": f"Amount: Rs. {o.total:.2f} | Status: {o.status.upper()}",
            "time": o.created_at,
            "type": "order"
        })
        
    recent_users = User.objects.filter(is_staff=False).order_by("-date_joined")[:3]
    for u in recent_users:
        recent_activity.append({
            "title": f"User {u.username} registered",
            "subtitle": u.email,
            "time": u.date_joined,
            "type": "user"
        })
        
    recent_activity.sort(key=lambda x: x["time"], reverse=True)
    recent_activity = recent_activity[:6]

 
    for act in recent_activity:
        act["time_display"] = act["time"].strftime("%Y-%m-%d %H:%M")

    context = {
        "total_users": total_users,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
      
        "chart_labels": labels,
        "chart_values": values,
        "chart_filter": chart_filter,
     
        "best_products": best_products,
        "best_categories": best_categories,
       
        "recent_activity": recent_activity,
    }
    return render(request, "admin_use/admin_dashboard.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_user_list_view(request):
    search_query = request.GET.get("q", "").strip()

    users = User.objects.filter(is_staff=False).order_by("-date_joined")

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    paginator = Paginator(users, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "admin_use/admin_users.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "total_users": users.count(),
        },
    )


@never_cache
@staff_member_required(login_url="admin_login")
def toggle_block_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id, is_staff=False)
        user.is_blocked = not user.is_blocked
        user.save()
        action = "blocked" if user.is_blocked else "unblocked"
        messages.success(request, f'User "{user.username}" has been {action}.')
    return redirect("admin_user_list")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_user_detail_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id, is_staff=False)
    from admin_panel.admin_order.models import Order
    from admin_panel.admin_product.models import Review
    from django.db.models import Sum, Count

    orders = Order.objects.filter(user=target_user).order_by("-created_at")
    order_stats = orders.aggregate(
        total_spent=Sum("total"),
        order_count=Count("id"),
    )
    reviews = Review.objects.filter(user=target_user).select_related("product").order_by("-created_at")

    context = {
        "target_user": target_user,
        "orders": orders[:10],
        "order_count": order_stats["order_count"] or 0,
        "total_spent": order_stats["total_spent"] or 0,
        "reviews": reviews,
    }
    return render(request, "admin_use/admin_user.html", context)


@never_cache
def admin_logout_view(request):
    logout(request)
    return redirect("admin_login")


@never_cache
@staff_member_required(login_url="admin_login")
def sales_report_view(request):
    from admin_panel.admin_order.models import Order

  
    filter_type = request.GET.get("filter", "daily")
    today = date.today()

    if filter_type == "daily":
        date_from = today
        date_to = today
    elif filter_type == "weekly":
        date_from = today - timedelta(days=6)
        date_to = today
    elif filter_type == "yearly":
        date_from = date(today.year, 1, 1)
        date_to = today
    elif filter_type == "custom":
        try:
            date_from = date.fromisoformat(request.GET.get("date_from", ""))
            date_to   = date.fromisoformat(request.GET.get("date_to",   ""))
        except (ValueError, TypeError):
            date_from = today
            date_to   = today
    else:
        date_from = today
        date_to   = today

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    
    orders_qs = Order.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).exclude(status="cancelled")

 
    agg = orders_qs.aggregate(
        total_sales=Sum("total"),
        total_subtotal=Sum("subtotal"),
        total_discount=Sum("discount"),
        total_shipping=Sum("shipping_charge"),
        order_count=Count("id"),
    )
    total_sales    = agg["total_sales"]    or 0
    total_subtotal = agg["total_subtotal"] or 0
    total_discount = agg["total_discount"] or 0
    total_shipping = agg["total_shipping"] or 0
    order_count    = agg["order_count"]    or 0

    avg_order_value = (total_sales / order_count) if order_count else 0


    payment_breakdown = (
        orders_qs.values("payment_method")
        .annotate(count=Count("id"), revenue=Sum("total"))
        .order_by("-revenue")
    )


    status_breakdown = (
        orders_qs.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


    daily_data_qs = (
        orders_qs
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            day_total=Sum("total"),
            day_orders=Count("id"),
            day_discount=Sum("discount"),
        )
        .order_by("day")
    )

   
    delta = (date_to - date_from).days + 1
    all_dates = [date_from + timedelta(days=i) for i in range(delta)]
    daily_map = {row["day"]: row for row in daily_data_qs}
    daily_chart = []
    for d in all_dates:
        row = daily_map.get(d, {})
        daily_chart.append({
            "date":     d.strftime("%d %b"),
            "total":    float(row.get("day_total",    0) or 0),
            "orders":   int(row.get("day_orders",   0) or 0),
            "discount": float(row.get("day_discount", 0) or 0),
        })

  
    recent_orders = orders_qs.select_related("user").order_by("-created_at")

   
    export_format = request.GET.get("export")
    if export_format == "csv":
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="sales_report_{filter_type}_{date_from}_to_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Order ID", "Date", "Customer", "Email", "Payment Method", "Status", "Subtotal", "Discount", "Total"])
        for order in recent_orders:
            writer.writerow([
                order.order_id,
                order.created_at.strftime("%Y-%m-%d %H:%M"),
                order.user.get_full_name() if order.user else "Guest",
                order.user.email if order.user else "",
                order.payment_method.upper(),
                order.status.upper(),
                order.subtotal,
                order.discount,
                order.total
            ])
        return response
    elif export_format == "pdf":
        from io import BytesIO
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name='TitleStyle',
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#111827'),
            alignment=1, 
        )
        subtitle_style = ParagraphStyle(
            name='SubtitleStyle',
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#6B7280'),
            alignment=1, 
        )
        section_style = ParagraphStyle(
            name='SectionStyle',
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#111827'),
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            name='BodyStyle',
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#374151'),
        )
        header_cell_style = ParagraphStyle(
            name='HeaderCellStyle',
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.white,
        )
        
        story = []
        
        story.append(Paragraph("Begnex Admin Sales Report", title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Period: {date_from.strftime('%d %b %Y')} to {date_to.strftime('%d %b %Y')} ({filter_type.capitalize()})", subtitle_style))
        story.append(Spacer(1, 20))
        
     
        summary_data = [
            ["Gross Sales", "Total Discount", "Shipping Charge", "Net Revenue", "Total Orders"],
            [
                f"Rs. {total_subtotal:,.2f}",
                f"- Rs. {total_discount:,.2f}",
                f"Rs. {total_shipping:,.2f}",
                f"Rs. {total_sales:,.2f}",
                str(order_count)
            ]
        ]
        summary_table = Table(summary_data, colWidths=[108, 108, 108, 108, 108])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#374151')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,1), (-1,1), 11),
            ('TEXTCOLOR', (3,1), (3,1), colors.HexColor('#059669')),
            ('TEXTCOLOR', (1,1), (1,1), colors.HexColor('#DC2626')),
        ]))
        
        story.append(Paragraph("Executive Summary", section_style))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
       
        story.append(Paragraph("Orders List", section_style))
        
        table_headers = [
            Paragraph("Order ID", header_cell_style),
            Paragraph("Date", header_cell_style),
            Paragraph("Customer", header_cell_style),
            Paragraph("Payment", header_cell_style),
            Paragraph("Status", header_cell_style),
            Paragraph("Subtotal", header_cell_style),
            Paragraph("Discount", header_cell_style),
            Paragraph("Total", header_cell_style),
        ]
        orders_data = [table_headers]
        
        for order in recent_orders:
            cust_name = order.user.get_full_name() or order.user.username
            cust_info = f"{cust_name}<br/>{order.user.email}"
            orders_data.append([
                Paragraph(f"#{order.order_id}", body_style),
                Paragraph(order.created_at.strftime("%d %b %Y %H:%M"), body_style),
                Paragraph(cust_info, body_style),
                Paragraph(order.payment_method.upper(), body_style),
                Paragraph(order.status.upper(), body_style),
                Paragraph(f"Rs. {order.subtotal:,.2f}", body_style),
                Paragraph(f"- Rs. {order.discount:,.2f}" if order.discount else "Rs. 0.00", body_style),
                Paragraph(f"Rs. {order.total:,.2f}", body_style),
            ])
            
        orders_table = Table(orders_data, colWidths=[65, 75, 110, 50, 60, 60, 60, 60])
        orders_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#111827')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        
        story.append(orders_table)
        
        doc.build(story)
        
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{filter_type}_{date_from}_to_{date_to}.pdf"'
        response.write(pdf)
        return response

    paginator  = Paginator(recent_orders, 15)
    page_obj   = paginator.get_page(request.GET.get("page"))

    context = {
       
        "filter_type": filter_type,
        "date_from":   date_from.isoformat(),
        "date_to":     date_to.isoformat(),
        "date_from_display": date_from.strftime("%d %b %Y"),
        "date_to_display":   date_to.strftime("%d %b %Y"),
      
        "total_sales":     total_sales,
        "total_subtotal":  total_subtotal,
        "total_discount":  total_discount,
        "total_shipping":  total_shipping,
        "order_count":     order_count,
        "avg_order_value": avg_order_value,
     
        "payment_breakdown": payment_breakdown,
        "status_breakdown":  status_breakdown,
       
        "daily_chart": daily_chart,
        "page_obj":    page_obj,
    }
    return render(request, "admin_use/sales_report.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_reviews_view(request):
    from admin_panel.admin_product.models import Review
    from django.db.models import Q

    search_query = request.GET.get("q", "").strip()
    rating_filter = request.GET.get("rating", "").strip()

    reviews = Review.objects.select_related("product", "user").order_by("-created_at")

    if search_query:
        reviews = reviews.filter(
            Q(product__name__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(comment__icontains=search_query)
        )

    if rating_filter:
        try:
            reviews = reviews.filter(rating=int(rating_filter))
        except ValueError:
            pass

    paginator = Paginator(reviews, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "rating_filter": rating_filter,
        "total_reviews": reviews.count(),
    }
    return render(request, "admin_use/admin_reviews.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_review_delete_view(request, review_id):
    from admin_panel.admin_product.models import Review
    if request.method == "POST":
        review = get_object_or_404(Review, id=review_id)
        review.delete()
        messages.success(request, "Review deleted successfully.")
    return redirect("admin_reviews")
