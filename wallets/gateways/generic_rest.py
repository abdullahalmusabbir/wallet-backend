# import requests
# import json
# from decimal import Decimal

# class GenericRESTGateway(BasePaymentGateway):
#     def initiate_withdrawal(self, amount, bank_account, reference):
#         payload = {
#             "amount": float(amount / 100),  # Convert paisa to taka
#             "currency": "BDT",
#             "to_account": bank_account.account_number,
#             "to_bank": bank_account.bank_name,
#             "reference": reference,
#             "purpose": "wallet_withdrawal",
#         }
        
#         response = requests.post(
#             f"{self.base_url}/v1/transfers",
#             json=payload,
#             headers=self._auth_headers(),
#             timeout=30
#         )
        
#         data = response.json()
#         return {
#             "success": response.status_code == 201 and data.get('status') == 'success',
#             "external_transaction_id": data.get('transaction_id'),
#             "status": data.get('status'),
#             "raw_response": data,
#         }