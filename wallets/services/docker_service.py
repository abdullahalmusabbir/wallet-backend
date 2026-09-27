import secrets
import logging
from decimal import Decimal

from django.db import transaction as db_transaction

from ..models import Wallet, Transaction, Employee

logger = logging.getLogger(__name__)


def generate_api_key():
    return secrets.token_hex(32)


class DockerTransactionService:
    """
    Each method runs inside an isolated DB transaction (simulating
    container-level isolation). In production these could be dispatched
    to separate Docker microservice containers via HTTP/gRPC.
    The atomic() block guarantees that concurrent race conditions
    (e.g. simultaneous withdraw + transfer) are handled safely
    using select_for_update() row-level locking.
    """

    @staticmethod
    def process_deposit(
        wallet_id: str,
        amount_paisa: int,
        idempotency_key: str,
        note: str,
        performed_by_employee: Employee,
    ) -> dict:
        try:
            with db_transaction.atomic():
                # Row-level lock on wallet
                wallet = Wallet.objects.select_for_update().get(
                    wallet_id=wallet_id
                )

                if not wallet.is_active:
                    return {
                        "success": False,
                        "message": "Wallet is inactive.",
                        "status_code": 400,
                    }

                if amount_paisa <= 0:
                    return {
                        "success": False,
                        "message": "Amount must be greater than zero.",
                        "status_code": 400,
                    }

                balance_before = wallet.balance
                wallet.balance += amount_paisa
                wallet.save()

                api_key = generate_api_key()

                txn = Transaction.objects.create(
                    idempotency_key=idempotency_key,
                    api_key=api_key,
                    wallet=wallet,
                    company=wallet.employee.company,
                    employee=wallet.employee,
                    transaction_type='deposit',
                    amount=amount_paisa,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    status='success',
                    note=note,
                )

                from ..serializers import TransactionSerializer
                return {
                    "success": True,
                    "data": TransactionSerializer(txn).data,
                    "message": "Deposit successful.",
                }

        except Wallet.DoesNotExist:
            logger.error(f"[DEPOSIT] Wallet not found: {wallet_id}")
            return {
                "success": False,
                "message": "Wallet not found.",
                "status_code": 404,
            }
        except Exception as e:
            logger.error(f"[DEPOSIT] Unexpected error: {str(e)}")
            return {
                "success": False,
                "message": "Deposit failed due to an internal error.",
                "errors": {"detail": str(e)},
                "status_code": 500,
            }

    @staticmethod
    def process_withdraw(
        wallet_id: str,
        amount_paisa: int,
        idempotency_key: str,
        note: str,
        performed_by_employee: Employee,
    ) -> dict:
        try:
            with db_transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(
                    wallet_id=wallet_id
                )

                if not wallet.is_active:
                    return {
                        "success": False,
                        "message": "Wallet is inactive.",
                        "status_code": 400,
                    }

                if amount_paisa <= 0:
                    return {
                        "success": False,
                        "message": "Amount must be greater than zero.",
                        "status_code": 400,
                    }

                # Insufficient balance check
                if wallet.balance < amount_paisa:
                    insufficient_taka = Decimal(wallet.balance) / 100
                    needed_taka = Decimal(amount_paisa) / 100
                    return {
                        "success": False,
                        "message": (
                            f"Insufficient balance. "
                            f"Available: ৳{insufficient_taka:.2f}, "
                            f"Requested: ৳{needed_taka:.2f}"
                        ),
                        "errors": {
                            "balance": f"Available balance is ৳{insufficient_taka:.2f}"
                        },
                        "status_code": 400,
                    }

                balance_before = wallet.balance
                wallet.balance -= amount_paisa
                wallet.save()

                api_key = generate_api_key()

                txn = Transaction.objects.create(
                    idempotency_key=idempotency_key,
                    api_key=api_key,
                    wallet=wallet,
                    company=wallet.employee.company,
                    employee=wallet.employee,
                    transaction_type='withdraw',
                    amount=amount_paisa,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    status='success',
                    note=note,
                )

                from ..serializers import TransactionSerializer
                return {
                    "success": True,
                    "data": TransactionSerializer(txn).data,
                    "message": "Withdrawal successful.",
                }

        except Wallet.DoesNotExist:
            logger.error(f"[WITHDRAW] Wallet not found: {wallet_id}")
            return {
                "success": False,
                "message": "Wallet not found.",
                "status_code": 404,
            }
        except Exception as e:
            logger.error(f"[WITHDRAW] Unexpected error: {str(e)}")
            return {
                "success": False,
                "message": "Withdrawal failed due to an internal error.",
                "errors": {"detail": str(e)},
                "status_code": 500,
            }

    @staticmethod
    def process_transfer(
        from_wallet_id: str,
        to_wallet_id: str,
        amount_paisa: int,
        idempotency_key: str,
        note: str,
        performed_by_employee: Employee,
    ) -> dict:
        try:
            with db_transaction.atomic():
                # Lock both wallets in consistent order to prevent deadlock
                wallet_ids = sorted([from_wallet_id, to_wallet_id])
                wallets = {
                    w.wallet_id: w
                    for w in Wallet.objects.select_for_update().filter(
                        wallet_id__in=wallet_ids
                    )
                }

                from_wallet = wallets.get(from_wallet_id)
                to_wallet = wallets.get(to_wallet_id)

                if not from_wallet or not to_wallet:
                    return {
                        "success": False,
                        "message": "One or both wallets not found.",
                        "status_code": 404,
                    }

                if not from_wallet.is_active or not to_wallet.is_active:
                    return {
                        "success": False,
                        "message": "One or both wallets are inactive.",
                        "status_code": 400,
                    }

                if amount_paisa <= 0:
                    return {
                        "success": False,
                        "message": "Amount must be greater than zero.",
                        "status_code": 400,
                    }

                # Insufficient balance
                if from_wallet.balance < amount_paisa:
                    available_taka = Decimal(from_wallet.balance) / 100
                    needed_taka = Decimal(amount_paisa) / 100
                    return {
                        "success": False,
                        "message": (
                            f"Insufficient balance. "
                            f"Available: ৳{available_taka:.2f}, "
                            f"Requested: ৳{needed_taka:.2f}"
                        ),
                        "errors": {
                            "balance": f"Available balance is ৳{available_taka:.2f}"
                        },
                        "status_code": 400,
                    }

                # Debit sender
                sender_balance_before = from_wallet.balance
                from_wallet.balance -= amount_paisa
                from_wallet.save()

                # Credit receiver
                receiver_balance_before = to_wallet.balance
                to_wallet.balance += amount_paisa
                to_wallet.save()

                api_key = generate_api_key()

                # Transfer out transaction (sender)
                txn_out = Transaction.objects.create(
                    idempotency_key=f"transfer_out_{idempotency_key}",
                    api_key=api_key,
                    wallet=from_wallet,
                    company=from_wallet.employee.company,
                    employee=from_wallet.employee,
                    related_wallet=to_wallet,
                    related_employee=to_wallet.employee,
                    transaction_type='transfer_out',
                    amount=amount_paisa,
                    balance_before=sender_balance_before,
                    balance_after=from_wallet.balance,
                    status='success',
                    note=note,
                )

                # Transfer in transaction (receiver)
                txn_in = Transaction.objects.create(
                    idempotency_key=f"transfer_in_{idempotency_key}",
                    api_key=generate_api_key(),
                    wallet=to_wallet,
                    company=to_wallet.employee.company,
                    employee=to_wallet.employee,
                    related_wallet=from_wallet,
                    related_employee=from_wallet.employee,
                    transaction_type='transfer_in',
                    amount=amount_paisa,
                    balance_before=receiver_balance_before,
                    balance_after=to_wallet.balance,
                    status='success',
                    note=note,
                )

                from ..serializers import TransactionSerializer
                return {
                    "success": True,
                    "data": {
                        "transfer_out": TransactionSerializer(txn_out).data,
                        "transfer_in": TransactionSerializer(txn_in).data,
                    },
                    "message": "Transfer successful.",
                }

        except Exception as e:
            logger.error(f"[TRANSFER] Unexpected error: {str(e)}")
            return {
                "success": False,
                "message": "Transfer failed due to an internal error.",
                "errors": {"detail": str(e)},
                "status_code": 500,
            }