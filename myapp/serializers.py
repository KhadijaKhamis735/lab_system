# myapp/serializers.py
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.contrib.auth.hashers import make_password

from .models import (
    User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient
)

# ---------------- Authentication ----------------
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


# ---------------- User / Department / Division ----------------
class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    division_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'department', 'department_name',
            'division', 'division_name',
            'specialization',   # ✅ add this
        ]


class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'department', 'division', 'password',
            'specialization',   # ✅ add this
        ]
        extra_kwargs = {'password': {'write_only': True, 'required': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user



class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class DivisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Division
        fields = '__all__'


# ---------------- Customers ----------------
class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id',
            'first_name', 'middle_name', 'last_name',
            'national_id',
            'is_organization', 'organization_name', 'organization_id',
            'country', 'region', 'street',
            'phone_country_code', 'phone_number',
            'email',
        ]


# ---------------- Ingredients / Tests ----------------
class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'price', 'test_type']


class TestSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer()
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)

    class Meta:
        model = Test
        fields = [
            'id', 'sample', 'ingredient', 'assigned_to', 'assigned_to_name',
            'results', 'price', 'status'
        ]


class SimpleTestSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_price = serializers.DecimalField(source='ingredient.price', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Test
        fields = ['id', 'ingredient_name', 'ingredient_price', 'status']


# ---------------- Payments / Results ----------------
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


# ---------------- Samples ----------------
class UnclaimedSampleSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    tests = SimpleTestSerializer(many=True, source='test_set', read_only=True)

    full_customer_name = serializers.SerializerMethodField()
    sample_name = serializers.SerializerMethodField()

    class Meta:
        model = Sample
        fields = [
            'id',
            'sample_name',
            'sample_details',
            'status',
            'date_received',
            'customer',
            'full_customer_name',
            'payment',
            'tests',
            'control_number',
        ]

    def get_full_customer_name(self, obj):
        if obj.customer:
            return " ".join(filter(None, [
                obj.customer.first_name,
                obj.customer.middle_name,
                obj.customer.last_name
            ])).strip()
        return None

    def get_sample_name(self, obj):
        return getattr(obj, 'sample_name', None) or obj.sample_details or obj.control_number


class SampleDashboardSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    registrar_name = serializers.CharField(source='registrar.username', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    tests = TestSerializer(many=True, source='test_set', read_only=True)   # ✅ shows test list
    sample_name = serializers.CharField(read_only=True)                   # ✅ added

    class Meta:
        model = Sample
        fields = [
            'id', 'control_number', 'sample_name', 'sample_details',
            'customer', 'registrar_name', 'date_received',
            'status', 'payment_status', 'tests'
        ]



class FullSampleSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    tests = TestSerializer(source="test_set", many=True, read_only=True)  # ✅ includes tests
    payment = PaymentSerializer(read_only=True)
    sample_name = serializers.CharField(read_only=True)                   # ✅ added

    class Meta:
        model = Sample
        fields = [
            "id", "control_number", "sample_name", "sample_details",
            "status", "date_received", "customer", "tests", "payment",
        ]




# ---------------- Submission ----------------



class RegisterCustomerSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True)
    middle_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    phone_country_code = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    country = serializers.CharField(required=True)
    region = serializers.CharField(required=True)
    street = serializers.CharField(required=True)
    national_id = serializers.CharField(required=False, allow_blank=True)

    # Organization fields
    is_organization = serializers.BooleanField(required=False, default=False)
    organization_name = serializers.CharField(required=False, allow_blank=True)
    organization_id = serializers.CharField(required=False, allow_blank=True)


class SampleSubmissionSerializer(serializers.Serializer):
    sample_name = serializers.CharField(required=True)
    sample_details = serializers.CharField(required=True)
    selected_ingredients = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, required=True
    )


# serializers.py

class RegisterSampleSerializer(serializers.Serializer):
    customer = serializers.DictField(required=True)
    samples = serializers.ListField(
        child=SampleSubmissionSerializer(), allow_empty=False, required=True
    )

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        customer_data = validated_data.pop("customer")
        samples_data = validated_data.pop("samples")

        # --- Create/Get Customer ---
        customer, _ = Customer.objects.get_or_create(
            email=customer_data.get("email", ""),
            defaults={
                "first_name": customer_data.get("first_name", ""),
                "middle_name": customer_data.get("middle_name", ""),
                "last_name": customer_data.get("last_name", ""),
                "phone_number": customer_data.get("phone_number", ""),
                "phone_country_code": customer_data.get("phone_country_code", ""),
                "country": customer_data.get("country", ""),
                "region": customer_data.get("region", ""),
                "street": customer_data.get("street", ""),
                "national_id": customer_data.get("national_id", ""),
                "is_organization": customer_data.get("is_organization", False),
                "organization_name": customer_data.get("organization_name", ""),
                "organization_id": customer_data.get("organization_id", ""),
            },
        )

        created_samples = []
        for sample_data in samples_data:
            sample = Sample.objects.create(
                customer=customer,
                registrar=request.user,
                sample_name=sample_data.get("sample_name", ""),   # ✅ added
                sample_details=sample_data.get("sample_details", ""),
                status="Awaiting HOD Review",
            )

            # --- Create Tests ---
            for ingredient_id in sample_data.get("selected_ingredients", []):
                try:
                    ingredient = Ingredient.objects.get(id=ingredient_id)
                    Test.objects.create(
                        sample=sample,
                        ingredient=ingredient,
                        price=ingredient.price,
                        status="Pending",
                    )
                except Ingredient.DoesNotExist:
                    continue

            created_samples.append(sample)

        # --- Payment (for first sample, covers all tests + marking fee) ---
        MARKING_FEE = Decimal("10000.00")
        all_ingredient_ids = [
            ing for s in samples_data for ing in s.get("selected_ingredients", [])
        ]
        total_ingredients_price = sum(
            Ingredient.objects.filter(id__in=all_ingredient_ids).values_list("price", flat=True),
            Decimal("0.00"),
        )
        total_amount = (MARKING_FEE * Decimal(len(samples_data))) + total_ingredients_price

        if created_samples:
            Payment.objects.update_or_create(
                sample=created_samples[0],
                defaults={"amount_due": total_amount, "status": "Pending"},
            )

        return created_samples
    

    # myapp/serializers.py

class TechnicianSampleSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    tests = serializers.SerializerMethodField()

    class Meta:
        model = Sample
        fields = ["id", "customer_id", "sample_name", "sample_details", "tests"]

    def get_tests(self, obj):
        return [
            {
                "id": t.id,
                "ingredient_name": t.ingredient.name,
                "ingredient_price": str(t.ingredient.price),
                "test_type": t.ingredient.test_type,
                "status": t.status,
            }
            for t in obj.test_set.all()
        ]


# serializers.py

class TechnicianIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name", "test_type"]

class TechnicianTestSerializer(serializers.ModelSerializer):
    ingredient = TechnicianIngredientSerializer()

    class Meta:
        model = Test
        fields = ["id", "ingredient", "status"]

class TechnicianSampleSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    tests = TechnicianTestSerializer(source="test_set", many=True)

    class Meta:
        model = Sample
        fields = ["id", "sample_name", "sample_details", "customer", "tests"]

    def get_customer(self, obj):
        return {"id": obj.customer.id}
