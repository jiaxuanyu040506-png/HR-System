import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login, hash_password
from utils.leave_calc import get_leave_balance, init_year_balance
from utils.sheets_client import read_table, append_row, update_row, delete_row

inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])
st.title("Employee Management")

role = st.session_state["role"]
df = read_table("Employees")

# Widened so long-tenured staff (company started in 1998) can pick their real dates.
MIN_DATE = date(1950, 1, 1)
MAX_DATE = date.today()

DEPARTMENTS = ["Secretary", "Service", "Account"]

if role != "hr_admin":
    st.subheader("Directory")
    display_cols = ["employee_id", "name", "email"]
    st.dataframe(df[display_cols] if not df.empty else df, use_container_width=True)
    st.caption("To update your own details, go to 'My Profile'.")
    st.stop()

tab_list, tab_add, tab_edit = st.tabs(["📋  Employee List", "➕  Add Employee", "✏️  Edit Employee"])

# ---------- Employee List ----------
with tab_list:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### All Employees")
    st.caption("Click a row to select an employee, then switch to the **Edit Employee** tab to update them.")

    if df.empty:
        st.caption("No employees found yet.")
    else:
        display_cols = [c for c in ["employee_id", "name", "email", "department", "status", "role", "admin_email"]
                         if c in df.columns]
        event = st.dataframe(
            df[display_cols],
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="employee_list_table",
        )
        selected_rows = event.selection["rows"] if event and event.selection else []
        if selected_rows:
            selected_employee_id = df.iloc[selected_rows[0]]["employee_id"]
            st.session_state["edit_employee_id"] = selected_employee_id
            selected_name = df.iloc[selected_rows[0]]["name"]
            st.success(f"Selected **{selected_name}** — go to the 'Edit Employee' tab to update their details.")

# ---------- Add Employee ----------
with tab_add:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### New Employee Details")
    with st.form("add_employee_form"):
        custom_id = st.text_input("Employee ID", placeholder="e.g. L001")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number")
        department = st.selectbox("Department", DEPARTMENTS)
        address = st.text_area("Address")
        col1, col2 = st.columns(2)
        dob = col1.date_input("Date of Birth", value=date(1990, 1, 1), min_value=MIN_DATE, max_value=MAX_DATE)
        join_date = col2.date_input("Join Date", value=date.today(), min_value=MIN_DATE, max_value=MAX_DATE)
        col3, col4 = st.columns(2)
        income_tax_no = col3.text_input("Income Tax No.")
        epf_no = col4.text_input("EPF No.")
        admin_email = st.text_input("Admin/Manager Email (leave blank if none)")
        bank_account = st.text_input("Bank Account")
        initial_password = st.text_input("Initial Password", value="Welcome123")
        emp_role = st.selectbox("Role", ["employee", "manager", "hr_admin"])
        submitted = st.form_submit_button("Create Employee", use_container_width=True)

    if submitted:
        if not custom_id.strip() or not name or not email:
            st.error("Employee ID, name, and email are required.")
        elif not df.empty and custom_id.strip() in df["employee_id"].values:
            st.error(f"Employee ID '{custom_id}' is already in use — pick a different one.")
        else:
            append_row("Employees", {
                "employee_id": custom_id.strip(),
                "name": name,
                "email": email,
                "phone": phone,
                "department": department,
                "address": address,
                "date_of_birth": str(dob),
                "join_date": str(join_date),
                "income_tax_no": income_tax_no,
                "epf_no": epf_no,
                "status": "Active",
                "admin_email": admin_email,
                "bank_account": bank_account,
                "password_hash": hash_password(initial_password),
                "force_password_reset": "Yes",
                "role": emp_role,
            })
            st.success(f"Employee {name} added with ID {custom_id}. "
                       f"Tell them their initial password: {initial_password}")
            st.rerun()

