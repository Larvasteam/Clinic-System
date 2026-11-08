<<<<<<< HEAD
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from patients.models import Patient
from pharmacy.models import Medicine, StockMovement
from billing.models import Visit, Sale, SaleItem, ExchangeRate


class Command(BaseCommand):
    help = 'Populates the clinic system with 400 clean patients, 65 medicines, active ZiG balances, and transactions.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding database with full demo dataset...")

        # 0. Ensure an active Exchange Rate exists for ZiG
        zig_rate, _ = ExchangeRate.objects.get_or_create(
            source='ZiG',
            defaults={
                'usd_to_zwg': Decimal('13.5000'),
                'date': timezone.localdate()
            }
        )

        # 1. Create 65 Medicines
        self.stdout.write("Creating 65 medicines and initial stock...")
        medicine_names = [
            "Paracetamol 500mg", "Ibuprofen 400mg", "Amoxicillin 250mg", "Ciprofloxacin 500mg",
            "Metformin 500mg", "Amlodipine 5mg", "Omeprazole 20mg", "Azithromycin 500mg",
            "Diclofenac 50mg", "Cetirizine 10mg", "Aspirin 75mg", "Salbutamol Inhaler",
            "Hydrochlorothiazide 25mg", "Atorvastatin 20mg", "Insulin Actrapid", "ORS Sachets",
            "Co-trimoxazole 480mg", "Erythromycin 250mg", "Metronidazole 400mg", "Albendazole 400mg",
            "Vitamin C 500mg", "Multivitamin Tablets", "Zinc Sulphate 20mg", "Ferrous Sulphate 200mg",
            "Folic Acid 5mg", "Calcium Carbonate", "Prednisolone 5mg", "Hydrocortisone Cream",
            "Benzylpenicillin Injection", "Gentamycin Injection", "Ceftriaxone 1g Injection", "Lidocaine 2%",
            "Silver Sulfadiazine Cream", "Benzathine Penicillin", "Artemether-Lumefantrine", "Quinine Sulphate 300mg",
            "Rapid Malaria Test Kits", "Pregnancy Test Strips", "HIV Test Kits", "Glucose Test Strips",
            "Cough Syrup 100ml", "Antacid Suspension", "Loperamide 2mg", "Promethazine 25mg",
            "Diazepam 5mg", "Phenobarbitone 30mg", "Carbamazepine 200mg", "Fluconazole 150mg",
            "Clotrimazole Pessaries", "Acyclovir 200mg", "Tenofovir/Lamivudine/Efavirenz", "Nevirapine 200mg",
            "Cotrimoxazole 960mg", "Pyrazinamide 500mg", "Isoniazid 300mg", "Rifampicin 150mg",
            "Ethambutol 400mg", "Streptomycin 1g", "Saline Nasal Drops", "Chloramphenicol Eye Drops",
            "Tetracycline Eye Ointment", "Calamine Lotion", "Benzyl Benzoate Lotion", "Povidone Iodine 10%", "Ethanol 70%"
        ]

        medicines = []
        for name in medicine_names[:65]:
            med, created = Medicine.objects.get_or_create(
                name=name,
                defaults={
                    'unit_price': Decimal(str(round(random.uniform(0.50, 25.00), 2))),
                    'expiry_date': timezone.localdate() + timedelta(days=random.randint(90, 730)),
                    'is_contraceptive': 'Contraceptive' in name or 'Pregnancy' in name
                }
            )
            if created or med.quantity < 50:
                StockMovement.objects.create(
                    medicine=med,
                    movement_type='in',
                    quantity=300,
                    note='Initial bulk seeding'
                )
            medicines.append(med)

        # 2. Create 400 Patients with Clean Names (No numbers/underscores)
        self.stdout.write("Creating 400 patients with clean names...")
        first_names = [
            "Tinotenda", "Rudo", "Farai", "Chipo", "Tashinga", "Kudakwashe", "Nyasha", "Tendai",
            "Tarisai", "Simbarashe", "Takudzwa", "Panashe", "Vimbai", "Tadiwanashe", "Anesu", "Munashe",
            "Tanaka", "Tariro", "Norest", "Blessing", "Nomatter", "Tendekai", "Memory", "Faith",
            "Grace", "Success", "Gift", "Melody", "Shingirai", "Tatenda", "Mutsa", "Ngonidzashe",
            "Bongani", "Chido", "Kudzai", "Tichaona", "Fadzai", "Tafadzwa", "Rumbidzai", "Procious"
        ]
        surnames = [
            "Moyo", "Chigumba", "Ndlovu", "Dube", "Ncube", "Sibanda", "Mhofu", "Gumbo",
            "Mupfumi", "Mutasa", "Chikonye", "Shoko", "Bhebhe", "Mpofu", "Tshuma", "Sithole",
            "Mtero", "Zvoushe", "Matiza", "Nkomo", "Gono", "Mangwiro", "Chitsunge", "Makoni",
            "Zwane", "Khumalo", "Nyathi", "Goredema", "Chimusoro", "Biti", "Taderera", "Mtero"
        ]
        medical_providers = ["CIMAS", "PSMAS", "First Mutual Health", "Generation Health", "MASCA", "Other"]
        durations = ["1 Semester", "2 Semesters", "1 Year", "Per Visit"]

        created_patients = []
        for _ in range(400):
            fn = random.choice(first_names)
            sn = random.choice(surnames)
            gender = random.choice(['M', 'F'])
            days_ago = random.randint(18 * 365, 30 * 365)
            dob = timezone.localdate() - timedelta(days=days_ago)
            phone = f"+263{random.choice(['71', '77', '78', '73'])}{random.randint(1000000, 9999999)}"

            has_ma = random.choice([True, False, True])
            provider = random.choice(medical_providers) if has_ma else ""
            duration = random.choice(durations) if has_ma else ""
            expiry = (timezone.localdate() + timedelta(days=random.randint(30, 365))) if has_ma else None

            patient = Patient.objects.create(
                first_name=fn,
                surname=sn,
                date_of_birth=dob,
                gender=gender,
                phone=phone,
                has_medical_aid=has_ma,
                medical_aid_provider=provider,
                medical_aid_duration=duration,
                medical_aid_expiry_date=expiry,
            )
            created_patients.append(patient)

        # 3. Create visits and sales distributed between USD and ZiG
        self.stdout.write("Generating visits and sales records with ZiG and USD currencies...")
        payment_methods = ['cash', 'ecocash', 'medical_aid']
        currencies = ['USD', 'ZiG']

        for patient in created_patients:
            choice = random.choice(['visit', 'sale', 'both'])
            currency_choice = random.choice(currencies)
            
            visit_kwargs = {
                'patient': patient,
                'consultation_fee': Decimal(str(round(random.uniform(5.00, 20.00), 2))),
                'payment_method': random.choice(payment_methods),
                'currency': currency_choice,
                'notes': "Routine medical checkup consultation seeded."
            }
            if currency_choice == 'ZiG':
                visit_kwargs['exchange_rate_id'] = zig_rate.id

            if choice in ['visit', 'both']:
                Visit.objects.create(**visit_kwargs)

            if choice in ['sale', 'both']:
                sale_kwargs = {
                    'patient': patient,
                    'payment_method': random.choice(payment_methods),
                    'currency': currency_choice
                }
                if currency_choice == 'ZiG':
                    sale_kwargs['exchange_rate_id'] = zig_rate.id

                sale = Sale.objects.create(**sale_kwargs)
                num_items = random.randint(1, 3)
                chosen_meds = random.sample(medicines, num_items)
                for med in chosen_meds:
                    qty = random.randint(1, 3)
                    SaleItem.objects.create(
                        sale=sale,
                        medicine=med,
                        quantity=qty,
                        unit_price=med.unit_price
                    )

        self.stdout.write(self.style.SUCCESS("Successfully seeded 400 clean patients with active ZiG and USD transactions!"))
=======
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
>>>>>>> 8f5d9a4659fcc4fb4a90d495056f243c30d25f0a
