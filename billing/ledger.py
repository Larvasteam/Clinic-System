"""Money totals in both currencies.

Prices are kept in USD. A payment made in ZiG is stored with the rate that applied at that moment, so
 - the USD balance is what was received in US dollars,
 - the ZiG balance is what was received in ZiG, and
 - the total is the USD value of everything (ZiG payments counted at their own locked-in rate).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import DecimalField, F, Sum

from .models import PaymentInfo

MONEY = DecimalField(max_digits=18, decimal_places=4)
ZERO = Decimal('0')
METHOD_LABELS = dict(PaymentInfo.PAYMENT_CHOICES)


def cents(value):
    return (value or ZERO).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def summarise(visits, items):
    """visits: a Visit queryset. items: a SaleItem queryset. Both already limited to the period wanted."""
    totals = {'usd_received': ZERO, 'zwg_received': ZERO, 'zwg_in_usd': ZERO, 'fees': ZERO, 'meds': ZERO}
    methods = {}

    def add(kind, method, currency, usd, zwg):
        usd, zwg = usd or ZERO, zwg or ZERO
        totals[kind] += usd
        if currency == 'ZWG':
            totals['zwg_received'] += zwg
            totals['zwg_in_usd'] += usd
            received = zwg
        else:
            totals['usd_received'] += usd
            received = usd
        row = methods.setdefault((method, currency), [ZERO, ZERO])
        row[0] += received
        row[1] += usd

    for r in (visits.order_by().values('payment_method', 'currency')
              .annotate(usd=Sum('consultation_fee'),
                        zwg=Sum(F('consultation_fee') * F('exchange_rate'), output_field=MONEY))):
        add('fees', r['payment_method'], r['currency'], r['usd'], r['zwg'])

    for r in (items.order_by().values('sale__payment_method', 'sale__currency')
              .annotate(usd=Sum(F('quantity') * F('unit_price'), output_field=MONEY),
                        zwg=Sum(F('quantity') * F('unit_price') * F('sale__exchange_rate'),
                                output_field=MONEY))):
        add('meds', r['sale__payment_method'], r['sale__currency'], r['usd'], r['zwg'])

    result = {k: cents(v) for k, v in totals.items()}
    result['total_usd'] = result['usd_received'] + result['zwg_in_usd']
    result['methods'] = [
        {'label': METHOD_LABELS.get(method, method), 'currency': currency,
         'received': cents(received), 'usd': cents(usd)}
        for (method, currency), (received, usd) in sorted(methods.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]
    return result
