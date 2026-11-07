import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billing.models import ExchangeRate, Sale, SaleItem, Visit
from patients.models import Patient
from pharmacy.models import Medicine, StockMovement

# Prices are rough estimates for testing only: replace them with the clinic's real price list.
MEDICINES = [
    # name, price, low, high, months to expiry, contraceptive, stock in
    ('Paracetamol 500mg (strip of 10)', '0.30', 50, 300, 22, False, 400),
    ('Amoxicillin 500mg (course of 21 capsules)', '2.50', 20, 80, 16, False, 45),
    ('Cotrimoxazole 480mg (strip of 10)', '0.40', 30, 150, 19, False, 120),
    ('ORS sachet', '0.40', 30, 150, 5, False, 20),
    ('Ibuprofen 400mg (strip of 10)', '0.50', 30, 150, 21, False, 160),
    ('Microgynon 30 combined pill (28 tablets)', '2.00', 15, 60, 20, True, 60),
]

PATIENTS = [
    ('Rudo', 'Chirwa', 'F', 27), ('Tafara', 'Ncube', 'M', 34), ('Nomsa', 'Dube', 'F', 52),
    ('Farai', 'Moyo', 'M', 9), ('Ruvimbo', 'Sibanda', 'F', 31),
]


class Command(BaseCommand):
    help = 'Add fake demo data (never use real patient data in a test system).'

    def add_arguments(self, parser):
        parser.add_argument('--with-users', action='store_true',
                            help='Also create demo users pharm1 and recep1.')
        parser.add_argument('--password', help='Password for the demo users (required with --with-users).')

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['with_users'] and not opts['password']:
            raise CommandError('Give a password with --password when using --with-users.')
        call_command('setup_roles', stdout=io.StringIO())
        today = timezone.localdate()

        if not ExchangeRate.objects.exists():
            # A made-up demo rate. Use `python manage.py update_rate` to load the real one.
            ExchangeRate.objects.create(date=today, usd_to_zwg=Decimal('26.1500'), source='Demo rate (not real)')
            self.stdout.write('Demo exchange rate added.')

        if not Medicine.objects.exists():
            for name, price, low, high, months, contra, stock in MEDICINES:
                med = Medicine.objects.create(
                    name=name, unit_price=Decimal(price), low_threshold=low, high_threshold=high,
                    expiry_date=today + timedelta(days=30 * months), is_contraceptive=contra)
                StockMovement.objects.create(medicine=med, movement_type='in', quantity=stock,
                                             note='Opening stock')
            self.stdout.write('Medicines and opening stock added.')

        if not Patient.objects.exists():
            for first, surname, gender, age in PATIENTS:
                dob = date(today.year - age, min(today.month, 28), min(today.day, 28)) - timedelta(days=40)
                Patient.objects.create(first_name=first, surname=surname, gender=gender, date_of_birth=dob,
                                       phone='')
            self.stdout.write('Patients added.')

            rudo = Patient.objects.get(first_name='Rudo')
            tafara = Patient.objects.get(first_name='Tafara')
            Visit.objects.create(patient=rudo, consultation_fee=Decimal('5.00'), payment_method='cash')
            Visit.objects.create(patient=tafara, consultation_fee=Decimal('5.00'),
                                 payment_method='ecocash', payment_reference='DEMO-0001')
            Visit.objects.create(patient=Patient.objects.get(first_name='Nomsa'), consultation_fee=Decimal('5.00'),
                                 payment_method='cash', currency='ZWG')  # paid in ZiG
            sale = Sale.objects.create(patient=rudo, payment_method='cash')
            SaleItem.objects.create(sale=sale, medicine=Medicine.objects.get(name__startswith='Microgynon'), quantity=1)
            SaleItem.objects.create(sale=sale, medicine=Medicine.objects.get(name__startswith='Paracetamol'), quantity=2)
            self.stdout.write('Demo visits and a sale added.')

        if opts['with_users']:
            User = get_user_model()
            for username, role in (('pharm1', 'Pharmacist'), ('recep1', 'Receptionist')):
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(username, password=opts['password'])
                    user.groups.add(Group.objects.get(name=role))
            self.stdout.write('Demo users pharm1 (Pharmacist) and recep1 (Receptionist) ready.')

        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
