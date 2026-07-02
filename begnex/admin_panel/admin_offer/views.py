from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from admin_panel.admin_category.models import Category
from admin_panel.admin_product.models import Product

from .models import CategoryOffer, ProductOffer


@never_cache
@staff_member_required(login_url="admin_login")
def admin_offer_list_view(request):
    product_offers = ProductOffer.objects.select_related("product").all()
    category_offers = CategoryOffer.objects.select_related("category").all()

    products = Product.objects.filter(is_deleted=False, is_active=True)
    categories = Category.objects.filter(is_deleted=False, is_active=True)

    context = {
        "product_offers": product_offers,
        "category_offers": category_offers,
        "products": products,
        "categories": categories,
        "today": timezone.now().date(),
    }
    return render(request, "offers.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_offer_create_view(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        discount_percentage = request.POST.get("discount_percentage", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not product_id:
            errors.append("Product is required.")
        else:
            product = get_object_or_404(Product, id=product_id)

        if not discount_percentage:
            errors.append("Discount percentage is required.")
        else:
            try:
                pct = int(discount_percentage)
                if pct < 1 or pct > 99:
                    errors.append("Percentage must be between 1 and 99.")
            except ValueError:
                errors.append("Percentage must be a whole number.")

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

        if not errors:
            overlapping = (
                ProductOffer.objects.filter(product=product, is_active=True)
                .filter(
                    models.Q(valid_from__lte=valid_until, valid_until__gte=valid_from)
                )
                .exists()
            )
            if overlapping:
                errors.append(
                    f"An active offer already overlaps with this date range for product '{product.name}'."
                )

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            ProductOffer.objects.create(
                product=product,
                discount_percentage=pct,
                is_active=is_active,
                valid_from=valid_from,
                valid_until=valid_until,
            )
            messages.success(request, "Product offer created successfully!")

    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_offer_create_view(request):
    if request.method == "POST":
        category_id = request.POST.get("category_id")
        discount_percentage = request.POST.get("discount_percentage", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not category_id:
            errors.append("Category is required.")
        else:
            category = get_object_or_404(Category, id=category_id)

        if not discount_percentage:
            errors.append("Discount percentage is required.")
        else:
            try:
                pct = int(discount_percentage)
                if pct < 1 or pct > 99:
                    errors.append("Percentage must be between 1 and 99.")
            except ValueError:
                errors.append("Percentage must be a whole number.")

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

        if not errors:
            overlapping = (
                CategoryOffer.objects.filter(category=category, is_active=True)
                .filter(
                    models.Q(valid_from__lte=valid_until, valid_until__gte=valid_from)
                )
                .exists()
            )
            if overlapping:
                errors.append(
                    f"An active offer already overlaps with this date range for category '{category.name}'."
                )

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            CategoryOffer.objects.create(
                category=category,
                discount_percentage=pct,
                is_active=is_active,
                valid_from=valid_from,
                valid_until=valid_until,
            )
            messages.success(request, "Category offer created successfully!")

    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_offer_edit_view(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        discount_percentage = request.POST.get("discount_percentage", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not product_id:
            errors.append("Product is required.")
        else:
            product = get_object_or_404(Product, id=product_id)

        if not discount_percentage:
            errors.append("Discount percentage is required.")
        else:
            try:
                pct = int(discount_percentage)
                if pct < 1 or pct > 99:
                    errors.append("Percentage must be between 1 and 99.")
            except ValueError:
                errors.append("Percentage must be a whole number.")

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

        if not errors:
            overlapping = (
                ProductOffer.objects.filter(product=product, is_active=True)
                .exclude(id=offer_id)
                .filter(
                    models.Q(valid_from__lte=valid_until, valid_until__gte=valid_from)
                )
                .exists()
            )
            if overlapping:
                errors.append(
                    f"An active offer already overlaps with this date range for product '{product.name}'."
                )

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            offer.product = product
            offer.discount_percentage = pct
            offer.valid_from = valid_from
            offer.valid_until = valid_until
            offer.is_active = is_active
            offer.save()
            messages.success(request, "Product offer updated successfully!")

    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_offer_edit_view(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    if request.method == "POST":
        category_id = request.POST.get("category_id")
        discount_percentage = request.POST.get("discount_percentage", "").strip()
        valid_from = request.POST.get("valid_from", "").strip()
        valid_until = request.POST.get("valid_until", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not category_id:
            errors.append("Category is required.")
        else:
            category = get_object_or_404(Category, id=category_id)

        if not discount_percentage:
            errors.append("Discount percentage is required.")
        else:
            try:
                pct = int(discount_percentage)
                if pct < 1 or pct > 99:
                    errors.append("Percentage must be between 1 and 99.")
            except ValueError:
                errors.append("Percentage must be a whole number.")

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

        if not errors:
            overlapping = (
                CategoryOffer.objects.filter(category=category, is_active=True)
                .exclude(id=offer_id)
                .filter(
                    models.Q(valid_from__lte=valid_until, valid_until__gte=valid_from)
                )
                .exists()
            )
            if overlapping:
                errors.append(
                    f"An active offer already overlaps with this date range for category '{category.name}'."
                )

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            offer.category = category
            offer.discount_percentage = pct
            offer.valid_from = valid_from
            offer.valid_until = valid_until
            offer.is_active = is_active
            offer.save()
            messages.success(request, "Category offer updated successfully!")

    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_offer_delete_view(request, offer_id):
    if request.method == "POST":
        offer = get_object_or_404(ProductOffer, id=offer_id)
        prod_name = offer.product.name
        offer.delete()
        messages.success(request, f"Offer for '{prod_name}' deleted successfully.")
    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_offer_delete_view(request, offer_id):
    if request.method == "POST":
        offer = get_object_or_404(CategoryOffer, id=offer_id)
        cat_name = offer.category.name
        offer.delete()
        messages.success(
            request, f"Offer for category '{cat_name}' deleted successfully."
        )
    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_offer_toggle_view(request, offer_id):
    if request.method == "POST":
        offer = get_object_or_404(ProductOffer, id=offer_id)
        offer.is_active = not offer.is_active
        offer.save()
        status = "activated" if offer.is_active else "deactivated"
        messages.success(request, f"Offer for '{offer.product.name}' {status}.")
    return redirect("admin_offers")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_offer_toggle_view(request, offer_id):
    if request.method == "POST":
        offer = get_object_or_404(CategoryOffer, id=offer_id)
        offer.is_active = not offer.is_active
        offer.save()
        status = "activated" if offer.is_active else "deactivated"
        messages.success(
            request, f"Offer for category '{offer.category.name}' {status}."
        )
    return redirect("admin_offers")


from decimal import Decimal

from .models import ReferralOffer, ReferralRecord


@never_cache
@staff_member_required(login_url="admin_login")
def admin_referrals_view(request):
    config, _ = ReferralOffer.objects.get_or_create(
        id=1,
        defaults={
            "referrer_reward": Decimal("100.00"),
            "referee_reward": Decimal("50.00"),
            "is_active": True,
        },
    )
    records = (
        ReferralRecord.objects.select_related("referrer", "referee")
        .all()
        .order_by("-created_at")
    )

    total_referrals = records.count()
    total_payout = sum(r.referrer_reward_paid + r.referee_reward_paid for r in records)

    context = {
        "config": config,
        "records": records,
        "total_referrals": total_referrals,
        "total_payout": total_payout,
    }
    return render(request, "referrals.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_referral_offer_save_view(request):
    if request.method == "POST":
        referrer_reward = request.POST.get("referrer_reward", "").strip()
        referee_reward = request.POST.get("referee_reward", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []
        try:
            ref_amt = Decimal(referrer_reward)
            if ref_amt < 0:
                errors.append("Referrer reward amount must be 0 or greater.")
        except (ValueError, TypeError, ArithmeticError):
            errors.append("Invalid Referrer reward amount.")

        try:
            refee_amt = Decimal(referee_reward)
            if refee_amt < 0:
                errors.append("Referee reward amount must be 0 or greater.")
        except (ValueError, TypeError, ArithmeticError):
            errors.append("Invalid Referee reward amount.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            config, _ = ReferralOffer.objects.get_or_create(id=1)
            config.referrer_reward = ref_amt
            config.referee_reward = refee_amt
            config.is_active = is_active
            config.save()
            messages.success(request, "Referral settings updated successfully!")

    return redirect("admin_referrals")
