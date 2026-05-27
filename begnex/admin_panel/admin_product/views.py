import base64
import os
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from PIL import Image

from admin_panel.admin_category.models import Category

from .models import Product, ProductImage, ProductVariant, VariantImage


def generate_product_id():
    """Auto-generate a unique product ID like PRD-001, PRD-002"""
    last = Product.objects.order_by("-id").first()
    if last:
        try:
            num = int(last.product_id.split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = Product.objects.count() + 1
    else:
        num = 1
    return f"PRD-{num:03d}"


def resize_image(image_path):

    img = Image.open(image_path)

    img = img.convert("RGB")

    img.thumbnail((800, 800))

    img.save(image_path, optimize=True, quality=85)


def handle_base64_image(base64_string, product, is_primary):
   
    if base64_string and ";base64," in base64_string:
        format, imgstr = base64_string.split(";base64,")


        ext = format.split("/")[-1]
        filename = f"{product.product_id}_{uuid.uuid4().hex[:6]}.{ext}"
        data = ContentFile(base64.b64decode(imgstr), name=filename)

        ProductImage.objects.create(
            product=product, image=data, is_primary=is_primary
        )


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_list_view(request):

    from datetime import timedelta

    from django.utils import timezone

    search_query = request.GET.get("q", "").strip()
    category_filter = request.GET.get("category", "").strip()
    status_filter = request.GET.get("status", "").strip()
    filter_option = request.GET.get("filter_option", "").strip()

    products = Product.objects.filter(
        is_deleted=False, category__is_deleted=False
    )

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(product_id__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    if category_filter:
        products = products.filter(category_id=category_filter)

    if status_filter == "active":
        products = products.filter(is_active=True)
    elif status_filter == "inactive":
        products = products.filter(is_active=False)



    if filter_option == "newest":
        products = products.order_by("-id")
    elif filter_option == "oldest":
        products = products.order_by("id")
    elif filter_option == "a_z":
        products = products.order_by("name")
    elif filter_option == "z_a":
        products = products.order_by("-name")
    else:
        products = products.order_by("-id") 




    total_products = Product.objects.filter(is_deleted=False, category__is_deleted=False).count()


    active_products = Product.objects.filter(
        is_deleted=False, is_active=True, category__is_deleted=False).count()


    out_of_stock = ProductVariant.objects.filter(
        product__is_deleted=False, is_deleted=False, stock=0
    ).count()

  
    seven_days_ago = timezone.now() - timedelta(days=7)
    new_products = Product.objects.filter(
        is_deleted=False,
        category__is_deleted=False,
        created_at__gte=seven_days_ago,).count()


    paginator = Paginator(products, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(is_deleted=False, is_active=True)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "filter_option": filter_option,
        "total_products": total_products,
        "active_products": active_products,
        "out_of_stock": out_of_stock,
        "new_products": new_products,
        "categories": categories,
    }
    return render(request, "products.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_product_add_view(request):

    name = request.POST.get("name", "").strip()
    category_id = request.POST.get("category")
    material = request.POST.get("material", "").strip()
    fit_type = request.POST.get("fit_type", "").strip()
    description = request.POST.get("description", "").strip()
    is_active = request.POST.get("is_active", "true") == "true"

    if not name or not category_id:
        messages.error(request, "Name and Category are required.")
        return redirect("admin_products")

    if Product.objects.filter(name__iexact=name, is_deleted=False).exists():
        messages.error(request, f'Product "{name}" already exists.')
        return redirect("admin_products")

    try:
        category = Category.objects.get(id=category_id, is_deleted=False)

    except Category.DoesNotExist:

        messages.error(request, "Selected category does not exist.")

        return redirect("admin_products")

    Product.objects.create(
        product_id=generate_product_id(),
        name=name,
        category=category,
        material=material,
        description=description,
        is_active=is_active,
    )

    messages.success(request, f'Product "{name}" created successfully.')

    return redirect("admin_products")


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_product_edit_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    name = request.POST.get("name", "").strip()
    category_id = request.POST.get("category")
    material = request.POST.get("material", "").strip()
    description = request.POST.get("description", "").strip()
    is_active = request.POST.get("is_active", "true") == "true"

    if not name or not category_id:
        messages.error(request, "Name and Category are required.")
        return redirect("admin_products")

    if (
        Product.objects.filter(name__iexact=name, is_deleted=False)
        .exclude(id=product.id)
        .exists()
    ):
        messages.error(request, f'Product "{name}" already exists.')
        return redirect("admin_products")

    try:
        category = Category.objects.get(id=category_id, is_deleted=False)
    except Category.DoesNotExist:
        messages.error(request, "Selected category does not exist.")
        return redirect("admin_products")

    product.name = name
    product.category = category
    product.material = material
    product.description = description
    product.is_active = is_active
    product.save()

    # Handle image deletions
    delete_images = request.POST.getlist("delete_images")
    if delete_images:
        for img_id in delete_images:
            try:
                img = ProductImage.objects.get(id=img_id, product=product)
                if os.path.isfile(img.image.path):
                    os.remove(img.image.path)
                img.delete()
            except ProductImage.DoesNotExist:
                pass

 
    first_remaining = product.images.first()
    if first_remaining and not product.images.filter(is_primary=True).exists():
        first_remaining.is_primary = True
        first_remaining.save()

    
    has_primary = product.images.filter(is_primary=True).exists()
    handle_base64_image(
        request.POST.get("image1_base64"), product, is_primary=not has_primary
    )

    has_primary = product.images.filter(is_primary=True).exists()
    handle_base64_image(
        request.POST.get("image2_base64"), product, is_primary=not has_primary
    )

    has_primary = product.images.filter(is_primary=True).exists()
    handle_base64_image(
        request.POST.get("image3_base64"), product, is_primary=not has_primary
    )

    messages.success(request, f'Product "{name}" updated successfully.')
    return redirect("admin_products")


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_product_toggle_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_active = not product.is_active
    product.save()
    status = "activated" if product.is_active else "deactivated"
    messages.success(request, f'Product "{product.name}" has been {status}.')
    return redirect("admin_products")


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_product_delete_view(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    product.is_deleted = True
    product.save()

    ProductVariant.objects.filter(product=product).update(is_deleted=True)

    messages.success(
        request, f'Product "{product.name}" and related variants deleted.'
    )

    return redirect("admin_products")





@never_cache
@staff_member_required(login_url="admin_login")
def admin_variant_list_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    stock_filter = request.GET.get("stock", "").strip()

    variants = ProductVariant.objects.filter(
        product=product, is_deleted=False
    ).order_by("-id")

    if search_query:
        variants = variants.filter(
            Q(name__icontains=search_query) | Q(sku__icontains=search_query)
        )

    if status_filter == "active":
        variants = variants.filter(is_active=True)
    elif status_filter == "inactive":
        variants = variants.filter(is_active=False)

    if stock_filter == "in_stock":
        variants = variants.filter(stock__gt=0)
    elif stock_filter == "out_of_stock":
        variants = variants.filter(stock=0)

    total_variants = ProductVariant.objects.filter(
        product=product, is_deleted=False
    ).count()
    active_variants = ProductVariant.objects.filter(
        product=product, is_deleted=False, is_active=True
    ).count()
    out_of_stock = ProductVariant.objects.filter(
        product=product, is_deleted=False, stock=0
    ).count()

    paginator = Paginator(variants, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "product": product,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "stock_filter": stock_filter,
        "total_variants": total_variants,
        "active_variants": active_variants,
        "out_of_stock": out_of_stock,
    }
    return render(request, "variants.html", context)


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_variant_add_view(request, product_id):

    product = get_object_or_404(Product, id=product_id, is_deleted=False)

    color = request.POST.get("color", "").strip()
    size = request.POST.get("size", "").strip()

    name = f"{color} / {size}"

    if not color or not size:

        messages.error(request, "Color and Size are required.")

        return redirect("admin_variants", product_id=product.id)

    sku = request.POST.get("sku", "").strip()
    price = request.POST.get("price", "0")
    stock = request.POST.get("stock", "0")
    is_active = request.POST.get("is_active", "true") == "true"

    if ProductVariant.objects.filter(
        sku__iexact=sku, is_deleted=False
    ).exists():

        messages.error(request, f'SKU "{sku}" already exists.')

        return redirect("admin_variants", product_id=product.id)

    is_default = False

    if not ProductVariant.objects.filter(
        product=product, is_deleted=False
    ).exists():

        is_default = True

    variant = ProductVariant.objects.create(
        product=product,
        name=name,
        sku=sku,
        price=price,
        stock=stock,
        is_active=is_active,
        is_default=is_default,
    )

   

    image1 = request.FILES.get("image_1")
    image2 = request.FILES.get("image_2")
    image3 = request.FILES.get("image_3")

    if not image1 or not image2 or not image3:

        variant.delete()

        messages.error(request, "Minimum 3 images are required.")

        return redirect("admin_variants", product_id=product.id)

    variant_image_1 = VariantImage.objects.create(
        variant=variant, image=image1, is_primary=True
    )

    resize_image(variant_image_1.image.path)

    variant_image_2 = VariantImage.objects.create(
        variant=variant, image=image2, is_primary=False
    )

    resize_image(variant_image_2.image.path)

    variant_image_3 = VariantImage.objects.create(
        variant=variant, image=image3, is_primary=False
    )

    resize_image(variant_image_3.image.path)

    messages.success(request, f'Variant "{name}" added successfully.')

    return redirect("admin_variants", product_id=product.id)


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_variant_edit_view(request, variant_id):

    variant = get_object_or_404(
        ProductVariant, id=variant_id, is_deleted=False
    )

    product_id = variant.product.id

    color = request.POST.get("color", "").strip()
    size = request.POST.get("size", "").strip()

    name = f"{color} / {size}"

    if not color or not size:

        messages.error(request, "Color and Size are required.")

        return redirect("admin_variants", product_id=product_id)

    sku = request.POST.get("sku", "").strip()
    price = request.POST.get("price", "0")
    stock = request.POST.get("stock", "0")
    is_active = request.POST.get("is_active", "true") == "true"

    if (
        ProductVariant.objects.filter(sku__iexact=sku, is_deleted=False)
        .exclude(id=variant.id)
        .exists()
    ):

        messages.error(request, f'SKU "{sku}" already exists.')

        return redirect("admin_variants", product_id=product_id)

    variant.name = name
    variant.sku = sku
    variant.price = price
    variant.stock = stock
    variant.is_active = is_active
    variant.save()

    # DELETE SELECTED IMAGES

    for i in range(1, 4):

        clear_value = request.POST.get(f"clear_image_{i}")

        if clear_value and clear_value.isdigit():

            try:

                img = VariantImage.objects.get(id=clear_value, variant=variant)

                if os.path.isfile(img.image.path):
                    os.remove(img.image.path)

                img.delete()

            except VariantImage.DoesNotExist:
                pass

    # ADD NEW IMAGES

    image1 = request.FILES.get("image_1")
    image2 = request.FILES.get("image_2")
    image3 = request.FILES.get("image_3")

    new_images = [image1, image2, image3]

    for image in new_images:

        if image:

            has_primary = variant.images.filter(is_primary=True).exists()

            variant_image = VariantImage.objects.create(
                variant=variant, image=image, is_primary=not has_primary
            )

            resize_image(variant_image.image.path)
    # ENSURE ONE PRIMARY IMAGE

    first_image = variant.images.first()

    if first_image and not variant.images.filter(is_primary=True).exists():

        first_image.is_primary = True
        first_image.save()

    messages.success(request, f'Variant "{name}" updated successfully.')

    return redirect("admin_variants", product_id=product_id)


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_variant_delete_view(request, variant_id):

    variant = get_object_or_404(
        ProductVariant, id=variant_id, is_deleted=False
    )

    product_id = variant.product.id

    was_default = variant.is_default

    variant.is_deleted = True
    variant.save()

    # SET NEW DEFAULT VARIANT

    if was_default:

        next_variant = (
            ProductVariant.objects.filter(
                product=variant.product, is_deleted=False
            )
            .exclude(id=variant.id)
            .first()
        )

        if next_variant:

            next_variant.is_default = True
            next_variant.save()

    messages.success(request, f'Variant "{variant.name}" deleted.')

    return redirect("admin_variants", product_id=product_id)


@never_cache
@staff_member_required(login_url="admin_login")
@require_POST
def admin_variant_set_default_view(request, variant_id):
    variant = get_object_or_404(
        ProductVariant, id=variant_id, is_deleted=False
    )
    product_id = variant.product.id

    ProductVariant.objects.filter(
        product=variant.product, is_deleted=False
    ).update(is_default=False)
    variant.is_default = True
    variant.save()

    messages.success(request, f'Variant "{variant.name}" set as default.')
    return redirect("admin_variants", product_id=product_id)
