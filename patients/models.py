from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Patient(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    first_name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
            if self.age > 120:
                raise ValidationError({'date_of_birth': 'Please check the date of birth (age is over 120).'})

    def __str__(self):
        return f"{self.first_name} {self.surname}"
