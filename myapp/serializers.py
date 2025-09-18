# myapp/serializers.py
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    User, Department, Division, Customer, Sample,
    Test, Payment, Result, Ingredient
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
            user = authenticate(request=self.context.get('request'),
                                username=username, password=password)
        elif email:
            try:
                user_obj = User.objects.get(email__iexact=email)
                user = authenticate(request=self.context.get('request'),
                                    username=user_obj.username, password=password)
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
            'specialization',   # ✅ include specialization
        ]

    def get_department_name(self, obj):
        return obj.department.name if obj.department else None

    def get_division_name(self, obj):
        return obj.division.name if obj.division else None


class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role',
            'department', 'division', 'password',
            'specialization',
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
# serializers.py

class CustomerSerializer(serializers.ModelSerializer):
    phone_number = serializers.SerializerMethodField()

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

    def get_phone_number(self, obj):
        try:
            return str(obj.phone_number) if obj.phone_number else None
        except Exception:
            # In case of InvalidPhoneNumber or bad formatting
            return str(obj.phone_number.raw_input) if obj.phone_number else None




# ---------------- Ingredients / Tests ----------------
class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'price', 'test_type']


class TestSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer()
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    sample = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'sample', 'ingredient', 'assigned_to',
            'assigned_to_name', 'results', 'price', 'status', 'submitted_date'
        ]

    def get_sample(self, obj):
        sample = obj.sample
        if not sample:
            return None
        return {
            "id": sample.id,
            "sample_name": sample.sample_name,
            "sample_details": sample.sample_details,
            "date_received": sample.date_received,
            "registrar_name": sample.registrar.username if sample.registrar else None,
            "control_number": sample.control_number,
            "laboratory_number": sample.laboratory_number,  # Added
        }


class SimpleTestSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_price = serializers.DecimalField(source='ingredient.price',
                                                max_digits=12, decimal_places=2,
                                                read_only=True)

    class Meta:
        model = Test
        fields = ['id', 'ingredient_name', 'ingredient_price', 'status']


