from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.testutils import make_medicine, make_user, setup_roles
from .models import Medicine, StockMovement


class StockColourTests(TestCase):
    def colour(self, qty):
        m = Medicine(name='x', unit_price=1, quantity=qty, low_threshold=10, high_threshold=50)
        return m.stock_colour

    def test_thresholds(self):
        assert self.colour(0) == 'red'
        assert self.colour(10) == 'red'      # at the low level = red
        assert self.colour(11) == 'yellow'
        assert self.colour(49) == 'yellow'
        assert self.colour(50) == 'green'    # at the high level = green
        assert self.colour(500) == 'green'

    def test_out_of_stock_label(self):
        assert Medicine(name='x', unit_price=1, quantity=0).stock_status == 'Out of stock'


class StockMovementTests(TestCase):
    def test_movements_change_the_quantity(self):
        med = make_medicine(stock=0)
        StockMovement.objects.create(medicine=med, movement_type='in', quantity=60)
        StockMovement.objects.create(medicine=med, movement_type='sale', quantity=20)
        StockMovement.objects.create(medicine=med, movement_type='adjust', quantity=-5)
        med.refresh_from_db()
        assert med.quantity == 35

    def test_cannot_remove_more_than_is_in_stock(self):
        med = make_medicine(stock=5)
        with self.assertRaises(ValidationError):
            StockMovement.objects.create(medicine=med, movement_type='sale', quantity=6)
        med.refresh_from_db()
        assert med.quantity == 5

    def test_movements_cannot_be_edited(self):
        med = make_medicine(stock=5)
        mv = StockMovement.objects.filter(medicine=med).first()
        mv.note = 'changed'
        with self.assertRaises(ValidationError):
            mv.save()

    def test_negative_stock_in_is_refused(self):
        med = make_medicine(stock=5)
        with self.assertRaises(ValidationError):
            StockMovement(medicine=med, movement_type='in', quantity=-3).full_clean()


class ExpiryTests(TestCase):
    def test_expiring_within_six_months(self):
        today = timezone.localdate()
        assert Medicine(name='a', unit_price=1, expiry_date=today + timedelta(days=150)).expiring_soon
        assert not Medicine(name='b', unit_price=1, expiry_date=today + timedelta(days=400)).expiring_soon
        assert Medicine(name='c', unit_price=1, expiry_date=today - timedelta(days=1)).expired
        assert not Medicine(name='d', unit_price=1).expiring_soon


class MedicineViewTests(TestCase):
    def setUp(self):
        setup_roles()
        self.pharmacist = make_user('Pharmacist')
        self.reception = make_user('Receptionist')

    def test_pharmacist_adds_medicine_with_opening_stock(self):
        self.client.force_login(self.pharmacist)
        r = self.client.post(reverse('medicine_add'), {
            'name': 'ORS sachet', 'unit_price': '0.40', 'low_threshold': 30, 'high_threshold': 150,
            'expiry_date': '', 'opening_stock': 20})
        self.assertRedirects(r, reverse('medicine_list'))
        med = Medicine.objects.get()
        assert med.quantity == 20
        assert med.movements.get().note == 'Opening stock'

    def test_high_level_must_be_above_low_level(self):
        self.client.force_login(self.pharmacist)
        r = self.client.post(reverse('medicine_add'), {
            'name': 'X', 'unit_price': '1.00', 'low_threshold': 50, 'high_threshold': 10})
        self.assertContains(r, 'must be larger')
        assert not Medicine.objects.exists()

    def test_stock_form_refuses_overselling(self):
        med = make_medicine(stock=5)
        self.client.force_login(self.pharmacist)
        r = self.client.post(reverse('medicine_stock', args=[med.pk]), {
            'medicine': med.pk, 'movement_type': 'adjust', 'quantity': -9, 'note': 'x'})
        self.assertContains(r, 'Not enough stock')
        med.refresh_from_db()
        assert med.quantity == 5

    def test_stock_form_records_stock_in_with_user(self):
        med = make_medicine(stock=5)
        self.client.force_login(self.pharmacist)
        self.client.post(reverse('medicine_stock', args=[med.pk]), {
            'medicine': med.pk, 'movement_type': 'in', 'quantity': 10, 'note': 'Delivery'})
        med.refresh_from_db()
        assert med.quantity == 15
        assert med.movements.first().created_by == self.pharmacist

    def test_receptionist_can_view_medicines_only(self):
        med = make_medicine()
        self.client.force_login(self.reception)
        assert self.client.get(reverse('medicine_list')).status_code == 200
        assert self.client.get(reverse('medicine_add')).status_code == 403
        assert self.client.get(reverse('medicine_edit', args=[med.pk])).status_code == 403
        assert self.client.get(reverse('medicine_stock', args=[med.pk])).status_code == 403
        assert self.client.get(reverse('stock_management')).status_code == 403
        assert self.client.get(reverse('expiry_alerts')).status_code == 403

    def test_csv_export_neutralises_formulas(self):
        make_medicine(name='=HYPERLINK("http://bad")')
        self.client.force_login(self.pharmacist)
        body = self.client.get(reverse('medicine_export')).content.decode()
        assert "'=HYPERLINK" in body

    def test_filter_by_status(self):
        make_medicine(name='Plenty', stock=100)
        make_medicine(name='Scarce', stock=3)
        self.client.force_login(self.pharmacist)
        r = self.client.get(reverse('medicine_list'), {'level': 'red'})
        self.assertContains(r, 'Scarce')
        self.assertNotContains(r, 'Plenty')
