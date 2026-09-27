import uuid
import secrets
import hashlib
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction as db_transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from wallets.models import *
from wallets.serializers import *
from wallets.services.docker_service import DockerTransactionService


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def success_response(data=None, message="Success", status_code=200):
    return Response(
        {"success": True, "message": message, "data": data},
        status=status_code,
    )


def error_response(message="Error", errors=None, status_code=400):
    return Response(
        {"success": False, "message": message, "errors": errors},
        status=status_code,
    )


def generate_wallet_id():
    while True:
        wallet_id = "WL" + secrets.token_hex(4).upper()
        if not Wallet.objects.filter(wallet_id=wallet_id).exists():
            return wallet_id


def generate_employee_id(company_id):
    while True:
        emp_id = f"EMP{company_id}{secrets.token_hex(3).upper()}"
        if not Employee.objects.filter(employee_id=emp_id).exists():
            return emp_id


def generate_api_key():
    return secrets.token_hex(32)


def taka_to_paisa(amount_taka):
    """Convert taka (Decimal) to paisa (int)"""
    return int(Decimal(str(amount_taka)) * 100)


def paisa_to_taka(amount_paisa):
    """Convert paisa (int) to taka (Decimal)"""
    return Decimal(amount_paisa) / 100


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def get_employee_from_request(request):
    try:
        return Employee.objects.select_related(
            'user', 'company', 'wallet'
        ).get(user=request.user)
    except Employee.DoesNotExist:
        return None


def paginate_queryset(queryset, page, page_size):
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    data = queryset[start:end]
    return data, {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "has_next": end < total,
        "has_previous": page > 1,
    }


