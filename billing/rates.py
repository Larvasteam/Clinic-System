"""Fetching and storing the USD to ZiG exchange rate."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import ExchangeRate

# AllRatesToday serves the Reserve Bank of Zimbabwe's official daily interbank sheet as JSON.
# Free plan: latest rates only, around 300 requests a month, API key needed (allratestoday.com/register).
ALLRATES_URL = 'https://allratestoday.com/api/v1/central-bank/rbz/latest'
# Keyless market-rate fallback (updates once a day; asks for attribution to exchangerate-api.com).
OPEN_URL = 'https://open.er-api.com/v6/latest/USD'

RATE_MIN = Decimal('1')      # ZiG per US dollar: anything outside this range is a typing mistake
RATE_MAX = Decimal('500')


class RateError(Exception):
    pass


def _get_json(url, headers=None, timeout=15):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'clinic-system/1.0',
                                    **(headers or {})})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except (OSError, ValueError) as exc:  # network trouble, HTTP errors and bad JSON
        raise RateError(f"could not read {url.split('/')[2]} ({exc})")


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise RateError(f'unreadable rate value: {value!r}')


def parse_allrates(data):
    """The RBZ middle rate (ZiG per 1 USD) from the bank's full latest table."""
    try:
        published = date.fromisoformat(data['rate_date'])
    except (KeyError, TypeError, ValueError):
        raise RateError('the RBZ reply has no valid rate_date')
    legs = {row.get('type'): row.get('value') for row in data.get('rates', [])
            if row.get('base') == 'USD' and row.get('quote') == 'ZWG'}
    if legs.get('middle') is not None:
        return _to_decimal(legs['middle']), published
    if legs.get('buy') is not None and legs.get('sell') is not None:
        return (_to_decimal(legs['buy']) + _to_decimal(legs['sell'])) / 2, published
    raise RateError('the RBZ table has no USD to ZWG rate')


def parse_open(data):
    if data.get('result') != 'success':
        raise RateError('open.er-api.com did not return a successful result')
    zwg = (data.get('rates') or {}).get('ZWG')
    if not zwg:
        raise RateError('open.er-api.com has no ZWG rate')
    return _to_decimal(zwg), timezone.localdate()


def fetch_rate():
    """Return (rate, rate_date, source). Tries the RBZ official rate first, then the market fallback."""
    problems = []
    key = getattr(settings, 'ALLRATES_API_KEY', '')
    if key:
        try:
            rate, published = parse_allrates(_get_json(ALLRATES_URL, {'Authorization': f'Bearer {key}'}))
            return rate, published, 'RBZ interbank middle rate (AllRatesToday)'
        except RateError as exc:
            problems.append(f'RBZ feed: {exc}')
    else:
        problems.append('RBZ feed: ALLRATES_API_KEY is not set')
    try:
        rate, published = parse_open(_get_json(OPEN_URL))
        return rate, published, 'Market rate (open.er-api.com)'
    except RateError as exc:
        problems.append(f'fallback: {exc}')
    raise RateError('; '.join(problems))


def store_rate(rate, rate_date, source, user=None, force=False):
    """Save a rate. Returns (ExchangeRate, created). Refuses absurd values and sudden jumps unless forced."""
    rate = Decimal(rate).quantize(Decimal('0.0001'))
    if not (RATE_MIN <= rate <= RATE_MAX):
        raise RateError(f'{rate} is outside the believable range ({RATE_MIN} to {RATE_MAX} ZiG per USD).')
    last = ExchangeRate.current()
    if last and not force:
        change = abs(rate / last.usd_to_zwg - 1)
        if change > Decimal(str(getattr(settings, 'RATE_MAX_CHANGE', 0.25))):
            raise RateError(f'{rate} is {change:.0%} different from the last rate ({last.usd_to_zwg}). '
                            'Check it, then enter it by hand (or use --force) if it is correct.')
    if last and last.date == rate_date and last.usd_to_zwg == rate:
        return last, False
    return ExchangeRate.objects.create(date=rate_date, usd_to_zwg=rate, source=source, created_by=user), True
