import secrets
from django.db import models
from django.core.exceptions import ValidationError


def generate_locker_token():
    """Generate a unique URL-safe token for locker identification."""
    return secrets.token_urlsafe(16)


class Locker(models.Model):
    locker_number = models.CharField(max_length=20, unique=True)
    token = models.CharField(
        max_length=100, unique=True,
        default=generate_locker_token,
        editable=False,   # shown read-only in admin/forms
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Locker #{self.locker_number}"

    def get_customers(self):
        # Use related_name='locker_users' defined on LockerUser.locker FK
        return Customer.objects.filter(locker_users__locker=self)

    @property
    def customer_count(self):
        return LockerUser.objects.filter(locker=self).count()

    @property
    def capacity_pct(self):
        """Capacity as integer 0-100 for use in widthratio template tag."""
        return (self.customer_count * 100) // 3

    class Meta:
        ordering = ['locker_number']


class Customer(models.Model):
    ID_PROOF_CHOICES = [
        ('aadhaar', 'Aadhaar Card'),
        ('pan', 'PAN Card'),
        ('passport', 'Passport'),
        ('voter_id', 'Voter ID'),
        ('driving_license', 'Driving License'),
    ]

    name = models.CharField(max_length=200)
    id_proof_type = models.CharField(max_length=50, choices=ID_PROOF_CHOICES)
    id_proof_file = models.FileField(upload_to='id_proofs/')

    def __str__(self):
        return self.name

    def get_lockers(self):
        # Use related_name='locker_users' defined on LockerUser.customer FK
        return Locker.objects.filter(locker_users__customer=self)

    class Meta:
        ordering = ['name']


class LockerUser(models.Model):
    locker = models.ForeignKey(Locker, on_delete=models.CASCADE, related_name='locker_users')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='locker_users')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('locker', 'customer')
        ordering = ['assigned_at']

    def __str__(self):
        return f"{self.customer.name} → Locker #{self.locker.locker_number}"

    def clean(self):
        # Guard: skip if locker or customer FKs are not yet assigned
        # (prevents RelatedObjectDoesNotExist during full_clean calls)
        if not self.locker_id or not self.customer_id:
            return

        # Business Rule: max 3 customers per locker
        existing_count = LockerUser.objects.filter(locker_id=self.locker_id).exclude(pk=self.pk).count()
        if existing_count >= 3:
            raise ValidationError(
                f"Locker #{self.locker.locker_number} already has the maximum of 3 customers."
            )
        # Business Rule: same customer cannot be added twice to same locker
        if LockerUser.objects.filter(locker_id=self.locker_id, customer_id=self.customer_id).exclude(pk=self.pk).exists():
            raise ValidationError(
                f"{self.customer.name} is already assigned to Locker #{self.locker.locker_number}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AccessLog(models.Model):
    locker = models.ForeignKey(Locker, on_delete=models.CASCADE, related_name='access_logs')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='access_logs')
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-check_in_time']

    def __str__(self):
        return f"{self.customer.name} | Locker #{self.locker.locker_number} | {self.check_in_time.strftime('%Y-%m-%d %H:%M')}"

    def is_active(self):
        return self.check_out_time is None

    def duration(self):
        if self.check_out_time:
            delta = self.check_out_time - self.check_in_time
            minutes = int(delta.total_seconds() // 60)
            hours = minutes // 60
            mins = minutes % 60
            if hours:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        return "In Progress"
