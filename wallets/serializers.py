from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *
from decimal import Decimal

# ──────────────────────────────────────────────
# User Serializers
# ──────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


# ──────────────────────────────────────────────
# Company Serializers
# ──────────────────────────────────────────────

class CompanySerializer(serializers.ModelSerializer):
    total_employees = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'email', 'phone',
            'address', 'logo', 'is_active',
            'total_employees', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_employees(self, obj):
        return obj.employees.filter(is_active=True).count()

    def validate_email(self, value):
        instance = self.instance
        if Company.objects.filter(email=value).exclude(
            pk=instance.pk if instance else None
        ).exists():
            raise serializers.ValidationError("A company with this email already exists.")
        return value


class CompanyMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'email']


# ──────────────────────────────────────────────
# Wallet Serializers
# ──────────────────────────────────────────────

class WalletSerializer(serializers.ModelSerializer):
    balance_in_taka = serializers.ReadOnlyField()

    class Meta:
        model = Wallet
        fields = [
            'id', 'wallet_id', 'balance',
            'balance_in_taka', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'wallet_id', 'balance',
            'balance_in_taka', 'created_at', 'updated_at',
        ]

    def validate_wallet_id(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Wallet ID cannot be empty.")
        return value


class WalletMinimalSerializer(serializers.ModelSerializer):
    balance_in_taka = serializers.ReadOnlyField()

    class Meta:
        model = Wallet
        fields = ['wallet_id', 'balance', 'balance_in_taka', 'is_active']


# ──────────────────────────────────────────────
# Employee Serializers
# ──────────────────────────────────────────────

class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    company = CompanyMinimalSerializer(read_only=True)
    wallet = WalletMinimalSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'company', 'employee_id',
            'role', 'phone', 'avatar', 'is_active',
            'wallet', 'full_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'employee_id', 'created_at', 'updated_at',
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class EmployeeCreateSerializer(serializers.Serializer):
    # User fields
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    password = serializers.CharField(write_only=True, min_length=8)

    # Employee fields
    role = serializers.ChoiceField(choices=Employee.ROLE_CHOICES, default='employee')
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        max_length=150, required=False, source='user.first_name'
    )
    last_name = serializers.CharField(
        max_length=150, required=False, source='user.last_name'
    )

    class Meta:
        model = Employee
        fields = ['role', 'phone', 'avatar', 'is_active', 'first_name', 'last_name']


class EmployeeMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name', 'username', 'role']

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


# ──────────────────────────────────────────────
# Transaction Serializers
# ──────────────────────────────────────────────

class TransactionSerializer(serializers.ModelSerializer):
    amount_in_taka = serializers.ReadOnlyField()
    balance_before_in_taka = serializers.ReadOnlyField()
    balance_after_in_taka = serializers.ReadOnlyField()
    employee = EmployeeMinimalSerializer(read_only=True)
    related_employee = EmployeeMinimalSerializer(read_only=True)
    company = CompanyMinimalSerializer(read_only=True)
    wallet_id = serializers.CharField(source='wallet.wallet_id', read_only=True)
    related_wallet_id = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_id', 'api_key', 'idempotency_key',
            'wallet_id', 'related_wallet_id',
            'company', 'employee', 'related_employee',
            'transaction_type', 'amount', 'amount_in_taka',
            'balance_before', 'balance_before_in_taka',
            'balance_after', 'balance_after_in_taka',
            'status', 'note', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_related_wallet_id(self, obj):
        if obj.related_wallet:
            return obj.related_wallet.wallet_id
        return None


class DepositSerializer(serializers.Serializer):
    wallet_id = serializers.CharField(max_length=20)
    # Amount in taka (will be converted to paisa in view)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    note = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=255)

    def validate_wallet_id(self, value):
        if not Wallet.objects.filter(wallet_id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive wallet ID.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_idempotency_key(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Idempotency key is required.")
        return value.strip()


class WithdrawSerializer(serializers.Serializer):
    wallet_id = serializers.CharField(max_length=20)
    # Amount in taka (will be converted to paisa in view)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    note = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=255)

    def validate_wallet_id(self, value):
        if not Wallet.objects.filter(wallet_id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive wallet ID.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_idempotency_key(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Idempotency key is required.")
        return value.strip()


class TransferSerializer(serializers.Serializer):
    from_wallet_id = serializers.CharField(max_length=20)
    to_wallet_id = serializers.CharField(max_length=20)
    # Amount in taka (will be converted to paisa in view)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    note = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=255)

    def validate_from_wallet_id(self, value):
        if not Wallet.objects.filter(wallet_id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive sender wallet ID.")
        return value

    def validate_to_wallet_id(self, value):
        if not Wallet.objects.filter(wallet_id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive receiver wallet ID.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_idempotency_key(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Idempotency key is required.")
        return value.strip()

    def validate(self, data):
        from_wallet = data.get('from_wallet_id')
        to_wallet = data.get('to_wallet_id')

        if from_wallet and to_wallet:
            if from_wallet == to_wallet:
                raise serializers.ValidationError(
                    "Sender and receiver wallet cannot be the same."
                )

            # Check both wallets belong to the same company
            try:
                sender_wallet = Wallet.objects.select_related(
                    'employee__company'
                ).get(wallet_id=from_wallet)

                receiver_wallet = Wallet.objects.select_related(
                    'employee__company'
                ).get(wallet_id=to_wallet)

                if sender_wallet.employee.company != receiver_wallet.employee.company:
                    raise serializers.ValidationError(
                        "Transfer is only allowed within the same company."
                    )
            except Wallet.DoesNotExist:
                pass

        return data


class TransactionHistoryQuerySerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(
        choices=[('deposit', 'Deposit'), ('withdraw', 'Withdraw'),
                 ('transfer_in', 'Transfer In'), ('transfer_out', 'Transfer Out')],
        required=False,
    )
    status = serializers.ChoiceField(
        choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
        required=False,
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=10
    )
