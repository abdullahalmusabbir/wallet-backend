# from celery import shared_task
# import logging
# from decimal import Decimal
# from django.utils import timezone

# from .services.bank_service import BankTransferService

# logger = logging.getLogger(__name__)


# @shared_task(bind=True, max_retries=3, default_retry_delay=60)
# def process_bank_withdrawal_task(self, external_transaction_id: int):
#     """
#     Async task: Call payment gateway API to execute the bank transfer.
#     Retries on transient failures.
#     """
#     from .models import ExternalTransaction
    
#     try:
#         ext_txn = ExternalTransaction.objects.get(id=external_transaction_id)
        
#         # Call payment gateway API
#         result = PaymentGatewayClient.transfer_to_bank(
#             amount=ext_txn.external_amount,
#             destination_account=ext_txn.bank_account.account_number,
#             destination_bank=ext_txn.bank_account.bank_name,
#             reference=ext_txn.external_transaction_id,
#         )
        
#         if result['success']:
#             BankTransferService.handle_bank_callback(
#                 external_transaction_id=ext_txn.external_transaction_id,
#                 status='completed',
#                 gateway_response=result,
#             )
#         else:
#             # Gateway rejected - reverse the wallet debit
#             BankTransferService.handle_bank_callback(
#                 external_transaction_id=ext_txn.external_transaction_id,
#                 status='failed',
#                 gateway_response=result,
#             )
            
#     except ExternalTransaction.DoesNotExist:
#         logger.error(f"Task: External transaction {external_transaction_id} not found")
#     except Exception as exc:
#         logger.error(f"Task failed: {exc}")
#         raise self.retry(exc=exc)


# @shared_task
# def reconcile_pending_transactions():
#     """
#     Periodic task (every 5 minutes) to check status of pending transactions.
#     """
#     from .models import ExternalTransaction
    
#     pending = ExternalTransaction.objects.filter(
#         external_status__in=['initiated', 'pending', 'processing']
#     )
    
#     for ext_txn in pending:
#         # Call gateway status check API
#         result = PaymentGatewayClient.check_status(ext_txn.external_transaction_id)
#         if result.get('status') != ext_txn.external_status:
#             BankTransferService.handle_bank_callback(
#                 external_transaction_id=ext_txn.external_transaction_id,
#                 status=result['status'],
#                 gateway_response=result,
#             )