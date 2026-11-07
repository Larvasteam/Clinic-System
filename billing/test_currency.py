import io
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.testutils import (make_medicine, make_patient, make_rate, make_user, sale_post, setup_roles)
from . import rates
from .ledger import summarise
from .models import ExchangeRate, Sale, SaleItem, Visit
from .rates import RateError, parse_allrates, parse_open, store_rate

RBZ_TABLE = {
    'bank': 'rbz', 'rate_date': '2026-10-09',
    'rates': [
        {'base': 'AUD', 'quote': 'ZWG', 'type': 'middle', 'value': 18.6467},
        {'base': 'USD', 'quote': 'ZWG', 'type': 'buy', 'value': 26.0203},
        {'base': 'USD', 'quote': 'ZWG', 'type': 'middle', 'value': 26.1500},
        {'base': 'USD', 'quote': 'ZWG', 'type': 'sell', 'value': 26.2797},
    ],
}


class ExchangeRateModelTests(TestCase):
    def test_current_is_the_newest_date_then_the_latest_entry(self):
        make_rate('26.0', days_old=5)
        newest = make_rate('26.2', days_old=1)
        assert ExchangeRate.current() == newest
        corrected = make_rate('26.3', days_old=1)  # same date, entered later: it wins
        assert ExchangeRate.current() == corrected

    def test_stale_after_three_days(self):
        assert not make_rate(days_old=3).is_stale
        assert make_rate(days_old=4).is_stale


