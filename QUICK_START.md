# Quick Start

This guide walks through the full setup and first-run process for the HR System.

---

## 1. Prerequisites

Before you start, make sure you have:

- Python 3.10+
- A Google Cloud project with API access
- A Google service account JSON key
- A Google Sheet named `HR_System_Database`
- A second rate table spreadsheet named `SOCSO_EPF_RateConfig`
- A Supabase project with Storage enabled for MC / EA Form / payslip uploads
- A valid Supabase project configuration in `.streamlit/secrets.toml`

---

## 2. Clone and install

```bash
git clone <your-repo-url>
cd LH_SYSTEM
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Configure secrets

Create the local secrets file:

```bash
mkdir -p .streamlit
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

On Linux/macOS, use:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then fill in the values in `.streamlit/secrets.toml` with:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- all fields under `[gcp_service_account]`
- any required extra config values for your environment

Example structure:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-or-service-key"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "hr-system@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your%40project.iam.gserviceaccount.com"
```

> Do not commit `.streamlit/secrets.toml` to Git.

---

## 4. Google Cloud setup

This is the part that most often blocks the app from running correctly. Do it in the exact order below.

### 4.1 Create a project

1. Open [Google Cloud Console](https://console.cloud.google.com).
2. Click `New Project`.
3. Give the project a clear name such as `HR-System`.
4. Wait until the project is created and selected.

### 4.2 Enable the required APIs

Go to `APIs & Services` → `Enabled APIs & Services` and turn on:

- `Google Sheets API`
- `Google Drive API`

These two APIs are required because the app reads and writes the main database in Google Sheets and uploads EA form files via Google Drive.

### 4.3 Create the service account

1. Go to `IAM & Admin` → `Service Accounts`.
2. Click `Create Service Account`.
3. Use a name like `hr-system-bot`.
4. Finish creation.
5. Open the created service account and go to the `Keys` tab.
6. Click `Add Key` → `Create new key` → `JSON`.
7. Download the JSON file and save it securely.

This file contains the private credentials the app uses to authenticate to Google.

> Important: do not commit this file to Git. Keep it in a secure local folder or a deployment secret manager.

### 4.4 Handle organization policy blocks

If Google refuses to create the key and shows an error such as `iam.disableServiceAccountKeyCreation`, it usually means your Google Workspace organization has an organization policy blocking service account key creation.

In that case:

1. Ask your Google Workspace admin to grant the `Organization Policy Administrator` role or equivalent rights.
2. Go to `IAM & Admin` → `Organization Policies`.
3. Find the policy that is blocking service account key creation.
4. Set it to `Not enforced`.
5. Wait a few minutes, then retry creating the JSON key.

### 4.5 Copy the service account email

Open the downloaded JSON file and copy the value of `client_email`.

Example:

```text
hr-system@your-project.iam.gserviceaccount.com
```

You will use this email when you share the Google Sheets with the service account.

---

## 5. Create your Google Sheets

### 5.1 Main database spreadsheet

Create a spreadsheet named exactly:

```text
HR_System_Database
```

Inside this spreadsheet, create the tabs below. The sheet names and column headers must match the app exactly, because the code reads them by name.

### 5.2 Required table names in `HR_System_Database`

These are the tab names that must exist in the main spreadsheet:

| Table name | Purpose |
|---|---|
| `Employees` | Employee master data and login credentials |
| `LeaveRequests` | Leave applications and approval records |
| `LeaveBalance` | Annual / medical / unpaid leave balance snapshot by employee and year |
| `Payslips` | Monthly payslip records |
| `Attendance` | Manual attendance exception overrides |
| `PublicHolidays` | Public holidays and special holidays |
| `PerformanceRecords` | Performance tracking entries |
| `Companies` | Client / company list for performance tracking |

> If you want the app to work correctly, these tab names should be created first before adding any row data.

### 5.3 Required tabs and columns

#### Employees

| Column name | Notes |
|---|---|
| employee_id | unique employee ID, e.g. `EMP001` |
| name | full name |
| email | login email |
| phone | contact number |
| department | department name |
| gender | gender value used by app |
| address | full address |
| date_of_birth | ISO format `YYYY-MM-DD` |
| join_date | ISO format `YYYY-MM-DD` |
| income_tax_no | tax number |
| epf_no | EPF number |
| ic_no | NRIC / ID number |
| status | usually `Active` or `Resigned` |
| bank_account | bank account number |
| password_hash | bcrypt hash generated by `generate_hash.py` |
| force_password_reset | `Yes` or `No` |
| role | `employee`, `manager`, or `hr_admin` |

#### LeaveRequests

| Column name | Notes |
|---|---|
| request_id | unique leave request ID |
| employee_id | ID of the employee |
| employee_name | employee full name |
| leave_type | e.g. `Annual`, `Medical`, `Unpaid`, `Special`, `Married` |
| start_date | ISO date |
| end_date | ISO date |
| days | number of leave days |
| session | `Full Day` or `Half Day` |
| reason | leave reason |
| status | `Pending`, `Approved`, or `Rejected` |
| approved_by | approver name or email |
| submit_date | datetime string |

#### LeaveBalance

| Column name | Notes |
|---|---|
| employee_id | employee ID |
| year | year, e.g. `2026` |
| annual_total | total annual leave entitlement |
| annual_used | used annual leave |
| medical_total | total medical leave entitlement |
| medical_used | used medical leave |
| unpaid_used | unpaid leave used |

#### Payslips

| Column name | Notes |
|---|---|
| payslip_id | unique payslip ID |
| employee_id | employee ID |
| employee_name | employee full name |
| month | month in `YYYY-MM` format |
| basic_salary | base salary |
| allowance | allowance amount |
| red_packet | bonus / red packet |
| bik | BIK amount |
| unpaid_leave_days | unpaid leave days |
| unpaid_leave_deduction | deduction amount |
| pre_join_days | days before join date |
| pre_join_deduction | deduction for pre-join period |
| gross_salary | gross salary |
| epf_employee | employee EPF contribution |
| epf_employer | employer EPF contribution |
| socso_employee | employee SOCSO portion |
| socso_employer | employer SOCSO amount |
| eis_employee | employee EIS contribution |
| eis_employer | employer EIS contribution |
| skbbk | SKBBK contribution |
| skbbk_status | `Yes` or `No` |
| pcb | manual PCB input |
| net_pay | final net pay |

#### Attendance

| Column name | Notes |
|---|---|
| employee_id | employee ID |
| employee_name | employee full name |
| date | ISO date |
| status | e.g. `Absent`, `Late`, `Half Day` |
| remarks | extra remarks for the record |

#### PublicHolidays

| Column name | Notes |
|---|---|
| date | holiday date |
| holiday_name | holiday name |
| holiday_type | `Public Holiday` or `Special Holiday` |
| year | year |
| active | `TRUE` / `FALSE` or equivalent flag |

#### PerformanceRecords

| Column name | Notes |
|---|---|
| record_id | unique record ID |
| company_name | client / company name |
| category | category of company |
| employee_id | assigned employee ID |
| employee_name | employee name |
| due_date | due date |
| completion_date | completion date, if any |
| status | `Pending`, `On Time`, or `Late` |

#### Companies

| Column name | Notes |
|---|---|
| company_name | company / client name |
| category | company category |
| company_type | company type if applicable |
| year_end | year-end value for private limited companies |

> Tip: create these tabs before the first login. The app reads the sheet names exactly as above. If the header names differ even slightly, the app may fail to read or write the data correctly.

### 5.3 Rate config spreadsheet

Create a second spreadsheet named exactly:

```text
SOCSO_EPF_RateConfig
```

It should contain these tabs:

- `SOCSO`
- `EPF`
- `EPF_60`

#### EPF / EPF_60 tab columns

| Column name | Notes |
|---|---|
| salary_min | minimum salary for the bracket |
| salary_max | maximum salary for the bracket |
| employer_amount | employer EPF contribution |
| employee_amount | employee EPF contribution |

#### SOCSO tab columns

| Column name | Notes |
|---|---|
| salary_min | minimum salary |
| salary_max | maximum salary |
| cat1_employer | employer contribution for category 1 |
| cat1_employee_keilatan | employee invalidity contribution |
| cat1_employee_skbbk | employee SKBBK contributions |
| cat2_employer | employer contribution for category 2 |
| cat2_employee_skbbk | employee SKBBK for age 60+ |
| eis_employer | employer EIS contribution |
| eis_employee | employee EIS contribution |

### 5.4 Share both spreadsheets with the service account

1. Open each spreadsheet.
2. Click `Share`.
3. Paste the `client_email` from the JSON key.
4. Give it `Editor` access.
5. Save.

---

## 6. Supabase document storage setup

This project is set up for Supabase Storage for employee documents, especially MC files, EA Forms, and payslips. This is the recommended storage setup for the current Streamlit HR System flow.

### 6.1 Create the Supabase project

1. Go to [Supabase](https://supabase.com).
2. Click `New project`.
3. Create a new project and wait until it is ready.
4. Note down:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

### 6.2 Create the storage bucket

In your Supabase project:

1. Open `Storage`
2. Click `New bucket`
3. Create a bucket named:

```text
employee-documents
```

This bucket name matches the current app configuration.

### 6.3 Set the bucket as private

Make sure the bucket is configured as a private bucket, not public.

This is important because employee documents such as:

- MC
- EA Form
- payslip

should not be publicly visible.

### 6.4 Recommended folder structure

Use this path pattern inside the bucket:

```text
mc/{employee_id}/{filename}
ea_form/{employee_id}/{filename}
payslip/{employee_id}/{filename}
```

Example:

```text
employee-documents/
├── mc/
│   ├── EMP001/
│   │   ├── MC_2026-08-11.pdf
│   │   └── MC_2026-08-20.pdf
│   └── EMP002/
│       └── MC_2026-08-15.pdf
├── ea_form/
│   ├── EMP001/
│   │   ├── EA_2024_EMP001.pdf
│   │   └── EA_2025_EMP001.pdf
│   └── EMP002/
│       └── EA_2025_EMP002.pdf
└── payslip/
    ├── EMP001/
    │   ├── Payslip_2026-06_EMP001.pdf
    │   └── Payslip_2026-07_EMP001.pdf
    └── EMP002/
        └── Payslip_2026-07_EMP002.pdf
