from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=15, blank=True, null=True)

    profile_photo = models.ImageField(
        upload_to="profile_photos/", blank=True, null=True
    )

    is_blocked = models.BooleanField(default=False)

    referral_code = models.CharField(max_length=50, unique=True, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            import random
            import string

            while True:
                code = "BNX-" + "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=6)
                )
                # Avoid circular import or direct queries if model is not ready
                if not User.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):

        return self.username
