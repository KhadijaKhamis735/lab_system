from django.db import models
from django.contrib.auth.models import AbstractUser

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
    contact_info = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Sample(models.Model):
    STATUS_CHOICES = (
        ('Registered', 'Registered'),
        ('In Progress', 'In Progress'),
        ('Awaiting HOD Confirmation', 'Awaiting HOD Confirmation'),
        ('Awaiting Director Confirmation', 'Awaiting Director Confirmation'),
        ('Completed', 'Completed'),
        ('Sent to DPF', 'Sent to DPF'),
    )
    control_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    registrar = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='registered_samples')
    date_received = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Registered')
    assigned_to_hodv = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_samples')

    def __str__(self):
        return self.control_number

class Test(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    test_type = models.CharField(max_length=100)
    assigned_to = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    results = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.test_type} for {self.sample.control_number}"

class Payment(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Canceled', 'Canceled'),
    )
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
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
        return f"Result for {self.sample.control_number} - {self.test.test_type}"
