from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.utils.safestring import mark_safe
from .models import Company, Employee, Wallet, Transaction


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'email', 'phone',
        'total_employees', 'total_balance_display',
        'is_active', 'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'email', 'phone', 'address', 'logo'),
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def total_employees(self, obj):
        return obj.employees.filter(is_active=True).count()
    total_employees.short_description = 'Active Employees'

    def total_balance_display(self, obj):
        total_paisa = Wallet.objects.filter(
            employee__company=obj,
            is_active=True,
        ).aggregate(total=Sum('balance'))['total'] or 0
        taka = total_paisa / 100
        return f"৳ {taka:,.2f}"
    total_balance_display.short_description = 'Total Balance (Taka)'


class WalletInline(admin.StackedInline):
    model = Wallet
    readonly_fields = [
        'wallet_id', 'balance', 'balance_in_taka_display',
        'created_at', 'updated_at',
    ]
    extra = 0
    can_delete = False

    def balance_in_taka_display(self, obj):
        return f"৳ {obj.balance / 100:,.2f}"
    balance_in_taka_display.short_description = 'Balance (Taka)'


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'employee_id', 'full_name', 'company',
        'role', 'wallet_id_display', 'balance_display',
        'is_active', 'created_at',
    ]
    list_filter = ['role', 'is_active', 'company', 'created_at']
    search_fields = [
        'user__username', 'user__email',
        'user__first_name', 'user__last_name',
        'employee_id', 'company__name',
    ]
    readonly_fields = ['employee_id', 'created_at', 'updated_at']
    inlines = [WalletInline]
    ordering = ['-created_at']

    fieldsets = (
        ('User Account', {
            'fields': ('user',),
        }),
        ('Employee Info', {
            'fields': ('company', 'employee_id', 'role', 'phone', 'avatar'),
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    full_name.short_description = 'Full Name'

    def wallet_id_display(self, obj):
        try:
            return obj.wallet.wallet_id
        except Wallet.DoesNotExist:
            return '—'
    wallet_id_display.short_description = 'Wallet ID'

    def balance_display(self, obj):
        try:
            taka = obj.wallet.balance / 100
            return f"৳ {taka:,.2f}"
        except Wallet.DoesNotExist:
            return '—'
    balance_display.short_description = 'Balance'


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'wallet_id', 'employee_name', 'company_name',
        'balance_display', 'is_active', 'created_at',
    ]
    list_filter = ['is_active', 'employee__company', 'created_at']
    search_fields = [
        'wallet_id',
        'employee__user__username',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__company__name',
    ]
    readonly_fields = [
        'wallet_id', 'balance', 'balance_display',
        'created_at', 'updated_at',
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Wallet Info', {
            'fields': ('wallet_id', 'employee', 'is_active'),
        }),
        ('Balance', {
            'fields': ('balance', 'balance_display'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def employee_name(self, obj):
        return obj.employee.user.get_full_name() or obj.employee.user.username
    employee_name.short_description = 'Employee'

    def company_name(self, obj):
        return obj.employee.company.name
    company_name.short_description = 'Company'

    def balance_display(self, obj):
        taka = obj.balance / 100
        return mark_safe(f'<strong>৳ {taka:,.2f}</strong>')
    balance_display.short_description = 'Balance (Taka)'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id_short', 'transaction_type', 'company',
        'employee_name', 'amount_display', 'status',
        'api_key_short', 'created_at',
    ]
    list_filter = [
        'transaction_type', 'status',
        'company', 'created_at',
    ]
    search_fields = [
        'transaction_id', 'api_key', 'idempotency_key',
        'wallet__wallet_id', 'employee__user__username',
        'employee__user__first_name', 'employee__user__last_name',
        'company__name',
    ]
    readonly_fields = [
        'transaction_id', 'api_key', 'idempotency_key',
        'wallet', 'related_wallet',
        'company', 'employee', 'related_employee',
        'transaction_type', 'amount', 'amount_display',
        'balance_before', 'balance_after',
        'balance_before_display', 'balance_after_display',
        'status', 'created_at', 'updated_at',
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Transaction Identity', {
            'fields': (
                'transaction_id', 'api_key',
                'idempotency_key', 'transaction_type', 'status',
            ),
        }),
        ('Parties', {
            'fields': (
                'company', 'employee', 'wallet',
                'related_employee', 'related_wallet',
            ),
        }),
        ('Amount & Balance', {
            'fields': (
                'amount', 'amount_display',
                'balance_before', 'balance_before_display',
                'balance_after', 'balance_after_display',
            ),
        }),
        ('Note', {
            'fields': ('note',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def transaction_id_short(self, obj):
        return str(obj.transaction_id)[:8] + '...'
    transaction_id_short.short_description = 'Transaction ID'

    def api_key_short(self, obj):
        return obj.api_key[:12] + '...' if obj.api_key else '—'
    api_key_short.short_description = 'API Key'

    def employee_name(self, obj):
        return obj.employee.user.get_full_name() or obj.employee.user.username
    employee_name.short_description = 'Employee'

    def amount_display(self, obj):
        taka = obj.amount / 100
        color = {
            'deposit': 'green',
            'transfer_in': 'green',
            'withdraw': 'red',
            'transfer_out': 'red',
        }.get(obj.transaction_type, 'black')
        return mark_safe(f'<span style="color:{color}; font-weight:bold;">৳ {taka:,.2f}</span>')
    amount_display.short_description = 'Amount (Taka)'

    def balance_before_display(self, obj):
        taka = obj.balance_before / 100
        return f"৳ {taka:,.2f}"
    balance_before_display.short_description = 'Balance Before (Taka)'

    def balance_after_display(self, obj):
        taka = obj.balance_after / 100
        return f"৳ {taka:,.2f}"
    balance_after_display.short_description = 'Balance After (Taka)'
