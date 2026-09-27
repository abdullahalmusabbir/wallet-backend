import uuid
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from wallets.models import Transaction, Wallet, Employee


def _deposit_payload(wallet_id, amount=1000.00, note='Test deposit', idempotency_key=None):
    if idempotency_key is None:
        idempotency_key = f'dep-{wallet_id}-{amount}'
    return {
        'wallet_id': wallet_id,
        'amount': str(amount),
        'note': note,
        'idempotency_key': idempotency_key,
    }


def _withdraw_payload(wallet_id, amount=500.00, note='Test withdraw', idempotency_key=None):
    if idempotency_key is None:
        idempotency_key = f'wd-{wallet_id}-{amount}'
    return {
        'wallet_id': wallet_id,
        'amount': str(amount),
        'note': note,
        'idempotency_key': idempotency_key,
    }


def _transfer_payload(from_wallet_id, to_wallet_id, amount=200.00, note='Test transfer', idempotency_key=None):
    if idempotency_key is None:
        idempotency_key = f'trf-{from_wallet_id}-{to_wallet_id}-{amount}'
    return {
        'from_wallet_id': from_wallet_id,
        'to_wallet_id': to_wallet_id,
        'amount': str(amount),
        'note': note,
        'idempotency_key': idempotency_key,
    }


