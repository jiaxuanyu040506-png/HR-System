# HR System (Employee · Leave · Payslip Management)

Internal HR system for a ~20-person company, replacing Excel, WhatsApp, and paper-based processes.

- **Frontend + Backend**: Streamlit (Python)
- **Data storage**: Google Sheets (read/write via a service account API)
- **Deployment**: Streamlit Community Cloud

---

## Modules

- **Employee Management**: employee records, department, position, active/resigned status
- **Leave Management**: submit/approve requests, automatic leave balance deduction
- **Payslip Management**: enter salary data, auto-calculate EPF/SOCSO/EIS, generate PDF, employee self-service download

---

## Project Structure

```
hr_system/
├── app.py                     # Main entry point, login page
├── requirements.txt
├── .streamlit/
│   └── secrets.toml           # Local secrets config (not committed to Git)
├── config.yaml                # streamlit-authenticator account config
├── credentials/
│   └── service_account.json   # Google service account key (not committed to Git)
├── pages/
│   ├── 1_Employees.py
│   ├── 2_Leave.py
│   ├── 3_Payslips.py
│   └── 4_My_Profile.py
├── utils/
│   ├── sheets_client.py       # Wraps all Google Sheets read/write operations
│   ├── auth.py                # Login and role-based access
│   ├── leave_calc.py          # Leave balance calculations
│   └── pdf_generator.py       # Payslip PDF generation
├── assets/
│   └── payslips/               # Generated payslip PDFs (runtime data)
├── NOTES.local.md              # Personal dev notes (not committed to Git)
├── SESSION.md                  # Development progress log
└── README.md                   # This file
```

---

## Local Setup

1. Clone the repo and create a virtual environment

   ```bash
   python -m venv venv
   source venv/bin/activate       # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Set up a Google service account

   - In Google Cloud Console, create a project and enable the Google Sheets API and Google Drive API
   - Create a service account and download the JSON key file
   - Open the target Google Sheet and share it with the service account's email (the `client_email` field in the JSON) as an **Editor**

3. Configure secrets

   - Local: put the service account info in `.streamlit/secrets.toml` (this file is not committed to Git)
   - Streamlit Cloud deployment: paste the same content into the app's "Secrets" settings

4. Run locally

   ```bash
   streamlit run app.py
   ```

---

## Data Model

The Google Sheets file (`HR_System_Database`) contains the following tabs — see the design doc for full field details:

- `Employees`
- `LeaveRequests`
- `LeaveBalances`
- `Payslips`
- `RateConfig`

Enum values (leave types, status values, etc.) are tracked in `NOTES.local.md` (not committed to Git, personal reference only).

---

## Deployment

Push to a private GitHub repo, then connect it on [Streamlit Community Cloud](https://share.streamlit.io) for one-click deployment, with `app.py` as the entry point.

---

## Security Notes

- `credentials/`, `.streamlit/secrets.toml`, and `NOTES.local.md` are all listed in `.gitignore` — never force-commit them
- Employee passwords are stored as encrypted hashes, never in plaintext
- Bank account details are only fully visible to the `hr_admin` role

---

## Progress

See [`SESSION.md`](./SESSION.md).
