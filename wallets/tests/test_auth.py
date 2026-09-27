import uuid
import pytest
from django.contrib.auth.models import User
from wallets.models import Company, Employee, Wallet
from rest_framework_simplejwt.tokens import RefreshToken


class TestRegisterView:

    @pytest.mark.django_db
    def test_register_success(self, api_client):
        payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'strongpass123',
            'company_name': 'New Corp',
            'company_email': 'newcorp@example.com',
            'first_name': 'New',
            'last_name': 'User',
        }
        response = api_client.post('/auth/register/', payload, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert 'tokens' in response.data['data']
        assert response.data['data']['user']['username'] == 'newuser'
        assert response.data['data']['employee']['role'] == 'admin'

    @pytest.mark.django_db
    def test_register_missing_fields(self, api_client):
        response = api_client.post('/auth/register/', {}, format='json')
        assert response.status_code == 400
        assert response.data['success'] is False

    @pytest.mark.django_db
    def test_register_duplicate_username(self, api_client, user):
        payload = {
            'username': user.username,
            'email': 'another@example.com',
            'password': 'strongpass123',
            'company_name': 'Another Corp',
            'company_email': 'anothercorp@example.com',
        }
        response = api_client.post('/auth/register/', payload, format='json')
        assert response.status_code == 400
        assert 'username' in response.data['errors']

    @pytest.mark.django_db
    def test_register_duplicate_company_email(self, api_client, company):
        payload = {
            'username': 'newuser2',
            'email': 'new2@example.com',
            'password': 'strongpass123',
            'company_name': 'Another Company',
            'company_email': company.email,
        }
        response = api_client.post('/auth/register/', payload, format='json')
        assert response.status_code == 400
        assert 'company_email' in response.data['errors']


class TestLoginView:

    @pytest.mark.django_db
    def test_login_success(self, api_client, user, employee):
        payload = {
            'username': user.username,
            'password': 'Emon1996$',
        }
        response = api_client.post('/auth/login/', payload, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'tokens' in response.data['data']
        assert response.data['data']['employee']['role'] == 'employee'

    @pytest.mark.django_db
    def test_login_invalid_credentials(self, api_client):
        payload = {
            'username': 'nonexistent',
            'password': 'wrongpass',
        }
        response = api_client.post('/auth/login/', payload, format='json')
        assert response.status_code == 401
        assert response.data['success'] is False

    @pytest.mark.django_db
    def test_login_missing_fields(self, api_client):
        response = api_client.post('/auth/login/', {}, format='json')
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_login_inactive_employee(self, api_client, user, company):
        emp = Employee.objects.create(
            user=user,
            company=company,
            employee_id='EMPINACTIVE',
            role='employee',
            is_active=False,
        )
        Wallet.objects.create(
            wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
            employee=emp,
        )
        payload = {
            'username': user.username,
            'password': 'Emon1996$',
        }
        response = api_client.post('/auth/login/', payload, format='json')
        assert response.status_code == 403
        assert response.data['success'] is False


class TestLogoutView:

    @pytest.mark.django_db
    def test_logout_success(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        payload = {'refresh': str(refresh)}
        response = auth_client.post('/auth/logout/', payload, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True

    @pytest.mark.django_db
    def test_logout_missing_refresh(self, auth_client):
        response = auth_client.post('/auth/logout/', {}, format='json')
        assert response.status_code == 400
        assert 'refresh' in response.data['errors']

    @pytest.mark.django_db
    def test_logout_invalid_token(self, auth_client):
        payload = {'refresh': 'invalid-token'}
        response = auth_client.post('/auth/logout/', payload, format='json')
        assert response.status_code == 400


class TestForgotPasswordView:

    @pytest.mark.django_db
    def test_forgot_password_existing_email(self, api_client, user, monkeypatch):
        monkeypatch.setattr('wallet.views.send_mail', lambda *a, **kw: 1)
        response = api_client.post('/auth/forgot-password/', {'email': user.email}, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True

    @pytest.mark.django_db
    def test_forgot_password_nonexistent_email(self, api_client):
        response = api_client.post('/auth/forgot-password/', {'email': 'noone@example.com'}, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True

    @pytest.mark.django_db
    def test_forgot_password_missing_email(self, api_client):
        response = api_client.post('/auth/forgot-password/', {}, format='json')
        assert response.status_code == 400
        assert 'email' in response.data['errors']


class TestResetPasswordView:

    @pytest.mark.django_db
    def test_reset_password_success(self, api_client, user, monkeypatch):
        from django.core.cache import cache
        token = 'valid-reset-token-123'
        cache.set(f'password_reset_{token}', user.id, timeout=3600)

        payload = {
            'token': token,
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }
        response = api_client.post('/auth/reset-password/', payload, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True

        user.refresh_from_db()
        assert user.check_password('newpass123') is True

    @pytest.mark.django_db
    def test_reset_password_mismatch(self, api_client):
        payload = {
            'token': 'sometoken',
            'new_password': 'newpass123',
            'confirm_password': 'differentpass',
        }
        response = api_client.post('/auth/reset-password/', payload, format='json')
        assert response.status_code == 400
        assert 'Passwords do not match' in response.data['message']

    @pytest.mark.django_db
    def test_reset_password_invalid_token(self, api_client):
        payload = {
            'token': 'invalid-token',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }
        response = api_client.post('/auth/reset-password/', payload, format='json')
        assert response.status_code == 400
        assert 'invalid' in response.data['message'].lower()