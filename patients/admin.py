from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('surname', 'first_name', 'age', 'gender', 'phone', 'created_at')
    search_fields = ('first_name', 'surname', 'phone')
    list_filter = ('gender',)
