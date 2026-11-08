from django.urls import path

from . import views

urlpatterns = [
    path('visits/add/', views.visit_add, name='visit_add'),
    path('sales/add/', views.sale_add, name='sale_add'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('rates/', views.rate_list, name='rate_list'),
    path('rates/add/', views.rate_add, name='rate_add'),
    path('rates/fetch/', views.rate_fetch, name='rate_fetch'),
]
