# import logging
# import uuid
# from decimal import Decimal
# from django.db import transaction as db_transaction
# from django.utils import timezone

# from ..models import Wallet, Transaction, ExternalTransaction, BankAccount
# from .reconciliation_service import ReconciliationService

# logger = logging.getLogger(__name__)


# class BankTransferService:
#     """
#     Handles real-time bank transfers via payment gateway integration.
#     """

#     @staticmethod
#     def initiate_withdrawal(
#         wallet_id: str,
#         amount_paisa: int,
#         bank_account_id: int,
#         idempotency_key: str,
#         note: str,
#         performed_by_employee,
#     ) -> dict:
#         """
#         Step 1: Debit internal wallet, create pending external transaction.
#         Step 2: Dispatch async task to gateway.
#         """
#         try:
#             with db_transaction.atomic():
#                 # 1. Lock wallet
#                 wallet = Wallet.objects.select_for_update().get(wallet_id=wallet_id)
                
#                 if not wallet.is_active:
#                     return {"success": False, "message": "Wallet inactive.", "status_code": 400}

#                 if wallet.balance < amount_paisa:
#                     return {
#                         "success": False,
#                         "message": f"Insufficient balance.",
#                         "errors": {"balance": f"Available: ৳{wallet.balance / 100:.2f}"},
#                         "status_code": 400,
#                     }

#                 # 2. Verify bank account belongs to same employee/company
#                 bank_account = BankAccount.objects.select_related('employee').get(
#                     id=bank_account_id,
#                     employee=wallet.employee,
#                     status='active'
#                 )

#                 # 3. Debit wallet immediately (optimistic - may be reversed if bank fails)
#                 balance_before = wallet.balance
#                 wallet.balance -= amount_paisa
#                 wallet.save()

#                 # 4. Create internal transaction (pending settlement)
#                 api_key = secrets.token_hex(32)
#                 txn = Transaction.objects.create(
#                     idempotency_key=idempotency_key,
#                     api_key=api_key,
#                     wallet=wallet,
#                     company=wallet.employee.company,
#                     employee=wallet.employee,
#                     transaction_type='withdraw',
#                     amount=amount_paisa,
#                     balance_before=balance_before,
#                     balance_after=wallet.balance,
#                     status='pending_settlement',
#                     note=note,
#                 )

#                 # 5. Create external transaction record
#                 external_txn_id = f"EXT-{uuid.uuid4().hex[:12].upper()}"
#                 external_txn = ExternalTransaction.objects.create(
#                     transaction=txn,
#                     bank_account=bank_account,
#                     external_transaction_id=external_txn_id,
#                     external_status='initiated',
#                     external_amount=amount_paisa,
#                 )

#                 # 6. Dispatch async task (Celery)
#                 from ..tasks import process_bank_withdrawal_task
#                 process_bank_withdrawal_task.delay(
#                     external_transaction_id=external_txn.id
#                 )

#                 return {
#                     "success": True,
#                     "data": {
#                         "transaction_id": str(txn.transaction_id),
#                         "external_transaction_id": external_txn_id,
#                         "status": "pending_settlement",
#                         "estimated_completion": "Within 24 hours",
#                     },
#                     "message": "Withdrawal initiated. Funds will be transferred to your bank.",
#                 }

#         except Wallet.DoesNotExist:
#             return {"success": False, "message": "Wallet not found.", "status_code": 404}
#         except BankAccount.DoesNotExist:
#             return {"success": False, "message": "Bank account not found or inactive.", "status_code": 400}
#         except Exception as e:
#             logger.error(f"[WITHDRAWAL] Error: {str(e)}", exc_info=True)
#             return {"success": False, "message": "Withdrawal failed.", "errors": {"detail": str(e)}, "status_code": 500}

#     @staticmethod
#     def handle_bank_callback(external_transaction_id: str, status: str, gateway_response: dict):
#         """
#         Webhook handler: Update transaction status based on bank response.
#         Called by the payment gateway callback endpoint.
#         """
#         try:
#             with db_transaction.atomic():
#                 ext_txn = ExternalTransaction.objects.select_for_update().get(
#                     external_transaction_id=external_transaction_id
#                 )
#                 txn = ext_txn.transaction

#                 # Idempotency check
#                 if txn.status in ['success', 'failed', 'cancelled', 'reversed']:
#                     logger.warning(f"Webhook already processed: {external_transaction_id}")
#                     return

#                 ext_txn.external_status = status
#                 ext_txn.gateway_response = gateway_response

#                 if status == 'completed':
#                     ext_txn.completed_at = timezone.now()
#                     txn.status = 'success'
#                     txn.save()
#                     ext_txn.save()
                    
#                     # Trigger reconciliation
#                     ReconciliationService.log_reconciliation(txn, is_resolved=True)

#                 elif status in ['failed', 'cancelled', 'reversed']:
#                     ext_txn.failed_at = timezone.now()
#                     ext_txn.error_message = gateway_response.get('error_message', 'Unknown error')
#                     ext_txn.save()

#                     # REVERSE the wallet debit
#                     wallet = txn.wallet
#                     wallet.balance += txn.amount
#                     wallet.save()

#                     txn.status = 'failed'
#                     txn.save()

#                     # Log reconciliation failure
#                     ReconciliationService.log_reconciliation(txn, is_resolved=False)

#         except ExternalTransaction.DoesNotExist:
#             logger.error(f"Webhook: External transaction not found: {external_transaction_id}")
#         except Exception as e:
#             logger.error(f"Webhook error: {str(e)}", exc_info=True)