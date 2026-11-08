from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal


class Medicine(models.Model):
    name = models.CharField(max_length=150, unique=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2,
                                     validators=[MinValueValidator(Decimal('0.01'))])
    quantity = models.PositiveIntegerField(default=0, editable=False)
    low_threshold = models.PositiveIntegerField(
        default=10, verbose_name='Low stock level', help_text='At or below this many units = RED.')
    high_threshold = models.PositiveIntegerField(
        default=50, verbose_name='High stock level', help_text='At or above this many units = GREEN.')
    expiry_date = models.DateField(null=True, blank=True)
    is_contraceptive = models.BooleanField(
        default=False, help_text='Restricted: never issued to male or over-age patients.')

    class Meta:
        ordering = ['name']

    def clean(self):
        super().clean()
        if self.low_threshold is not None and self.high_threshold is not None \
                and self.high_threshold <= self.low_threshold:
            raise ValidationError({'high_threshold': 'The high level must be larger than the low level.'})

    @property
    def sku(self):
        return f"MED-{self.pk:04d}" if self.pk else 'MED-NEW'

    @property
    def stock_colour(self):
        if self.quantity <= self.low_threshold:
            return 'red'
        if self.quantity < self.high_threshold:
            return 'yellow'
        return 'green'

    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'Out of stock'
        return {'red': 'Low stock', 'yellow': 'Medium stock', 'green': 'High stock'}[self.stock_colour]

    @property
    def expired(self):
        return self.expiry_date is not None and self.expiry_date < timezone.localdate()

    @property
    def expiring_soon(self):
        """Expired, or expiring within about six months."""
        return (self.expiry_date is not None
                and self.expiry_date <= timezone.localdate() + timedelta(days=183))

    def __str__(self):
        return self.name


class StockMovement(models.Model):
    TYPE_CHOICES = [
        ('in', 'Stock in (order received)'),
        ('sale', 'Sale'),
        ('adjust', 'Adjustment (+ or -)'),
    ]

    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.IntegerField(help_text='Enter a positive number. Only adjustments may be negative.')
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    @property
    def delta(self):
        if self.movement_type == 'in':
            return abs(self.quantity)
        if self.movement_type == 'sale':
            return -abs(self.quantity)
        return self.quantity  # adjustment keeps its sign

    def clean(self):
        super().clean()
        if self.quantity is None or not self.movement_type:
            return
        if self.quantity == 0:
            raise ValidationError({'quantity': 'The quantity cannot be zero.'})
        if self.movement_type in ('in', 'sale') and self.quantity < 0:
            raise ValidationError({'quantity': 'Use a positive number (only adjustments can be negative).'})
        if self.medicine_id and not self.pk and self.medicine.quantity + self.delta < 0:
            raise ValidationError(f"Not enough stock: only {self.medicine.quantity} units of "
                                  f"{self.medicine.name} are in stock.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Stock movements can't be edited. Add a new adjustment instead.")
        with transaction.atomic():
            med = Medicine.objects.select_for_update().get(pk=self.medicine_id)
            new_qty = med.quantity + self.delta
            if new_qty < 0:
                raise ValidationError(f"Not enough stock: only {med.quantity} units of {med.name} are in stock.")
            med.quantity = new_qty
            med.save(update_fields=['quantity'])
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine} {self.delta:+d}"
