from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from admin_panel.admin_category.models import Category
from admin_panel.admin_product.models import Product


class ProductOffer(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="offers"
    )
    discount_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Offer {self.discount_percentage}% on {self.product.name}"

    @property
    def is_valid(self):
        today = timezone.now().date()
        return self.is_active and self.valid_from <= today <= self.valid_until


class CategoryOffer(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="offers"
    )
    discount_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Offer {self.discount_percentage}% on Category {self.category.name}"

    @property
    def is_valid(self):
        today = timezone.now().date()
        return self.is_active and self.valid_from <= today <= self.valid_until


from django.conf import settings


class ReferralOffer(models.Model):
    referrer_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    referee_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Referral Offer: Referrer {self.referrer_reward} | Referee {self.referee_reward}"


class ReferralRecord(models.Model):
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_received",
    )
    referrer_reward_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    referee_reward_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.referrer.username} referred {self.referee.username}"
