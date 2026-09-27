# from abc import ABC, abstractmethod

# class BasePaymentGateway(ABC):
#     @abstractmethod
#     def initiate_deposit(self, amount, currency, wallet_id, user_id) -> dict:
#         pass

#     @abstractmethod
#     def initiate_withdrawal(self, amount, bank_account) -> dict:
#         pass

#     @abstractmethod
#     def verify_webhook(self, payload, signature) -> bool:
#         pass

#     @abstractmethod
#     def check_status(self, external_transaction_id) -> dict:
#         pass