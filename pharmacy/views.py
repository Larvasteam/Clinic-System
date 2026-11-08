import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, F, Max, Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import MedicineForm, StockMovementForm
from .models import Medicine, StockMovement

MONEY = DecimalField(max_digits=14, decimal_places=2)


@login_required
@permission_required('pharmacy.view_medicine', raise_exception=True)
def medicine_list(request):
    q = request.GET.get('q', '').strip()
    level = request.GET.get('level', '')
    qs = Medicine.objects.prefetch_related(Prefetch(
        'movements',
        queryset=StockMovement.objects.select_related('created_by').order_by('-created_at', '-id')[:5],
        to_attr='recent'))
    if q:
        qs = qs.filter(name__icontains=q)
    everything = list(Medicine.objects.all())
    counts = {'green': 0, 'yellow': 0, 'red': 0}
    for m in everything:
        counts[m.stock_colour] += 1
    meds = list(qs)
    if level in counts:
        meds = [m for m in meds if m.stock_colour == level]
    return render(request, 'pharmacy/medicine_list.html', {
        'medicines': meds, 'total': len(everything), 'counts': counts, 'q': q, 'level': level})


def csv_safe(value):
    """Stop spreadsheet formula injection when a name starts with = + - or @."""
    s = str(value)
    return "'" + s if s[:1] in ('=', '+', '-', '@') else s


@login_required
@permission_required('pharmacy.view_medicine', raise_exception=True)
def medicine_export(request):
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="medicines.csv"'
    w = csv.writer(resp)
    w.writerow(['Medicine', 'Unit price (USD)', 'Quantity', 'Low level', 'High level',
                'Stock level', 'Expiry date', 'Contraceptive'])
    for m in Medicine.objects.all():
        w.writerow([csv_safe(m.name), m.unit_price, m.quantity, m.low_threshold, m.high_threshold,
                    m.stock_colour, m.expiry_date or '', 'Yes' if m.is_contraceptive else 'No'])
    return resp


@login_required
@permission_required('pharmacy.add_medicine', raise_exception=True)
def medicine_add(request):
    form = MedicineForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            med = form.save()
            opening = form.cleaned_data.get('opening_stock') or 0
            if opening:
                StockMovement.objects.create(medicine=med, movement_type='in', quantity=opening,
                                             note='Opening stock', created_by=request.user)
        messages.success(request, f'{med.name} was added.')
        return redirect('medicine_list')
    return render(request, 'form_page.html', {
        'form': form, 'title': 'Add Medicine', 'cancel_url': reverse('medicine_list'),
        'submit_label': 'Save medicine'})


@login_required
@permission_required('pharmacy.change_medicine', raise_exception=True)
def medicine_edit(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    form = MedicineForm(request.POST or None, instance=med)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{med.name} was updated. Old sales keep the price they were sold at.')
        return redirect('medicine_list')
    return render(request, 'form_page.html', {
        'form': form, 'title': f'Edit {med.name}', 'cancel_url': reverse('medicine_list'),
        'submit_label': 'Save changes'})


@login_required
@permission_required('pharmacy.add_stockmovement', raise_exception=True)
def medicine_stock(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    form = StockMovementForm(request.POST or None, initial={'medicine': med.pk, 'movement_type': 'in'})
    if request.method == 'POST' and form.is_valid():
        movement = form.save(commit=False)
        movement.created_by = request.user
        try:
            movement.save()
        except ValidationError as e:
            form.add_error(None, e)
        else:
            messages.success(request, f'Stock updated: {movement.medicine.name} now has '
                                      f'{movement.medicine.quantity} units.')
            return redirect('medicine_list')
    return render(request, 'form_page.html', {
        'form': form, 'title': f'Stock: {med.name}', 'cancel_url': reverse('medicine_list'),
        'submit_label': 'Record stock change'})


@login_required
@permission_required('pharmacy.view_stockmovement', raise_exception=True)
def stock_management(request):
    q = request.GET.get('q', '').strip()
    qs = Medicine.objects.annotate(last_updated=Max('movements__created_at'))
    if q:
        qs = qs.filter(name__icontains=q)
    meds = list(qs)

    everything = list(Medicine.objects.order_by('name'))
    top = max([m.quantity for m in everything] + [m.low_threshold for m in everything] + [1])
    chart = [{'name': m.name, 'qty': m.quantity, 'reorder': m.low_threshold,
              'qty_pct': m.quantity / top * 100, 'reorder_pct': m.low_threshold / top * 100}
             for m in everything]
    value = Medicine.objects.aggregate(
        t=Sum(F('quantity') * F('unit_price'), output_field=MONEY))['t'] or Decimal('0')

    return render(request, 'pharmacy/stock_management.html', {
        'medicines': meds, 'chart': chart, 'q': q,
        'ticks': [top, round(top * 0.75), round(top * 0.5), round(top * 0.25), 0],
        'total_value': value, 'total_skus': len(everything),
        'low': sum(1 for m in everything if m.stock_colour == 'red' and m.quantity > 0),
        'out': sum(1 for m in everything if m.quantity == 0),
    })


@login_required
@permission_required('pharmacy.view_stockmovement', raise_exception=True)
def expiry_alerts(request):
    today = timezone.localdate()
    meds = [m for m in Medicine.objects.exclude(expiry_date=None).order_by('expiry_date')
            if m.expiring_soon]
    for m in meds:
        m.days_left = (m.expiry_date - today).days
    return render(request, 'pharmacy/expiry_alerts.html', {
        'medicines': meds,
        'expired_count': sum(1 for m in meds if m.expired),
        'soon_count': sum(1 for m in meds if not m.expired),
    })
