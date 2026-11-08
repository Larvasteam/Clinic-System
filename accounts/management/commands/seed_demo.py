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