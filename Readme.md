# WalletBD Backend

A secure, multi-company wallet and ledger management REST API built with **Django REST Framework**.

WalletBD allows companies to manage employees, wallets, and financial transactions including deposits, withdrawals, and wallet-to-wallet transfers. Each company's data is isolated, and all wallet balance changes are recorded through an immutable transaction ledger.

The backend is designed with transaction safety, idempotency, tenant isolation, and concurrent request handling in mind.

---

## 🚀 Key Features

* Company-based multi-tenancy
* JWT-based authentication
* Company admin and employee roles
* Employee management
* Individual wallets for employees
* Deposit and withdrawal operations
* Wallet-to-wallet transfers within the same company
* Immutable transaction ledger
* Idempotent financial operations
* Insufficient balance protection
* Atomic transactions
* Database row locking using `select_for_update()`
* Company-level data isolation
* Paginated transaction history
* Transaction filtering
* PostgreSQL database support
* Redis cache support
* Docker deployment support
* Static file handling with WhiteNoise
* Production server support with Gunicorn

---

# 🛠 Tech Stack

| Technology            | Purpose                |
| --------------------- | ---------------------- |
| Python 3.12           | Backend language       |
| Django 5.0.4          | Web framework          |
| Django REST Framework | REST API               |
| Simple JWT            | Authentication         |
| PostgreSQL            | Primary database       |
| Supabase              | Hosted PostgreSQL      |
| Redis                 | Caching                |
| Docker                | Containerization       |
| Gunicorn              | Production WSGI server |
| WhiteNoise            | Static file serving    |

---

# 🔐 Authentication

WalletBD uses **JWT authentication**.

Users can:

* Register a company and admin account
* Login and receive access/refresh tokens
* Logout and blacklist refresh tokens
* Request password reset
* Reset password using a reset token
* View and update their profile

## Authentication APIs

| Method | Endpoint                 | Description                        |
| ------ | ------------------------ | ---------------------------------- |
| POST   | `/auth/register/`        | Register company + admin user      |
| POST   | `/auth/login/`           | Login and receive JWT tokens       |
| POST   | `/auth/logout/`          | Logout and blacklist refresh token |
| POST   | `/auth/forgot-password/` | Request password reset             |
| POST   | `/auth/reset-password/`  | Reset password                     |

---

# 👤 Profile APIs

| Method | Endpoint | Description                   |
| ------ | -------- | ----------------------------- |
| GET    | `/me/`   | Get current user's profile    |
| PUT    | `/me/`   | Update current user's profile |

---

# 🏢 Company Management

Each user belongs to a company. Company-level data is isolated from other companies.

### APIs

| Method | Endpoint    | Access              |
| ------ | ----------- | ------------------- |
| GET    | `/company/` | Authenticated users |
| PUT    | `/company/` | Company admin       |

An admin can update company information, while employees have read-only access according to their permissions.

---

# 👨‍💼 Employee Management

Employees are associated with a company and have their own wallet.

### APIs

| Method | Endpoint                    | Description            |
| ------ | --------------------------- | ---------------------- |
| GET    | `/employees/`               | List company employees |
| POST   | `/employees/`               | Create employee        |
| GET    | `/employees/{employee_id}/` | Get employee details   |
| PUT    | `/employees/{employee_id}/` | Update employee        |
| DELETE | `/employees/{employee_id}/` | Deactivate employee    |

The employee list is paginated.

Only company administrators can create, update, or deactivate employees.

---

# 💰 Wallet Management

Every employee has an associated wallet.

Wallet balances are stored in **paisa** instead of floating-point values.

```text
1 Taka = 100 Paisa
```

For example:

```text
৳100.50 = 10050 paisa
```

This avoids floating-point precision problems when handling money.

### APIs

| Method | Endpoint               | Description                   |
| ------ | ---------------------- | ----------------------------- |
| GET    | `/wallet/`             | Get current user's wallet     |
| GET    | `/wallet/{wallet_id}/` | Get wallet by ID (admin only) |

---

# 💸 Transactions

Wallet balance changes are handled through transactions.

Supported operations:

* Deposit
* Withdraw
* Wallet-to-wallet transfer

Every balance-changing operation creates a transaction record.

## Deposit

