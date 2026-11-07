from django.contrib import admin

from .forms import SaleItemFormSet
from .models import ExchangeRate, Sale, SaleItem, Visit
from .rules import MIN_PAYMENT


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    formset = SaleItemFormSet
    extra = 3
    fields = ('medicine', 'quantity', 'unit_price', 'line_total')
    readonly_fields = ('unit_price', 'line_total')
    autocomplete_fields = ['medicine']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'patient', 'consultation_fee', 'currency', 'payment_method', 'created_by')
    list_filter = ('payment_method',)
    search_fields = ('patient__first_name', 'patient__surname')
    autocomplete_fields = ['patient']
    readonly_fields = ('created_by', 'exchange_rate')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'consultation_fee':
            field.widget.attrs.update({'min': str(MIN_PAYMENT), 'step': '0.01'})
        return field

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'patient', 'currency', 'payment_method', 'total_display', 'created_by')
    list_filter = ('payment_method',)
    search_fields = ('patient__first_name', 'patient__surname')
    autocomplete_fields = ['patient', 'visit']
    readonly_fields = ('created_by', 'exchange_rate', 'total_display')
    inlines = [SaleItemInline]

    @admin.display(description='Total')
    def total_display(self, obj):
        if obj and obj.pk:
            return f"{obj.total:.2f} USD"
        return '-'

    def has_change_permission(self, request, obj=None):
        return obj is None  # sales are view-only once saved

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('date', 'usd_to_zwg', 'source', 'created_by', 'created_at')
    readonly_fields = ('created_by',)

    def has_change_permission(self, request, obj=None):
        return obj is None  # rates are history: add a new one instead of editing

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
