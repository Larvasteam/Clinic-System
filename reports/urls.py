from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('reports/sheet/', views.sheet, name='sheet'),
    path('search/', views.global_search, name='search'),
]