# ---------------- Payments / Results ----------------
class PaymentSerializer(serializers.ModelSerializer):
    sample_control_number = serializers.CharField(source='sample.control_number',
                                                  read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'


class ResultSerializer(serializers.ModelSerializer):
    test_ingredient_name = serializers.CharField(source='test.ingredient.name',
                                                 read_only=True)
    sample_control_number = serializers.CharField(source='test.sample.control_number',
                                                  read_only=True)

    class Meta:
        model = Result
        fields = '__all__'


# ---------------- Samples ----------------
class UnclaimedSampleSerializer(serializers.ModelSerializer):
    customer_details = serializers.SerializerMethodField()
    payment = PaymentSerializer(read_only=True)
    tests = SimpleTestSerializer(many=True, source="test_set", read_only=True)
    sample_name = serializers.SerializerMethodField()

    class Meta:
        model = Sample
        fields = [
            "id",
            "sample_name",
            "sample_details",
            "status",
            "date_received",
            "customer_details",
            "payment",
            "tests",
            "control_number",
        ]

    def get_customer_details(self, obj):
        customer = obj.customer
        if not customer:
            return None

        # Safe phone string
        try:
            phone = str(customer.phone_number) if customer.phone_number else None
        except Exception:
            phone = getattr(customer.phone_number, "raw_input", None)

        if customer.is_organization:
            return {
                "type": "Organization",
                "organization_name": customer.organization_name,
                "organization_id": customer.organization_id,
                "country": customer.country,
                "region": customer.region,
                "street": customer.street,
                "phone_country_code": customer.phone_country_code,
                "phone_number": phone,
                "email": customer.email,
            }

        return {
            "type": "Individual",
            "first_name": customer.first_name,
            "middle_name": customer.middle_name,
            "last_name": customer.last_name,
            "national_id": customer.national_id,
            "country": customer.country,
            "region": customer.region,
            "street": customer.street,
            "phone_country_code": customer.phone_country_code,
            "phone_number": phone,
            "email": customer.email,
        }

    def get_sample_name(self, obj):
        return (
            getattr(obj, "sample_name", None)
            or obj.sample_details
            or obj.control_number
        )









class SampleDashboardSerializer(serializers.ModelSerializer):
    customer_details = serializers.SerializerMethodField()
    registrar_name = serializers.CharField(source="registrar.username", read_only=True)
    payment_status = serializers.CharField(source="payment.status", read_only=True)
    tests = TestSerializer(many=True, source="test_set", read_only=True)
    sample_name = serializers.CharField(read_only=True)

    class Meta:
        model = Sample
        fields = [
            "id",
            "control_number",
            "sample_name",
            "sample_details",
            "customer_details",
            "registrar_name",
            "date_received",
            "status",
            "payment_status",
            "tests",
        ]

    def get_customer_details(self, obj):
        customer = obj.customer
        if not customer:
            return None

        if customer.is_organization:
            return {
                "type": "Organization",
                "organization_name": customer.organization_name,
                "organization_id": customer.organization_id,
                "country": customer.country,
                "region": customer.region,
                "street": customer.street,
                "phone": f"{customer.phone_country_code or ''}{customer.phone_number or ''}".strip(),
                "email": customer.email,
            }

        full_name = " ".join(filter(None, [
            customer.first_name,
            customer.middle_name,
            customer.last_name,
        ])).strip() or "Unnamed Customer"

        return {
            "type": "Individual",
            "full_name": full_name,
            "national_id": customer.national_id,
            "country": customer.country,
            "region": customer.region,
            "street": customer.street,
            "phone": f"{customer.phone_country_code or ''}{customer.phone_number or ''}".strip(),
            "email": customer.email,
        }



class FullSampleSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    tests = TestSerializer(source="test_set", many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    sample_name = serializers.CharField(read_only=True)
    claimed_by = serializers.SerializerMethodField()

    class Meta:
        model = Sample
        fields = [
            "id", "control_number", "laboratory_number", "sample_name", "sample_details",
            "status", "date_received", "customer", "tests", "payment", "claimed_by",
        ]

    def get_claimed_by(self, obj):
        if obj.registrar:
            return {"id": obj.registrar.id, "username": obj.registrar.username}
        return None





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

    is_organization = serializers.BooleanField(required=False, default=False)
    organization_name = serializers.CharField(required=False, allow_blank=True)
    organization_id = serializers.CharField(required=False, allow_blank=True)


class SampleSubmissionSerializer(serializers.Serializer):
    sample_name = serializers.CharField(required=True)
    sample_details = serializers.CharField(required=True)
    selected_ingredients = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, required=True
    )


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
                sample_name=sample_data.get("sample_name", ""),
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

        # --- Payment ---
        MARKING_FEE = Decimal("10000.00")
        all_ingredient_ids = [
            ing for s in samples_data for ing in s.get("selected_ingredients", [])
        ]
        total_ingredients_price = sum(
            Ingredient.objects.filter(id__in=all_ingredient_ids)
            .values_list("price", flat=True),
            Decimal("0.00"),
        )
        total_amount = (MARKING_FEE * Decimal(len(samples_data))) + total_ingredients_price

        if created_samples:
            Payment.objects.update_or_create(
                sample=created_samples[0],
                defaults={"amount_due": total_amount, "status": "Pending"},
            )

        return created_samples


# ---------------- Technician View ----------------
class TechnicianIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name", "test_type"]

class TechnicianDashboardSerializer(serializers.ModelSerializer):
    ingredient = TechnicianIngredientSerializer()
    sample = serializers.SerializerMethodField()
    assigned_by_hod = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ["id", "ingredient", "status", "sample", "assigned_by_hod"]

    def get_sample(self, obj):
        sample = obj.sample
        if not sample:
            return None
        return {
            "id": sample.id,
            "sample_name": sample.sample_name,
            "sample_details": sample.sample_details,   # ✅ Sample Details
            "date_received": sample.date_received,     # ✅ Assigned Date
            "registrar_name": sample.registrar.username if sample.registrar else None,  # ✅ Submitted By
            "customer": {"id": sample.customer.id} if sample.customer else None,
            "control_number": sample.control_number,   # ✅ Use as Sample Code
        }

    def get_assigned_by_hod(self, obj):
        return {
            "name": obj.assigned_to.username if obj.assigned_to else "HOD"
        }


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No account found with this email.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)

        # Generate token
        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        # Send email
        send_mail(
            "Password Reset Request",
            f"Click the link to reset your password: {reset_link}",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return {"message": "Password reset instructions sent to email."}
    

    class ResetPasswordSerializer(serializers.Serializer):
      uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError("Invalid UID")

        if not PasswordResetTokenGenerator().check_token(user, data['token']):
            raise serializers.ValidationError("Invalid or expired token")

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return {"message": "Password has been reset successfully."}







