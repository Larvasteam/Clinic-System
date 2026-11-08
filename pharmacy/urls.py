from django.urls import path

from . import views

urlpatterns = [
    path('medicines/', views.medicine_list, name='medicine_list'),
    path('medicines/add/', views.medicine_add, name='medicine_add'),
    path('medicines/export/', views.medicine_export, name='medicine_export'),
    path('medicines/<int:pk>/edit/', views.medicine_edit, name='medicine_edit'),
    path('medicines/<int:pk>/stock/', views.medicine_stock, name='medicine_stock'),
    path('inventory/stock/', views.stock_management, name='stock_management'),
    path('inventory/expiry/', views.expiry_alerts, name='expiry_alerts'),
]
