# import hashlib
# import hmac
# import json
# from .base import BasePaymentGateway
# from django.conf import settings

# class bKashGateway(BasePaymentGateway):
#     def __init__(self):
#         self.base_url = settings.BKASH_BASE_URL
#         self.app_key = settings.BKASH_APP_KEY
#         self.app_secret = settings.BKASH_APP_SECRET
#         self.username = settings.BKASH_USERNAME
#         self.password = settings.BKASH_PASSWORD

#     def _get_token(self):
#         # bKash token flow
#         pass

#     def initiate_withdrawal(self, amount, currency, wallet_id, user_id):
#         # bKash Payout / Money Transfer API
#         pass

#     def initiate_deposit(self, amount, currency, wallet_id, user_id):
#         # bKash Create Payment
#         pass

#     def verify_webhook(self, payload, signature):
#         expected = hmac.new(
#             self.app_secret.encode(),
#             payload.encode(),
#             hashlib.sha256
#         ).hexdigest()
#         return hmac.compare_digest(expected, signature)