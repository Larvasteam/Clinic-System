from django import forms

from .models import Medicine, StockMovement


class MedicineForm(forms.ModelForm):
    opening_stock = forms.IntegerField(
        min_value=0, required=False, label='Opening stock',
        help_text='Units already on the shelf. This is recorded as a stock-in movement.')

    class Meta:
        model = Medicine
        fields = ['name', 'unit_price', 'low_threshold', 'high_threshold', 'expiry_date', 'is_contraceptive']
        widgets = {'expiry_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields['opening_stock']  # stock only changes through stock movements


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['medicine', 'movement_type', 'quantity', 'note']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['movement_type'].choices = [c for c in StockMovement.TYPE_CHOICES if c[0] != 'sale']
        self.fields['movement_type'].label = 'Type'
        self.fields['medicine'].label_from_instance = lambda m: f"{m.name} ({m.quantity} in stock)"
