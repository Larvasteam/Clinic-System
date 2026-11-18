from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Patient(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    first_name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Medical Aid fields (Retained)
    has_medical_aid = models.BooleanField(default=False)
    medical_aid_requested = models.BooleanField(default=False)
    medical_aid_provider = models.CharField(max_length=100, blank=True)
    medical_aid_duration = models.CharField(max_length=50, blank=True)
    medical_aid_expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['surname', 'first_name']

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def clean(self):
        super().clean()
        if self.date_of_birth:
            if self.date_of_birth > timezone.localdate():
                raise ValidationError({'date_of_birth': 'Date of birth cannot be in the future.'})
            if self.age and self.age > 120:
                raise ValidationError({'date_of_birth': 'Please check the date of birth (age is over 120).'})

    def __str__(self):
        return f"{self.first_name} {self.surname}"