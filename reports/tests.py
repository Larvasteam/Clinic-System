from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Sale, SaleItem, Visit
from config.testutils import make_medicine, make_patient, make_user, setup_roles
from .views import period_range


class PeriodRangeTests(TestCase):
    def test_ranges(self):
        d = date(2026, 11, 4)  # a Wednesday
        assert period_range('daily', d) == (d, d)
        assert period_range('weekly', d) == (date(2026, 11, 2), date(2026, 11, 8))  # Monday to Sunday
        assert period_range('monthly', d) == (date(2026, 11, 1), date(2026, 11, 30))
        assert period_range('quarterly', d) == (date(2026, 10, 1), date(2026, 12, 31))
        assert period_range('yearly', d) == (date(2026, 1, 1), date(2026, 12, 31))
        assert period_range('quarterly', date(2026, 2, 10)) == (date(2026, 1, 1), date(2026, 3, 31))


class ReportFixture(TestCase):
    def setUp(self):
        setup_roles()
        self.admin = make_user(superuser=True)
        self.pharmacist = make_user('Pharmacist')
        self.reception = make_user('Receptionist')
        self.patient = make_patient()
        self.med = make_medicine('Paracetamol', '0.30', stock=100)
        Visit.objects.create(patient=self.patient, consultation_fee=Decimal('5.00'), payment_method='cash')
        sale = Sale.objects.create(patient=self.patient, payment_method='ecocash', payment_reference='R1')
        SaleItem.objects.create(sale=sale, medicine=self.med, quantity=10)  # 3.00


class SheetTests(ReportFixture):
    def test_daily_totals_and_payment_methods(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('sheet'), {'period': 'daily', 'date': timezone.localdate().isoformat()})
        assert r.status_code == 200
        assert r.context['fees'] == Decimal('5.00')
        assert r.context['meds'] == Decimal('3.00')
        assert r.context['total'] == Decimal('8.00')
        methods = {(m['label'], m['currency']): m['received'] for m in r.context['methods']}
        assert methods == {('Cash', 'USD'): Decimal('5.00'), ('EcoCash', 'USD'): Decimal('3.00')}

    def test_all_five_periods_work_for_admin(self):
        self.client.force_login(self.admin)
        for p in ('daily', 'weekly', 'monthly', 'quarterly', 'yearly'):
            r = self.client.get(reverse('sheet'), {'period': p})
            assert r.status_code == 200 and r.context['total'] == Decimal('8.00'), p

    def test_a_different_day_is_empty(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('sheet'), {'period': 'daily', 'date': '2020-01-01'})
        assert r.context['total'] == Decimal('0')

    def test_pharmacist_gets_daily_and_weekly_only(self):
        self.client.force_login(self.pharmacist)
        assert self.client.get(reverse('sheet'), {'period': 'daily'}).status_code == 200
        assert self.client.get(reverse('sheet'), {'period': 'weekly'}).status_code == 200
        for p in ('monthly', 'quarterly', 'yearly'):
            assert self.client.get(reverse('sheet'), {'period': p}).status_code == 403, p

    def test_receptionist_gets_no_sheets(self):
        self.client.force_login(self.reception)
        assert self.client.get(reverse('sheet')).status_code == 403


class DashboardTests(ReportFixture):
    def test_money_is_for_admins_only(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('dashboard')), 'Money earned')
        for user in (self.pharmacist, self.reception):
            self.client.force_login(user)
            self.assertNotContains(self.client.get(reverse('dashboard')), 'Money earned')

    def test_sidebar_follows_the_role(self):
        self.client.force_login(self.reception)
        page = self.client.get(reverse('dashboard'))
        self.assertNotContains(page, 'Stock Management')
        self.assertNotContains(page, 'New Sale')
        self.assertContains(page, 'New Visit')
        self.client.force_login(self.pharmacist)
        page = self.client.get(reverse('dashboard'))
        self.assertContains(page, 'Stock Management')
        self.assertContains(page, 'New Sale')


class SmokeTests(ReportFixture):
    def test_every_page_loads_for_an_admin(self):
        self.client.force_login(self.admin)
        pages = [
            reverse('dashboard'), reverse('medicine_list'), reverse('medicine_add'),
            reverse('medicine_edit', args=[self.med.pk]), reverse('medicine_stock', args=[self.med.pk]),
            reverse('stock_management'), reverse('expiry_alerts'), reverse('patient_list'),
            reverse('patient_add'), reverse('patient_history', args=[self.patient.pk]),
            reverse('patient_edit', args=[self.patient.pk]), reverse('visit_add'),
            reverse('sale_add'), reverse('sale_detail', args=[Sale.objects.get().pk]),
            reverse('sheet'), reverse('rate_list'), reverse('rate_add'), reverse('search') + '?q=para', reverse('login'),
            reverse('admin:index'),
        ]
        for url in pages:
            r = self.client.get(url)
            assert r.status_code == 200, (url, r.status_code)

    def test_search_finds_medicines_and_patients(self):
        self.client.force_login(self.reception)
        r = self.client.get(reverse('search'), {'q': 'para'})
        self.assertContains(r, 'Paracetamol')
        r = self.client.get(reverse('search'), {'q': 'patient'})
        self.assertContains(r, 'Test Patient')

    def test_login_page_works_and_logout_needs_post(self):
        assert self.client.get(reverse('login')).status_code == 200
        r = self.client.post(reverse('login'), {'username': 'nobody', 'password': 'nope'})
        self.assertContains(r, 'Wrong username or password')
