from django.urls import path
from . import views

urlpatterns = [
    path('', views.address_list, name='address_list'),
    path('add/', views.add_address, name='add_address'),
    path('edit/<int:id>/', views.edit_address, name='edit_address'),
    path('delete/<int:id>/', views.delete_address, name='delete_address'),
    path('set-default/<int:id>/', views.set_default_address, name='set_default_address'),
]
