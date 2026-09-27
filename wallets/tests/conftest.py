import os
import uuid
import pytest
from decimal import Decimal
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import Company, Employee, Wallet, Transaction


# ──────────────────────────────────────────────
# Override DB/Cache BEFORE Django initializes
# ──────────────────────────────────────────────
def pytest_configure():
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    settings.CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-cache',
        }
    }


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='01944145085',
        email='emon@gmail.com',
        password='Emon1996$',
        first_name='Emon',
        last_name='Sheikh',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='01944145084',
        email='aabdullahmusabbir703@gmail.com',
        password='Shuvo1996$',
        first_name='Shuvo',
        last_name='Sheikh',
    )


@pytest.fixture
def company(db):
    return Company.objects.create(
        name='Test Company',
        email='company@example.com',
        phone='01700000000',
        address='Dhaka, Bangladesh',
    )


@pytest.fixture
def employee(db, user, company):
    emp = Employee.objects.create(
        user=user,
        company=company,
        employee_id='EMP001',
        role='employee',
        phone='01711111111',
    )
    Wallet.objects.create(
        wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
        employee=emp,
        balance=0,
    )
    return emp


@pytest.fixture
def admin_employee(db, admin_user, company):
    emp = Employee.objects.create(
        user=admin_user,
        company=company,
        employee_id='EMPADMIN',
        role='admin',
        phone='01722222222',
    )
    Wallet.objects.create(
        wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
        employee=emp,
        balance=0,
    )
    return emp


@pytest.fixture
def employee_wallet(employee):
    return employee.wallet


@pytest.fixture
def admin_wallet(admin_employee):
    return admin_employee.wallet


def _get_access_token(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


@pytest.fixture
def access_token(user):
    return _get_access_token(user)


@pytest.fixture
def admin_access_token(admin_user):
    return _get_access_token(admin_user)


@pytest.fixture
def auth_client(api_client, access_token):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_access_token):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_access_token}')
    return api_client


@pytest.fixture
def second_company(db):
    return Company.objects.create(
        name='Second Company',
        email='second@example.com',
        phone='01733333333',
    )


@pytest.fixture
def second_employee(db, second_company):
    user = User.objects.create_user(
        username='seconduser',
        email='second@example.com',
        password='secondpass123',
    )
    emp = Employee.objects.create(
        user=user,
        company=second_company,
        employee_id='EMPSEC',
        role='employee',
    )
    Wallet.objects.create(
        wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
        employee=emp,
        balance=500000,  # 5000 taka
    )
    return emp

# ──────────────────────────────────────────────
# Close DB connections after test session
# Fixes: OperationalError: database "test_postgres" is being accessed by other users
# ──────────────────────────────────────────────
def pytest_sessionfinish(session, exitstatus):
    from django.db import connections
    for conn in connections.all():
        conn.close()