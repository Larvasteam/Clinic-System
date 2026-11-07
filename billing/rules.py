from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError

# The smallest payment the clinic accepts (USD). Every check reads this one value.
MIN_PAYMENT = Decimal('0.50')


def check_minimum_payment(amount, field=None):
    if amount is None or amount >= MIN_PAYMENT:
        return
    message = (f"Payments below {MIN_PAYMENT:.2f} USD are not allowed "
               f"(this one is {amount:.2f} USD).")
    raise ValidationError({field: message} if field else message)


def check_contraceptive_allowed(patient):
    max_age = getattr(settings, 'CONTRACEPTIVE_MAX_AGE', 49)
    if patient.gender != 'F':
        raise ValidationError("Contraceptives can't be issued to male patients.")
    if patient.age > max_age:
        raise ValidationError(f"Contraceptives can't be issued to patients over {max_age}.")
