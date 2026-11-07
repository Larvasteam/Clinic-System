import random
from datetime import timedelta, date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from patients.models import Patient
from pharmacy.models import Medicine, StockMovement
from billing.models import Visit, Sale, SaleItem

class Command(BaseCommand):
    help = 'Generates 50 medicines, 500 patients with guaranteed visits, and correlates low stock with high sales turnover.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding high-turnover clinic demo data...'))
        today = timezone.localdate()

        admin_user = User.objects.filter(is_superuser=True).first()

        # 1. Seed 50 Diverse Medicines
        base_medicines = [
            ('Paracetamol 500mg', Decimal('1.50'), 45, 30, 300, True),     # Low stock (High turnover)
            ('Amoxicillin 250mg', Decimal('4.00'), 35, 40, 200, False),    # Low stock
            ('Ibuprofen 400mg', Decimal('2.00'), 25, 25, 150, False),      # Low stock
            ('Cough Syrup 100ml', Decimal('3.50'), 12, 15, 60, False),     # Low stock
            ('Malaria Rapid Test Kit', Decimal('5.00'), 10, 20, 100, False),# Low stock
            ('ORS Sachets', Decimal('0.50'), 45, 50, 500, False),          # Low stock
            ('Antimalarial Lumartem', Decimal('7.50'), 20, 30, 120, False),# Low stock
            ('Multivitamin Tablets', Decimal('2.50'), 180, 40, 300, False),
            ('Cetirizine 10mg', Decimal('1.20'), 15, 20, 100, False),      # Low stock
            ('Contraceptive Pills (Generic)', Decimal('1.00'), 25, 30, 200, True), # Low stock
            ('Aspirin 81mg', Decimal('1.10'), 220, 50, 400, False),
            ('Azithromycin 500mg', Decimal('6.50'), 35, 20, 150, False),
            ('Ciprofloxacin 500mg', Decimal('4.50'), 18, 25, 120, False),
            ('Omeprazole 20mg', Decimal('3.00'), 110, 30, 250, False),
            ('Diclofenac Sodium 50mg', Decimal('2.20'), 90, 25, 200, False),
            ('Metformin 500mg', Decimal('2.80'), 140, 40, 300, False),
            ('Amlodipine 5mg', Decimal('3.20'), 75, 25, 150, False),
            ('Hydrocortisone Cream 1%', Decimal('4.80'), 40, 15, 100, False),
            ('Salbutamol Inhaler', Decimal('12.00'), 14, 10, 60, False),
            ('Insulin Regular 10ml', Decimal('25.00'), 8, 10, 40, False),
            ('ORS Zinc Tablets', Decimal('1.80'), 160, 30, 250, False),
            ('Albendazole 400mg', Decimal('1.50'), 310, 60, 500, False),
            ('Benzyl Penicillin Vial', Decimal('5.50'), 50, 20, 150, False),
            ('Metronidazole 400mg', Decimal('2.30'), 85, 25, 180, False),
            ('Erythromycin 250mg', Decimal('4.20'), 42, 20, 140, False),
            ('Prednisolone 5mg', Decimal('1.90'), 95, 30, 200, False),
            ('Folic Acid 5mg', Decimal('0.80'), 400, 100, 800, False),
            ('Iron Sulfate Tablets', Decimal('1.20'), 230, 50, 400, False),
            ('Chlorpheniramine 4mg', Decimal('0.90'), 150, 40, 300, False),
            ('Loratadine 10mg', Decimal('1.60'), 120, 30, 250, False),
            ('Calcium Carbonate 500mg', Decimal('3.00'), 90, 25, 200, False),
            ('Magnesium Trisilicate', Decimal('2.10'), 65, 20, 150, False),
            ('Tetra-Eye Ointment', Decimal('3.80'), 22, 15, 80, False),
            ('Silver Sulfadiazine Cream', Decimal('6.00'), 16, 10, 50, False),
            ('Paracetamol Syrup 60ml', Decimal('2.50'), 45, 15, 100, False),
            ('Amoxicillin Paediatric Drops', Decimal('3.90'), 30, 15, 90, False),
            ('Vitamin C 500mg', Decimal('1.50'), 350, 80, 600, False),
            ('Zinc Oxide Ointment', Decimal('2.80'), 55, 20, 120, False),
            ('Clotrimazole Cream 1%', Decimal('4.50'), 38, 15, 100, False),
            ('Fluconazole 150mg', Decimal('5.20'), 25, 10, 80, False),
            ('Doxycycline 100mg', Decimal('3.40'), 70, 25, 150, False),
            ('Tramadol 50mg', Decimal('4.10'), 12, 20, 90, False),
            ('Hyoscine Butylbromide', Decimal('2.60'), 88, 25, 160, False),
            ('Bisacodyl 5mg', Decimal('1.10'), 200, 40, 350, False),
            ('Glycerin Suppositories', Decimal('4.00'), 19, 10, 60, False),
            ('Adrenaline Injection', Decimal('15.00'), 6, 5, 25, False),
            ('Atropine Eye Drops', Decimal('3.50'), 21, 10, 70, False),
            ('Xylocaine Local Anesthetic', Decimal('8.50'), 15, 10, 50, False),
            ('Ketoconazole 200mg', Decimal('4.70'), 48, 20, 120, False),
            ('Emergency Contraceptive Pill', Decimal('3.00'), 20, 20, 150, True),
        ]

        medicines = []
        for name, price, qty, low, high, is_contraceptive in base_medicines:
            expiry = today + timedelta(days=random.randint(15, 240))
            med, _ = Medicine.objects.get_or_create(
                name=name,
                defaults={
                    'unit_price': price,
                    'quantity': qty,
                    'low_threshold': low,
                    'high_threshold': high,
                    'is_contraceptive': is_contraceptive,
                    'expiry_date': expiry
                }
            )
            medicines.append(med)
        self.stdout.write(self.style.SUCCESS(f'Verified/Created {len(medicines)} medicines.'))

        # 2. Guarantee Exactly 500 Patients
        first_names = [
            'Tinashe', 'Rudo', 'Kundai', 'Blessing', 'Farai', 'Chipo', 'Nyasha', 'Thabo', 
            'Sibusiso', 'Tendai', 'Simbarashe', 'Panashe', 'Vimbai', 'Takudzwa', 'Tatenda',
            'Mandla', 'Zibusiso', 'Nothando', 'Precious', 'Memory', 'Faith', 'Prodigy',
            'Anesu', 'Tanatswa', 'Chido', 'Kudzai', 'Bhekimpilo', 'Nomagugu', 'Meluleki'
        ]
        last_names = [
            'Moyo', 'Ncube', 'Dube', 'Khumalo', 'Ndlovu', 'Sibanda', 'Gumbo', 'Mutasa', 
            'Zwane', 'Chikwanha', 'Chivayo', 'Mpofu', 'Sithole', 'Hadebe', 'Mabhida',
            'Phiri', 'Bhebhe', 'Tshuma', 'Nyathi', 'Mlalazi', 'Gumedze', 'Kaseke'
        ]

        current_patient_count = Patient.objects.count()
        target_patients = 500
        created_count = 0

        while current_patient_count < target_patients:
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            phone = f"+2637{random.randint(10, 89)}{random.randint(100, 999)} {random.randint(100, 999)}"
            random_days_old = random.randint(18 * 365, 28 * 365)
            dob = today - timedelta(days=random_days_old)
            
            if not Patient.objects.filter(phone=phone).exists():
                Patient.objects.create(first_name=fname, surname=lname, phone=phone, date_of_birth=dob)
                current_patient_count += 1
                created_count += 1

        all_patients = list(Patient.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Total patient pool ready: {len(all_patients)} records.'))

        # 3. Ensure EVERY Patient has a Visit & Sales (with weighted preference for depleting/low stock)
        payment_methods = ['cash', 'ecocash', 'medical_aid']
        created_visits = 0
        created_sales = 0

        for patient in all_patients:
            days_ago = random.randint(0, 30)
            visit_date = timezone.now() - timedelta(days=days_ago, hours=random.randint(1, 8), minutes=random.randint(0, 59))
            
            visit = Visit.objects.create(
                patient=patient,
                consultation_fee=Decimal('5.00'),
                payment_method=random.choice(payment_methods),
                created_at=visit_date
            )
            created_visits += 1

            sale = Sale.objects.create(
                patient=patient,
                payment_method=visit.payment_method,
                created_at=visit_date + timedelta(minutes=random.randint(10, 30)),
                created_by=admin_user
            )
            
            # Identify current low/depleting stock items
            low_stock_pool = [m for m in medicines if m.quantity <= m.low_threshold and m.quantity > 0]

            # Add 1 to 3 items per sale, favoring depleting stock
            for _ in range(random.randint(1, 3)):
                if low_stock_pool and random.random() < 0.7:
                    med = random.choice(low_stock_pool)
                else:
                    med = random.choice(medicines)

                if med.quantity > 2:
                    qty = random.randint(1, 2)
                    try:
                        SaleItem.objects.create(
                            sale=sale,
                            medicine=med,
                            quantity=qty,
                            unit_price=med.unit_price
                        )
                        med.refresh_from_db()
                        created_sales += 1
                    except Exception:
                        pass

        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {created_visits} visits and {created_sales} high-turnover sales items across all {len(all_patients)} patients!'))
        self.stdout.write(self.style.SUCCESS('Mass demo generation complete!'))