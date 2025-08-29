from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'department', 'division', 'is_active')
    list_filter = ('role', 'department', 'division', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'department', 'division')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('email', 'role', 'department', 'division')}),
    )

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'test_type')
    list_filter = ('test_type', 'price')
    search_fields = ('name',)

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('sample', 'ingredient', 'assigned_to', 'status', 'price')
    list_filter = ('status', 'ingredient', 'assigned_to')
    search_fields = ('sample__control_number', 'ingredient__name')
    readonly_fields = ('sample', 'ingredient')

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ('control_number', 'customer', 'registrar', 'status', 'date_received')
    list_filter = ('status', 'date_received', 'registrar')
    search_fields = ('control_number', 'customer__name')
    readonly_fields = ('control_number', 'date_received')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('sample', 'amount_due', 'status', 'verified_by', 'verification_date')
    list_filter = ('status', 'verification_date')
    search_fields = ('sample__control_number',)

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('sample', 'test', 'confirmed_by_hod', 'confirmed_by_director', 'sent_to_dpf')
    list_filter = ('confirmed_by_hod', 'confirmed_by_director', 'sent_to_dpf')
    search_fields = ('sample__control_number', 'test__ingredient__name')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(Division)
admin.site.register(Customer)