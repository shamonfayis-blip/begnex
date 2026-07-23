import base64
import os
import uuid
from decimal import Decimal, InvalidOperation

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

        ProductImage.objects.create(product=product, image=data, is_primary=is_primary)


def _save_base64_image(b64_string, prefix="var"):

    if not b64_string or ";base64," not in b64_string:
        return None
    _, imgstr = b64_string.split(";base64,", 1)
    filename = f"{prefix}_{uuid.uuid4().hex}.jpg"
    return ContentFile(base64.b64decode(imgstr), name=filename)


@never_cache
@staff_member_required(login_url="admin_login")
def admin_product_list_view(request):

    from datetime import timedelta

    from django.utils import timezone

    search_query = request.GET.get("q", "").strip()
    category_filter = request.GET.get("category", "").strip()
    status_filter = request.GET.get("status", "").strip()
    filter_option = request.GET.get("filter_option", "").strip()

    products = Product.objects.filter(is_deleted=False, category__is_deleted=False)

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

    total_products = Product.objects.filter(
        is_deleted=False, category__is_deleted=False
    ).count()

    active_products = Product.objects.filter(
        is_deleted=False, is_active=True, category__is_deleted=False
    ).count()

    out_of_stock = ProductVariant.objects.filter(
        product__is_deleted=False, is_deleted=False, stock=0
    ).count()

    seven_days_ago = timezone.now() - timedelta(days=7)
    new_products = Product.objects.filter(
        is_deleted=False,
        category__is_deleted=False,
        created_at__gte=seven_days_ago,
    ).count()

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
    description = request.POST.get("description", "").strip()
    is_active = request.POST.get("is_active", "true") == "true"

    if not name or not category_id:
        messages.error(request, "Name and Category are required.")
        return redirect("admin_products")

    if len(name) < 2:
        messages.error(request, "Product name must be at least 2 characters.")
        return redirect("admin_products")
    if len(name) > 200:
        messages.error(request, "Product name cannot exceed 200 characters.")
        return redirect("admin_products")
    if not any(c.isalpha() for c in name):
        messages.error(request, "Product name must contain at least one letter.")
        return redirect("admin_products")
    if material and len(material) > 100:
        messages.error(request, "Material cannot exceed 100 characters.")
        return redirect("admin_products")
    if description and len(description) > 2000:
        messages.error(request, "Description cannot exceed 2000 characters.")
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

    if len(name) < 2:
        messages.error(request, "Product name must be at least 2 characters.")
        return redirect("admin_products")
    if len(name) > 200:
        messages.error(request, "Product name cannot exceed 200 characters.")
        return redirect("admin_products")
    if not any(c.isalpha() for c in name):
        messages.error(request, "Product name must contain at least one letter.")
        return redirect("admin_products")
    if material and len(material) > 100:
        messages.error(request, "Material cannot exceed 100 characters.")
        return redirect("admin_products")
    if description and len(description) > 2000:
        messages.error(request, "Description cannot exceed 2000 characters.")
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

    if not product.is_active:
        from user.wishlist.models import Wishlist

        Wishlist.objects.filter(product=product).delete()

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

    if not product.is_active:
        from user.wishlist.models import Wishlist

        Wishlist.objects.filter(product=product).delete()
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

    from user.wishlist.models import Wishlist

    Wishlist.objects.filter(product=product).delete()

    ProductVariant.objects.filter(product=product).update(is_deleted=True)

    messages.success(request, f'Product "{product.name}" and related variants deleted.')

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
def admin_variant_add_view(request, product_id):

    product = get_object_or_404(Product, id=product_id, is_deleted=False)

    if request.method != "POST":
        return redirect("admin_variants", product_id=product.id)

    color = request.POST.get("color", "").strip()
    size = request.POST.get("size", "").strip()
    sku = request.POST.get("sku", "").strip()
    price_str = request.POST.get("price", "0").strip()
    stock_str = request.POST.get("stock", "0").strip()
    is_active = request.POST.get("is_active", "true") == "true"

    name = f"{color} / {size}"

    error = None

    if not color or not size:
        error = "Color and Size are required."
    elif len(color) < 2 or not any(c.isalpha() for c in color):
        error = "Color must be at least 2 characters and contain at least one letter."
    elif not sku:
        error = "SKU is required."
    elif ProductVariant.objects.filter(sku__iexact=sku, is_deleted=False).exists():
        error = f'SKU "{sku}" already exists.'
    else:
        try:
            price_val = Decimal(price_str)
            if price_val <= 0:
                error = "Price must be greater than ₹0."
            elif price_val > Decimal("9999999"):
                error = "Price value is too large."
        except InvalidOperation:
            error = "Invalid price value entered."

    if not error:
        try:
            stock_val = int(stock_str)
            if stock_val < 0:
                error = "Stock quantity cannot be negative."
            elif stock_val > 99999:
                error = "Stock value is too large (max 99,999)."
        except (ValueError, TypeError):
            error = "Stock must be a whole number."

    if not error:
        image1 = None
        image2 = None
        image3 = None

        img1_b64 = request.POST.get("image_1_base64")
        img2_b64 = request.POST.get("image_2_base64")
        img3_b64 = request.POST.get("image_3_base64")

        if img1_b64:
            image1 = _save_base64_image(img1_b64, prefix=f"var_{sku}_1")
        else:
            image1 = request.FILES.get("image_1")

        if img2_b64:
            image2 = _save_base64_image(img2_b64, prefix=f"var_{sku}_2")
        else:
            image2 = request.FILES.get("image_2")

        if img3_b64:
            image3 = _save_base64_image(img3_b64, prefix=f"var_{sku}_3")
        else:
            image3 = request.FILES.get("image_3")

        if not image1 or not image2 or not image3:
            error = "All 3 variant images are required."
        else:
            ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
            for img in [image1, image2, image3]:
                if hasattr(img, "content_type") and img.content_type not in ALLOWED_IMAGE_TYPES:
                    error = f'"{img.name}" is not a valid image. Only JPG, PNG, and WEBP are allowed.'
                    break

    if error:
       
        search_query = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        stock_filter = request.GET.get("stock", "").strip()
        variants = ProductVariant.objects.filter(product=product, is_deleted=False).order_by("-id")
        total_variants = variants.count()
        active_variants = variants.filter(is_active=True).count()
        out_of_stock = variants.filter(stock=0).count()
        paginator = Paginator(variants, 10)
        page_obj = paginator.get_page(request.GET.get("page"))
        context = {
            "product": product,
            "page_obj": page_obj,
            "search_query": search_query,
            "status_filter": status_filter,
            "stock_filter": stock_filter,
            "total_variants": total_variants,
            "active_variants": active_variants,
            "out_of_stock": out_of_stock,
            # Add-form error state
            "add_form_error": error,
            "add_form_color": color,
            "add_form_size": size,
            "add_form_sku": sku,
            "add_form_price": price_str,
            "add_form_stock": stock_str,
            "add_form_is_active": is_active,
        }
        return render(request, "variants.html", context)

    is_default = not ProductVariant.objects.filter(
        product=product, is_deleted=False
    ).exists()

    variant = ProductVariant.objects.create(
        product=product,
        name=name,
        sku=sku,
        price=price_val,
        stock=stock_val,
        is_active=is_active,
        is_default=is_default,
    )

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

    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
    product_id = variant.product.id

    color = request.POST.get("color", "").strip()
    size = request.POST.get("size", "").strip()
    sku = request.POST.get("sku", "").strip()
    price_str = request.POST.get("price", "0").strip()
    stock_str = request.POST.get("stock", "0").strip()
    is_active = request.POST.get("is_active", "true") == "true"

    name = f"{color} / {size}"

    if not color or not size:
        messages.error(request, "Color and Size are required.")
        return redirect("admin_variants", product_id=product_id)
    if len(color) < 2 or not any(c.isalpha() for c in color):
        messages.error(
            request,
            "Color must be at least 2 characters and contain at least one letter.",
        )
        return redirect("admin_variants", product_id=product_id)

    if not sku:
        messages.error(request, "SKU is required.")
        return redirect("admin_variants", product_id=product_id)
    if (
        ProductVariant.objects.filter(sku__iexact=sku, is_deleted=False)
        .exclude(id=variant.id)
        .exists()
    ):
        messages.error(request, f'SKU "{sku}" already exists.')
        return redirect("admin_variants", product_id=product_id)

    try:
        price_val = Decimal(price_str)
        if price_val <= 0:
            messages.error(request, "Price must be greater than ₹0.")
            return redirect("admin_variants", product_id=product_id)
        if price_val > Decimal("9999999"):
            messages.error(request, "Price value is too large.")
            return redirect("admin_variants", product_id=product_id)
    except InvalidOperation:
        messages.error(request, "Invalid price value entered.")
        return redirect("admin_variants", product_id=product_id)

    try:
        stock_val = int(stock_str)
        if stock_val < 0:
            messages.error(request, "Stock quantity cannot be negative.")
            return redirect("admin_variants", product_id=product_id)
        if stock_val > 99999:
            messages.error(request, "Stock value is too large (max 99,999).")
            return redirect("admin_variants", product_id=product_id)
    except (ValueError, TypeError):
        messages.error(request, "Stock must be a whole number.")
        return redirect("admin_variants", product_id=product_id)

    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
    for i in range(1, 4):
        img = request.FILES.get(f"image_{i}")
        if img and img.content_type not in ALLOWED_IMAGE_TYPES:
            messages.error(
                request,
                f'"{img.name}" is not a valid image. Only JPG, PNG, and WEBP are allowed.',
            )
            return redirect("admin_variants", product_id=product_id)

    variant.name = name
    variant.sku = sku
    variant.price = price_val
    variant.stock = stock_val
    variant.is_active = is_active
    variant.save()

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

    for i in range(1, 4):
        b64_data = request.POST.get(f"image_{i}_base64")
        if b64_data:
            image = _save_base64_image(b64_data, prefix=f"var_{variant.sku}_{i}")
            if image:
                has_primary = variant.images.filter(is_primary=True).exists()
                VariantImage.objects.create(
                    variant=variant, image=image, is_primary=not has_primary
                )
        else:
            image = request.FILES.get(f"image_{i}")
            if image:
                has_primary = variant.images.filter(is_primary=True).exists()
                variant_image = VariantImage.objects.create(
                    variant=variant, image=image, is_primary=not has_primary
                )
                resize_image(variant_image.image.path)

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

    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)

    product_id = variant.product.id

    was_default = variant.is_default

    variant.is_deleted = True
    variant.save()

    if was_default:

        next_variant = (
            ProductVariant.objects.filter(product=variant.product, is_deleted=False)
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
    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
    product_id = variant.product.id

    ProductVariant.objects.filter(product=variant.product, is_deleted=False).update(
        is_default=False
    )
    variant.is_default = True
    variant.save()

    messages.success(request, f'Variant "{variant.name}" set as default.')
    return redirect("admin_variants", product_id=product_id)
