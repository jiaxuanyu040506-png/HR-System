import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login, hash_password
from utils.leave_calc import get_leave_summary, recalculate_year_balance, init_year_balance
from utils.sheets_client import read_table, append_row, update_row, delete_row
from utils.employee_lifecycle import delete_employee_and_all_data


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
GENDER = ["Female", "Male"]

if role != "hr_admin" and role != "manager":
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
        display_cols = [c for c in ["employee_id", "name", "email", "department", "status", "role"]
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
        custom_id = st.text_input("Employee ID", placeholder="e.g. LH-ABC")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number")
        col1, col2 = st.columns(2)
        department = col1.selectbox("Department", DEPARTMENTS)
        gender = col2.selectbox("Gender", GENDER)
        address = st.text_area("Address")
        col3, col4 = st.columns(2)
        dob = col3.date_input("Date of Birth", value=date(1990, 1, 1), min_value=MIN_DATE, max_value=MAX_DATE)
        join_date = col4.date_input("Join Date", value=date.today(), min_value=MIN_DATE, max_value=MAX_DATE)
        col5, col6 = st.columns(2)
        income_tax_no = col5.text_input("Income Tax No.")
        epf_no = col6.text_input("EPF No.")
        ic_no = st.text_input("I/C No.")
        # admin_email = st.text_input("Admin/Manager Email (leave blank if none)")
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
                "gender": gender,
                "address": address,
                "date_of_birth": str(dob),
                "join_date": str(join_date),
                "income_tax_no": income_tax_no,
                "epf_no": epf_no,
                "ic_no": ic_no,
                "status": "Active",
                # "admin_email": admin_email,
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
            edit_id = st.text_input("Employee ID", value=str(employee.get("employee_id", "")))
            edit_name = st.text_input("Full Name", value=str(employee.get("name", "")))
            edit_email = st.text_input("Email", value=str(employee.get("email", "")))
            edit_phone = st.text_input("Phone Number", value=str(employee.get("phone", "")))
            col1, col2 = st.columns(2)
            dept_value = str(employee.get("department", DEPARTMENTS[0]))
            edit_department = col1.selectbox(
                "Department", DEPARTMENTS,
                index=DEPARTMENTS.index(dept_value) if dept_value in DEPARTMENTS else 0,
            )
            gender_value = str(employee.get("gender", GENDER[0]))
            edit_gender = col2.selectbox(
                "Gender", GENDER,
                index=GENDER.index(gender_value) if gender_value in GENDER else 0,
            )
            edit_address = st.text_area("Address", value=str(employee.get("address", "")))
            col3, col4 = st.columns(2)
            edit_status = col3.selectbox(
                "Status", ["Active", "Resigned"],
                index=0 if str(employee.get("status", "Active")) == "Active" else 1,
            )
            edit_role = col4.selectbox(
                "Role", ["employee", "manager", "hr_admin"],
                index=["employee", "manager", "hr_admin"].index(str(employee.get("role", "employee"))),
            )
            col5, col6 = st.columns(2)
            edit_income_tax_no = col5.text_input("Income Tax No.", value=str(employee.get("income_tax_no", "")))
            edit_epf_no = col6.text_input("EPF No.", value=str(employee.get("epf_no", "")))
            edit_ic_no = st.text_input("I/C No.", value=str(employee.get("ic_no", "")))
            # edit_admin = st.text_input("Admin/Manager Email", value=str(employee.get("admin_email", "")))
            edit_bank = st.text_input("Bank Account", value=str(employee.get("bank_account", "")))
            save = st.form_submit_button("Save Changes", use_container_width=True)

        if save:
            update_row(
                "Employees",
                {"employee_id": employee["employee_id"]},
                {
                    "employee_id": edit_id,
                    "name": edit_name,
                    "email": edit_email,
                    "phone": edit_phone,
                    "department": edit_department,
                    "gender": edit_gender,
                    "address": edit_address,
                    "status": edit_status,
                    "role": edit_role,
                    "income_tax_no": edit_income_tax_no,
                    "epf_no": edit_epf_no,
                    "ic_no": edit_ic_no,
                    # "admin_email": edit_admin,
                    "bank_account": edit_bank,
                },
            )
            st.session_state.pop("edit_employee_id", None)
            st.success("Employee updated.")
            st.rerun()

        # Updated 17 July
        year = date.today().year
        summary = get_leave_summary(employee["employee_id"], year)
        st.html("<div style='height:18px'></div>")

        st.html(
            f"""
            <div style="
                font-size:1.15rem;
                font-weight:700;
                color:#172033;
                margin-bottom:10px;
            ">
                Leave Balance · {year}
            </div>
            """
        )

        annual_total = float(summary["annual_total"])
        annual_used = float(summary["annual_used"])
        annual_remaining = (annual_total - annual_used)

        medical_total = float(summary["medical_total"])
        medical_used = float(summary["medical_used"])
        medical_remaining = (medical_total - medical_used)

        unpaid_used = float(summary.get("unpaid_used", 0))

        # BALANCE CARDS
        b1, b2, b3 = st.columns(3)
        with b1:
            annual_progress = (max( 0, min(100, (annual_used / annual_total * 100) if annual_total > 0 else 0,),))
            st.html(
                f"""
                <div class="balance-card">

                    <div class="balance-card-title">
                        🏖️ Annual Leave
                    </div>

                    <div class="balance-number">
                        {annual_remaining:g}
                    </div>

                    <div class="balance-label">
                        days remaining
                    </div>

                    <div class="balance-detail">
                        {annual_used:g} used
                        ·
                        {annual_total:g} total
                    </div>

                    <div class="balance-progress">
                        <div style="
                            width:{annual_progress:.1f}%;
                            height:100%;
                            background:#5b8def;
                            border-radius:999px;
                        "></div>
                    </div>

                </div>
                """
            )

        with b2:
            medical_progress = (max(0, min(100, (medical_used / medical_total * 100) if medical_total > 0 else 0, ),))
            st.html(
                f"""
                <div class="balance-card">

                    <div class="balance-card-title">
                        🩺 Medical Leave
                    </div>

                    <div class="balance-number">
                        {medical_remaining:g}
                    </div>

                    <div class="balance-label">
                        days remaining
                    </div>

                    <div class="balance-detail">
                        {medical_used:g} used
                        ·
                        {medical_total:g} total
                    </div>

                    <div class="balance-progress">
                        <div style="
                            width:{medical_progress:.1f}%;
                            height:100%;
                            background:#f28c8c;
                            border-radius:999px;
                        "></div>
                    </div>

                </div>
                """
            )

        with b3:
            st.html(
                f"""
                <div class="balance-card">

                    <div class="balance-card-title">
                        💼 Unpaid Leave
                    </div>

                    <div class="balance-number">
                        {unpaid_used:g}
                    </div>

                    <div class="balance-label">
                        days used
                    </div>

                    <div class="balance-detail">
                        No annual entitlement
                    </div>

                    <div class="balance-progress">
                        <div style="
                            width:100%;
                            height:100%;
                            background:#94a3b8;
                            border-radius:999px;
                            opacity:0.55;
                        "></div>
                    </div>

                </div>
                """
            )

        if st.button("🔄 Recalculate this year's leave balance", key="recalc_balance_btn"):
            recalculate_year_balance(employee["employee_id"], year)
            st.success("Recalculated using the current entitlement rules.")
            st.rerun()
        st.caption(
            "Use this if the annual/medical days shown look wrong — e.g. after the "
            "proration or probation rules were updated, since existing balances "
            "aren't recalculated automatically."
        )

        st.divider()
        with st.expander("🗑️ Delete this employee record (testing / data-entry mistakes only)"):
            st.warning(
                "This permanently removes the employee AND all their linked data: "
                "leave requests, leave balances, payslips, attendance, performance "
                "records, and EA Forms. This cannot be undone. For a real departure, "
                "use 'Mark as Resigned' via the Status field above instead — that "
                "keeps their history intact."
            )
            confirm = st.checkbox(f"Yes, permanently delete {employee['name']} and ALL their data", key="confirm_delete_employee")
            if st.button("Delete Employee", disabled=not confirm, key="delete_employee_btn"):
                deleted_summary = delete_employee_and_all_data(employee["employee_id"])
                st.session_state.pop("edit_employee_id", None)
                details = ", ".join(f"{k}: {v}" for k, v in deleted_summary.items() if v)
                st.success(f"Employee and all linked data deleted. ({details or 'no linked records found'})")
                st.rerun()