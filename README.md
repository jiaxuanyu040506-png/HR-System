# HR System

HR System is an internal HR and employee management platform built for small organizations that still rely on spreadsheets, manual approvals, and shared document workflows. The goal is to centralize employee records, leave tracking, attendance, payroll, performance monitoring, and HR document handling in one system.

The application is built with Python and Streamlit, and it uses Google Sheets as the primary operational data source. Employee documents such as MC files, EA forms, and payslips are stored in Supabase Storage using a private bucket structure.

---

## Overview

The system is structured around two main areas:

- HR System: company-wide admin functions
- My Workspace: employee self-service portal

This allows HR administrators to manage the company while employees can view their own personal data, apply leave, access payslips, and manage profile-related actions.

---

## Core Modules

### Employee Management
- Add, edit, and manage employee records
- Maintain status, role, department, and bank / identity information
- Support first-time account creation and login setup
- Allow controlled employee resignation and deletion workflows

### Leave Management
- Submit leave requests
- Approve and reject leave applications
- Track leave balances by year
- Support public holidays and special holidays
- Handle annual, medical, unpaid, and special leave logic
- Apply probation-aware and prorated leave entitlement rules

### Attendance
- Auto-calculate presence, leave, holiday, and rest-day status
- Allow HR to input manual attendance exceptions such as Absent, Late, and Half Day
- Display employee and company-wide attendance views
- Export attendance records to Excel

### Payroll
- Generate monthly payslip records
- Support basic salary, allowance, bonus, BIK, unpaid leave deduction, and manual PCB input
- Calculate EPF, SOCSO, EIS, and SKBBK contributions
- Produce PDF payslips and retain historical payroll information

### Performance Tracking
- Record work completion against company or client assignments
- Track due dates and completion status
- View employee performance summaries and task counts

### HR Document Management
- Upload and manage employee MC files, EA forms, and related HR documents
- Store files in a private Supabase Storage bucket
- Organize files by document type and employee ID
- Restrict document access based on employee role and permissions

---

## User Roles

### HR Admin
HR administrators have access to company-wide functions, including:
- Employee records and onboarding
- Leave approvals
- Attendance exceptions and reporting
- Payroll and payslip generation
- Performance monitoring
- HR document management
- Reports and dashboard summaries

### Employee
Employees can access:
- Dashboard
- Leave application and history
- Payslips
- Attendance overview
- Profile information and password change
- Accessible HR documents

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python |
| Primary data store | Google Sheets |
| Service account auth | Google Cloud IAM / service accounts |
| Document storage | Supabase Storage |
| PDF generation | fpdf2 |
| Excel export | OpenPyXL |
| Password hashing | bcrypt |
| Deployment | Streamlit-compatible hosting |

---

## Project Structure

```text
LH_SYSTEM/
├── app.py
├── requirements.txt
├── README.md
├── QUICK_START.md
├── CHANGELOG.md
├── generate_hash.py
├── .streamlit/
│   ├── secrets.toml.example
├── pages/
│   ├── 0_Dashboard.py
│   ├── 1_Employee_Management.py
│   ├── 2_Leave_Management.py
│   ├── 3_Payslip_Management.py
│   ├── 4_My_Profile.py
│   ├── 5_Payroll_Management.py
│   ├── 6_Pay.py
│   ├── 7_Reports.py
│   ├── 8_Time.py
│   ├── 9_HR_Overview.py
│   ├── 10_Performance.py
│   ├── 11_Attendance.py
│   └── 12_Public_Holidays.py
├── utils/
│   ├── attendance.py
│   ├── auth.py
│   ├── dashboard.py
│   ├── date_utils.py
│   ├── drive_client.py
│   ├── ea_forms.py
│   ├── employee_lifecycle.py
│   ├── excel_export.py
│   ├── leave_attachment.py
│   ├── leave_calc.py
│   ├── leave_rules.py
│   ├── payroll_calc.py
│   ├── pdf_generator.py
│   ├── performance.py
│   ├── sheets_client.py
│   ├── supabase_client.py
│   ├── ui.py
│   └── __init__.py
└── .gitignore
```

---

## Getting Started

For the full setup flow and data model instructions, see [QUICK_START.md](QUICK_START.md).

Typical local startup:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

---

## Configuration

The app expects a local secrets file at:

```text
.streamlit/secrets.toml
```

That file should include the required Google service account credentials and the Supabase settings used for employee document storage, including:

- `SUPABASE_URL`
- `SUPABASE_KEY`

Do not commit the real secrets file to version control.

---

## Security and Operational Notes
- Keep all API keys and credentials out of Git
- Restrict employee access via role-based logic
- Use strong password hashing and reset flow
- Review statutory payroll rules before going live
- Use a controlled internal environment for employee and payroll data

---

## Current Status

This project is a functioning internal HR system for day-to-day HR operations, with ongoing refinement around policy rules, file handling, and automation improvements.

---

## Documentation

- [QUICK_START.md](QUICK_START.md): environment setup, Google Cloud configuration, spreadsheet structure, and deployment guidance
- [CHANGELOG.md](CHANGELOG.md): feature history and release notes

---

## License

This project is intended for internal company use and is not currently distributed as a public software product.