```

### 6.5 Add the Supabase secrets

Add these values to `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-project-anon-or-service-key"
```

### 6.6 Storage policies

Create storage policies for the `employee-documents` bucket so the app can upload, download, update, and delete files.

#### Policy 1: Allow app upload

- Policy name: `Allow app upload`
- Operation: `INSERT`
- Target roles: `anon`
- Definition:

```sql
bucket_id = 'employee-documents'
```

#### Policy 2: Allow app download

- Policy name: `Allow app download`
- Operation: `SELECT`
- Target roles: `anon`
- Definition:

```sql
bucket_id = 'employee-documents'
```

#### Policy 3: Allow app update

- Policy name: `Allow app update`
- Operation: `UPDATE`
- Target roles: `anon`
- Definition:

```sql
bucket_id = 'employee-documents'
```

#### Policy 4: Allow app delete

- Policy name: `Allow app delete`
- Operation: `DELETE`
- Target roles: `anon`
- Definition:

```sql
bucket_id = 'employee-documents'
```

> For a simple internal HR system, this is the cleanest setup: private bucket + app-managed file access + path organized by document type and employee ID.

---

## 7. First-time login setup

Before the app is usable, create the first HR admin user manually in the `Employees` sheet.

Use the following values:

- `status` = `Active`
- `role` = `hr_admin`
- `force_password_reset` = `No`
- `password_hash` = hash generated from the helper script

Generate the hash with:

```bash
python generate_hash.py YourChosenPassword
```

Paste the returned hash into the `password_hash` column.

Then start the app:

```bash
streamlit run app.py
```

Login with that account and continue using the system.

---

## 8. Day-to-day usage

### HR admin
- Add/edit employees
- Approve or reject leave requests
- Review attendance exceptions
- Generate payslips and payroll records
- Review performance and employee activity
- Manage EA forms and document visibility

### Employee
- View dashboard and leave balance
- Submit leave requests
- Check attendance and payslips
- Update profile details
- Change password
- Download available HR documents

---

## 9. Deployment

### Option A: Streamlit Community Cloud

1. Push the repo to a private GitHub repository.
2. Connect to Streamlit Community Cloud.
3. Set the app entry point as `app.py`.
4. Paste the contents of `.streamlit/secrets.toml` into the app secrets section.
5. Share the public app URL with employees as needed.

### Option B: VM or internal server

Run the app behind a normal process manager or reverse proxy such as Nginx, for example:

```bash
streamlit run app.py
```

This is the better option if you need a non-sleeping production deployment.

---

## 10. Common troubleshooting

### Login fails
- Check that `password_hash` was generated correctly
- Confirm the employee row is in `Active` status
- Ensure the role matches a valid value like `hr_admin` or `employee`

### Google Sheets access fails
- Confirm the service account email has Editor access
- Confirm the spreadsheet name matches exactly
- Confirm the relevant Google APIs are enabled

### EA forms cannot upload
- Create and use a Shared Drive
- Ensure the service account is added with manager-level access
- Check that the Drive API is enabled

### Leave balances look wrong
Use the recalculation feature in Employee Management if the policy changed after the employee record was created.

---

## 11. Project files to keep private

These should not be committed:

```text
.streamlit/secrets.toml
credentials/
```

---

## 12. Recommended first action

If this is a fresh deployment, do the following in order:

1. Create the Google service account and secret file
2. Set up the required Sheets and rate config workbook
3. Add your first HR admin employee
4. Sign in and verify dashboard access
5. Add a few test employees and validate leave and payroll flows

This gives a safe onboarding path before going live with real staff data.
