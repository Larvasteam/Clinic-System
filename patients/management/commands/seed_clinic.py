from django.core.management.base import BaseCommand
from patients.models import Patient
from pharmacy.models import Medicine, StockMovement
from datetime import date
from decimal import Decimal

class Command(BaseCommand):
    help = 'Populates the clinic system with demo data'

    def handle(self, *args, **kwargs):
        self.stdout.write("Creating demo patients...")
        
        Patient.objects.get_or_create(
            first_name="Tinotenda", 
            surname="Moyo", 
            defaults={
                'date_of_birth': date(2003, 5, 14),
                'gender': "M", 
                'phone': "0771234567"
            }
        )
        
        Patient.objects.get_or_create(
            first_name="Rudo", 
            surname="Chigumba", 
            defaults={
                'date_of_birth': date(2001, 11, 22),
                'gender': "F", 
                'phone': "0789876543"
            }
        )

        self.stdout.write("Creating demo medicines and initial stock...")
        
        # 1. Paracetamol 500mg
        med1, created1 = Medicine.objects.get_or_create(
            name="Paracetamol 500mg", 
            defaults={
                'unit_price': Decimal('0.50'),
                'expiry_date': date(2028, 12, 31)
            }
        )
        if created1 or med1.quantity == 0:
            StockMovement.objects.create(
                medicine=med1,
                movement_type='in',
                quantity=150,
                note='Initial stock seeding'
            )

        # 2. Amoxicillin 250mg
        med2, created2 = Medicine.objects.get_or_create(
            name="Amoxicillin 250mg", 
            defaults={
                'unit_price': Decimal('2.00'),
                'expiry_date': date(2027, 6, 30)
            }
        )
        if created2 or med2.quantity == 0:
            StockMovement.objects.create(
                medicine=med2,
                movement_type='in',
                quantity=80,
                note='Initial stock seeding'
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded demo clinic data and inventory!"))