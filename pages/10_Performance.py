import streamlit as st
import pandas as pd
from datetime import date

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.performance import (
    get_all_performance_records,
    delete_performance_record,
    update_performance_record,
    get_companies,
    add_company,
    calculate_due_date,
    get_due_date_with_completion_rollover,
    submit_performance_record,
    update_company,
    CATEGORIES,
)

# INITIALIZE
inject_css()
require_role(["hr_admin", "manager"])
render_nav_sidebar(st.session_state["role"])

st.title("📌 Work Performance")
st.caption("Log employee performance records and track completion history.")
employees = read_table("Employees")

# MAIN TABS
tab_log, tab_performance = st.tabs(["📝 Log Record", "📊 Employee Performance"])

# LOG RECORD
with tab_log:
    st.html("<div style='height:8px'></div>")
    st.html(
        """
        <div class="dashboard-section-title">
            Log Performance Record
        </div>
        """)

    st.caption("Assign a company to an employee and record its completion status.")

    # COMPANY INFORMATION
    with st.container(border=True):
        st.markdown("#### 🏢 Company Information")
        companies = get_companies()
        if not companies:
            st.warning("No companies have been added yet. Please add a company under Manage Records.")
        else:
            category = st.selectbox("Company Type", CATEGORIES, key="perf_category",)
            matching = [c for c in companies if c.get("category") == category]
            company_names = [c["company_name"] for c in matching]
            if not company_names:
                st.info("No companies have been added under this category yet.")
            else:
                selected_company = st.selectbox("Company Name", company_names, key="selected_company",)
                company_info = next(c for c in matching if c["company_name"] == selected_company)
                due_date_ = get_due_date_with_completion_rollover(company_name = selected_company,
                                                                  company_type = company_info["category"], 
                                                                  year = date.today().year, 
                                                                  year_end = company_info.get("year_end"),)
                st.html(
                    f"""
                    <div class="deadline-box">
                        <div class="deadline-label">PERFORMANCE DEADLINE</div>
                        <div class="deadline-date">📅 {due_date_.strftime('%d %b %Y')}</div>
                    </div>
                    """)

    # EMPLOYEE & COMPLETION
    if companies and company_names:
        st.html('<div class="spacer-sm"></div>')
        with st.container(border=True):
            st.markdown("#### 👤 Employee & Completion")
            emp_names = (employees["name"].tolist() if not employees.empty else [])

            if not emp_names:
                st.warning("No employees found.")
            else:
                selected_emp_name = st.selectbox("Responsible Employee", emp_names, key = "performance_employee_name",)
                status_choice = st.radio("Completion Status", ["Pending", "Completed"], horizontal = True, key = "performance_status",)

                completion_date_ = None
                if status_choice == "Completed":
                    completion_date_ = st.date_input("Completion Date", value = date.today(),
                                                     key = "performance_completion_date", help = "Enter the date when the work was completed.",)
                else:
                    st.html(
                        """
                        <div class="notice-box">
                            ⏳ This company is currently assigned to this employee but has not been completed yet.
                        </div>
                        """)

                st.html("<div style='height:8px'></div>")
                if st.button("Log Performance", use_container_width = True, key = "log_performance_btn",):
                    emp_row = employees[employees["name"] == selected_emp_name].iloc[0]
                    submit_performance_record(
                        selected_company, category,
                        emp_row["employee_id"], selected_emp_name,
                        due_date_, completion_date_,)

                    if status_choice == "Completed":
                        st.success(f"Performance record for {selected_emp_name} has been completed.")
                    else:
                        st.success(f"{selected_company} has been assigned to {selected_emp_name} as Pending.")
                    st.rerun()

    # MANAGE RECORDS
    st.html("<div style='height:26px'></div>")
    st.html(
        """
        <div class="dashboard-section-title">
            Manage Records
        </div>
        """
    )
    st.caption("Manage companies and existing performance records.")
    manage_add, manage_edit_company, manage_edit_record, manage_delete = st.columns(4, gap="medium")

    # ADD COMPANY
    with manage_add:
        with st.expander("➕ Add Company", expanded=False):
            st.caption("Add a new company under the selected company type.")
            new_company_name = st.text_input("Company Name", key = "new_company_name",)
            new_category = st.selectbox("Company Type", CATEGORIES, key = "new_company_category",)
            new_year_end = None
            if new_category == "Private Limited":
                new_year_end = st.text_input("Year End", placeholder = "31-Jan",
                                             key = "new_company_year_end", help = "Example: 31-Jan",)
            if st.button("Add Company", use_container_width = True, key = "add_company_btn",):
                if not new_company_name.strip():
                    st.error("Please enter a company name.")
                else:
                    add_company(new_company_name.strip(), new_category, new_year_end,)
                    st.success(f"{new_company_name.strip()} has been added.")
                    st.rerun()

    # EDIT COMPANY
    with manage_edit_company:
        with st.expander("✏️ Edit Company", expanded=False):
            st.caption("Update company information.")

            companies = get_companies()

            if not companies:
                st.info("No companies available.")
            else:
                company_options = {company["company_name"]: company for company in companies}

                selected_edit_company = st.selectbox("Select Company", list(company_options.keys()), key="edit_company_selection",)
                selected_company_info = company_options[selected_edit_company]
                edit_company_name = st.text_input("Company Name", value=selected_company_info.get("company_name", ""), key="edit_company_name",)

                company_categories = CATEGORIES
                current_category = selected_company_info.get("category", "")
                edit_company_category = st.selectbox("Company Type", company_categories,
                                                      index=(company_categories.index(current_category) if current_category in company_categories else 0),
                                                      key="edit_company_category",)
                edit_company_year_end = None
                if edit_company_category == "Private Limited":
                    edit_company_year_end = st.text_input("Year End", value=selected_company_info.get("year_end", "") or "",
                                                          placeholder="31-Jan", key="edit_company_year_end", help="Example: 31-Jan",)
                if st.button("Save Changes",type="primary", use_container_width=True, key="save_company_edit_btn",):
                    if not edit_company_name.strip():
                        st.error("Please enter a company name.")
                    elif (edit_company_category == "Private Limited" and not edit_company_year_end.strip()):
                        st.error("Please enter the financial year end.")
                    else:
                        success = update_company(old_company_name=selected_edit_company, company_name=edit_company_name.strip(),
                                                 category=edit_company_category, year_end=(edit_company_year_end.strip() if edit_company_category == "Private Limited" else None),)
                        if success:
                            st.success(f"{edit_company_name.strip()} has been updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update company.")

    # EDIT RECORD
    with manage_edit_record:
        with st.expander("✏️ Edit Record", expanded=False):
            st.caption("Update an existing performance record.")

            records = get_all_performance_records()
            if records.empty:
                st.info("No performance records available.")
            else:
                record_options = {(f"{row['company_name']} - {row['employee_name']} ({row['record_id']})"): row["record_id"] for _, row in records.iterrows()}
                selected_record_label = st.selectbox("Select Record", list(record_options.keys()), key = "edit_performance_record",)
                selected_record_id = record_options[selected_record_label]
                if st.button("Edit Record", use_container_width = True, key = "edit_record_btn",):
                    st.session_state["editing_performance_record"] = selected_record_id
                    st.rerun()

    # REMOVE RECORD
    with manage_delete:
        with st.expander("🗑 Remove Record", expanded=False):
            st.caption("Remove an incorrect performance record.")

            records = get_all_performance_records()
            if records.empty:
                st.info("No performance records available.")
            else:
                record_options_delete = {f"{row['company_name']} - {row['employee_name']} ({row['record_id']})": row["record_id"] for _, row in records.iterrows()}
                selected_delete = st.selectbox("Select Record", list(record_options_delete.keys()), key = "delete_performance_record",)
                confirm_delete = st.checkbox("I understand this cannot be undone.", key = "confirm_performance_delete",)
                if st.button("Remove Record", type = "primary", use_container_width = True, key = "remove_record_btn", disabled = not confirm_delete,):
                    record_id = record_options_delete[selected_delete]
                    if delete_performance_record(record_id):
                        st.success("Performance record removed.")
                        st.rerun()
                    else:
                        st.error("Failed to remove the performance record.")

    # EDIT FORM
    if "editing_performance_record" in st.session_state:
        editing_id = st.session_state["editing_performance_record"]
        records = get_all_performance_records()
        editing_rows = records[records["record_id"].astype(str) == str(editing_id)]
        if not editing_rows.empty:
            editing_row = editing_rows.iloc[0]
            st.html('<div class="spacer-md"></div>')
            with st.container(border=True):
                st.markdown("#### ✏️ Update Performance Record")
                st.caption(f"Record ID: {editing_id}")

                # CATEGORY
                edit_companies = get_companies()
                current_category = str(editing_row.get("category", ""))
                edit_category = st.selectbox("Company Type", CATEGORIES, 
                                             index = (CATEGORIES.index(current_category) if current_category in CATEGORIES else 0),
                                             key = "edit_category",)
                edit_matching = [c for c in edit_companies if c.get("category") == edit_category]
                edit_company_names = [c["company_name"] for c in edit_matching]
                if edit_company_names:
                    current_company = str(editing_row.get("company_name", ""))
                    company_index = (edit_company_names.index(current_company) if current_company in edit_company_names else 0)
                    edit_company = st.selectbox("Company Name", edit_company_names, index = company_index, key = "edit_company",)
                    edit_company_info = next(c for c in edit_matching if c["company_name"] == edit_company)
                    edit_due_date = calculate_due_date(edit_category, date.today().year, edit_company_info.get("year_end"),)
                    st.html(
                        f"""
                        <div class="deadline-inline-box">
                            <span class="deadline-inline-label">Updated Deadline</span>
                            <br>
                            <strong class="deadline-inline-date">📅 {edit_due_date.strftime('%d %b %Y')}</strong>
                        </div>
                        """
                    )

                    # EMPLOYEE
                    emp_names_edit = (employees["name"].tolist() if not employees.empty else [])
                    current_employee = str(editing_row.get("employee_name", ""))
                    employee_index = (emp_names_edit.index(current_employee) if current_employee in emp_names_edit else 0)
                    edit_employee = st.selectbox("Responsible Employee", emp_names_edit, index = employee_index, key = "edit_employee",)

                    # STATUS
                    current_status = str(editing_row.get("status", "Pending"))
                    edit_status = st.selectbox("Status", ["Pending", "Completed"], index=(1 if current_status in ["On Time", "Late"] else 0), key="edit_status",)

                    # COMPLETION DATE
                    edit_completion_date = None
                    if edit_status == "Completed":
                        current_completion = editing_row.get("completion_date", None,)
                        try:
                            if (current_completion and str(current_completion) != "nan"):
                                completion_value = date.fromisoformat(str(current_completion))
                            else:
                                completion_value = date.today()

                        except Exception:
                            completion_value = date.today()

                        edit_completion_date = st.date_input("Completion Date", value = completion_value, key = "edit_completion_date",)

                    else:
                        st.html(
                            """
                            <div class="info-note warning-note">
                                ⏳ This record will remain
                                <strong>Pending</strong>.
                                No completion date is required.
                            </div>
                            """
                        )

                    # BUTTONS
                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        save_edit = st.button("Save Changes", type = "primary", use_container_width = True, key = "save_performance_edit",)
                    with cancel_col:
                        cancel_edit = st.button("Cancel", use_container_width = True, key = "cancel_performance_edit",)
                    if cancel_edit:
                        st.session_state.pop("editing_performance_record", None,)
                        st.rerun()
                    if save_edit:
                        employee_row = employees[employees["name"] == edit_employee].iloc[0]
                        success = update_performance_record(
                            record_id = editing_id,
                            company_name = edit_company,
                            category = edit_category,
                            employee_id = employee_row["employee_id"],
                            employee_name = edit_employee,
                            due_date = edit_due_date,
                            completion_date = edit_completion_date,)
                        if success:
                            st.session_state.pop("editing_performance_record", None,)
                            st.success("Performance record updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update performance record.")
                else:
                    st.warning("No companies are available for this category.")

