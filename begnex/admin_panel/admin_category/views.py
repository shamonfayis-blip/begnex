import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from admin_panel.admin_product.models import Product

from .models import Category


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
            Q(name__icontains=search_query)|Q(category_id__icontains=search_query))

    total_categories = Category.objects.filter(is_deleted=False).count()


    active_categories = Category.objects.filter(
        is_deleted=False, is_active=True).count()
    inactive_categories = Category.objects.filter(is_deleted=False, is_active=False).count()




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

        if not name:
            messages.error(request, "Category name is required.")
            return redirect("admin_categories")

        if Category.objects.filter(
            name__iexact=name, is_deleted=False
        ).exists():
            
            messages.error(request, f'Category "{name}" already exists.')
            return redirect("admin_categories")

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
        clear_image = request.POST.get("clear_image") == "1"

        if not name:
            messages.error(request, "Category name is required.")
            return redirect("admin_categories")

        if (
            Category.objects.filter(name__iexact=name, is_deleted=False)
            .exclude(id=category.id)
            .exists()
        ):
            messages.error(request, f'Category "{name}" already exists.')
            return redirect("admin_categories")

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
