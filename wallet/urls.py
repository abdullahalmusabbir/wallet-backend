from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', views.HealthView.as_view(), name='health'),
     # Auth
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),

    # Profile
    path('me/', views.MyProfileView.as_view(), name='my-profile'),

    # Company
    path('company/', views.CompanyDetailView.as_view(), name='company-detail'),

    # Employees
    path('employees/', views.EmployeeListCreateView.as_view(), name='employee-list-create'),
    path('employees/<str:employee_id>/', views.EmployeeDetailView.as_view(), name='employee-detail'),

    # Wallet
    path('wallet/', views.WalletDetailView.as_view(), name='wallet-detail'),
    path('wallet/<str:wallet_id>/', views.WalletByIdView.as_view(), name='wallet-by-id'),

    # Transactions
    path('transactions/deposit/', views.DepositView.as_view(), name='deposit'),
    path('transactions/withdraw/', views.WithdrawView.as_view(), name='withdraw'),
    path('transactions/transfer/', views.TransferView.as_view(), name='transfer'),

    # History
    path('transactions/history/', views.MyTransactionHistoryView.as_view(), name='my-transactions'),
    path('transactions/company/', views.CompanyTransactionHistoryView.as_view(), name='company-transactions'),
    path('transactions/<uuid:transaction_id>/', views.TransactionDetailView.as_view(), name='transaction-detail'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )