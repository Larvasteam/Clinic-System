from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from patients.models import Patient
from pharmacy.models import Medicine, StockMovement
from .rules import MIN_PAYMENT, check_minimum_payment

CENT = Decimal('0.01')


class ExchangeRate(models.Model):
    """How many ZiG (ZWG) one US dollar buys on a given date. The newest rate is the current one."""
    date = models.DateField(help_text='The date this rate applies to.')
    usd_to_zwg = models.DecimalField('ZiG per 1 USD', max_digits=12, decimal_places=4,
                                     validators=[MinValueValidator(Decimal('0.0001'))])
    source = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(usd_to_zwg__gt=0), name='rate_is_positive'),
        ]

    @classmethod
    def current(cls):
        return cls.objects.first()  # newest date; if two share a date, the later entry wins

    @classmethod
    def current_rate(cls):
        rate = cls.current()
        return rate.usd_to_zwg if rate else None

    @property
    def age_days(self):
        return (timezone.localdate() - self.date).days

    @property
    def is_stale(self):
        return self.age_days > getattr(settings, 'RATE_MAX_AGE_DAYS', 3)

    def __str__(self):
        return f"1 USD = {self.usd_to_zwg} ZiG ({self.date})"


CURRENCY_CHOICES = [('USD', 'US dollars (USD)'), ('ZWG', 'ZiG (ZWG)')]


class PaymentInfo(models.Model):
    """Shared by visits and sales. Prices stay in USD; the currency says what the patient actually paid in,
    and the rate is locked in at the moment of payment so old records never change."""
    PAYMENT_CHOICES = [('cash', 'Cash'), ('ecocash', 'EcoCash'), ('bank', 'Bank'), ('other', 'Other')]
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    payment_reference = models.CharField(max_length=100, blank=True)
    currency = models.CharField('Paid in', max_length=3, choices=CURRENCY_CHOICES, default='USD')
    exchange_rate = models.DecimalField('ZiG per 1 USD at the time', max_digits=12, decimal_places=4,
                                        null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def amount_usd(self):
        raise NotImplementedError

    @property
    def amount_zwg(self):
        """The amount in ZiG at the rate that was current when it was paid."""
        if self.exchange_rate is None or self.amount_usd is None:
            return None
        return (self.amount_usd * self.exchange_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def paid_amount(self):
        """The amount in the currency the patient paid in."""
        return self.amount_zwg if self.currency == 'ZWG' else self.amount_usd

    def clean(self):
        super().clean()
        if self.payment_method in ('ecocash', 'bank') and not self.payment_reference:
            raise ValidationError({'payment_reference': 'A reference is required for EcoCash and bank payments.'})
        if self.currency == 'ZWG' and self.exchange_rate is None and ExchangeRate.current() is None:
            raise ValidationError({'currency': 'No ZiG exchange rate has been set yet. '
                                               'Ask the administrator to set today\'s rate.'})

    def save(self, *args, **kwargs):
        if self.exchange_rate is None:
            self.exchange_rate = ExchangeRate.current_rate()  # locked in at the time of payment
        if self.currency == 'ZWG' and self.exchange_rate is None:
            raise ValidationError('No ZiG exchange rate has been set yet.')
        super().save(*args, **kwargs)


class Visit(PaymentInfo):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='visits')
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2,
                                           validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(consultation_fee__gte=MIN_PAYMENT),
                                   name='visit_fee_at_least_minimum'),
            models.CheckConstraint(condition=models.Q(currency='USD') | models.Q(exchange_rate__isnull=False),
                                   name='visit_zig_needs_rate'),
        ]

    @property
    def amount_usd(self):
        return self.consultation_fee

    def clean(self):
        super().clean()
        check_minimum_payment(self.consultation_fee, 'consultation_fee')

    def save(self, *args, **kwargs):
        check_minimum_payment(self.consultation_fee)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Visit #{self.pk} - {self.patient}"


class Sale(PaymentInfo):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='sales')
    visit = models.ForeignKey(Visit, null=True, blank=True, on_delete=models.PROTECT, related_name='sales')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(currency='USD') | models.Q(exchange_rate__isnull=False),
                                   name='sale_zig_needs_rate'),
        ]

    @property
    def total(self):
        return sum((i.line_total for i in self.items.all()), Decimal('0'))

    @property
    def amount_usd(self):
        return self.total

    def clean(self):
        super().clean()
        if self.visit_id and self.patient_id and self.visit.patient_id != self.patient_id:
            raise ValidationError("This visit belongs to a different patient.")

    def __str__(self):
        return f"Sale #{self.pk} - {self.patient}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    @property
    def line_total(self):
        return (self.quantity or 0) * (self.unit_price or Decimal('0'))

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Sale items can't be edited.")
        with transaction.atomic():
            self.unit_price = self.medicine.unit_price  # price is locked in at the time of sale
            super().save(*args, **kwargs)
            StockMovement.objects.create(
                medicine=self.medicine, movement_type='sale', quantity=self.quantity,
                note=f"Sale #{self.sale_id}", created_by=self.sale.created_by,
            )

    def __str__(self):
        return f"{self.quantity} x {self.medicine}"
