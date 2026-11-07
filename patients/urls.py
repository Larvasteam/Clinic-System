from django.urls import path

from . import views

urlpatterns = [
    path('', views.patient_list, name='patient_list'),
    path('add/', views.patient_add, name='patient_add'),
    path('<int:pk>/', views.patient_history, name='patient_history'),
    path('<int:pk>/edit/', views.patient_edit, name='patient_edit'),
]
