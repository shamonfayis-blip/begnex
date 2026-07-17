import base64
import os
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from admin_panel.admin_product.models import Product

from .models import Category


def _save_base64_image(b64_string):
    """Decode a base64 data-URL and return a Django ContentFile."""
    from django.core.files.base import ContentFile

    if not b64_string or ";base64," not in b64_string:
        return None
    _, imgstr = b64_string.split(";base64,", 1)
    filename = f"cat_{uuid.uuid4().hex}.jpg"
    return ContentFile(base64.b64decode(imgstr), name=filename)


def generate_category_id():
    last = Category.objects.order_by("-id").first()
    if last:
        try:
            num = int(last.category_id.split("-")[-1]) + 1

        except (ValueError, IndexError):
            num = Category.objects.count() + 1

    else:
        num = 1
    return f"CAT-{num:03d}"


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_list_view(request):

    search_query = request.GET.get("q", "").strip()
    categories = Category.objects.filter(is_deleted=False).order_by("-id")

    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) | Q(category_id__icontains=search_query)
        )

    total_categories = Category.objects.filter(is_deleted=False).count()

    active_categories = Category.objects.filter(
        is_deleted=False, is_active=True
    ).count()
    inactive_categories = Category.objects.filter(
        is_deleted=False, is_active=False
    ).count()

    paginator = Paginator(categories, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "total_categories": total_categories,
        "active_categories": active_categories,
        "inactive_categories": inactive_categories,
    }
    return render(request, "categories.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_add_view(request):

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active", "true") == "true"
        image = request.FILES.get("image")
        if not image:
            image = _save_base64_image(request.POST.get("image_base64", ""))

        error = None

        if not name:
            error = "Category name is required."
        elif len(name) < 2:
            error = "Category name must be at least 2 characters."
        elif len(name) > 100:
            error = "Category name cannot exceed 100 characters."
        elif not any(c.isalpha() for c in name):
            error = "Category name must contain at least one letter."
        elif Category.objects.filter(name__iexact=name, is_deleted=False).exists():
            error = f'Category "{name}" already exists.'
        else:
            ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
            if (
                image
                and hasattr(image, "content_type")
                and image.content_type not in ALLOWED_IMAGE_TYPES
            ):
                error = "Invalid image format. Only JPG, PNG, and WEBP are allowed."

        if error:
            # Re-render the page with the drawer open and form values preserved
            search_query = request.GET.get("q", "").strip()
            categories = Category.objects.filter(is_deleted=False).order_by("-id")
            total_categories = categories.count()
            active_categories = categories.filter(is_active=True).count()
            inactive_categories = categories.filter(is_active=False).count()
            paginator = Paginator(categories, 5)
            page_obj = paginator.get_page(request.GET.get("page"))
            context = {
                "page_obj": page_obj,
                "search_query": search_query,
                "total_categories": total_categories,
                "active_categories": active_categories,
                "inactive_categories": inactive_categories,
                # Add-form error state
                "add_form_error": error,
                "add_form_name": name,
                "add_form_description": description,
                "add_form_is_active": is_active,
            }
            return render(request, "categories.html", context)

        category_id = generate_category_id()
        Category.objects.create(
            name=name,
            category_id=category_id,
            description=description,
            is_active=is_active,
            image=image,
        )
        messages.success(request, f'Category "{name}" added successfully.')
        return redirect("admin_categories")

    return redirect("admin_categories")


@never_cache
@staff_member_required(login_url="admin_login")
def admin_category_edit_view(request, category_id):

    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active", "true") == "true"
        image = request.FILES.get("image")
        if not image:
            image = _save_base64_image(request.POST.get("image_base64", ""))
        clear_image = request.POST.get("clear_image") == "1"

        error = None

        if not name:
            error = "Category name is required."
        elif len(name) < 2:
            error = "Category name must be at least 2 characters."
        elif len(name) > 100:
            error = "Category name cannot exceed 100 characters."
        elif not any(c.isalpha() for c in name):
            error = "Category name must contain at least one letter."
        elif (
            Category.objects.filter(name__iexact=name, is_deleted=False)
            .exclude(id=category.id)
            .exists()
        ):
            error = f'Category "{name}" already exists.'
        else:
            ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
            if (
                image
                and hasattr(image, "content_type")
                and image.content_type not in ALLOWED_IMAGE_TYPES
            ):
                error = "Invalid image format. Only JPG, PNG, and WEBP are allowed."

        if error:
            # Re-render the page with the edit drawer open and form values preserved
            search_query = request.GET.get("q", "").strip()
            categories = Category.objects.filter(is_deleted=False).order_by("-id")
            total_categories = categories.count()
            active_categories = categories.filter(is_active=True).count()
            inactive_categories = categories.filter(is_active=False).count()
            paginator = Paginator(categories, 5)
            page_obj = paginator.get_page(request.GET.get("page"))
            context = {
                "page_obj": page_obj,
                "search_query": search_query,
                "total_categories": total_categories,
                "active_categories": active_categories,
                "inactive_categories": inactive_categories,
                # Edit-form error state
                "edit_form_error": error,
                "edit_form_category_id": category.id,
                "edit_form_name": name,
                "edit_form_description": description,
                "edit_form_is_active": is_active,
                "edit_form_image_url": category.image.url if category.image else "",
            }
            return render(request, "categories.html", context)

        category.name = name
        category.description = description
        category.is_active = is_active

        if clear_image and category.image:
            if os.path.isfile(category.image.path):
                os.remove(category.image.path)
            category.image = None

        if image:
            if category.image and os.path.isfile(category.image.path):
                os.remove(category.image.path)
            category.image = image

        category.save()
        messages.success(request, f'Category "{name}" updated successfully.')
        return redirect("admin_categories")

    return redirect("admin_categories")


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_category_toggle_view(request, category_id):

    category = get_object_or_404(Category, id=category_id)
    category.is_active = not category.is_active
    category.save()

    Product.objects.filter(category=category, is_deleted=False).update(
        is_active=category.is_active
    )
    status = "activated" if category.is_active else "deactivated"
    messages.success(request, f'Category "{category.name}" has been {status}.')
    return redirect("admin_categories")


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_category_delete_view(request, category_id):

    category = get_object_or_404(Category, id=category_id)

    category.is_deleted = True
    category.save()

    Product.objects.filter(category=category).update(is_deleted=True)

    messages.success(
        request,
        f'Category "{category.name}" and related products deleted successfully.',
    )

    return redirect("admin_categories")
