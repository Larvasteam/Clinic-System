"""Small helpers shared by the test suites."""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone

from billing.models import ExchangeRate
from patients.models import Patient
from pharmacy.models import Medicine, StockMovement

PASSWORD = 'a-long-test-password-1'


def setup_roles():
    call_command('setup_roles', stdout=io.StringIO())


def make_user(role=None, superuser=False, username=None):
    User = get_user_model()
    username = username or (role or 'super').lower()
    if superuser:
        return User.objects.create_superuser(username, password=PASSWORD)
    user = User.objects.create_user(username, password=PASSWORD)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def make_patient(gender='F', age=25, first='Test', surname='Patient'):
    today = timezone.localdate()
    dob = date(today.year - age, min(today.month, 28), min(today.day, 28)) - timedelta(days=30)
    return Patient.objects.create(first_name=first, surname=surname, gender=gender, date_of_birth=dob)


def make_medicine(name='Paracetamol', price='0.30', stock=100, contraceptive=False,
                  expiry=None, low=10, high=50):
    med = Medicine.objects.create(
        name=name, unit_price=Decimal(price), low_threshold=low, high_threshold=high,
        expiry_date=expiry, is_contraceptive=contraceptive)
    if stock:
        StockMovement.objects.create(medicine=med, movement_type='in', quantity=stock)
    med.refresh_from_db()
    return med


def make_rate(rate='26.0000', days_old=0):
    return ExchangeRate.objects.create(date=timezone.localdate() - timedelta(days=days_old),
                                       usd_to_zwg=Decimal(rate), source='test')


def sale_post(patient, items, method='cash', ref='', currency='USD'):
    """Build the POST data for the New Sale form: items is a list of (medicine, quantity)."""
    data = {'patient': patient.pk, 'currency': currency, 'payment_method': method, 'payment_reference': ref,
            'items-TOTAL_FORMS': str(len(items)), 'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000'}
    for i, (med, qty) in enumerate(items):
        data[f'items-{i}-medicine'] = med.pk
        data[f'items-{i}-quantity'] = qty
    return data
