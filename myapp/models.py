from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
import logging

from django.db import models

logger = logging.getLogger(__name__)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Registrar', 'Registrar'),
        ('HOD', 'Head of Department'),
        ('HODv', 'Head of Division'),
        ('Technician', 'Laboratory Technician'),
        ('Director', 'Director'),
    )

    SPECIALIZATION_CHOICES = (
        ('Chemistry', 'Chemistry'),
        ('Microbiology', 'Microbiology'),
    )

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Technician')
    specialization = models.CharField(   # 🔹 NEW FIELD
        max_length=50,
        choices=SPECIALIZATION_CHOICES,
        null=True,
        blank=True,
        help_text="Only applies if role is Technician"
    )
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    division = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        if self.role == "Technician" and self.specialization:
            return f"{self.username} ({self.role} - {self.specialization})"
        return f"{self.username} ({self.role})"


class Department(models.Model):
    name = models.CharField(max_length=100)
    hod = models.OneToOneField('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_department')

    def __str__(self):
        return self.name

class Division(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    hodv = models.OneToOneField('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='hodv_division')

    def __str__(self):
        return f"{self.name} ({self.department.name})"

# models.py
class Customer(models.Model):
    first_name = models.CharField(max_length=100, null=True, blank=True)
    middle_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    national_id = models.CharField(max_length=50, null=True, blank=True)

    is_organization = models.BooleanField(default=False)
    organization_name = models.CharField(max_length=200, null=True, blank=True)
    organization_id = models.CharField(max_length=100, null=True, blank=True)

    country = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    street = models.CharField(max_length=200, null=True, blank=True)

    phone_country_code = models.CharField(max_length=10, null=True, blank=True)
    phone_number = PhoneNumberField(null=True, blank=True)

    email = models.EmailField(unique=True, null=True, blank=True)

    def __str__(self):
        # full name fallback
        if self.is_organization:
            return f"{self.organization_name} ({self.organization_id})"
        return f"{self.first_name} {self.last_name}".strip()


class Ingredient(models.Model):
    TEST_TYPE_CHOICES = (
        ('Microbiology', 'Microbiology'),
        ('Chemistry', 'Chemistry'),
    )
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    test_type = models.CharField(max_length=50, choices=TEST_TYPE_CHOICES, default='Microbiology')

    def __str__(self):
        return f"{self.name} (TZS {self.price}) - {self.test_type}"

# myapp/models.py


class Sample(models.Model):
    STATUS_CHOICES = (
        ('Registered', 'Registered'),
        ('Awaiting Registrar Approval', 'Awaiting Registrar Approval'),
        ('Awaiting HOD Review', 'Awaiting HOD Review'),
        ('Submitted to HOD', 'Submitted to HOD'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Sent to DPF', 'Sent to DPF'),
    )

    control_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="System-generated or manually entered control number."
    )
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.CASCADE,
        related_name="samples"
    )
    registrar = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_samples"
    )
    date_received = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="Registered"
    )
    

    
    assigned_to_hod = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hod_samples"
    )
    assigned_to_hodv = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hodv_samples"
    )
    assigned_to_technician = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_samples"
    )

    # 🔹 Sample details
    sample_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Short title or name for the sample (e.g., Water Sample, Soil Sample)."
    )
    sample_details = models.TextField(
        null=True,
        blank=True,
        help_text="Detailed description of the sample."
    )

    def __str__(self):
        return f"{self.control_number or 'No Ctrl#'} - {self.sample_name or self.sample_details or 'Unnamed Sample'}"




class Test(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Awaiting HOD Review', 'Awaiting HOD Review'),
        ('Completed', 'Completed'),
    )
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='test_set')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True)
    assigned_to = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tests')
    results = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_tests')
    approved_date = models.DateTimeField(null=True, blank=True)
    submitted_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        ingredient_name = self.ingredient.name if self.ingredient else "N/A"
        return f"{ingredient_name} test for {self.sample.control_number}"

class Payment(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Canceled', 'Canceled'),
    )
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    verified_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for {self.sample.control_number} - {self.status}"

class Result(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    result_data = models.TextField()
    confirmed_by_hod = models.BooleanField(default=False)
    confirmed_by_director = models.BooleanField(default=False)
    finalized_date = models.DateTimeField(null=True, blank=True)
    sent_to_dpf = models.BooleanField(default=False)

    def __str__(self):
        ingredient_name = self.test.ingredient.name if self.test and self.test.ingredient else "N/A"
        return f"Result for {self.sample.control_number} – {ingredient_name}"

class VerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Token for {self.user.username}"