from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
import logging

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
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Technician')
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    division = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
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

class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = PhoneNumberField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

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

class Sample(models.Model):
    STATUS_CHOICES = (
        ('Registered', 'Registered'),
        ('Awaiting HOD Review', 'Awaiting HOD Review'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Sent to DPF', 'Sent to DPF'),
    )
    control_number = models.CharField(max_length=50, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    registrar = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='registered_samples')
    date_received = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Registered')
    assigned_to_hod = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_samples')
    assigned_to_hodv = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='hodv_samples')
    assigned_to_technician = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='technician_samples')
    sample_details = models.TextField(null=True, blank=True, help_text="Type of sample provided by the customer (e.g., Blood, Water)")

    def __str__(self):
        return self.control_number

    def save(self, *args, **kwargs):
        if not self.control_number:
            with transaction.atomic():
                today = timezone.now().date()
                date_prefix = today.strftime("%Y%m%d")
                last_sample = Sample.objects.filter(control_number__startswith=date_prefix).order_by('control_number').last()
                new_number = 1
                if last_sample and last_sample.control_number[len(date_prefix):].isdigit():
                    last_number_str = last_sample.control_number[len(date_prefix):]
                    last_number = int(last_number_str)
                    new_number = last_number + 1
                self.control_number = f'{date_prefix}{new_number:04d}'
        super().save(*args, **kwargs)

    def submit_to_hod(self):
        if not self.registrar or not self.registrar.department or not self.registrar.department.hod:
            raise ValueError("Registrar, department, or HOD not assigned")
        self.status = 'Awaiting HOD Review'
        self.assigned_to_hod = self.registrar.department.hod
        self.save()
        logger.info(f"Sample {self.control_number} assigned to HOD: {self.assigned_to_hod.username}")

    def assign_to_technician(self, technician):
        if not isinstance(technician, User) or technician.role != 'Technician':
            raise ValueError("Invalid technician assignment. Must be a Technician.")
        with transaction.atomic():
            self.assigned_to_technician = technician
            self.status = 'In Progress'
            self.save(update_fields=['assigned_to_technician', 'status'])
            tests_updated = self.test_set.update(assigned_to=technician, status='In Progress')
            logger.info(f"Sample {self.control_number} assigned to Technician {technician.username}. Updated {tests_updated} tests.")
        return True

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