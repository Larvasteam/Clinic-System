from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import PatientForm
from .models import Patient


@login_required
@permission_required('patients.view_patient', raise_exception=True)
def patient_list(request):
    q = request.GET.get('q', '').strip()
    patients = Patient.objects.all()
    if q:
        patients = patients.filter(Q(first_name__icontains=q) | Q(surname__icontains=q)
                                   | Q(phone__icontains=q))
    return render(request, 'patients/list.html', {'patients': patients[:100], 'q': q})


@login_required
@permission_required('patients.add_patient', raise_exception=True)
def patient_add(request):
    form = PatientForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        patient = form.save()
        messages.success(request, f'{patient} was registered.')
        return redirect('patient_history', pk=patient.pk)
    return render(request, 'form_page.html', {
        'form': form, 'title': 'Add Patient', 'cancel_url': reverse('patient_list'),
        'submit_label': 'Register patient'})


@login_required
@permission_required('patients.change_patient', raise_exception=True)
def patient_edit(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{patient} was updated.')
        return redirect('patient_history', pk=patient.pk)
    return render(request, 'form_page.html', {
        'form': form, 'title': f'Edit {patient}', 'cancel_url': reverse('patient_history', args=[pk]),
        'submit_label': 'Save changes'})


@login_required
@permission_required('patients.view_patient', raise_exception=True)
def patient_history(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    visits = patient.visits.all()
    sales = patient.sales.prefetch_related('items__medicine')
    fees = visits.aggregate(t=Sum('consultation_fee'))['t'] or Decimal('0')
    meds = sum((s.total for s in sales), Decimal('0'))
    return render(request, 'patients/history.html', {
        'patient': patient, 'visits': visits, 'sales': sales,
        'fees': fees, 'meds': meds, 'total': fees + meds,
    })
