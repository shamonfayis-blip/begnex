from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from admin_panel.admin_category.models import Category


class Product(models.Model):
    product_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    material = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_default_variant(self):
        # Return default variant or first variant
        variant = self.variants.filter(
            is_deleted=False, is_default=True
        ).first()
        if not variant:
            variant = self.variants.filter(is_deleted=False).first()
        return variant

    def get_primary_image(self):
        """Returns the primary VariantImage for the default variant."""
        variant = self.get_default_variant()
        if not variant:
            return None
        img = variant.images.filter(is_primary=True).first()
        if not img:
            img = variant.images.first()
        return img

    def get_price(self):
        """Returns price from the default variant."""
        variant = self.get_default_variant()
        return variant.price if variant else None

    def get_total_stock(self):
        """Returns total stock across all active variants."""
        return sum(variant.stock for variant in self.variants.filter(is_deleted=False))


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="product_images/")
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    name = models.CharField(max_length=200)  # e.g. "Red - M"
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class VariantImage(models.Model):
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="variant_images/")
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for variant {self.variant.name}"


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.product.name} ({self.rating}/5)"


class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}%)"
