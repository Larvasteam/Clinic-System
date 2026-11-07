from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import CURRENCY_CHOICES, ExchangeRate, Sale, SaleItem, Visit
from .rates import RATE_MAX, RATE_MIN
from .rules import MIN_PAYMENT, check_contraceptive_allowed, check_minimum_payment


def patient_label(p):
    return f"{p.surname}, {p.first_name} ({p.age}, {p.get_gender_display()})"


def setup_currency_field(field):
    """Offer ZiG only when a rate exists, and show today's rate under the choice."""
    rate = ExchangeRate.current()
    if rate:
        field.help_text = f"Today's rate: 1 USD = {rate.usd_to_zwg} ZiG ({rate.date:%d %b %Y}). It is saved with the payment."
    else:
        field.choices = [c for c in CURRENCY_CHOICES if c[0] == 'USD']
        field.help_text = 'No ZiG rate has been set yet, so only US dollars can be recorded. Ask the administrator to set the rate.'


class VisitForm(forms.ModelForm):
    # The fee is fixed by the clinic (settings.CONSULTATION_FEE_USD). It is shown but cannot be edited,
    # and a disabled field ignores anything sent by the browser, so it cannot be changed by tampering either.
    consultation_fee = forms.DecimalField(label='Consultation fee (USD)', disabled=True, required=False,
                                          max_digits=10, decimal_places=2)

    class Meta:
        model = Visit
        fields = ['patient', 'consultation_fee', 'currency', 'payment_method', 'payment_reference', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fee = settings.CONSULTATION_FEE_USD
        if self.instance.pk:
            fee = self.instance.consultation_fee  # an existing visit keeps the fee it was charged
        self.initial['consultation_fee'] = fee
        rate = ExchangeRate.current()
        self.fields['consultation_fee'].help_text = (
            f"Fixed fee. That is {(fee * rate.usd_to_zwg).quantize(Decimal('0.01'))} ZiG at today's rate."
            if rate else 'Fixed fee.')
        self.fields['patient'].label_from_instance = patient_label
        self.fields['payment_reference'].help_text = 'Required for EcoCash and bank payments.'
        setup_currency_field(self.fields['currency'])


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['patient', 'currency', 'payment_method', 'payment_reference']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].label_from_instance = patient_label
        self.fields['payment_reference'].help_text = 'Required for EcoCash and bank payments.'
        setup_currency_field(self.fields['currency'])


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['medicine', 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def label(m):
            tag = ' [contraceptive]' if m.is_contraceptive else ''
            return f"{m.name}{tag} ({m.quantity} in stock, {m.unit_price} USD)"
        self.fields['medicine'].label_from_instance = label
        self.fields['quantity'].widget.attrs['min'] = '1'


class SaleItemFormSet(BaseInlineFormSet):
    """All the rules for a sale live here, so the admin and the app enforce exactly the same ones."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        patient = self.instance.patient if self.instance.patient_id else None
        wanted = {}  # medicine id -> [medicine, total quantity]
        for form in self.forms:
            med = form.cleaned_data.get('medicine')
            qty = form.cleaned_data.get('quantity')
            if not med or not qty:
                continue
            wanted.setdefault(med.pk, [med, 0])[1] += qty
        if not wanted:
            raise ValidationError("Add at least one medicine.")
        today = timezone.localdate()
        for med, qty in wanted.values():
            if med.expiry_date and med.expiry_date < today:
                raise ValidationError(f"{med.name} expired on {med.expiry_date:%d %b %Y} and cannot be sold.")
            if med.is_contraceptive and patient:
                check_contraceptive_allowed(patient)
            if qty > med.quantity:
                raise ValidationError(f"Not enough {med.name} in stock (only {med.quantity} left).")
        # the whole sale is one payment, so the minimum applies to its total
        total = sum((med.unit_price * qty for med, qty in wanted.values()), Decimal('0'))
        check_minimum_payment(total)


ItemFormSet = inlineformset_factory(
    Sale, SaleItem, form=SaleItemForm, formset=SaleItemFormSet,
    fields=('medicine', 'quantity'), extra=3, can_delete=False)


class ExchangeRateForm(forms.ModelForm):
    confirm_large_change = forms.BooleanField(
        required=False, label='I have checked this rate and it is correct',
        help_text='Only needed when the rate moved a lot since the last one.')

    class Meta:
        model = ExchangeRate
        fields = ['date', 'usd_to_zwg', 'source']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}
        labels = {'usd_to_zwg': 'ZiG per 1 USD'}
        help_texts = {'usd_to_zwg': 'Example: 26.1500', 'source': 'Optional note, for example "RBZ sheet, morning".'}

    def clean_date(self):
        when = self.cleaned_data['date']
        if when > timezone.localdate():
            raise ValidationError('The date cannot be in the future.')
        return when

    def clean_usd_to_zwg(self):
        rate = self.cleaned_data['usd_to_zwg']
        if not (RATE_MIN <= rate <= RATE_MAX):
            raise ValidationError(f'Enter how many ZiG one US dollar buys (between {RATE_MIN} and {RATE_MAX}).')
        return rate

    def clean(self):
        data = super().clean()
        rate, last = data.get('usd_to_zwg'), ExchangeRate.current()
        if rate and last and not data.get('confirm_large_change'):
            change = abs(rate / last.usd_to_zwg - 1)
            if change > Decimal(str(getattr(settings, 'RATE_MAX_CHANGE', 0.25))):
                raise ValidationError(f'This is {change:.0%} different from the last rate ({last.usd_to_zwg}). '
                                      'Check it, then tick the confirmation box.')
        return data