# PERFORMANCE TAB
with tab_performance:
    st.html("<div style='height:8px'></div>")
    st.html(
        """
        <div class="dashboard-section-title">
            Employee Performance
        </div>
        """)
    st.caption("View the companies assigned to an employee and their completion status.")
    if employees.empty:
        st.info("No employees found.")
    else:
        emp_names = employees["name"].tolist()                      # EMPLOYEE SELECTOR
        selected_employee = st.selectbox("Select Employee", emp_names, key = "performance_employee",)
        st.html('<div class="spacer-xs"></div>')

        all_records = get_all_performance_records()                  # GET EMPLOYEE RECORDS
        if all_records.empty:
            employee_records = all_records
        else:
            employee_records = all_records[all_records["employee_name"] == selected_employee].copy()

        total_records = len(employee_records)                         # SUMMARY
        done_records = len(employee_records[employee_records["status"] == "On Time"])
        late_records = len(employee_records[employee_records["status"] == "Late"])
        pending_records = len(employee_records[employee_records["status"] == "Pending"])
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.html(
                f"""
                <div class="dashboard-summary-card">
                    <div class="dashboard-card-label">🏢 Total Records</div>
                    <div class="dashboard-card-value">{total_records}</div>
                    <div class="dashboard-card-sub">companies assigned</div>
                </div>
                """
            )
        with c2:
            st.html(
                f"""
                <div class="dashboard-summary-card">
                    <div class="dashboard-card-label">✅ Done</div>
                    <div class="dashboard-card-value">{done_records}</div>
                    <div class="dashboard-card-sub">completed on time</div>
                </div>
                """
            )
        with c3:
            st.html(
                f"""
                <div style="
                    border:1px solid #e2e8f0;
                    border-radius:14px;
                    padding:18px 20px;
                    background:#ffffff;
                    min-height:120px;
                    box-shadow:0 2px 8px rgba(15,23,42,0.03);
                ">
                    <div style="
                        font-size:0.9rem;
                        color:#64748b;
                        font-weight:600;
                        margin-bottom:10px;
                    ">
                        ⚠️ Late
                    </div>

                    <div style="
                        font-size:1.9rem;
                        font-weight:700;
                        color:#172033;
                        line-height:1.1;
                    ">
                        {late_records}
                    </div>

                    <div style="
                        font-size:0.82rem;
                        color:#64748b;
                        margin-top:7px;
                    ">
                        completed after deadline
                    </div>
                </div>
                """
            )

        with c4:
            st.html(
                f"""
                <div class="dashboard-summary-card">
                    <div class="dashboard-card-label">⏳ Pending</div>
                    <div class="dashboard-card-value">{pending_records}</div>
                    <div class="dashboard-card-sub">still outstanding</div>
                </div>
                """
            )
            
        # COMPANY LIST
        st.html("<div style='height:26px'></div>")
        st.html(
            """
            <div class="dashboard-section-title">
                Company Performance
            </div>
            """)
        st.caption("Filter the employee's assigned companies by completion status.")

        if employee_records.empty:
            st.info(f"No performance records found for {selected_employee}.")
        else:
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                filter_category = st.selectbox(
                    "Filter Company Type",
                    ["All"] + CATEGORIES,
                    key="performance_category_filter",
                )

            with filter_col2:
                filter_status = st.selectbox(
                    "Filter Status",
                    ["All", "Pending", "Done", "Late"],
                    key="performance_status_filter",
                )

            filtered_records = employee_records.copy()

            # MAP COMPANY TYPE FROM COMPANY NAME
            companies = get_companies()

            company_category_map = {
                company["company_name"]: company.get("category", "")
                for company in companies
            }

            filtered_records["company_type"] = filtered_records["company_name"].map(
                company_category_map
            )

            # FILTER BY COMPANY TYPE
            if filter_category != "All":
                filtered_records = filtered_records[
                    filtered_records["company_type"] == filter_category
                ]

            # FILTER BY STATUS
            if filter_status == "Pending":
                filtered_records = filtered_records[
                    filtered_records["status"] == "Pending"
                ]
            elif filter_status == "Done":
                filtered_records = filtered_records[
                    filtered_records["status"] == "On Time"
                ]
            elif filter_status == "Late":
                filtered_records = filtered_records[
                    filtered_records["status"] == "Late"
                ]

            # DISPLAY
            if filtered_records.empty:
                st.info(f"No {filter_status.lower()} records found for {selected_employee}.")
            else:
                for _, row in filtered_records.iterrows():
                    status = str(row.get("status", "Pending"))
                    if status == "On Time":
                        status_text = "✅ Done"
                    elif status == "Late":
                        status_text = "⚠️ Late"
                    else:
                        status_text = "⏳ Pending"

                    company_name = str(row.get("company_name", "-"))
                    due_date = str(row.get("due_date", "-"))
                    completion_date = row.get("completion_date", "",)
                    if (pd.isna(completion_date) if "pd" in globals() else str(completion_date) in ["", "nan", "None"]):
                        completion_date = "-"
                    if str(completion_date) in ["", "nan", "None",]:

                        completion_date = "-"

                    st.html(
                        f"""
                        <div class="dashboard-request-card">
                            <div style="display:flex; justify-content:space-between; align-items:center; gap:15px;">
                                <div style="min-width:0; flex:1;">
                                    <div class="dashboard-request-title">{company_name}</div>
                                    <div class="dashboard-request-date">Due: {due_date} &nbsp;&nbsp;•&nbsp;&nbsp; Completed: {completion_date}</div>
                                </div>
                                <div style="white-space:nowrap; font-size:0.88rem; font-weight:600;">{status_text}</div>
                            </div>
                        </div>
                        """
                    )