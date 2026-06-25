from django.conf import settings
from django.db import models

from admin_panel.admin_product.models import ProductVariant


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending",          "Pending"),
        ("shipped",          "Shipped"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered",        "Delivered"),
        ("cancelled",        "Cancelled"),
        ("return_requested", "Return Requested"),
        ("returned",         "Returned"),
        ("return_rejected",  "Return Rejected"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cod",    "Cash on Delivery"),
        ("online", "Online Payment"),
        ("wallet", "Wallet"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("paid",     "Paid"),
        ("unpaid",   "Unpaid"),
        ("refunded", "Refunded"),
    ]

    order_id = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cod"
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid"
    )

    # Razorpay tracking fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)

    cancel_reason  = models.TextField(blank=True, null=True)
    return_reason  = models.TextField(blank=True, null=True)

    # Address snapshot
    full_name      = models.CharField(max_length=200, blank=True)
    phone          = models.CharField(max_length=20, blank=True)
    address_line   = models.TextField(blank=True)
    city           = models.CharField(max_length=100, blank=True)
    state          = models.CharField(max_length=100, blank=True)
    pincode        = models.CharField(max_length=10, blank=True)

    # Coupon
    coupon_code     = models.CharField(max_length=20, blank=True, null=True)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Pricing
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total           = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.order_id} — {self.user.username}"

    def get_item_count(self):
        return self.items.count()


class OrderItem(models.Model):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant      = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL,
        null=True, related_name="order_items"
    )
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=200)
    sku          = models.CharField(max_length=50, blank=True)
    quantity     = models.PositiveIntegerField(default=1)
    unit_price   = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal     = models.DecimalField(max_digits=10, decimal_places=2)

    status         = models.CharField(
        max_length=20,
        choices=[
            ("ordered",          "Ordered"),
            ("cancelled",        "Cancelled"),
            ("return_requested", "Return Requested"),
            ("returned",         "Returned"),
            ("return_rejected",  "Return Rejected"),
        ],
        default="ordered"
    )
    cancel_reason  = models.TextField(blank=True, null=True)
    return_reason  = models.TextField(blank=True, null=True)

    # Partial quantity tracking
    cancelled_quantity        = models.PositiveIntegerField(default=0)
    return_requested_quantity = models.PositiveIntegerField(default=0)

    def get_image_url(self):
        """Returns the URL of the variant or product image, if available."""
        if self.variant:
            img = self.variant.images.filter(is_primary=True).first()
            if not img:
                img = self.variant.images.first()
            if not img and self.variant.product:
                product_imgs = self.variant.product.images
                img = product_imgs.filter(is_primary=True).first()
                if not img:
                    img = product_imgs.first()
            if img:
                return img.image.url
        return None

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.variant_name})"
