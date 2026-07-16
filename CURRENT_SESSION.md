# Development Progress Log (Session Log)

> Add a new entry below each time you wrap up a work session. This makes it easy
> to pick up where you left off, especially after a long break.

---

## Template (copy this to start a new entry)

```
## YYYY-MM-DD

### Completed
-

### Issues / stuck points
-

### Next steps
-

### Notes
-
```

---

## Progress Overview (check off as each milestone is done, matches README setup steps)

- [ ] Google Cloud project + service account created
- [ ] Google Sheets tabs created (Employees / LeaveRequests / LeaveBalances / Payslips / RateConfig)
- [ ] Local Python environment set up
- [ ] `sheets_client.py` can successfully read/write Sheets (first key milestone)
- [ ] Login page + role-based access control
- [ ] Employee management page
- [ ] Leave management page
- [ ] Payslip management page (incl. EPF/SOCSO/EIS auto-calculation)
- [ ] Full local test of all three modules' main flows
- [ ] Deployed to Streamlit Community Cloud
- [ ] 3-5 person pilot test
- [ ] Officially launched

---

## Log

## 2026-07-07

### Completed
- Decided on tech stack: Streamlit + Google Sheets
- Completed overall design doc (architecture, data model, module design, deployment plan)
- Decided on login approach: HR sets initial passwords, employees are forced to change on first login
- Decided EPF/SOCSO/EIS and leave balance calculations happen entirely in the Python layer; Sheets only stores final results
- Set up project file structure (README / NOTES.local / SESSION)

### Issues / stuck points
- None yet (code hasn't started)

### Next steps
- Create Google Cloud project, enable APIs, generate service account key
- Set up Google Sheets tabs and fill in test data
- Get `sheets_client.py` working — hit the first milestone of successfully reading test data

### Notes
-
