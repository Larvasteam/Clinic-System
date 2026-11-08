import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from billing.ledger import summarise
from billing.models import Sale, SaleItem, Visit
from patients.models import Patient
from pharmacy.models import Medicine
from .roles import user_roles

MONEY = DecimalField(max_digits=14, decimal_places=2)
PERIODS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']


def line_sum():
    return Sum(F('quantity') * F('unit_price'), output_field=MONEY)


def summary_since(start=None):
    visits, items = Visit.objects.all(), SaleItem.objects.all()
    if start:
        visits = visits.filter(created_at__date__gte=start)
        items = items.filter(sale__created_at__date__gte=start)
    return summarise(visits, items)


def period_range(period, d):
    if period == 'daily':
        return d, d
    if period == 'weekly':
        start = d - timedelta(days=d.weekday())  # Monday to Sunday
        return start, start + timedelta(days=6)
    if period == 'monthly':
        return d.replace(day=1), d.replace(day=calendar.monthrange(d.year, d.month)[1])
    if period == 'quarterly':
        first = 3 * ((d.month - 1) // 3) + 1
        last = first + 2
        return date(d.year, first, 1), date(d.year, last, calendar.monthrange(d.year, last)[1])
    return date(d.year, 1, 1), date(d.year, 12, 31)


@login_required
def dashboard(request):
    roles = user_roles(request.user)
    order = {'red': 0, 'yellow': 1, 'green': 2}
    medicines = sorted(Medicine.objects.all(), key=lambda m: (order[m.stock_colour], m.name))
    counts = {'green': 0, 'yellow': 0, 'red': 0}
    for m in medicines:
        counts[m.stock_colour] += 1

    today = timezone.localdate()
    can_see_money = 'Admin' in roles
    periods = []
    if can_see_money:
        periods = [
            ('Today', summary_since(today)),
            ('This month', summary_since(today.replace(day=1))),
            ('All time', summary_since()),
        ]
    return render(request, 'reports/dashboard.html', {
        'medicines': medicines,
        'total_units': sum(m.quantity for m in medicines),
        'counts': counts,
        'expiring': [m for m in medicines if m.expiring_soon],
        'periods': periods,
        'can_see_money': can_see_money,
    })


@login_required
def sheet(request):
    roles = user_roles(request.user)
    if 'Admin' in roles:
        allowed = PERIODS
    elif 'Pharmacist' in roles:
        allowed = ['daily', 'weekly']
    else:
        raise PermissionDenied

    period = request.GET.get('period', 'daily')
    if period not in PERIODS:
        period = 'daily'
    if period not in allowed:
        raise PermissionDenied
    try:
        picked = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        picked = timezone.localdate()
    start, end = period_range(period, picked)

    visits = (Visit.objects.filter(created_at__date__range=(start, end))
              .select_related('patient').order_by('created_at'))
    sales = (Sale.objects.filter(created_at__date__range=(start, end))
             .select_related('patient').prefetch_related('items__medicine').order_by('created_at'))
    items = SaleItem.objects.filter(sale__created_at__date__range=(start, end))

    summary = summarise(visits, items)

    sold = (items.order_by().values('medicine__name')
            .annotate(qty=Sum('quantity'), revenue=line_sum()).order_by('-revenue'))

    return render(request, 'reports/sheet.html', {
        'period': period, 'allowed': allowed, 'picked': picked, 'start': start, 'end': end,
        'summary': summary, 'fees': summary['fees'], 'meds': summary['meds'], 'total': summary['total_usd'],
        'methods': summary['methods'], 'sold': sold, 'visits': visits, 'sales': sales,
    })


@login_required
def global_search(request):
    if not (request.user.has_perm('pharmacy.view_medicine') and request.user.has_perm('patients.view_patient')):
        raise PermissionDenied
    q = request.GET.get('q', '').strip()
    meds, patients = [], []
    if q:
        meds = list(Medicine.objects.filter(name__icontains=q)[:25])
        patients = list(Patient.objects.filter(
            Q(first_name__icontains=q) | Q(surname__icontains=q) | Q(phone__icontains=q))[:25])
    return render(request, 'reports/search.html', {'q': q, 'medicines': meds, 'patients': patients})
