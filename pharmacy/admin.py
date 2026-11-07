from django.contrib import admin
from django.utils.html import format_html

from .models import Medicine, StockMovement


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_price', 'quantity', 'stock_level', 'expiry_date',
                    'expiry_warning', 'is_contraceptive')
    search_fields = ('name',)
    list_filter = ('is_contraceptive',)
    readonly_fields = ('quantity',)

    @admin.display(description='Stock level')
    def stock_level(self, obj):
        colours = {'green': '#2e7d32', 'yellow': '#f9a825', 'red': '#c62828'}
        return format_html('<b style="color:{}">● {}</b>',
                           colours[obj.stock_colour], obj.stock_colour.title())

    @admin.display(description='Expiry')
    def expiry_warning(self, obj):
        if obj.expiring_soon:
            return format_html('<b style="color:{}">{}</b>', '#c62828', 'Expiring / expired')
        return '-'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'medicine', 'movement_type', 'quantity', 'created_by')
    list_filter = ('movement_type', 'medicine')
    readonly_fields = ('created_by',)

    def has_change_permission(self, request, obj=None):
        return obj is None  # records are view-only once saved

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
