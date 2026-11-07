from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _money(value, code):
    try:
        return f"{Decimal(str(value)):,.2f} {code}"
    except (InvalidOperation, ValueError, TypeError):
        return '-'


@register.filter
def usd(value):
    """1234.5 -> '1,234.50 USD'"""
    return _money(value, 'USD')


@register.filter
def zig(value):
    """1234.5 -> '1,234.50 ZiG'"""
    return _money(value, 'ZiG')


@register.filter
def paid(payment):
    """A visit or sale shown in the currency it was paid in."""
    amount = payment.paid_amount
    if amount is None:
        return '-'
    return zig(amount) if payment.currency == 'ZWG' else usd(amount)
