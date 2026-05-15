from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('user.accounts.urls')),

    path('accounts/', include('allauth.urls')),
    path('userinfo/', include('user.userinfo.urls')),
    path('address/', include('user.address.urls')),
    path('begnex-admin/', include('admin_panel.admin_use.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)