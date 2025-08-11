from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Department, Division, Customer, Sample, Test, Payment, Result
from rest_framework_simplejwt.tokens import RefreshToken

class LoginSerializer(serializers.Serializer):
    # Accept either email or username
    email = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        user = None
        if username:
            user = authenticate(username=username, password=password)
        elif email:
            # try to find user by email then authenticate using username
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            raise serializers.ValidationError("Invalid email/username or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        data['user'] = user
        return data

class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    division_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'department', 'department_name', 'division', 'division_name']

    def get_department_name(self, obj):
        return obj.department.name if obj.department else None

    def get_division_name(self, obj):
        return obj.division.name if obj.division else None

# Simple CRUD serializers
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'

class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class SampleSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    registrar_name = serializers.CharField(source='registrar.username', read_only=True)
    class Meta:
        model = Sample
        fields = '__all__'

class TestSerializer(serializers.ModelSerializer):
    sample_control_number = serializers.CharField(source='sample.control_number', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    class Meta:
        model = Test
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    sample_control_number = serializers.CharField(source='sample.control_number', read_only=True)
    class Meta:
        model = Payment
        fields = '__all__'

class ResultSerializer(serializers.ModelSerializer):
    sample_control_number = serializers.CharField(source='sample.control_number', read_only=True)
    test_type = serializers.CharField(source='test.test_type', read_only=True)
    class Meta:
        model = Result
        fields = '__all__'
