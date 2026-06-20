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
        
        variant = self.variants.filter(
            is_deleted=False, is_default=True
        ).first()
        if not variant:
            variant = self.variants.filter(is_deleted=False).first()
        return variant

    def get_primary_image(self):
        
        variant = self.get_default_variant()
        if not variant:
            return None
        img = variant.images.filter(is_primary=True).first()
        if not img:
            img = variant.images.first()
        return img

    def get_price(self):
        
        variant = self.get_default_variant()
        return variant.price if variant else None

    def get_discounted_price(self):
        variant = self.get_default_variant()
        return variant.get_discounted_price() if variant else None

    def get_active_offer_percentage(self):
        try:
            from admin_panel.admin_offer.models import ProductOffer, CategoryOffer
        except ImportError:
            return 0
        from django.utils import timezone
        
        today = timezone.now().date()
        
        # Product offer
        prod_offer = ProductOffer.objects.filter(
            product=self,
            is_active=True,
            valid_from__lte=today,
            valid_until__gte=today
        ).order_by("-discount_percentage").first()
        prod_discount = prod_offer.discount_percentage if prod_offer else 0
        
        # Category offer
        cat_offer = CategoryOffer.objects.filter(
            category=self.category,
            is_active=True,
            valid_from__lte=today,
            valid_until__gte=today
        ).order_by("-discount_percentage").first()
        cat_discount = cat_offer.discount_percentage if cat_offer else 0
        
        return max(prod_discount, cat_discount)

    def get_total_stock(self):
    
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

    def get_discounted_price(self):
        discount_percentage = self.product.get_active_offer_percentage()
        if discount_percentage > 0:
            from decimal import Decimal
            discount_amount = (self.price * Decimal(discount_percentage)) / Decimal(100)
            return round(self.price - discount_amount, 2)
        return self.price

    @property
    def discounted_price(self):
        return self.get_discounted_price()


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


