from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db.models import Q

# Pharmacist and Receptionist: (app, model) -> allowed actions.
# Only Admin can delete; nobody edits finished sales or stock records.
ROLES = {
    'Pharmacist': {
        ('patients', 'patient'): ['view'],
        ('billing', 'visit'): ['view'],
        ('pharmacy', 'medicine'): ['add', 'change', 'view'],
        ('pharmacy', 'stockmovement'): ['add', 'view'],
        ('billing', 'sale'): ['add', 'view'],
        ('billing', 'saleitem'): ['add', 'view'],
    },
    'Receptionist': {
        ('patients', 'patient'): ['add', 'change', 'view'],
        ('billing', 'visit'): ['add', 'view'],
        ('pharmacy', 'medicine'): ['view'],
    },
}


class Command(BaseCommand):
    help = 'Create or refresh the Admin, Pharmacist and Receptionist permission groups.'

    def handle(self, *args, **options):
        # Admin: everything in the clinic apps, plus managing users and groups
        admin_perms = Permission.objects.filter(
            Q(content_type__app_label__in=['patients', 'pharmacy', 'billing'])
            | Q(content_type__app_label='auth', content_type__model__in=['user', 'group'])
        )
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        admin_group.permissions.set(admin_perms)
        self.stdout.write(f'Admin: {admin_perms.count()} permissions')

        for name, rules in ROLES.items():
            perms = []
            for (app, model), actions in rules.items():
                for action in actions:
                    perms.append(Permission.objects.get(
                        content_type__app_label=app, codename=f'{action}_{model}'))
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(perms)
            self.stdout.write(f'{name}: {len(perms)} permissions')

        self.stdout.write(self.style.SUCCESS('Roles updated.'))
