from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from billing.rates import RateError, fetch_rate, store_rate


class Command(BaseCommand):
    help = ('Update the USD to ZiG exchange rate. With no options it fetches the RBZ rate '
            '(or the market fallback). Schedule it once every weekday morning.')

    def add_arguments(self, parser):
        parser.add_argument('--rate', help='Set the rate by hand instead of fetching it (ZiG per 1 USD).')
        parser.add_argument('--date', help='Date for --rate as YYYY-MM-DD (default: today).')
        parser.add_argument('--source', default='Manual (command line)', help='Note saved with a manual rate.')
        parser.add_argument('--force', action='store_true', help='Accept a rate even if it jumped a lot.')

    def handle(self, *args, **opts):
        try:
            if opts['rate']:
                try:
                    rate = Decimal(opts['rate'])
                    when = date.fromisoformat(opts['date']) if opts['date'] else timezone.localdate()
                except (InvalidOperation, ValueError):
                    raise CommandError('Give --rate as a number and --date as YYYY-MM-DD.')
                source = opts['source']
            else:
                rate, when, source = fetch_rate()
            obj, created = store_rate(rate, when, source, force=opts['force'])
        except RateError as exc:
            raise CommandError(str(exc))
        if created:
            self.stdout.write(self.style.SUCCESS(f'Saved: {obj}  [{obj.source}]'))
        else:
            self.stdout.write(f'Already up to date: {obj}')
