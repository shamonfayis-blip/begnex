from django.db import models


class Category(models.Model):

    category_id = models.CharField(max_length=20, unique=True)

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True, default="")

    image = models.ImageField(
        upload_to="category_images/", blank=True, null=True
    )

    is_active = models.BooleanField(default=True)

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