```http
POST /transactions/deposit/
```

Adds money to a wallet.

Only company administrators can perform deposits.

---

## Withdraw

```http
POST /transactions/withdraw/
```

Withdraws money from the authenticated user's wallet.

The operation is rejected if the wallet does not have sufficient funds.

Example:

```text
Current balance: ৳500
Withdrawal:      ৳700

Result: Rejected
Reason: Insufficient funds
```

---

## Transfer

```http
POST /transactions/transfer/
```

Transfers funds between two wallets belonging to the **same company**.

Example:

```text
Employee A
Balance: ৳1,000

        ↓ Transfer ৳300

Employee B
Balance: ৳500
```

After transfer:

```text
Employee A: ৳700
Employee B: ৳800
```

Cross-company transfers are rejected.

---

# 🔒 Transaction Safety

Financial operations are implemented with database transactions to prevent inconsistent balances.

Transfers are atomic:

```text
Sender debit
     +
Receiver credit
     +
Ledger entries
```

Either all operations succeed or none of them are committed.

Django's:

```python
transaction.atomic()
```

is used for atomic operations.

---

# 🔐 Concurrent Transaction Protection

Wallet operations use database row locking where necessary.

```python
select_for_update()
```

This prevents race conditions when multiple requests attempt to modify the same wallet simultaneously.

For example, if two withdrawal requests arrive at the same time, the wallet is locked while its balance is checked and updated.

This prevents situations such as:

```text
Balance = ৳1,000

Request A → Withdraw ৳800
Request B → Withdraw ৳700
```

Both requests should not be able to spend the same balance.

---

# 🔁 Idempotency

Deposit, withdrawal, and transfer operations support a client-provided **idempotency key**.

The purpose is to prevent duplicate transactions when a client retries the same request.

Example:

```text
idempotency_key = 550e8400-e29b-41d4-a716-446655440000
```

If the same request is sent multiple times with the same key, the transaction will not be processed repeatedly.

Example:

```text
First request:
Deposit ৳1,000 → Success

Retry with same idempotency key:
No additional deposit
```

Idempotency is scoped to the company.

---

# 📜 Transaction History

Wallet and company transaction history can be retrieved through dedicated endpoints.

### My Transaction History

```http
GET /transactions/history/
```

Returns the authenticated user's transaction history.

Supports:

* Pagination
* Filtering

### Company Transaction History

```http
GET /transactions/company/
```

Allows company administrators to view transactions belonging to their company.

### Transaction Details

```http
GET /transactions/{transaction_id}/
```

Returns details of a specific transaction.

---

# 📊 Transaction Types

The ledger supports transaction types such as:

```text
DEPOSIT
WITHDRAW
TRANSFER_IN
TRANSFER_OUT
```

Each transaction records the relevant wallet, amount, transaction type, idempotency information, and related metadata.

Transactions are treated as immutable ledger records.

---

# 🏗 Database Models

## Active Models

### Company

Stores company/tenant information.

```text
Company
 ├── Employees
 └── Wallets
```

### Employee

Stores employee information and connects:

```text
User
Company
Wallet
```

### Wallet

Stores the employee's wallet information and balance in paisa.

### Transaction

Stores all financial operations and acts as the transaction ledger.

---

# 🏦 Bank Integration

The project also contains prepared code for external bank withdrawals and reconciliation.

The following components are currently disabled/commented out because they require actual bank/payment-provider details and integration credentials.

### Prepared Components

* `BankAccount`
* `ExternalTransaction`
* `ReconciliationLog`
* `BankTransferService`
* `ReconciliationService`
* `process_bank_withdrawal_task`
* `reconcile_pending_transactions`

There is also a prepared payment gateway structure including:

* `BasePaymentGateway`
* `bKashGateway`

These components are kept in the codebase as an extension point.

Once the required bank/payment-provider details, credentials, API configuration, and integration requirements are available, the existing implementation can be enabled by uncommenting and configuring the relevant models, serializers, views, services, and gateway components.

No external bank transfer is currently performed by the active API.

---

# 🔌 Planned Bank APIs

The following endpoints are prepared for future bank integration.

