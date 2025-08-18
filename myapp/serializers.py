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

# Serializer for creating a new sample (sample submission)
class RegisterSampleSerializer(serializers.Serializer):
    customer = CustomerSerializer(required=True)
    sample_details = serializers.CharField(allow_blank=True, required=False)
    selected_ingredients = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=True
    )

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        customer_data = validated_data.pop('customer')
        sample_details = validated_data.get('sample_details', '')
        selected_ingredients = validated_data.get('selected_ingredients', [])

        try:
            customer = Customer.objects.get(email=customer_data.get('email', ''))
        except ObjectDoesNotExist:
            customer = Customer.objects.create(**customer_data)

        sample = Sample.objects.create(
            customer=customer,
            registrar=request.user,
            sample_details=sample_details,
            status='Awaiting HOD Review' # Set initial status
        )

        for ingredient_id in selected_ingredients:
            try:
                ingredient = Ingredient.objects.get(id=ingredient_id)
                Test.objects.create(
                    sample=sample,
                    ingredient=ingredient,
                    price=ingredient.price,
                    status='Pending'
                )
            except ObjectDoesNotExist:
                continue

        MARKING_FEE = Decimal('10000.00')
        total_ingredients_price = sum(
            Ingredient.objects.filter(id__in=selected_ingredients).values_list('price', flat=True),
            Decimal('0.00')
        )
        total_amount = MARKING_FEE + total_ingredients_price
        
        Payment.objects.create(sample=sample, amount_due=total_amount)

        return sample