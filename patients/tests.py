from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.testutils import make_patient, make_user, setup_roles
from .models import Patient


class PatientModelTests(TestCase):
    def test_age_is_worked_out_from_date_of_birth(self):
        assert make_patient(age=30).age == 30
        assert make_patient(age=9, first='Kid').age == 9

    def test_future_date_of_birth_is_refused(self):
        p = Patient(first_name='A', surname='B', gender='F',
                    date_of_birth=timezone.localdate() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_impossible_age_is_refused(self):
        p = Patient(first_name='A', surname='B', gender='F', date_of_birth=timezone.localdate().replace(year=1800))
        with self.assertRaises(ValidationError):
            p.full_clean()


class PatientViewTests(TestCase):
    def setUp(self):
        setup_roles()
        self.reception = make_user('Receptionist')
        self.pharmacist = make_user('Pharmacist')

    def test_receptionist_can_register_and_edit(self):
        self.client.force_login(self.reception)
        dob = timezone.localdate().replace(year=timezone.localdate().year - 30) - timedelta(days=5)
        r = self.client.post(reverse('patient_add'), {
            'first_name': 'Rudo', 'surname': 'Chirwa', 'date_of_birth': dob.isoformat(),
            'gender': 'F', 'phone': '0770000000'})
        patient = Patient.objects.get()
        self.assertRedirects(r, reverse('patient_history', args=[patient.pk]))
        r = self.client.post(reverse('patient_edit', args=[patient.pk]), {
            'first_name': 'Rudo', 'surname': 'Moyo', 'date_of_birth': dob.isoformat(),
            'gender': 'F', 'phone': ''})
        patient.refresh_from_db()
        assert patient.surname == 'Moyo'

    def test_pharmacist_can_view_but_not_add_or_edit(self):
        p = make_patient()
        self.client.force_login(self.pharmacist)
        assert self.client.get(reverse('patient_list')).status_code == 200
        assert self.client.get(reverse('patient_history', args=[p.pk])).status_code == 200
        assert self.client.get(reverse('patient_add')).status_code == 403
        assert self.client.get(reverse('patient_edit', args=[p.pk])).status_code == 403

    def test_search_finds_by_name(self):
        make_patient(first='Tendai', surname='Moyo')
        make_patient(first='Rudo', surname='Chirwa')
        self.client.force_login(self.reception)
        r = self.client.get(reverse('patient_list'), {'q': 'moyo'})
        self.assertContains(r, 'Tendai Moyo')
        self.assertNotContains(r, 'Rudo Chirwa')

    def test_anonymous_users_are_sent_to_login(self):
        r = self.client.get(reverse('patient_list'))
        assert r.status_code == 302 and '/accounts/login/' in r['Location']
