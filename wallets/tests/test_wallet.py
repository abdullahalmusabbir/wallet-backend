import pytest


class TestWalletDetailView:

    @pytest.mark.django_db
    def test_get_own_wallet(self, auth_client, employee_wallet):
        response = auth_client.get('/wallet/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['wallet_id'] == employee_wallet.wallet_id

    @pytest.mark.django_db
    def test_get_wallet_unauthenticated(self, api_client):
        response = api_client.get('/wallet/')
        assert response.status_code == 401


class TestWalletByIdView:

    @pytest.mark.django_db
    def test_get_wallet_by_id_as_admin(self, admin_client, admin_employee, employee_wallet):
        response = admin_client.get(f'/wallet/{employee_wallet.wallet_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['wallet_id'] == employee_wallet.wallet_id

    @pytest.mark.django_db
    def test_get_wallet_by_id_as_employee_forbidden(self, auth_client, employee_wallet):
        response = auth_client.get(f'/wallet/{employee_wallet.wallet_id}/')
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_get_wallet_by_id_not_found(self, admin_client):
        response = admin_client.get('/wallet/NONEXISTENT/')
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_wallet_from_other_company_as_admin(self, admin_client, second_employee):
        response = admin_client.get(f'/wallet/{second_employee.wallet.wallet_id}/')
        assert response.status_code == 404