| Method | Endpoint                       | Status   |
| ------ | ------------------------------ | -------- |
| GET    | `/bank-accounts/`              | Prepared |
| POST   | `/bank-accounts/`              | Prepared |
| GET    | `/bank-accounts/{account_id}/` | Prepared |
| PUT    | `/bank-accounts/{account_id}/` | Prepared |
| DELETE | `/bank-accounts/{account_id}/` | Prepared |
| POST   | `/transactions/bank-withdraw/` | Prepared |
| POST   | `/webhooks/{gateway_name}/`    | Prepared |

These APIs are not enabled in the current version.

---

# 🧩 Multi-Tenant Data Isolation

WalletBD follows a company-based tenant isolation model.

For example:

```text
Company A
 ├── Employee A1
 ├── Employee A2
 └── Wallets

Company B
 ├── Employee B1
 ├── Employee B2
 └── Wallets
```

Company A cannot access:

* Company B employees
* Company B wallets
* Company B transactions
* Company B financial data

Cross-company wallet transfers are also rejected.

All relevant queries are scoped to the authenticated user's company.

---

# 📁 Project Structure

A simplified project structure:

```text
backend/
│
├── wallet/
│   ├── manage.py
│   │
│   ├── wallet/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   │
│   ├── users/
│   ├── wallets/
│   ├── transactions/
│   └── ...
│
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

# ⚙️ Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DATABASE_URL=your-postgresql-url

REDIS_URL=your-redis-url

EMAIL_HOST=your-email-host
EMAIL_PORT=587
EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-password
```

Do not commit real credentials or secrets to GitHub.

---

# 🚀 Local Setup

## 1. Clone the repository

```bash
git clone <repository-url>
```

## 2. Go to the backend directory

```bash
cd backend/wallet
```

## 3. Create virtual environment

```bash
python -m venv venv
```

## 4. Activate virtual environment

### Windows

```powershell
venv\Scripts\activate
```

### macOS/Linux

```bash
source venv/bin/activate
```

## 5. Install dependencies

```bash
pip install -r requirements.txt
```

## 6. Configure environment variables

Create `.env` using `.env.example`.

## 7. Run migrations

```bash
python manage.py migrate
```

## 8. Create superuser

```bash
python manage.py createsuperuser
```

## 9. Start development server

```bash
python manage.py runserver
```

The API will be available at:

```text
http://127.0.0.1:8000/
```

---

# 🐳 Docker Setup

Docker is optional for local development.

Build the image:

```bash
docker build -t wallet-backend .
```

Run the container:

```bash
docker run -p 8000:8000 wallet-backend
```

The application will then be available at:

```text
http://localhost:8000/
```

---

# 🗄 Database

The project uses **PostgreSQL** as the primary database.

The production database can be hosted using **Supabase PostgreSQL**.

The application is designed to use database-level transactions and row locking for financial operations.

---

# 🧪 Testing

The core financial flows should be covered by automated tests, including:

* User/company registration
* Authentication
* Deposit
* Withdrawal
* Insufficient funds
* Wallet transfer
* Same-company transfer validation
* Cross-company access protection
* Duplicate idempotency key
* Concurrent wallet operations
* Transaction history
* Pagination
* Permission checks

Run tests with:

```bash
python manage.py test
```

---

# 🔐 Security Considerations

WalletBD is designed with the following security principles:

* JWT authentication
* Company-level data isolation
* Role-based permissions
* Server-side balance validation
* Atomic financial operations
* Database row locking
* Idempotency protection
* Immutable transaction records
* No floating-point money calculations
* Environment-based secret configuration

---

# 📌 Current Scope

The current active system focuses on:

```text
Authentication
      ↓
Company
      ↓
Employees
      ↓
Wallets
      ↓
Transactions
      ↓
Ledger / Transaction History
```

External bank transfers and payment gateway integrations are prepared but remain disabled until the required integration details and credentials are available.

---

# 🔮 Future Extensions

Possible future improvements include:

* Bank account integration
* bKash/payment gateway integration
* External bank withdrawals
* Webhook processing
* Automated reconciliation
* Celery-based background processing
* Advanced transaction reporting
* Audit logging
* Notification system
* Rate limiting
* API documentation with Swagger/OpenAPI

---

# 📄 License

This project is developed as a backend wallet management system and assessment project.