class ZigPaymentTests(TestCase):
    def setUp(self):
        setup_roles()
        self.rate = make_rate('26.0000')
        self.patient = make_patient()
        self.reception = make_user('Receptionist')
        self.pharmacist = make_user('Pharmacist')

    def visit_post(self, currency, fee='5.00', method='cash'):
        return {'patient': self.patient.pk, 'consultation_fee': fee, 'currency': currency,
                'payment_method': method, 'payment_reference': '', 'notes': ''}

    def test_visit_paid_in_zig_locks_the_rate(self):
        self.client.force_login(self.reception)
        self.client.post(reverse('visit_add'), self.visit_post('ZWG'))
        visit = Visit.objects.get()
        assert (visit.currency, visit.exchange_rate) == ('ZWG', Decimal('26.0000'))
        assert visit.amount_zwg == Decimal('130.00') and visit.paid_amount == Decimal('130.00')
        make_rate('40.0000')  # the rate moves later
        visit.refresh_from_db()
        assert visit.amount_zwg == Decimal('130.00')  # old records never change

    def test_usd_payment_also_remembers_the_rate(self):
        self.client.force_login(self.reception)
        self.client.post(reverse('visit_add'), self.visit_post('USD'))
        visit = Visit.objects.get()
        assert visit.paid_amount == Decimal('5.00') and visit.exchange_rate == Decimal('26.0000')

    def test_zig_is_not_offered_without_a_rate(self):
        ExchangeRate.objects.all().delete()
        self.client.force_login(self.reception)
        r = self.client.post(reverse('visit_add'), self.visit_post('ZWG'))
        assert r.status_code == 200 and not Visit.objects.exists()
        self.assertContains(self.client.get(reverse('visit_add')), 'only US dollars can be recorded')

    def test_the_model_itself_refuses_zig_without_a_rate(self):
        ExchangeRate.objects.all().delete()
        visit = Visit(patient=self.patient, consultation_fee=Decimal('5'), payment_method='cash', currency='ZWG')
        with self.assertRaises(ValidationError):
            visit.full_clean()
        with self.assertRaises(ValidationError):
            visit.save()

    def test_database_refuses_zig_without_a_rate(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Visit.objects.bulk_create([Visit(patient=self.patient, consultation_fee=Decimal('5'),
                                             payment_method='cash', currency='ZWG', exchange_rate=None)])

    def test_the_minimum_payment_still_applies_to_zig_payments(self):
        self.client.force_login(self.reception)
        r = self.client.post(reverse('visit_add'), self.visit_post('ZWG', fee='0.40'))
        self.assertContains(r, 'below 0.50')
        assert not Visit.objects.exists()

    def test_sale_in_zig(self):
        para = make_medicine('Paracetamol', '0.30', stock=100)
        self.client.force_login(self.pharmacist)
        r = self.client.post(reverse('sale_add'), sale_post(self.patient, [(para, 10)], currency='ZWG'))
        sale = Sale.objects.get()
        self.assertRedirects(r, reverse('sale_detail', args=[sale.pk]))
        assert sale.total == Decimal('3.00') and sale.amount_zwg == Decimal('78.00')
        page = self.client.get(reverse('sale_detail', args=[sale.pk]))
        self.assertContains(page, '78.00 ZiG')
        self.assertContains(page, '26.0000')

    def test_flash_message_says_what_to_collect(self):
        self.client.force_login(self.reception)
        r = self.client.post(reverse('visit_add'), self.visit_post('ZWG'), follow=True)
        self.assertContains(r, 'collect 130.00 ZiG')


class LedgerTests(TestCase):
    def setUp(self):
        make_rate('26.0000')
        self.patient = make_patient()
        self.para = make_medicine('Paracetamol', '0.30', stock=1000)

    def add_visit(self, fee, currency, method='cash'):
        Visit.objects.create(patient=self.patient, consultation_fee=Decimal(fee), payment_method=method,
                             currency=currency)

    def add_sale(self, qty, currency, method='cash'):
        sale = Sale.objects.create(patient=self.patient, payment_method=method, currency=currency)
        SaleItem.objects.create(sale=sale, medicine=self.para, quantity=qty)

    def test_two_balances_and_a_combined_total(self):
        self.add_visit('5.00', 'USD')
        self.add_visit('10.00', 'ZWG')      # 260 ZiG
        self.add_sale(10, 'USD')            # 3.00
        self.add_sale(10, 'ZWG')            # 78 ZiG
        s = summarise(Visit.objects.all(), SaleItem.objects.all())
        assert s['usd_received'] == Decimal('8.00')
        assert s['zwg_received'] == Decimal('338.00')
        assert s['zwg_in_usd'] == Decimal('13.00')
        assert s['total_usd'] == Decimal('21.00')
        assert (s['fees'], s['meds']) == (Decimal('15.00'), Decimal('6.00'))

    def test_old_zig_payments_keep_their_own_rate(self):
        self.add_visit('10.00', 'ZWG')      # at 26
        make_rate('30.0000')
        self.add_visit('10.00', 'ZWG')      # at 30
        s = summarise(Visit.objects.all(), SaleItem.objects.none())
        assert s['zwg_received'] == Decimal('560.00')   # 260 + 300
        assert s['total_usd'] == Decimal('20.00')

    def test_payment_methods_are_split_by_currency(self):
        self.add_visit('5.00', 'USD', 'cash')
        self.add_visit('5.00', 'ZWG', 'cash')
        s = summarise(Visit.objects.all(), SaleItem.objects.none())
        rows = {(m['label'], m['currency']): (m['received'], m['usd']) for m in s['methods']}
        assert rows[('Cash', 'USD')] == (Decimal('5.00'), Decimal('5.00'))
        assert rows[('Cash', 'ZWG')] == (Decimal('130.00'), Decimal('5.00'))

    def test_pages_show_both_balances(self):
        setup_roles()
        admin = make_user(superuser=True)
        self.add_visit('5.00', 'USD'); self.add_visit('10.00', 'ZWG')
        self.client.force_login(admin)
        page = self.client.get(reverse('dashboard'))
        self.assertContains(page, 'USD balance')
        self.assertContains(page, 'ZiG balance')
        self.assertContains(page, '260.00 ZiG')
        sheet = self.client.get(reverse('sheet'), {'period': 'daily'})
        self.assertContains(sheet, '260.00 ZiG')
        self.assertContains(sheet, '5.00 USD')


class ParsingTests(TestCase):
    def test_rbz_middle_rate_is_chosen_from_the_table(self):
        rate, published = parse_allrates(RBZ_TABLE)
        assert rate == Decimal('26.15') and published == date(2026, 10, 9)

    def test_middle_is_worked_out_from_buy_and_sell_if_missing(self):
        table = {**RBZ_TABLE, 'rates': [r for r in RBZ_TABLE['rates'] if r['type'] != 'middle']}
        rate, _ = parse_allrates(table)
        assert rate == (Decimal('26.0203') + Decimal('26.2797')) / 2

    def test_missing_usd_row_or_date_is_an_error(self):
        with self.assertRaises(RateError):
            parse_allrates({'rate_date': '2026-10-09', 'rates': [RBZ_TABLE['rates'][0]]})
        with self.assertRaises(RateError):
            parse_allrates({'rates': RBZ_TABLE['rates']})

    def test_open_api(self):
        rate, published = parse_open({'result': 'success', 'rates': {'USD': 1, 'ZWG': 26.9}})
        assert rate == Decimal('26.9') and published == timezone.localdate()
        with self.assertRaises(RateError):
            parse_open({'result': 'success', 'rates': {'USD': 1}})
        with self.assertRaises(RateError):
            parse_open({'result': 'error'})


class FetchAndStoreTests(TestCase):
    def test_uses_the_rbz_feed_when_a_key_is_set(self):
        with self.settings(ALLRATES_API_KEY='k'), mock.patch.object(rates, '_get_json', return_value=RBZ_TABLE) as g:
            rate, published, source = rates.fetch_rate()
        assert rate == Decimal('26.15') and 'RBZ' in source
        assert g.call_args.args[1] == {'Authorization': 'Bearer k'}

    def test_falls_back_to_the_open_api_when_there_is_no_key(self):
        reply = {'result': 'success', 'rates': {'ZWG': 26.9}}
        with self.settings(ALLRATES_API_KEY=''), mock.patch.object(rates, '_get_json', return_value=reply):
            rate, _, source = rates.fetch_rate()
        assert rate == Decimal('26.9') and 'open.er-api' in source

    def test_falls_back_when_the_rbz_feed_fails(self):
        def fake(url, headers=None, timeout=15):
            if 'allratestoday' in url:
                raise RateError('down')
            return {'result': 'success', 'rates': {'ZWG': 26.9}}
        with self.settings(ALLRATES_API_KEY='k'), mock.patch.object(rates, '_get_json', side_effect=fake):
            assert rates.fetch_rate()[0] == Decimal('26.9')

    def test_reports_every_problem_when_both_sources_fail(self):
        with self.settings(ALLRATES_API_KEY=''), mock.patch.object(rates, '_get_json', side_effect=RateError('offline')):
            with self.assertRaises(RateError) as ctx:
                rates.fetch_rate()
        assert 'ALLRATES_API_KEY' in str(ctx.exception) and 'offline' in str(ctx.exception)

    def test_store_rate_ignores_a_repeat_and_refuses_a_wild_jump(self):
        today = timezone.localdate()
        first, created = store_rate(Decimal('26.15'), today, 'x')
        again, created_again = store_rate(Decimal('26.15'), today, 'x')
        assert created and not created_again and first == again
        with self.assertRaises(RateError):
            store_rate(Decimal('40'), today, 'x')                     # +53%
        assert store_rate(Decimal('40'), today, 'x', force=True)[1]    # unless forced
        for silly in ('0.5', '900'):
            with self.assertRaises(RateError):
                store_rate(Decimal(silly), today, 'x', force=True)     # outside the believable range

    def test_update_rate_command_by_hand_and_by_fetch(self):
        out = io.StringIO()
        call_command('update_rate', '--rate', '26.2', stdout=out)
        assert ExchangeRate.current().usd_to_zwg == Decimal('26.2000')
        with mock.patch('billing.management.commands.update_rate.fetch_rate',
                        return_value=(Decimal('26.3'), timezone.localdate(), 'feed')):
            call_command('update_rate', stdout=out)
        assert ExchangeRate.current().source == 'feed'
        with self.assertRaises(CommandError):
            call_command('update_rate', '--rate', 'abc', stdout=out)
        with mock.patch('billing.management.commands.update_rate.fetch_rate', side_effect=RateError('offline')):
            with self.assertRaises(CommandError):
                call_command('update_rate', stdout=out)


class RateViewTests(TestCase):
    def setUp(self):
        setup_roles()
        self.admin = make_user(superuser=True)
        self.pharmacist = make_user('Pharmacist')
        self.reception = make_user('Receptionist')
        make_rate('26.0000')

    def test_only_the_admin_manages_rates(self):
        for user in (self.pharmacist, self.reception):
            self.client.force_login(user)
            assert self.client.get(reverse('rate_list')).status_code == 403
            assert self.client.get(reverse('rate_add')).status_code == 403
            assert self.client.post(reverse('rate_fetch')).status_code == 403

    def test_admin_sets_a_rate_by_hand(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse('rate_add'), {'date': timezone.localdate().isoformat(),
                                                   'usd_to_zwg': '26.5000', 'source': ''})
        self.assertRedirects(r, reverse('rate_list'))
        current = ExchangeRate.current()
        assert current.usd_to_zwg == Decimal('26.5000') and current.created_by == self.admin
        assert current.source == 'Manual'

    def test_typing_mistakes_are_caught(self):
        self.client.force_login(self.admin)
        today = timezone.localdate().isoformat()
        r = self.client.post(reverse('rate_add'), {'date': today, 'usd_to_zwg': '2.65'})
        self.assertContains(r, 'between')
        r = self.client.post(reverse('rate_add'), {'date': today, 'usd_to_zwg': '40'})   # +54%
        self.assertContains(r, 'different from the last rate')
        r = self.client.post(reverse('rate_add'), {'date': today, 'usd_to_zwg': '40', 'confirm_large_change': 'on'})
        self.assertRedirects(r, reverse('rate_list'))
        future = (timezone.localdate() + timedelta(days=2)).isoformat()
        r = self.client.post(reverse('rate_add'), {'date': future, 'usd_to_zwg': '40'})
        self.assertContains(r, 'cannot be in the future')

    def test_fetch_button(self):
        self.client.force_login(self.admin)
        with mock.patch('billing.views.fetch_rate', return_value=(Decimal('26.2'), timezone.localdate(), 'feed')):
            r = self.client.post(reverse('rate_fetch'), follow=True)
        self.assertContains(r, 'Rate updated')
        with mock.patch('billing.views.fetch_rate', side_effect=RateError('offline')):
            r = self.client.post(reverse('rate_fetch'), follow=True)
        self.assertContains(r, 'was not updated')
        assert self.client.get(reverse('rate_fetch')).status_code == 405

    def test_everyone_sees_the_current_rate_and_a_stale_warning(self):
        self.client.force_login(self.reception)
        self.assertContains(self.client.get(reverse('dashboard')), '1 USD = 26.0000 ZiG')
        ExchangeRate.objects.all().delete()
        make_rate('26.0000', days_old=9)
        page = self.client.get(reverse('dashboard'))
        self.assertContains(page, 'rate stale')
        ExchangeRate.objects.all().delete()
        self.assertContains(self.client.get(reverse('dashboard')), 'No ZiG rate set')
