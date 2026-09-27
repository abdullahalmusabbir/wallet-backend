import pytest


@pytest.mark.django_db
def test_health_check(api_client):
    response = api_client.get('/health/')
    assert response.status_code == 200
    assert response.data['success'] is True
    assert response.data['status'] == 'ok'