from .roles import user_roles


def nav(request):
    """Tells every page which sections this user may see, and what the current ZiG rate is."""
    from billing.models import ExchangeRate  # imported here to avoid a circular import at start-up

    user = request.user
    roles = user_roles(user)
    rate = ExchangeRate.current() if user.is_authenticated else None
    return {
        'can_sheets': bool(roles & {'Admin', 'Pharmacist'}),
        'can_stock': user.is_authenticated and user.has_perm('pharmacy.view_stockmovement'),
        'rate': rate,
        'rate_stale': bool(rate and rate.is_stale),
    }
