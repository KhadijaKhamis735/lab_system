from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Department, Division, Customer, Sample, Test, Payment, Result

class LoginSerializer(serializers.Serializer):
    """
    Serializer to handle user login.
    Accepts either a username or an email along with a password.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        # Ensure either username or email is provided
        if not (username or email):
            raise serializers.ValidationError("A username or email is required.")
        if not password:
            raise serializers.ValidationError("A password is required.")

        user = None
        # Authenticate using the provided username
        if username:
            user = authenticate(request=self.context.get('request'), username=username, password=password)
        # Or, authenticate using the provided email
        elif email:
            try:
                # Find the user by email first, then authenticate with their username
                user_obj = User.objects.get(email__iexact=email)
                user = authenticate(request=self.context.get('request'), username=user_obj.username, password=password)
            except ObjectDoesNotExist:
                pass # The user remains None if not found

        # Handle authentication failures
        if user is None:
            raise serializers.ValidationError("Invalid credentials provided.")
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

# Combined Serializer for Registration
class RegisterSampleSerializer(serializers.Serializer):
    customer = CustomerSerializer()
    sample = SampleSerializer(required=False)

    def create(self, validated_data):
        customer_data = validated_data.pop('customer')
        customer, created = Customer.objects.get_or_create(**customer_data)
        sample_data = validated_data.get('sample', {})
        sample_data['customer'] = customer
        sample_data['registrar'] = self.context['request'].user
        sample = Sample.objects.create(**sample_data)
        # Create initial payment based on number of tests (placeholder logic)
        tests_count = validated_data.get('tests_count', 1)  # Default to 1 test
        Payment.objects.create(sample=sample, amount_due=1000 * tests_count)
        return sample