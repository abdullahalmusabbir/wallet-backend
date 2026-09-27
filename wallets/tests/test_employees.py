import uuid
import pytest
from django.contrib.auth.models import User
from wallets.models import Employee, Wallet


class TestEmployeeListCreateView:

    @pytest.mark.django_db
    def test_list_employees_as_admin(self, admin_client, admin_employee, company):
        User.objects.create_user(username='emp2', password='pass123')
        Employee.objects.create(
            user=User.objects.get(username='emp2'),
            company=company,
            employee_id='EMP002',
            role='employee',
        )

        response = admin_client.get('/employees/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'employees' in response.data['data']
        assert 'pagination' in response.data['data']

    @pytest.mark.django_db
    def test_list_employees_as_regular_employee(self, auth_client, employee):
        response = auth_client.get('/employees/')
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_create_employee_as_admin(self, admin_client, admin_employee, company):
        payload = {
            'username': 'newemp',
            'email': 'newemp@example.com',
            'password': 'emppass123',
            'first_name': 'New',
            'last_name': 'Emp',
            'role': 'employee',
            'phone': '01744444444',
        }
        response = admin_client.post('/employees/', payload, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert response.data['data']['role'] == 'employee'

    @pytest.mark.django_db
    def test_create_employee_as_non_admin_forbidden(self, auth_client, employee, company):
        payload = {
            'username': 'newemp',
            'email': 'newemp@example.com',
            'password': 'emppass123',
        }
        response = auth_client.post('/employees/', payload, format='json')
        assert response.status_code == 403


class TestEmployeeDetailView:

    @pytest.mark.django_db
    def test_get_own_profile_as_employee(self, auth_client, employee):
        response = auth_client.get(f'/employees/{employee.employee_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['employee_id'] == employee.employee_id

    @pytest.mark.django_db
    def test_get_other_employee_as_non_admin_forbidden(self, auth_client, employee, company):
        user2 = User.objects.create_user(username='other', password='pass123')
        emp2 = Employee.objects.create(
            user=user2, company=company, employee_id='EMPOTH', role='employee'
        )
        response = auth_client.get(f'/employees/{emp2.employee_id}/')
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_get_other_employee_as_admin(self, admin_client, admin_employee, company):
        response = admin_client.get(f'/employees/{admin_employee.employee_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True

    @pytest.mark.django_db
    def test_update_employee_as_admin(self, admin_client, admin_employee):
        payload = {'phone': '01855555555', 'role': 'employee'}
        response = admin_client.put(f'/employees/{admin_employee.employee_id}/', payload, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['phone'] == '01855555555'

    @pytest.mark.django_db
    def test_delete_employee_as_admin(self, admin_client, admin_employee, company):
        target_user = User.objects.create_user(username='target', password='pass123')
        target_emp = Employee.objects.create(
            user=target_user, company=company, employee_id='EMPTGT', role='employee'
        )
        Wallet.objects.create(
            wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
            employee=target_emp,
        )

        response = admin_client.delete(f'/employees/{target_emp.employee_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True

        target_emp.refresh_from_db()
        target_user.refresh_from_db()
        assert target_emp.is_active is False
        assert target_user.is_active is False

    @pytest.mark.django_db
    def test_delete_self_as_admin_forbidden(self, admin_client, admin_employee):
        response = admin_client.delete(f'/employees/{admin_employee.employee_id}/')
        assert response.status_code == 400
        assert 'Cannot deactivate yourself' in response.data['message']