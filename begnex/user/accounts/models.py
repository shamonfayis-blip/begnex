from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=15, blank=True, null=True)

    profile_photo = models.ImageField(
        upload_to="profile_photos/", blank=True, null=True
    )

    is_blocked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):

        return self.username
