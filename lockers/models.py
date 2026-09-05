import os
import secrets
from django.db import models
from django.core.exceptions import ValidationError


# ─── File upload validation ───────────────────────────────────────────────────

# Allowed extensions and their corresponding magic-byte signatures
_ALLOWED_UPLOAD_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}

# First-bytes signatures for each allowed type (magic bytes)
_MAGIC_BYTES = {
    b'%PDF': '.pdf',
    b'\xff\xd8\xff': '.jpg',  # JPEG
    b'\x89PNG': '.png',
}


def validate_id_proof_file(file):
    """
    Validator for customer ID proof uploads.
    Checks:
      1. Extension is in the allowed whitelist (.pdf, .jpg, .jpeg, .png)
      2. File size does not exceed 5 MB
      3. File magic bytes match the declared extension (prevents MIME-type spoofing)
    """
    # 1. Extension check
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. "
            f"Allowed formats: PDF, JPG, PNG."
        )

    # 2. Size check
    max_bytes = 5 * 1024 * 1024  # 5 MB
    if hasattr(file, 'size') and file.size > max_bytes:
        raise ValidationError("File is too large. Maximum allowed size is 5 MB.")

    # 3. Magic-byte check (read first 8 bytes, then rewind)
    try:
        header = file.read(8)
        file.seek(0)
    except Exception:
        raise ValidationError("Could not read the uploaded file. Please try again.")

    matched = False
    for magic, mime_ext in _MAGIC_BYTES.items():
        if header.startswith(magic):
            # For .jpeg we also accept .jpg extension
            if mime_ext == '.jpg' and ext in ('.jpg', '.jpeg'):
                matched = True
                break
            if mime_ext == ext:
                matched = True
                break

    if not matched:
        raise ValidationError(
            "The file content does not match its extension. "
            "Please upload a genuine PDF, JPG, or PNG file."
        )


def generate_locker_token():
    """Generate a unique URL-safe token for locker identification."""
    return secrets.token_urlsafe(16)


class Locker(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending Payment'),
        ('overdue', 'Payment Overdue'),
    ]

    locker_number = models.CharField(max_length=20, unique=True)
    token = models.CharField(
        max_length=100, unique=True,
        default=generate_locker_token,
        editable=False,   # shown read-only in admin/forms
    )
    is_active = models.BooleanField(default=True)
    annual_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00, help_text="Annual rent fee")
    lease_start_date = models.DateField(null=True, blank=True, help_text="Start date of lease agreement")
    lease_end_date = models.DateField(null=True, blank=True, help_text="Expiration date of lease agreement")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='paid')

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

    @property
    def lease_status(self):
        from django.utils import timezone
        import datetime
        today = timezone.now().date()

        if self.payment_status == 'overdue':
            return 'overdue'
        if self.lease_end_date:
            if self.lease_end_date < today:
                return 'overdue'
            if today <= self.lease_end_date <= (today + datetime.timedelta(days=30)) or self.payment_status == 'pending':
                return 'expiring_soon'
        elif self.payment_status == 'pending':
            return 'expiring_soon'
        return 'current'

    @property
    def days_until_expiration(self):
        from django.utils import timezone
        if self.lease_end_date:
            return (self.lease_end_date - timezone.now().date()).days
        return None

    class Meta:
        ordering = ['locker_number']


def generate_customer_id():
    """Generate a unique customer ID."""
    return f"CUST-{secrets.token_hex(4).upper()}"


class Customer(models.Model):
    ID_PROOF_CHOICES = [
        ('aadhaar', 'Aadhaar Card'),
        ('pan', 'PAN Card'),
        ('passport', 'Passport'),
        ('voter_id', 'Voter ID'),
        ('driving_license', 'Driving License'),
    ]

    name = models.CharField(max_length=200)
    customer_id = models.CharField(max_length=50, unique=True, default=generate_customer_id, help_text="Unique Customer ID")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Phone number for SMS/WhatsApp alerts")
    email = models.EmailField(blank=True, null=True, help_text="Email address for access notifications")
    id_proof_type = models.CharField(max_length=50, choices=ID_PROOF_CHOICES)
    id_proof_file = models.FileField(
        upload_to='id_proofs/',
        validators=[validate_id_proof_file],
        help_text="Accepted formats: PDF, JPG, PNG. Max 5 MB.",
    )

    def __str__(self):
        return self.name

    def get_lockers(self):
        # Use related_name='locker_users' defined on LockerUser.customer FK
        return Locker.objects.filter(locker_users__customer=self)

    @property
    def id_proof_file_exists(self):
        if not self.id_proof_file:
            return False
        return self.id_proof_file.storage.exists(self.id_proof_file.name)

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


class LockerActivity(models.Model):
    ACTIVITY_CHOICES = [
        ('created', 'Locker Created'),
        ('edited', 'Locker Updated'),
        ('assigned', 'Customer Assigned'),
        ('unassigned', 'Customer Removed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('deleted', 'Locker Deleted'),
    ]

    locker = models.ForeignKey(Locker, on_delete=models.CASCADE, related_name='activities')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='locker_activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_CHOICES)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.locker.locker_number} - {self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
