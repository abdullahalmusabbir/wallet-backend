import pytest


class TestCompanyDetailView:

    @pytest.mark.django_db
    def test_get_company_authenticated(self, auth_client, employee, company):
        response = auth_client.get('/company/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['name'] == company.name

    @pytest.mark.django_db
    def test_get_company_unauthenticated(self, api_client):
        response = api_client.get('/company/')
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_update_company_as_admin(self, admin_client, admin_employee, company):
        payload = {'name': 'Updated Company', 'phone': '01800000000'}
        response = admin_client.put('/company/', payload, format='json')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['name'] == 'Updated Company'

    @pytest.mark.django_db
    def test_update_company_as_employee_forbidden(self, auth_client, employee, company):
        payload = {'name': 'Hacked Name'}
        response = auth_client.put('/company/', payload, format='json')
        assert response.status_code == 403
        assert response.data['success'] is False