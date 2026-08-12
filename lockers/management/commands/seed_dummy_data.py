# lockers/management/commands/seed_dummy_data.py
# Usage: python manage.py seed_dummy_data
#        python manage.py seed_dummy_data --clear   (wipe all data first)

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from lockers.models import Locker, Customer, LockerUser, AccessLog


CUSTOMERS_DATA = [
    {'name': 'Rajesh Kumar',  'id_proof_type': 'aadhaar'},
    {'name': 'Priya Sharma',  'id_proof_type': 'pan'},
    {'name': 'Amit Patel',    'id_proof_type': 'passport'},
    {'name': 'Sunita Mehta',  'id_proof_type': 'voter_id'},
    {'name': 'Vikram Singh',  'id_proof_type': 'driving_license'},
    {'name': 'Deepa Nair',    'id_proof_type': 'aadhaar'},
    {'name': 'Kiran Reddy',   'id_proof_type': 'pan'},
    {'name': 'Anita Joshi',   'id_proof_type': 'passport'},
]

LOCKER_NUMBERS = ['A-101', 'A-102', 'B-201', 'B-202', 'C-301', 'C-302']


class Command(BaseCommand):
    help = 'Seed the database with realistic dummy data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        w = self.stdout.write  # shorthand

        if options['clear']:
            w('Clearing existing data...')
            AccessLog.objects.all().delete()
            LockerUser.objects.all().delete()
            Locker.objects.all().delete()
            Customer.objects.all().delete()

        w('=== Seeding VaultBank Dummy Data ===\n')

        # 1. Lockers
        w('[LOCKERS]')
        lockers = []
        for number in LOCKER_NUMBERS:
            locker, created = Locker.objects.get_or_create(
                locker_number=number,
                defaults={'is_active': True}
            )
            if created:
                w(self.style.SUCCESS(f'  CREATED  #{number} | Token: {locker.token}'))
            else:
                w(f'  SKIP     #{number} already exists')
            lockers.append(locker)

        # Mark last locker inactive
        lockers[-1].is_active = False
        lockers[-1].save()
        w(f'  INFO     #{lockers[-1].locker_number} set INACTIVE\n')

        # 2. Customers
        w('[CUSTOMERS]')
        customers = []
        for data in CUSTOMERS_DATA:
            c, created = Customer.objects.get_or_create(
                name=data['name'],
                defaults={
                    'id_proof_type': data['id_proof_type'],
                    'id_proof_file': 'id_proofs/dummy_placeholder.pdf',
                }
            )
            if created:
                w(self.style.SUCCESS(f'  CREATED  {c.name} ({c.get_id_proof_type_display()})'))
            else:
                w(f'  SKIP     {c.name} already exists')
            customers.append(c)

        w('')

        # 3. Assignments (many-to-many via LockerUser)
        w('[ASSIGNMENTS]')
        assignments = [
            # (locker_index, [customer_indexes]) - max 3 per locker
            (0, [0, 1, 2]),   # A-101: full (3)
            (1, [3, 4]),      # A-102: 2 customers
            (2, [5]),         # B-201: 1 customer
            (3, [0, 6, 7]),   # B-202: Rajesh also here (multi-locker demo)
            (4, [1, 5]),      # C-301: Priya + Deepa
            (5, [2]),         # C-302: inactive, 1 customer
        ]

        for locker_idx, customer_idxs in assignments:
            locker = lockers[locker_idx]
            for cust_idx in customer_idxs:
                customer = customers[cust_idx]
                lu, created = LockerUser.objects.get_or_create(
                    locker=locker, customer=customer
                )
                if created:
                    w(self.style.SUCCESS(f'  LINKED   {customer.name} -> #{locker.locker_number}'))
                else:
                    w(f'  SKIP     {customer.name} -> #{locker.locker_number}')

        w('')

        # 4. Access Logs (closed sessions)
        w('[ACCESS LOGS - Closed]')
        now = timezone.now()

        closed_logs = [
            (0, 0, 48, 25),   # locker, customer, hours_ago, duration_mins
            (0, 1, 36, 15),
            (1, 3, 24, 40),
            (2, 5, 12, 10),
            (3, 6, 6, 20),
            (4, 1, 3, 30),
            (0, 2, 2, 12),
            (3, 0, 100, 18),
        ]

        for li, ci, hours_ago, dur_mins in closed_logs:
            check_in  = now - timedelta(hours=hours_ago)
            check_out = check_in + timedelta(minutes=dur_mins)
            log = AccessLog.objects.create(
                locker=lockers[li],
                customer=customers[ci],
                check_out_time=check_out,
            )
            # Update the auto_now_add check_in_time
            AccessLog.objects.filter(pk=log.pk).update(check_in_time=check_in)
            w(self.style.SUCCESS(
                f'  LOG      {customers[ci].name} @ #{lockers[li].locker_number} '
                f'| {dur_mins}min | {hours_ago}h ago'
            ))

        w('')
        w('[ACCESS LOGS - Active]')

        active_logs = [
            (1, 4, 22),   # A-102, Vikram, 22 min ago
            (4, 5, 8),    # C-301, Deepa, 8 min ago
        ]

        for li, ci, mins_ago in active_logs:
            locker = lockers[li]
            customer = customers[ci]
            if AccessLog.objects.filter(locker=locker, check_out_time__isnull=True).exists():
                w(f'  SKIP     #{locker.locker_number} already has active session')
                continue
            check_in = now - timedelta(minutes=mins_ago)
            log = AccessLog.objects.create(locker=locker, customer=customer)
            AccessLog.objects.filter(pk=log.pk).update(check_in_time=check_in)
            w(self.style.SUCCESS(
                f'  ACTIVE   {customer.name} @ #{locker.locker_number} | {mins_ago}min ago'
            ))

        # Summary
        w('\n' + '=' * 55)
        w(self.style.SUCCESS('DONE! Dummy data seeded.\n'))
        w(f'  Lockers     : {Locker.objects.count()}')
        w(f'  Customers   : {Customer.objects.count()}')
        w(f'  Assignments : {LockerUser.objects.count()}')
        w(f'  Logs (total): {AccessLog.objects.count()}')
        w(f'  Active now  : {AccessLog.objects.filter(check_out_time__isnull=True).count()}')
        w('=' * 55)

        w('\nLocker tokens for manual scan testing:')
        for lk in Locker.objects.all():
            status = 'ACTIVE  ' if lk.is_active else 'INACTIVE'
            w(f'  #{lk.locker_number:8}  {status}  {lk.token}')
        w('')