# ---------- Edit Employee ----------
with tab_edit:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("#### Update Employee Details")

    if df.empty:
        st.caption("No employees found yet.")
    else:
        name_to_id = dict(zip(df["name"], df["employee_id"]))
        names = list(name_to_id.keys())

        # If an employee was clicked in the List tab, default to them here.
        default_index = 0
        preselected_id = st.session_state.get("edit_employee_id")
        if preselected_id and preselected_id in df["employee_id"].values:
            preselected_name = df[df["employee_id"] == preselected_id].iloc[0]["name"]
            if preselected_name in names:
                default_index = names.index(preselected_name)

        selected_name = st.selectbox("Select employee to edit", names, index=default_index)
        employee = df[df["name"] == selected_name].iloc[0]

        with st.form("edit_employee_form"):
            edit_name = st.text_input("Full Name", value=str(employee.get("name", "")))
            edit_email = st.text_input("Email", value=str(employee.get("email", "")))
            edit_phone = st.text_input("Phone Number", value=str(employee.get("phone", "")))
            dept_value = str(employee.get("department", DEPARTMENTS[0]))
            edit_department = st.selectbox(
                "Department", DEPARTMENTS,
                index=DEPARTMENTS.index(dept_value) if dept_value in DEPARTMENTS else 0,
            )
            edit_address = st.text_area("Address", value=str(employee.get("address", "")))
            col1, col2 = st.columns(2)
            edit_status = col1.selectbox(
                "Status", ["Active", "Resigned"],
                index=0 if str(employee.get("status", "Active")) == "Active" else 1,
            )
            edit_role = col2.selectbox(
                "Role", ["employee", "manager", "hr_admin"],
                index=["employee", "manager", "hr_admin"].index(str(employee.get("role", "employee"))),
            )
            col3, col4 = st.columns(2)
            edit_income_tax_no = col3.text_input("Income Tax No.", value=str(employee.get("income_tax_no", "")))
            edit_epf_no = col4.text_input("EPF No.", value=str(employee.get("epf_no", "")))
            edit_admin = st.text_input("Admin/Manager Email", value=str(employee.get("admin_email", "")))
            edit_bank = st.text_input("Bank Account", value=str(employee.get("bank_account", "")))
            save = st.form_submit_button("Save Changes", use_container_width=True)

        if save:
            update_row(
                "Employees",
                {"employee_id": employee["employee_id"]},
                {
                    "name": edit_name,
                    "email": edit_email,
                    "phone": edit_phone,
                    "department": edit_department,
                    "address": edit_address,
                    "status": edit_status,
                    "role": edit_role,
                    "income_tax_no": edit_income_tax_no,
                    "epf_no": edit_epf_no,
                    "admin_email": edit_admin,
                    "bank_account": edit_bank,
                },
            )
            st.session_state.pop("edit_employee_id", None)
            st.success("Employee updated.")
            st.rerun()

        year = date.today().year
        balance = get_leave_balance(employee["employee_id"], year)
        if balance is None:
            st.warning(f"No leave balance row found for {year}. You can initialize it when needed.")
        else:
            annual_remaining = int(balance["annual_total"]) - float(balance["annual_used"])
            sick_remaining = float(balance["sick_balance"])
            st.markdown("#### Leave Balance (Current Year)")
            st.table({
                "Annual Total": [balance["annual_total"]],
                "Annual Used": [balance["annual_used"]],
                "Annual Remaining": [annual_remaining],
                "Sick Remaining": [sick_remaining],
            })

        st.divider()
        with st.expander("🗑️ Delete this employee record (testing / data-entry mistakes only)"):
            st.warning(
                "This permanently removes the row from the Employees sheet — it does NOT "
                "touch their leave/payslip history, which will be left pointing at a "
                "deleted employee. For a real departure, use 'Mark as Resigned' via the "
                "Status field above instead."
            )
            confirm = st.checkbox(f"Yes, permanently delete {employee['name']}", key="confirm_delete_employee")
            if st.button("Delete Employee", disabled=not confirm, key="delete_employee_btn"):
                delete_row("Employees", {"employee_id": employee["employee_id"]})
                st.session_state.pop("edit_employee_id", None)
                st.success("Employee record deleted.")
                st.rerun()
