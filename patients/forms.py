from django import forms

from .models import Patient


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'surname', 'date_of_birth', 'gender', 'phone']
        widgets = {'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}