# ──────────────────────────────────────────────
# Auth Views
# ──────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        # Validate required fields
        required = ['username', 'email', 'password', 'company_name', 'company_email']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return error_response(
                message="Missing required fields.",
                errors={f: "This field is required." for f in missing},
                status_code=400,
            )

        # Check existing user
        if User.objects.filter(username=data['username']).exists():
            return error_response(
                message="Username already taken.",
                errors={"username": "This username is already taken."},
                status_code=400,
            )

        if User.objects.filter(email=data['email']).exists():
            return error_response(
                message="Email already in use.",
                errors={"email": "This email is already registered."},
                status_code=400,
            )

        if Company.objects.filter(email=data['company_email']).exists():
            return error_response(
                message="Company email already registered.",
                errors={"company_email": "A company with this email already exists."},
                status_code=400,
            )

        try:
            with db_transaction.atomic():
                # Create User
                user = User.objects.create_user(
                    username=data['username'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                )

                # Create Company
                company = Company.objects.create(
                    name=data['company_name'],
                    email=data['company_email'],
                    phone=data.get('company_phone', ''),
                    address=data.get('company_address', ''),
                )

                # Create Employee (admin role)
                employee = Employee.objects.create(
                    user=user,
                    company=company,
                    employee_id=generate_employee_id(company.id),
                    role='admin',
                    phone=data.get('phone', ''),
                )

                # Create Wallet
                Wallet.objects.create(
                    wallet_id=generate_wallet_id(),
                    employee=employee,
                    balance=0,
                )

            tokens = get_tokens_for_user(user)
            return success_response(
                data={
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.get_full_name(),
                    },
                    "employee": {
                        "id": employee.id,
                        "employee_id": employee.employee_id,
                        "role": employee.role,
                        "company": {
                            "id": company.id,
                            "name": company.name,
                        },
                        "wallet_id": employee.wallet.wallet_id,
                    },
                },
                message="Registration successful.",
                status_code=201,
            )

        except Exception as e:
            return error_response(
                message="Registration failed.",
                errors={"detail": str(e)},
                status_code=500,
            )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return error_response(
                message="Username and password are required.",
                errors={
                    "username": "Required." if not username else None,
                    "password": "Required." if not password else None,
                },
                status_code=400,
            )

        user = authenticate(username=username, password=password)
        if not user:
            return error_response(
                message="Invalid credentials.",
                errors={"detail": "Username or password is incorrect."},
                status_code=401,
            )

        if not user.is_active:
            return error_response(
                message="Account is disabled.",
                errors={"detail": "Your account has been disabled."},
                status_code=403,
            )

        employee = get_employee_from_request(
            type('R', (), {'user': user})()
        )
        if not employee or not employee.is_active:
            return error_response(
                message="Employee account is inactive.",
                errors={"detail": "Your employee account is not active."},
                status_code=403,
            )

        tokens = get_tokens_for_user(user)
        return success_response(
            data={
                "tokens": tokens,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.get_full_name(),
                },
                "employee": {
                    "id": employee.id,
                    "employee_id": employee.employee_id,
                    "role": employee.role,
                    "company": {
                        "id": employee.company.id,
                        "name": employee.company.name,
                    },
                    "wallet_id": employee.wallet.wallet_id,
                },
            },
            message="Login successful.",
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return error_response(
                message="Refresh token is required.",
                errors={"refresh": "This field is required."},
                status_code=400,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response(message="Logged out successfully.")
        except TokenError:
            return error_response(
                message="Invalid or expired token.",
                errors={"refresh": "Token is invalid or already blacklisted."},
                status_code=400,
            )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return error_response(
                message="Email is required.",
                errors={"email": "This field is required."},
                status_code=400,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Security: don't reveal if email exists
            return success_response(
                message="If this email is registered, a reset link has been sent."
            )

        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        cache_key = f"password_reset_{reset_token}"
        cache.set(cache_key, user.id, timeout=3600)  # 1 hour

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        try:
            send_mail(
                subject="WalletBD - Password Reset Request",
                message=f"Click the link to reset your password: {reset_url}\n\nThis link expires in 1 hour.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            return error_response(
                message="Failed to send reset email. Please try again.",
                status_code=500,
            )

        return success_response(
            message="If this email is registered, a reset link has been sent."
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token', '').strip()
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        if not token:
            return error_response(
                message="Reset token is required.",
                errors={"token": "This field is required."},
                status_code=400,
            )

        if not new_password or not confirm_password:
            return error_response(
                message="Both password fields are required.",
                errors={
                    "new_password": "Required." if not new_password else None,
                    "confirm_password": "Required." if not confirm_password else None,
                },
                status_code=400,
            )

        if new_password != confirm_password:
            return error_response(
                message="Passwords do not match.",
                errors={"confirm_password": "Passwords do not match."},
                status_code=400,
            )

        if len(new_password) < 8:
            return error_response(
                message="Password too short.",
                errors={"new_password": "Password must be at least 8 characters."},
                status_code=400,
            )

        cache_key = f"password_reset_{token}"
        user_id = cache.get(cache_key)

        if not user_id:
            return error_response(
                message="Reset token is invalid or expired.",
                errors={"token": "Token is invalid or has expired."},
                status_code=400,
            )

        try:
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            cache.delete(cache_key)
            return success_response(message="Password reset successful.")
        except User.DoesNotExist:
            return error_response(
                message="User not found.",
                status_code=404,
            )


# ──────────────────────────────────────────────
# Company Views
# ──────────────────────────────────────────────

class CompanyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        serializer = CompanySerializer(employee.company)
        return success_response(data=serializer.data)

    def put(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        if employee.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can update company details."},
                status_code=403,
            )

        serializer = CompanySerializer(
            employee.company, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return success_response(
                data=serializer.data, message="Company updated successfully."
            )
        return error_response(
            message="Validation failed.", errors=serializer.errors, status_code=400
        )


# ──────────────────────────────────────────────
# Employee Views
# ──────────────────────────────────────────────

class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        employees = Employee.objects.filter(
            company=employee.company
        ).exclude(id=employee.id).select_related('user', 'company', 'wallet')

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        data, pagination = paginate_queryset(employees, page, page_size)

        serializer = EmployeeSerializer(data, many=True)
        return success_response(
            data={"employees": serializer.data, "pagination": pagination}
        )

    def post(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        if employee.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can add employees."},
                status_code=403,
            )

        serializer = EmployeeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )

        data = serializer.validated_data
        try:
            with db_transaction.atomic():
                new_user = User.objects.create_user(
                    username=data['username'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                )

                new_employee = Employee.objects.create(
                    user=new_user,
                    company=employee.company,
                    employee_id=generate_employee_id(employee.company.id),
                    role=data.get('role', 'employee'),
                    phone=data.get('phone', ''),
                )

                wallet = Wallet.objects.create(
                    wallet_id=generate_wallet_id(),
                    employee=new_employee,
                    balance=0,
                )

            return success_response(
                data=EmployeeSerializer(new_employee).data,
                message="Employee created successfully.",
                status_code=201,
            )

        except Exception as e:
            return error_response(
                message="Failed to create employee.",
                errors={"detail": str(e)},
                status_code=500,
            )


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        requester = get_employee_from_request(request)
        if not requester:
            return error_response(message="Employee not found.", status_code=404)

        # Admin can view any employee; employee can only view self
        if requester.role != 'admin' and requester.employee_id != employee_id:
            return error_response(
                message="Permission denied.",
                errors={"detail": "You can only view your own profile."},
                status_code=403,
            )

        try:
            emp = Employee.objects.select_related(
                'user', 'company', 'wallet'
            ).get(employee_id=employee_id, company=requester.company)
        except Employee.DoesNotExist:
            return error_response(message="Employee not found.", status_code=404)

        return success_response(data=EmployeeSerializer(emp).data)

    def put(self, request, employee_id):
        requester = get_employee_from_request(request)
        if not requester:
            return error_response(message="Employee not found.", status_code=404)

        if requester.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can update employee details."},
                status_code=403,
            )

        try:
            emp = Employee.objects.select_related('user').get(
                employee_id=employee_id, company=requester.company
            )
        except Employee.DoesNotExist:
            return error_response(message="Employee not found.", status_code=404)

        serializer = EmployeeUpdateSerializer(emp, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )

        validated = serializer.validated_data
        user_data = validated.pop('user', {})

        with db_transaction.atomic():
            for attr, value in user_data.items():
                setattr(emp.user, attr, value)
            emp.user.save()
            serializer.save()

        return success_response(
            data=EmployeeSerializer(emp).data,
            message="Employee updated successfully.",
        )

    def delete(self, request, employee_id):
        requester = get_employee_from_request(request)
        if not requester:
            return error_response(message="Employee not found.", status_code=404)

        if requester.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can deactivate employees."},
                status_code=403,
            )

        if requester.employee_id == employee_id:
            return error_response(
                message="Cannot deactivate yourself.",
                errors={"detail": "Admins cannot deactivate their own account."},
                status_code=400,
            )

        try:
            emp = Employee.objects.get(
                employee_id=employee_id, company=requester.company
            )
        except Employee.DoesNotExist:
            return error_response(message="Employee not found.", status_code=404)

        emp.is_active = False
        emp.user.is_active = False
        emp.user.save()
        emp.save()

        return success_response(message="Employee deactivated successfully.")


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Profile not found.", status_code=404)
        return success_response(data=EmployeeSerializer(employee).data)

    def put(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Profile not found.", status_code=404)

        data = request.data
        with db_transaction.atomic():
            if 'first_name' in data:
                employee.user.first_name = data['first_name']
            if 'last_name' in data:
                employee.user.last_name = data['last_name']
            if 'phone' in data:
                employee.phone = data['phone']
            if 'avatar' in request.FILES:
                employee.avatar = request.FILES['avatar']
            employee.user.save()
            employee.save()

        return success_response(
            data=EmployeeSerializer(employee).data,
            message="Profile updated successfully.",
        )


# ──────────────────────────────────────────────
# Wallet Views
# ──────────────────────────────────────────────

class WalletDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        try:
            wallet = employee.wallet
        except Wallet.DoesNotExist:
            return error_response(message="Wallet not found.", status_code=404)

        serializer = WalletSerializer(wallet)
        return success_response(data=serializer.data)


class WalletByIdView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        requester = get_employee_from_request(request)
        if not requester:
            return error_response(message="Employee not found.", status_code=404)

        if requester.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can look up wallets by ID."},
                status_code=403,
            )

        try:
            wallet = Wallet.objects.select_related(
                'employee__user', 'employee__company'
            ).get(wallet_id=wallet_id, employee__company=requester.company)
        except Wallet.DoesNotExist:
            return error_response(message="Wallet not found.", status_code=404)

        return success_response(data=WalletSerializer(wallet).data)


# ──────────────────────────────────────────────
# Transaction Views (Isolated Docker Services)
# ──────────────────────────────────────────────

class DepositView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        if employee.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can perform deposits."},
                status_code=403,
            )

        serializer = DepositSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )

        data = serializer.validated_data
        idempotency_key = data['idempotency_key']

        # Check idempotency - return existing transaction if key exists
        existing = Transaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return success_response(
                data=TransactionSerializer(existing).data,
                message="Transaction already processed (idempotent response).",
            )

        # Validate wallet belongs to this company
        try:
            wallet = Wallet.objects.select_related(
                'employee__company'
            ).get(wallet_id=data['wallet_id'])
        except Wallet.DoesNotExist:
            return error_response(message="Wallet not found.", status_code=404)

        if wallet.employee.company != employee.company:
            return error_response(
                message="Wallet does not belong to your company.",
                status_code=403,
            )

        if not wallet.is_active:
            return error_response(
                message="Wallet is inactive.",
                errors={"wallet_id": "This wallet is currently inactive."},
                status_code=400,
            )

        # Convert taka to paisa
        amount_paisa = taka_to_paisa(data['amount'])

        # Process via Docker isolated service
        result = DockerTransactionService.process_deposit(
            wallet_id=wallet.wallet_id,
            amount_paisa=amount_paisa,
            idempotency_key=idempotency_key,
            note=data.get('note', ''),
            performed_by_employee=employee,
        )

        if result['success']:
            return success_response(
                data=result['data'],
                message="Deposit successful.",
                status_code=201,
            )
        return error_response(
            message=result['message'],
            errors=result.get('errors'),
            status_code=result.get('status_code', 400),
        )


class WithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        serializer = WithdrawSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )

        data = serializer.validated_data
        idempotency_key = data['idempotency_key']

        # Check idempotency
        existing = Transaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return success_response(
                data=TransactionSerializer(existing).data,
                message="Transaction already processed (idempotent response).",
            )

        # Validate wallet
        try:
            wallet = Wallet.objects.select_related(
                'employee__company'
            ).get(wallet_id=data['wallet_id'])
        except Wallet.DoesNotExist:
            return error_response(message="Wallet not found.", status_code=404)

        # Employee can only withdraw from own wallet; admin can withdraw from any
        if employee.role != 'admin' and wallet.employee != employee:
            return error_response(
                message="Permission denied.",
                errors={"detail": "You can only withdraw from your own wallet."},
                status_code=403,
            )

        if wallet.employee.company != employee.company:
            return error_response(
                message="Wallet does not belong to your company.",
                status_code=403,
            )

        if not wallet.is_active:
            return error_response(
                message="Wallet is inactive.",
                errors={"wallet_id": "This wallet is currently inactive."},
                status_code=400,
            )

        amount_paisa = taka_to_paisa(data['amount'])

        result = DockerTransactionService.process_withdraw(
            wallet_id=wallet.wallet_id,
            amount_paisa=amount_paisa,
            idempotency_key=idempotency_key,
            note=data.get('note', ''),
            performed_by_employee=employee,
        )

        if result['success']:
            return success_response(
                data=result['data'],
                message="Withdrawal successful.",
                status_code=201,
            )
        return error_response(
            message=result['message'],
            errors=result.get('errors'),
            status_code=result.get('status_code', 400),
        )


class TransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        serializer = TransferSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
                status_code=400,
            )

        data = serializer.validated_data
        idempotency_key = data['idempotency_key']

        # Check idempotency
        existing = Transaction.objects.filter(
            idempotency_key=f"transfer_out_{idempotency_key}"
        ).first()
        if existing:
            return success_response(
                data=TransactionSerializer(existing).data,
                message="Transaction already processed (idempotent response).",
            )

        # Fetch wallets
        try:
            from_wallet = Wallet.objects.select_related(
                'employee__company', 'employee__user'
            ).get(wallet_id=data['from_wallet_id'])

            to_wallet = Wallet.objects.select_related(
                'employee__company', 'employee__user'
            ).get(wallet_id=data['to_wallet_id'])
        except Wallet.DoesNotExist:
            return error_response(message="Wallet not found.", status_code=404)

        # Permission: employee can only transfer from own wallet
        if employee.role != 'admin' and from_wallet.employee != employee:
            return error_response(
                message="Permission denied.",
                errors={"detail": "You can only transfer from your own wallet."},
                status_code=403,
            )

        # Same company check
        if from_wallet.employee.company != to_wallet.employee.company:
            return error_response(
                message="Cross-company transfer is not allowed.",
                errors={"detail": "You can only transfer within the same company."},
                status_code=403,
            )

        if not from_wallet.is_active or not to_wallet.is_active:
            return error_response(
                message="One or both wallets are inactive.",
                status_code=400,
            )

        amount_paisa = taka_to_paisa(data['amount'])

        result = DockerTransactionService.process_transfer(
            from_wallet_id=from_wallet.wallet_id,
            to_wallet_id=to_wallet.wallet_id,
            amount_paisa=amount_paisa,
            idempotency_key=idempotency_key,
            note=data.get('note', ''),
            performed_by_employee=employee,
        )

        if result['success']:
            return success_response(
                data=result['data'],
                message="Transfer successful.",
                status_code=201,
            )
        return error_response(
            message=result['message'],
            errors=result.get('errors'),
            status_code=result.get('status_code', 400),
        )


