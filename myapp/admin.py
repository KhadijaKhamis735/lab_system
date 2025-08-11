from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Division, Customer, Sample, Test, Payment, Result

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

admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(Division)
admin.site.register(Customer)
admin.site.register(Sample)
admin.site.register(Test)
admin.site.register(Payment)
admin.site.register(Result)
