from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(
        max_length=15,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
        help_text="Maximum discount cap (for percentage coupons)",
    )
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited usage",
    )
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.discount_type == "fixed":
            if self.min_order_amount is not None and self.discount_value is not None:
                if self.min_order_amount <= self.discount_value:
                    raise ValidationError("Minimum order amount must be greater than the flat coupon value.")

    @property
    def is_expired(self):
        return timezone.now().date() > self.valid_until

    @property
    def is_valid(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if today < self.valid_from or today > self.valid_until:
            return False
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False
        return True

    @property
    def usage_remaining(self):
        if self.usage_limit is None:
            return None
        return max(0, self.usage_limit - self.used_count)
