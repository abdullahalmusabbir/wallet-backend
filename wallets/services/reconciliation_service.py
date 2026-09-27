# import logging
# from decimal import Decimal
# from django.db import transaction as db_transaction
# from django.utils import timezone

# from ..models import Wallet, Transaction, ExternalTransaction, ReconciliationLog

# logger = logging.getLogger(__name__)


# class ReconciliationService:
#     @staticmethod
#     def log_reconciliation(transaction, is_resolved=True, notes=""):
#         txn = transaction
#         wallet = txn.wallet
        
#         external_amount = 0
#         if is_resolved and hasattr(txn, 'external_transaction'):
#             external_amount = txn.external_transaction.external_amount

#         internal_balance = wallet.balance
        
#         # For deposits: external confirms credit
#         # For withdrawals: external confirms debit
#         # Difference calculation depends on transaction type
#         if txn.transaction_type in ['deposit', 'transfer_in']:
#             difference = internal_balance - (wallet.balance - txn.amount)  # Simplified
#         else:
#             difference = (wallet.balance + txn.amount) - internal_balance  # Simplified
        
#         ReconciliationLog.objects.create(
#             employee=txn.employee,
#             wallet=wallet,
#             reconciliation_type=txn.transaction_type,
#             internal_balance=internal_balance,
#             external_balance=external_amount,
#             difference=difference,
#             is_resolved=is_resolved,
#             resolution_notes=notes,
#         )

#     @staticmethod
#     def daily_balance_check():
#         """
#         Periodic task to verify all wallet balances.
#         Compare internal balance vs sum of successful external transactions.
#         """
#         from ..models import Wallet
        
#         discrepancies = []
#         for wallet in Wallet.objects.select_related('employee__company').filter(is_active=True):
#             internal_balance = wallet.balance
            
#             # Calculate expected balance from transactions
#             successful_external = ExternalTransaction.objects.filter(
#                 transaction__wallet=wallet,
#                 external_status='completed'
#             )
            
#             # This is simplified - actual logic depends on your transaction model
#             expected_balance = internal_balance  # Placeholder
            
#             if internal_balance != expected_balance:
#                 discrepancies.append({
#                     'wallet_id': wallet.wallet_id,
#                     'internal': internal_balance,
#                     'expected': expected_balance,
#                     'difference': internal_balance - expected_balance,
#                 })
        
#         if discrepancies:
#             logger.warning(f"Reconciliation discrepancies found: {discrepancies}")
#             # Send alert to admin
        
#         return discrepancies