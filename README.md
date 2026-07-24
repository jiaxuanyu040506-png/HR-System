# HR System (Employee · Leave · Payroll · Attendance · Performance)

Internal HR system for a ~20-person company, replacing Excel, WhatsApp, and paper-based processes.

- **Frontend + Backend**: Streamlit (Python) — one codebase, no separate API server
- **Data storage**: Google Sheets (read/write via a service account)
- **File storage**: Google Drive (Shared Drive) — used for EA Form PDFs
- **Deployment**: Streamlit Community Cloud (or any host that runs `streamlit run app.py`)

---

## Modules

| Module | What it does |
|---|---|
| **Employee Management** | Employee directory, add/edit records, department, custom Employee IDs, cascading delete (removes all linked leave/payslip/attendance/performance data) |
| **Leave Management** | Apply/approve leave, leave calendar (company-wide), prorated annual/medical entitlement (tenure-based, probation-aware), auto-convert to Unpaid when annual balance is exhausted, leave summary charts |
| **Attendance** | Daily attendance derived automatically (Present/Rest Day/Public Holiday/On Leave) with HR-marked exceptions (Absent/Late/Half Day); monthly grid view for all employees; Excel export (single month or full year, one sheet per month) |
| **Payroll** | Auto-calculates EPF / SOCSO / SKBBK (togglable per government policy) / EIS from official rate tables; PCB entered manually; generates a PDF payslip matching the company's paper format |
| **Performance** | Logs which employee completed work for which client/company, on-time vs late, with a "who did the most" chart |
| **EA Form** | HR uploads each employee's annual EA Form (income statement) PDF; employees download it from their own Payslip page |
| **Reports** | Employee / Leave / Payroll summaries with CSV export |
| **My Profile** | Personal + employment details, change password |

Two sidebar sections once logged in:
- **HR System** (hr_admin only): company-wide admin tools
- **My Workspace**: personal self-service tools — shown to everyone, including HR admins (an HR admin is also an employee and needs to apply their own leave, view their own payslip, etc.)

---

## Project Structure

```
hr_system/
├── app.py                        # Login, password reset, then routes to the right dashboard
├── requirements.txt
├── .streamlit/
│   └── secrets.toml.example      # Copy to secrets.toml and fill in (see QUICK_START.md)
├── pages/
│   ├── 0_Dashboard.py            # My Workspace > Dashboard (personal view, everyone)
│   ├── 1_Employee_Management.py
│   ├── 2_Leave_Management.py     # HR-side: Approval / Calendar / Employee History / Record Leave
│   ├── 4_My_Profile.py
│   ├── 5_Payroll_Management.py   # Generate Payslip / Payroll History / Upload EA Form
│   ├── 6_Pay.py                  # My Workspace > My Payslips (+ EA Form download)
│   ├── 7_Reports.py
│   ├── 8_Time.py                 # My Workspace > My Leave (Apply / Calendar / History)
│   ├── 9_HR_Overview.py          # HR System > Dashboard (company-wide view)
│   ├── 10_Performance.py
│   └── 11_Attendance.py
├── utils/
│   ├── sheets_client.py          # ONLY place that talks to Google Sheets directly
│   ├── drive_client.py           # Google Drive upload/download (EA Forms)
│   ├── auth.py                   # Login, password hashing, role checks
│   ├── ui.py                     # Shared CSS + the custom sidebar (render_nav_sidebar)
│   ├── dashboard.py               # render_hr_dashboard() / render_personal_dashboard()
│   ├── leave_calc.py              # Leave request/approval logic, balance tracking
│   ├── leave_rules.py             # Tenure brackets, proration, probation, public holidays
│   ├── attendance.py              # Daily attendance derivation + monthly/yearly grids
│   ├── performance.py             # Company/task performance tracking
│   ├── payroll_calc.py            # EPF/SOCSO/SKBBK/EIS lookup + payslip calculation
│   ├── pdf_generator.py           # Payslip PDF (in-memory, never saved to disk)
│   ├── ea_forms.py                # EA Form upload/download records
│   ├── employee_lifecycle.py      # Cascading delete for an employee
│   ├── date_utils.py              # Tolerant date parsing (Google Sheets returns varied formats)
│   └── excel_export.py            # Attendance grid -> downloadable .xlsx
├── NOTES.local.md                 # Personal dev notes — NOT committed to Git
├── QUICK_START.md
└── README.md                      # This file
```

---

## Google Sheets Tabs Required

**Main database** (`HR_System_Database`):

| Tab | Key columns |
|---|---|
| `Employees` | employee_id, name, email, phone, department, address, date_of_birth, join_date, income_tax_no, epf_no, status, admin_email, bank_account, password_hash, force_password_reset, role |
| `LeaveRequests` | request_id, employee_id, employee_name, leave_type, start_date, end_date, days, session, reason, status, approved_by, submit_date |
| `LeaveBalance` | employee_id, year, annual_total, annual_used, medical_total, medical_used, unpaid_used |
| `Payslips` | payslip_id, employee_id, employee_name, month, basic_salary, allowance, epf_employee, epf_employer, socso_employee, socso_employer, skbbk, eis_employee, pcb, net_pay |
| `Companies` | company_name, category, company_type |
| `PerformanceRecords` | record_id, company_name, employee_id, employee_name, due_date, completion_date, status |
| `Attendance` | employee_id, employee_name, date, status, remarks *(only stores exceptions — everything else is auto-derived)* |
| `EAForms` | employee_id, employee_name, year, drive_file_id, uploaded_date |

**Separate file** (`SOCSO_EPF_RateConfig`): `SOCSO`, `EPF`, `EPF_60` tabs — cleaned official statutory rate tables (see QUICK_START.md for the expected column format).

---

## Security Notes

- `credentials/`, `.streamlit/secrets.toml`, and `NOTES.local.md` are all in `.gitignore` — never force-commit them.
- Passwords are stored as bcrypt hashes, never plaintext.
- Bank account and other sensitive fields are only fully visible to the `hr_admin` role.
- The Google service account only has `drive.file` scope (access to files it creates itself), not full Drive access.

---

## Known Limitations (by design, not oversights)

- **PCB (monthly tax deduction)** is entered manually by HR from LHDN's official e-PCB calculator — not auto-computed. Full automated PCB requires tracking each employee's marital status, children, and year-to-date income, which isn't built yet.
- **Leave attachments** (file uploads on the Apply Leave form) aren't persisted anywhere yet — needs Drive integration similar to EA Forms.
- **Public holiday dates** for movable holidays (Chinese New Year, Hari Raya, etc.) are hardcoded per year in `leave_rules.py` and must be updated annually.
- **Payroll Status / Payment Date** on the Payroll dashboard are placeholders — there's no real approval/release workflow yet.
- Reports are CSV exports, not formatted printable PDF reports.

See `SESSION.md` for the full development history and what's planned next.
