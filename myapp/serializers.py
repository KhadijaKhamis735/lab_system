from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from .models import (
    User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient
)

# Core Serializers
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not (username or email):
            raise serializers.ValidationError("A username or email is required.")
        if not password:
            raise serializers.ValidationError("A password is required.")

        user = None
        if username:
            user = authenticate(request=self.context.get('request'), username=username, password=password)
        elif email:
            try:
                user_obj = User.objects.get(email__iexact=email)
                user = authenticate(request=self.context.get('request'), username=user_obj.username, password=password)
            except ObjectDoesNotExist:
                pass

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
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'department', 'department_name', 'division', 'division_name'
        ]

    def get_department_name(self, obj):
        return obj.department.name if obj.department else None

    def get_division_name(self, obj):
        return obj.division.name if obj.division else None

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

class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'price']

class TestSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)

    class Meta:
        model = Test
        fields = [
            'id', 'sample', 'ingredient', 'ingredient_name',
            'assigned_to', 'assigned_to_name', 'results', 'price', 'status'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    sample_control_number = serializers.CharField(source='sample.control_number', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'

class ResultSerializer(serializers.ModelSerializer):
    test_ingredient_name = serializers.CharField(source='test.ingredient.name', read_only=True)
    sample_control_number = serializers.CharField(source='test.sample.control_number', read_only=True)

    class Meta:
        model = Result
        fields = '__all__'

# Serializer for Dashboards (includes nested data)
class SampleDashboardSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    tests = TestSerializer(many=True, read_only=True)
    registrar_name = serializers.CharField(source='registrar.username', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)

    class Meta:
        model = Sample
        fields = [
            'id', 'control_number', 'customer', 'registrar_name', 'date_received',
            'status', 'sample_details', 'tests', 'payment_status'
        ]

# --- NEW: Serializer for a single sample submission ---
class SampleSubmissionSerializer(serializers.Serializer):
    """
    A dedicated serializer for validating a single sample submission,
    ensuring all required fields are present and valid.
    """
    sample_details = serializers.CharField(allow_blank=False, required=True)
    selected_ingredients = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        allow_empty=False,
        required=True
    )

# --- CORRECTED: Main serializer for creating multiple samples ---
class RegisterSampleSerializer(serializers.Serializer):
    customer = serializers.DictField(
        child=serializers.CharField(),
        required=True
    )
    samples = serializers.ListField(
        child=SampleSubmissionSerializer(), # Now uses the dedicated serializer
        allow_empty=False,
        required=True
    )

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        customer_data = validated_data.pop('customer')
        samples_data = validated_data.pop('samples')

        # Try to get existing customer by email, create if not found
        try:
            customer, created = Customer.objects.get_or_create(
                email=customer_data.get('email', ''),
                defaults=customer_data
            )
        except Exception as e:
            raise serializers.ValidationError({'customer': f'Failed to process customer: {str(e)}'})

        created_samples = []
        for sample_data in samples_data:
            sample_details = sample_data.get('sample_details', '')
            selected_ingredients = sample_data.get('selected_ingredients', [])

            try:
                sample = Sample.objects.create(
                    customer=customer,
                    registrar=request.user,
                    sample_details=sample_details,
                    status='Awaiting HOD Review'
                )
                
                # Create Test rows for each selected ingredient
                for ingredient_id in selected_ingredients:
                    try:
                        ingredient = Ingredient.objects.get(id=ingredient_id)
                        Test.objects.create(
                            sample=sample,
                            ingredient=ingredient,
                            price=ingredient.price,
                            status='Pending'
                        )
                    except Ingredient.DoesNotExist:
                        raise serializers.ValidationError({'selected_ingredients': f'Ingredient {ingredient_id} does not exist.'})

                created_samples.append(sample)

            except Exception as e:
                raise serializers.ValidationError({'sample': f'Failed to create sample: {str(e)}'})

        MARKING_FEE = Decimal('10000.00')
        total_ingredients_price = sum(
            Ingredient.objects.filter(id__in=[ing for sample in samples_data for ing in sample.get('selected_ingredients', [])]).values_list('price', flat=True),
            Decimal('0.00')
        )
        total_amount = MARKING_FEE * Decimal(len(samples_data)) + total_ingredients_price

        # Update payment logic to handle multiple samples
        if created_samples:
            payment, _ = Payment.objects.get_or_create(
                sample=created_samples[0],
                defaults={'amount_due': total_amount, 'status': 'Pending'}
            )
            payment.amount_due = total_amount
            payment.save()

        return created_samples

    def validate(self, data):
        # The new SampleSubmissionSerializer now handles most of the validation
        customer_data = data.get('customer', {})
        samples_data = data.get('samples', [])
        
        # Manually validate customer data as before
        expected_customer_fields = {'name', 'phone_number', 'email', 'address'}
        if not all(k in expected_customer_fields for k in customer_data.keys()):
            raise serializers.ValidationError({'customer': 'Invalid customer fields. Use only name, phone_number, email, and address.'})
        if not all(k in customer_data for k in expected_customer_fields):
            raise serializers.ValidationError({'customer': 'Missing required fields: name, phone_number, email, and address are required.'})
            
        if not samples_data:
            raise serializers.ValidationError({'samples': 'At least one sample is required.'})

        return data