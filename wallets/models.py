from django.db import models
from django.contrib.auth.models import User
import uuid


class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='company/logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Employee(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='employees',
    )
    employee_id = models.CharField(max_length=50, unique=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='employee/avatars/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.company.name}"


class Wallet(models.Model):
    wallet_id = models.CharField(max_length=20, unique=True, editable=False)
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    # Balance stored in paisa (1 taka = 100 paisa)
    balance = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        ordering = ['-created_at']

    def __str__(self):
        return f"Wallet [{self.wallet_id}] - {self.employee}"

    @property
    def balance_in_taka(self):
        return self.balance / 100


class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    # Unique idempotency key to prevent duplicate transactions
    idempotency_key = models.CharField(max_length=255, unique=True)

    # Auto-generated API key for each transaction
    api_key = models.CharField(max_length=64, unique=True, editable=False)

    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='transactions',
    )

    # For transfer transactions
    related_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        related_name='related_transactions',
        null=True,
        blank=True,
    )
    related_employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        related_name='related_transactions',
        null=True,
        blank=True,
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    # Amount stored in paisa
    amount = models.PositiveBigIntegerField()
    # Balance after transaction in paisa
    balance_before = models.PositiveBigIntegerField()
    balance_after = models.PositiveBigIntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # external_transaction = models.OneToOneField(
    #     ExternalTransaction,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='internal_transaction'
    # )

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type.upper()} | {self.wallet.wallet_id} | {self.amount} paisa"

    @property
    def amount_in_taka(self):
        return self.amount / 100

    @property
    def balance_before_in_taka(self):
        return self.balance_before / 100

    @property
    def balance_after_in_taka(self):
        return self.balance_after / 100
    
# class BankAccount(models.Model):
#     ACCOUNT_TYPE_CHOICES = [
#         ('personal', 'Personal'),
#         ('business', 'Business'),
#     ]

#     STATUS_CHOICES = [
#         ('pending_verification', 'Pending Verification'),
#         ('active', 'Active'),
#         ('suspended', 'Suspended'),
#         ('closed', 'Closed'),
#     ]

#     employee = models.ForeignKey(
#         Employee,
#         on_delete=models.CASCADE,
#         related_name='bank_accounts'
#     )
#     account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
#     bank_name = models.CharField(max_length=100)
#     branch_name = models.CharField(max_length=100, blank=True, null=True)
#     account_number = models.CharField(max_length=50)
#     account_title = models.CharField(max_length=255)
#     routing_number = models.CharField(max_length=50, blank=True, null=True)  # For Bangladesh
#     swift_code = models.CharField(max_length=20, blank=True, null=True)
#     iban = models.CharField(max_length=50, blank=True, null=True)
#     is_primary = models.BooleanField(default=False)
#     status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_verification')
#     verification_notes = models.TextField(blank=True, null=True)
#     verified_at = models.DateTimeField(blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         unique_together = ['employee', 'account_number', 'bank_name']
#         ordering = ['-is_primary', '-created_at']

#     def __str__(self):
#         return f"{self.bank_name} - {self.account_number[-4:]}"


# class ExternalTransaction(models.Model):
#     """
#     Tracks the external bank transfer status for deposits/withdrawals.
#     Links internal transactions to external payment gateway responses.
#     """
#     EXTERNAL_STATUS_CHOICES = [
#         ('initiated', 'Initiated'),
#         ('pending', 'Pending'),
#         ('processing', 'Processing'),
#         ('completed', 'Completed'),
#         ('failed', 'Failed'),
#         ('cancelled', 'Cancelled'),
#         ('reversed', 'Reversed'),
#     ]

#     transaction = models.OneToOneField(
#         Transaction,
#         on_delete=models.CASCADE,
#         related_name='external_transaction'
#     )
#     bank_account = models.ForeignKey(
#         BankAccount,
#         on_delete=models.SET_NULL,
#         null=True,
#         related_name='external_transactions'
#     )
#     external_transaction_id = models.CharField(max_length=255, unique=True)
#     external_status = models.CharField(max_length=20, choices=EXTERNAL_STATUS_CHOICES, default='initiated')
#     external_amount = models.PositiveBigIntegerField()  # In paisa
#     external_currency = models.CharField(max_length=10, default='BDT')
#     gateway_response = models.JSONField(blank=True, null=True)
#     error_message = models.TextField(blank=True, null=True)
#     initiated_at = models.DateTimeField(auto_now_add=True)
#     completed_at = models.DateTimeField(blank=True, null=True)
#     failed_at = models.DateTimeField(blank=True, null=True)

#     class Meta:
#         ordering = ['-initiated_at']

#     def __str__(self):
#         return f"External {self.external_transaction_id} - {self.external_status}"


# class ReconciliationLog(models.Model):
#     """
#     Daily reconciliation between internal wallet balances and 
#     external payment gateway balances.
#     """
#     RECONCILIATION_TYPE_CHOICES = [
#         ('deposit', 'Deposit'),
#         ('withdrawal', 'Withdrawal'),
#         ('daily', 'Daily Balance'),
#     ]

#     employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='reconciliations')
#     wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='reconciliations')
#     reconciliation_type = models.CharField(max_length=20, choices=RECONCILIATION_TYPE_CHOICES)
#     internal_balance = models.PositiveBigIntegerField()  # paisa
#     external_balance = models.PositiveBigIntegerField()  # paisa
#     difference = models.BigIntegerField()  # can be negative
#     is_resolved = models.BooleanField(default=False)
#     resolution_notes = models.TextField(blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     resolved_at = models.DateTimeField(blank=True, null=True)

#     class Meta:
#         ordering = ['-created_at']