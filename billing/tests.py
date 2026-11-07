from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.testutils import make_medicine, make_patient, make_user, sale_post, setup_roles
from .models import Sale, Visit


class VisitRuleTests(TestCase):
    def setUp(self):
        self.patient = make_patient()

    def test_fee_below_minimum_is_refused_by_the_model(self):
        v = Visit(patient=self.patient, consultation_fee=Decimal('0.40'), payment_method='cash')
        with self.assertRaises(ValidationError):
            v.full_clean()
        with self.assertRaises(ValidationError):
            v.save()

    def test_minimum_fee_is_accepted(self):
        Visit.objects.create(patient=self.patient, consultation_fee=Decimal('0.50'), payment_method='cash')

    def test_database_itself_refuses_a_low_fee(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Visit.objects.bulk_create([Visit(patient=self.patient, consultation_fee=Decimal('0.10'),
                                             payment_method='cash')])

    def test_ecocash_needs_a_reference(self):
        v = Visit(patient=self.patient, consultation_fee=Decimal('5'), payment_method='ecocash')
        with self.assertRaises(ValidationError):
            v.full_clean()


class SaleRuleTests(TestCase):
    def setUp(self):
        setup_roles()
        self.pharmacist = make_user('Pharmacist')
        self.client.force_login(self.pharmacist)
        self.url = reverse('sale_add')
        self.woman = make_patient('F', 25, first='Rudo')
        self.man = make_patient('M', 30, first='Tafara')
        self.para = make_medicine('Paracetamol', '0.30', stock=100)
        self.pill = make_medicine('Pill', '2.00', stock=10, contraceptive=True)

    def post(self, patient, items, **kw):
        return self.client.post(self.url, sale_post(patient, items, **kw))

    def test_sale_deducts_stock_and_locks_the_price(self):
        r = self.post(self.woman, [(self.para, 4), (self.pill, 1)])
        sale = Sale.objects.get()
        self.assertRedirects(r, reverse('sale_detail', args=[sale.pk]))
        assert sale.total == Decimal('3.20')
        assert sale.created_by == self.pharmacist
        self.para.refresh_from_db(); self.pill.refresh_from_db()
        assert (self.para.quantity, self.pill.quantity) == (96, 9)
        self.para.unit_price = Decimal('9.99'); self.para.save()
        assert Sale.objects.get().total == Decimal('3.20')  # old sales keep their price

    def test_contraceptive_refused_for_male_patient(self):
        r = self.post(self.man, [(self.pill, 1)])
        self.assertContains(r, "be issued to male patients")
        assert not Sale.objects.exists()
        self.pill.refresh_from_db()
        assert self.pill.quantity == 10

    def test_contraceptive_refused_for_over_age_patient(self):
        old = make_patient('F', 60, first='Gogo')
        r = self.post(old, [(self.pill, 1)])
        self.assertContains(r, "be issued to patients over")
        assert not Sale.objects.exists()

    def test_other_medicines_are_fine_for_a_male_patient(self):
        self.post(self.man, [(self.para, 3)])
        assert Sale.objects.count() == 1

    def test_sale_total_must_reach_the_minimum_payment(self):
        r = self.post(self.woman, [(self.para, 1)])  # 0.30
        self.assertContains(r, 'below 0.50')
        assert not Sale.objects.exists()
        self.post(self.woman, [(self.para, 2)])      # 0.60
        assert Sale.objects.count() == 1

    def test_several_cheap_lines_can_add_up_to_the_minimum(self):
        ors = make_medicine('ORS', '0.40', stock=10)
        self.post(self.woman, [(self.para, 1), (ors, 1)])  # 0.70
        assert Sale.objects.count() == 1

    def test_cannot_sell_more_than_is_in_stock(self):
        r = self.post(self.woman, [(self.pill, 11)])
        self.assertContains(r, 'Not enough')
        # two lines of the same medicine are added together before checking
        r = self.post(self.woman, [(self.pill, 6), (self.pill, 6)])
        self.assertContains(r, 'Not enough')
        assert not Sale.objects.exists()

    def test_expired_medicine_cannot_be_sold(self):
        old = make_medicine('Old', '1.00', stock=5, expiry=timezone.localdate() - timedelta(days=1))
        r = self.post(self.woman, [(old, 1)])
        self.assertContains(r, 'expired')
        assert not Sale.objects.exists()

    def test_ecocash_sale_needs_a_reference(self):
        r = self.post(self.woman, [(self.para, 2)], method='ecocash')
        self.assertContains(r, 'reference is required')
        self.post(self.woman, [(self.para, 2)], method='ecocash', ref='MP260101.1234')
        assert Sale.objects.get().payment_reference == 'MP260101.1234'

    def test_a_sale_needs_at_least_one_medicine(self):
        r = self.client.post(self.url, sale_post(self.woman, []))
        self.assertContains(r, 'Add at least one medicine')

    def test_receipt_page(self):
        self.post(self.woman, [(self.para, 4)])
        sale = Sale.objects.get()
        r = self.client.get(reverse('sale_detail', args=[sale.pk]))
        self.assertContains(r, '1.20 USD')
        self.assertContains(r, 'Paracetamol')


class BillingPermissionTests(TestCase):
    def setUp(self):
        setup_roles()
        self.patient = make_patient()
        self.reception = make_user('Receptionist')
        self.pharmacist = make_user('Pharmacist')

    def test_receptionist_records_visits_but_cannot_sell(self):
        self.client.force_login(self.reception)
        r = self.client.post(reverse('visit_add'), {
            'patient': self.patient.pk, 'consultation_fee': '5.00', 'currency': 'USD', 'payment_method': 'cash',
            'payment_reference': '', 'notes': 'Check-up'})
        self.assertRedirects(r, reverse('patient_history', args=[self.patient.pk]))
        assert Visit.objects.get().created_by == self.reception
        assert self.client.get(reverse('sale_add')).status_code == 403

    def test_visit_form_refuses_a_low_fee(self):
        self.client.force_login(self.reception)
        r = self.client.post(reverse('visit_add'), {
            'patient': self.patient.pk, 'consultation_fee': '0.40', 'currency': 'USD', 'payment_method': 'cash',
            'payment_reference': '', 'notes': ''})
        self.assertContains(r, 'below 0.50')
        assert not Visit.objects.exists()

    def test_pharmacist_sells_but_cannot_record_visits(self):
        self.client.force_login(self.pharmacist)
        assert self.client.get(reverse('visit_add')).status_code == 403
        assert self.client.get(reverse('sale_add')).status_code == 200
