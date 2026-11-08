from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ExchangeRateForm, ItemFormSet, SaleForm, VisitForm
from .models import ExchangeRate, Sale
from .rates import RateError, fetch_rate, store_rate
from reports.templatetags.clinic_extras import paid


@login_required
@permission_required('billing.add_visit', raise_exception=True)
def visit_add(request):
    initial = {}
    if request.GET.get('patient', '').isdigit():
        initial['patient'] = request.GET['patient']
    form = VisitForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        visit = form.save(commit=False)
        visit.created_by = request.user
        visit.save()
        messages.success(request, f'Visit recorded for {visit.patient}: collect {paid(visit)}.')
        return redirect('patient_history', pk=visit.patient_id)
    return render(request, 'form_page.html', {
        'form': form, 'title': 'New Visit', 'cancel_url': reverse('patient_list'),
        'submit_label': 'Save visit'})


@login_required
@permission_required('billing.add_sale', raise_exception=True)
def sale_add(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        sale = form.save(commit=False) if form.is_valid() else Sale()
        formset = ItemFormSet(request.POST, instance=sale)
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    sale.created_by = request.user
                    sale.save()
                    formset.save()
            except ValidationError as e:  # e.g. someone else just sold the last units
                form.add_error(None, e)
            else:
                messages.success(request, f'Sale #{sale.pk} recorded: collect {paid(sale)}.')
                return redirect('sale_detail', pk=sale.pk)
    else:
        initial = {}
        if request.GET.get('patient', '').isdigit():
            initial['patient'] = request.GET['patient']
        form = SaleForm(initial=initial)
        formset = ItemFormSet(instance=Sale())
    return render(request, 'billing/sale_form.html', {'form': form, 'formset': formset})


@login_required
@permission_required('billing.view_sale', raise_exception=True)
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('patient', 'created_by')
                             .prefetch_related('items__medicine'), pk=pk)
    return render(request, 'billing/sale_detail.html', {'sale': sale})


@login_required
@permission_required('billing.view_exchangerate', raise_exception=True)
def rate_list(request):
    return render(request, 'billing/rate_list.html', {
        'rates': ExchangeRate.objects.select_related('created_by')[:60], 'current': ExchangeRate.current()})


@login_required
@permission_required('billing.add_exchangerate', raise_exception=True)
def rate_add(request):
    form = ExchangeRateForm(request.POST or None, initial={'date': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        rate = form.save(commit=False)
        rate.created_by = request.user
        rate.source = rate.source or 'Manual'
        rate.save()
        messages.success(request, f'Rate saved: {rate}.')
        return redirect('rate_list')
    return render(request, 'form_page.html', {
        'form': form, 'title': 'Set Exchange Rate', 'cancel_url': reverse('rate_list'),
        'submit_label': 'Save rate'})


@login_required
@permission_required('billing.add_exchangerate', raise_exception=True)
@require_POST
def rate_fetch(request):
    try:
        rate, published, source = fetch_rate()
        obj, created = store_rate(rate, published, source, user=request.user)
    except RateError as exc:
        messages.error(request, f'The rate was not updated: {exc}')
    else:
        messages.success(request, f'{"Rate updated" if created else "Already up to date"}: {obj}.')
    return redirect('rate_list')