# ──────────────────────────────────────────────
# Transaction History Views
# ──────────────────────────────────────────────

class MyTransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        query_serializer = TransactionHistoryQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return error_response(
                message="Invalid query parameters.",
                errors=query_serializer.errors,
                status_code=400,
            )

        params = query_serializer.validated_data
        transactions = Transaction.objects.filter(
            employee=employee
        ).select_related(
            'wallet', 'related_wallet',
            'company', 'employee__user',
            'related_employee__user',
        )

        if params.get('transaction_type'):
            transactions = transactions.filter(
                transaction_type=params['transaction_type']
            )
        if params.get('status'):
            transactions = transactions.filter(status=params['status'])
        if params.get('start_date'):
            transactions = transactions.filter(
                created_at__date__gte=params['start_date']
            )
        if params.get('end_date'):
            transactions = transactions.filter(
                created_at__date__lte=params['end_date']
            )

        page = params.get('page', 1)
        page_size = params.get('page_size', 10)
        data, pagination = paginate_queryset(transactions, page, page_size)

        serializer = TransactionSerializer(data, many=True)
        return success_response(
            data={"transactions": serializer.data, "pagination": pagination}
        )


class CompanyTransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        if employee.role != 'admin':
            return error_response(
                message="Permission denied.",
                errors={"detail": "Only admin can view company transactions."},
                status_code=403,
            )

        query_serializer = TransactionHistoryQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return error_response(
                message="Invalid query parameters.",
                errors=query_serializer.errors,
                status_code=400,
            )

        params = query_serializer.validated_data
        transactions = Transaction.objects.filter(
            company=employee.company
        ).select_related(
            'wallet', 'related_wallet',
            'company', 'employee__user',
            'related_employee__user',
        )

        if params.get('transaction_type'):
            transactions = transactions.filter(
                transaction_type=params['transaction_type']
            )
        if params.get('status'):
            transactions = transactions.filter(status=params['status'])
        if params.get('start_date'):
            transactions = transactions.filter(
                created_at__date__gte=params['start_date']
            )
        if params.get('end_date'):
            transactions = transactions.filter(
                created_at__date__lte=params['end_date']
            )

        # Filter by specific employee if provided
        emp_id = request.query_params.get('employee_id')
        if emp_id:
            transactions = transactions.filter(employee__employee_id=emp_id)

        page = params.get('page', 1)
        page_size = params.get('page_size', 10)
        data, pagination = paginate_queryset(transactions, page, page_size)

        serializer = TransactionSerializer(data, many=True)
        return success_response(
            data={"transactions": serializer.data, "pagination": pagination}
        )


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        employee = get_employee_from_request(request)
        if not employee:
            return error_response(message="Employee not found.", status_code=404)

        try:
            if employee.role == 'admin':
                txn = Transaction.objects.select_related(
                    'wallet', 'related_wallet',
                    'company', 'employee__user',
                    'related_employee__user',
                ).get(transaction_id=transaction_id, company=employee.company)
            else:
                txn = Transaction.objects.select_related(
                    'wallet', 'related_wallet',
                    'company', 'employee__user',
                    'related_employee__user',
                ).get(transaction_id=transaction_id, employee=employee)
        except Transaction.DoesNotExist:
            return error_response(message="Transaction not found.", status_code=404)

        return success_response(data=TransactionSerializer(txn).data)

class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "success": True,
            "status": "ok",
            "message": "Backend is active.",
        })