class TestDepositView:

    @pytest.mark.django_db
    def test_deposit_success(self, admin_client, admin_employee, employee_wallet):
        payload = _deposit_payload(employee_wallet.wallet_id, amount=1000.00)
        response = admin_client.post('/transactions/deposit/', payload, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert response.data['data']['transaction_type'] == 'deposit'
        assert response.data['data']['amount'] == 100000

        employee_wallet.refresh_from_db()
        assert employee_wallet.balance == 100000

    @pytest.mark.django_db
    def test_deposit_employee_forbidden(self, auth_client, employee_wallet):
        payload = _deposit_payload(employee_wallet.wallet_id, amount=1000.00)
        response = auth_client.post('/transactions/deposit/', payload, format='json')
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_deposit_invalid_wallet(self, admin_client):
        payload = _deposit_payload('WLFAKE', amount=1000.00)
        response = admin_client.post('/transactions/deposit/', payload, format='json')
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_deposit_idempotent(self, admin_client, admin_employee, employee_wallet):
        payload = _deposit_payload(employee_wallet.wallet_id, amount=1000.00, idempotency_key='idem-1')
        response1 = admin_client.post('/transactions/deposit/', payload, format='json')
        response2 = admin_client.post('/transactions/deposit/', payload, format='json')
        assert response1.status_code == 201
        assert response2.status_code == 200
        assert response1.data['data']['idempotency_key'] == response2.data['data']['idempotency_key']

    @pytest.mark.django_db
    def test_deposit_invalid_amount(self, admin_client, admin_employee, employee_wallet):
        payload = _deposit_payload(employee_wallet.wallet_id, amount=-100)
        response = admin_client.post('/transactions/deposit/', payload, format='json')
        assert response.status_code == 400


class TestWithdrawView:

    @pytest.mark.django_db
    def test_withdraw_success(self, admin_client, admin_employee, employee_wallet):
        employee_wallet.balance = 500000
        employee_wallet.save()

        payload = _withdraw_payload(employee_wallet.wallet_id, amount=1000.00)
        response = admin_client.post('/transactions/withdraw/', payload, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert response.data['data']['transaction_type'] == 'withdraw'

        employee_wallet.refresh_from_db()
        assert employee_wallet.balance == 400000

    @pytest.mark.django_db
    def test_withdraw_own_wallet_as_employee(self, auth_client, employee_wallet):
        employee_wallet.balance = 500000
        employee_wallet.save()

        payload = _withdraw_payload(employee_wallet.wallet_id, amount=1000.00)
        response = auth_client.post('/transactions/withdraw/', payload, format='json')
        assert response.status_code == 201

    @pytest.mark.django_db
    def test_withdraw_other_wallet_as_employee_forbidden(self, auth_client, employee, second_employee):
        payload = _withdraw_payload(second_employee.wallet.wallet_id, amount=1000.00)
        response = auth_client.post('/transactions/withdraw/', payload, format='json')
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_withdraw_insufficient_balance(self, admin_client, admin_employee, employee_wallet):
        employee_wallet.balance = 1000
        employee_wallet.save()

        payload = _withdraw_payload(employee_wallet.wallet_id, amount=5000.00)
        response = admin_client.post('/transactions/withdraw/', payload, format='json')
        assert response.status_code == 400
        assert 'Insufficient balance' in response.data['message']

    @pytest.mark.django_db
    def test_withdraw_inactive_wallet(self, admin_client, admin_employee, employee_wallet):
        employee_wallet.is_active = False
        employee_wallet.save()

        payload = _withdraw_payload(employee_wallet.wallet_id, amount=1000.00)
        response = admin_client.post('/transactions/withdraw/', payload, format='json')
        assert response.status_code == 400
        assert 'wallet_id' in response.data.get('errors', {})


class TestTransferView:

    @pytest.mark.django_db
    def test_transfer_success(self, admin_client, admin_employee, employee_wallet, company):
        employee_wallet.balance = 1000000
        employee_wallet.save()

        user2 = User.objects.create_user(username='trans_target', password='pass123')
        target_emp = Employee.objects.create(
            user=user2, company=company, employee_id='EMPTRANS', role='employee'
        )
        Wallet.objects.create(
            wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
            employee=target_emp,
            balance=500000,
        )

        payload = _transfer_payload(
            employee_wallet.wallet_id,
            target_emp.wallet.wallet_id,
            amount=500.00,
        )
        response = admin_client.post('/transactions/transfer/', payload, format='json')
        assert response.status_code == 201
        assert response.data['success'] is True
        assert 'transfer_out' in response.data['data']
        assert 'transfer_in' in response.data['data']

        employee_wallet.refresh_from_db()
        target_emp.wallet.refresh_from_db()
        assert employee_wallet.balance == 950000
        assert target_emp.wallet.balance == 550000

    @pytest.mark.django_db
    def test_transfer_own_wallet_as_employee(self, auth_client, employee_wallet, company):
        employee_wallet.balance = 1000000
        employee_wallet.save()

        user2 = User.objects.create_user(username='emp2', password='pass123')
        emp2 = Employee.objects.create(
            user=user2, company=company, employee_id='EMP002', role='employee'
        )
        Wallet.objects.create(
            wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
            employee=emp2,
        )

        payload = _transfer_payload(
            employee_wallet.wallet_id,
            emp2.wallet.wallet_id,
            amount=1000.00,
        )
        response = auth_client.post('/transactions/transfer/', payload, format='json')
        assert response.status_code == 201

    @pytest.mark.django_db
    def test_transfer_cross_company_forbidden(self, admin_client, admin_employee, employee_wallet, second_employee):
        payload = _transfer_payload(
            employee_wallet.wallet_id,
            second_employee.wallet.wallet_id,
            amount=1000.00,
        )
        response = admin_client.post('/transactions/transfer/', payload, format='json')
        assert response.status_code == 400
        errors = str(response.data.get('errors', {})).lower()
        assert 'same company' in errors or 'within the same company' in errors

    @pytest.mark.django_db
    def test_transfer_same_wallet_forbidden(self, admin_client, admin_employee, employee_wallet):
        payload = _transfer_payload(
            employee_wallet.wallet_id,
            employee_wallet.wallet_id,
            amount=1000.00,
        )
        response = admin_client.post('/transactions/transfer/', payload, format='json')
        assert response.status_code == 400
        errors = str(response.data.get('errors', {})).lower()
        assert 'same' in errors

    @pytest.mark.django_db
    def test_transfer_insufficient_balance(self, admin_client, admin_employee, employee_wallet, company):
        employee_wallet.balance = 10000
        employee_wallet.save()

        user2 = User.objects.create_user(username='insuff_target', password='pass123')
        target_emp = Employee.objects.create(
            user=user2, company=company, employee_id='EMPINS', role='employee'
        )
        Wallet.objects.create(
            wallet_id='WL' + uuid.uuid4().hex[:4].upper(),
            employee=target_emp,
            balance=0,
        )

        payload = _transfer_payload(
            employee_wallet.wallet_id,
            target_emp.wallet.wallet_id,
            amount=5000.00,
        )
        response = admin_client.post('/transactions/transfer/', payload, format='json')
        assert response.status_code == 400
        assert 'Insufficient balance' in response.data['message']


class TestMyTransactionHistoryView:

    @pytest.mark.django_db
    def test_get_my_transactions(self, auth_client, employee):
        wallet = employee.wallet
        wallet.balance = 100000
        wallet.save()

        Transaction.objects.create(
            idempotency_key='hist-test-1',
            api_key='key1',
            wallet=wallet,
            company=employee.company,
            employee=employee,
            transaction_type='deposit',
            amount=100000,
            balance_before=0,
            balance_after=100000,
            status='success',
        )

        response = auth_client.get('/transactions/history/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert 'transactions' in response.data['data']
        assert len(response.data['data']['transactions']) >= 1

    @pytest.mark.django_db
    def test_get_my_transactions_with_filters(self, auth_client, employee):
        wallet = employee.wallet
        wallet.balance = 200000
        wallet.save()

        Transaction.objects.create(
            idempotency_key='hist-filter-1',
            api_key='key2',
            wallet=wallet,
            company=employee.company,
            employee=employee,
            transaction_type='deposit',
            amount=200000,
            balance_before=0,
            balance_after=200000,
            status='success',
        )

        response = auth_client.get('/transactions/history/?transaction_type=deposit&status=success')
        assert response.status_code == 200
        assert response.data['success'] is True


class TestCompanyTransactionHistoryView:

    @pytest.mark.django_db
    def test_get_company_transactions_as_admin(self, admin_client, company, admin_employee):
        wallet = admin_employee.wallet
        wallet.balance = 300000
        wallet.save()

        Transaction.objects.create(
            idempotency_key='comp-hist-1',
            api_key='key3',
            wallet=wallet,
            company=company,
            employee=admin_employee,
            transaction_type='deposit',
            amount=300000,
            balance_before=0,
            balance_after=300000,
            status='success',
        )

        response = admin_client.get('/transactions/company/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert len(response.data['data']['transactions']) >= 1

    @pytest.mark.django_db
    def test_get_company_transactions_as_employee_forbidden(self, auth_client, employee):
        response = auth_client.get('/transactions/company/')
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_get_company_transactions_filter_by_employee(self, admin_client, company, admin_employee):
        response = admin_client.get(f'/transactions/company/?employee_id={admin_employee.employee_id}')
        assert response.status_code == 200


class TestTransactionDetailView:

    @pytest.mark.django_db
    def test_get_transaction_detail_as_admin(self, admin_client, admin_employee, company):
        wallet = admin_employee.wallet
        wallet.balance = 400000
        wallet.save()

        txn = Transaction.objects.create(
            idempotency_key='detail-test-1',
            api_key='key4',
            wallet=wallet,
            company=company,
            employee=admin_employee,
            transaction_type='deposit',
            amount=400000,
            balance_before=0,
            balance_after=400000,
            status='success',
        )

        response = admin_client.get(f'/transactions/{txn.transaction_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['transaction_id'] == str(txn.transaction_id)

    @pytest.mark.django_db
    def test_get_transaction_detail_as_employee(self, auth_client, employee):
        wallet = employee.wallet
        wallet.balance = 500000
        wallet.save()

        txn = Transaction.objects.create(
            idempotency_key='detail-test-2',
            api_key='key5',
            wallet=wallet,
            company=employee.company,
            employee=employee,
            transaction_type='deposit',
            amount=500000,
            balance_before=0,
            balance_after=500000,
            status='success',
        )

        response = auth_client.get(f'/transactions/{txn.transaction_id}/')
        assert response.status_code == 200
        assert response.data['success'] is True

    @pytest.mark.django_db
    def test_get_transaction_detail_not_found(self, admin_client):
        fake_uuid = uuid.uuid4()
        response = admin_client.get(f'/transactions/{fake_uuid}/')
        assert response.status_code == 404