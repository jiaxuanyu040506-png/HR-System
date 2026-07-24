# Quick Start

This walks through getting the HR System running from scratch: Google Cloud setup, local run, and day-to-day usage for HR and employees.

---

## 1. One-Time Google Cloud Setup

### 1.1 Create a project and a service account

1. Go to [Google Cloud Console](https://console.cloud.google.com), create a new project.
2. Enable **Google Sheets API** and **Google Drive API**.
3. Go to **IAM & Admin → Service Accounts → Create Service Account** (e.g. `hr-system-bot`).
4. Open the service account → **Keys** tab → **Add Key → Create new key → JSON**. This downloads a `.json` credentials file — keep it private, never commit it to Git.

> **If key creation fails with an organization policy error** (`iam.disableServiceAccountKeyCreation`): this is a Google security default for accounts under an organization. You (or your org's admin) need the **Organization Policy Administrator** role at the *organization* level, then go to **IAM & Admin → Organization Policies**, find that constraint, and set it to **Not enforced**. Wait a few minutes, then retry creating the key.

### 1.2 Create the main database spreadsheet

1. Create a new Google Sheet named exactly `HR_System_Database`.
2. Create the tabs listed in `README.md` → *Google Sheets Tabs Required*, with those exact column headers in row 1.
3. Open your service account's JSON file, copy the `client_email` value.
4. In the Sheet, click **Share**, paste that email, give it **Editor** access.

### 1.3 Create the rate config spreadsheet

1. Create a second Google Sheet named `SOCSO_EPF_RateConfig`, with `SOCSO`, `EPF`, `EPF_60` tabs.
2. These need **cleaned column names**, not the raw government format:
   - `EPF` / `EPF_60`: `salary_min, salary_max, employer_amount, employee_amount`
   - `SOCSO`: `salary_min, salary_max, cat1_employer, cat1_employee_keilatan, cat1_employee_skbbk, cat2_employer, cat2_employee_skbbk, eis_employer, eis_employee`
3. Share this Sheet with the same service account email as above.

### 1.4 Set up a Shared Drive (for EA Form uploads)

Service accounts have **zero storage quota** of their own — uploading a file directly always fails with `storageQuotaExceeded`. Files must go into a Shared Drive instead:

1. In Google Drive, create a **Shared Drive** (needs a Workspace plan that supports them — not available on free personal Gmail).
2. Add your service account's email as a **Content Manager** or higher.
3. Open the Shared Drive, copy its ID from the URL (`drive.google.com/drive/folders/<THIS PART>`).

If your account can't create a Shared Drive, EA Form upload won't work until you have one — everything else in the system works fine without it.

---

## 2. Local Setup

```bash
git clone <your-repo-url>
cd hr_system
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy the secrets template and fill it in:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Open `.streamlit/secrets.toml` and paste in:
- Every field from your downloaded service account JSON (under `[gcp_service_account]`)
- Your Shared Drive's folder ID as `drive_shared_folder_id`

Run it:

```bash
streamlit run app.py
```

---

## 3. First-Time Data Setup

1. In the `Employees` tab, manually add yourself as the first HR admin:
   - `status` = `Active`, `role` = `hr_admin`
   - `password_hash` — generate this with the included helper script:
     ```bash
     python generate_hash.py YourChosenPassword
     ```
     Paste the output string into `password_hash` (not the plain password).
   - `force_password_reset` = `No` (or `Yes` if you want to be prompted to change it on first login)
2. Log in with that account.
3. From here on, use **Employee Management → Add Employee** to add everyone else — it handles password hashing and initial leave balance setup automatically. Don't hand-edit the sheet for new employees; it's easy to miss a required field.

---

## 4. Deploying for the Whole Company

Push the repo to a **private** GitHub repository (it's fine that `secrets.toml` is gitignored — you'll set secrets separately on the host).

**Streamlit Community Cloud** (free, simplest):
1. Connect the repo at [share.streamlit.io](https://share.streamlit.io), set `app.py` as the entry point.
2. In the app's settings → **Secrets**, paste the entire contents of your local `secrets.toml`.
3. Share the resulting URL with employees.

Note: the free tier sleeps after inactivity — first load after a while takes a few seconds to wake up. For a non-sleeping deployment, run it on a small VM instead (e.g. `streamlit run app.py` behind Nginx on a $5/month box).

---

## 5. Day-to-Day Usage

### If you're HR
- **Dashboard** (HR System) — pending approvals, today's headcount on leave, quick links.
- **All Employees** — add/edit/delete staff. Deleting removes *all* their linked data (leave, payslips, attendance, etc.) — for someone who actually left, use **Mark as Resigned** instead, which keeps their history.
- **Leave Approvals** — approve/reject, see the company calendar, drill into any employee's leave history.
- **Attendance** — mark exceptions (Absent/Late/Half Day); everything else (Present, weekends, holidays, approved leave) fills in automatically. Download a month or a full year as Excel.
- **Payslips** — generate a payslip (EPF/SOCSO/SKBBK/EIS auto-calculated, PCB entered manually), review payroll history, upload each employee's annual EA Form.
- **Performance** — log which employee completed work for which client, and see who's completed the most.
- **Reports** — CSV exports of employee/leave/payroll data.

### If you're an employee (including HR admins, for their own records)
- **Dashboard** (My Workspace) — your remaining leave, latest payslip, quick access buttons.
- **My Leave** — apply for leave, see the company calendar, view your own history.
- **My Payslips** — download past payslips and your EA Form.
- **My Profile** — update your phone/address, change your password.

### If a balance looks wrong
Leave balances are calculated once when first created and **don't automatically update** if the underlying rules change later. If a number looks off (e.g. after a policy update), go to **Employee Management → Edit Employee** and click **🔄 Recalculate this year's leave balance** for that person.
