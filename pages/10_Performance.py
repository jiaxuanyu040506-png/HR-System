import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.dashboard import render_performance_chart
from utils.performance import get_all_performance_records, delete_performance_record, get_companies, add_company, calculate_due_date, submit_performance_record, \
    CATEGORIES, COMPANY_TYPES

inject_css()
require_role(["hr_admin"])
render_nav_sidebar(st.session_state["role"])
st.title("📌 Log Work Performance")

employees = read_table("Employees")

section = st.radio(
    "Section", ["Log Record", "Performance"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

# Updated 24 July, 2026
if section == "Log Record":

    companies = get_companies()
    category = st.selectbox("Company Type", CATEGORIES, key="perf_category")

    matching = [c for c in companies if c.get("category") == category]
    company_names = [c["company_name"] for c in matching]

    if company_names:
        selected_company = st.selectbox("Company Name", company_names, key="selected_company")

        # immediately update
        company_info = next(c for c in matching if c["company_name"] == selected_company)
        due_date_ = calculate_due_date(company_info["category"], date.today().year, company_info.get("year_end"))
        st.info(f"Deadline: {due_date_.strftime('%d %b %Y')}")

        with st.form("performance_form"):
            emp_names = (employees["name"].tolist() if not employees.empty else [])
            selected_emp_name = st.selectbox("Employee Name", emp_names)
            completion_date_ = st.date_input("Completion Date")
            submitted = st.form_submit_button("Log Record")

        if submitted:
            emp_row = employees[employees["name"] == selected_emp_name].iloc[0]
            submit_performance_record(
                selected_company, category, emp_row["employee_id"], selected_emp_name, due_date_, completion_date_
            )
            st.success("Recorded.")
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("➕ Add a new company"):
        new_company_name = st.text_input("New company name", key="new_company_name")
        
        year_end = None
        if category == "Private Limited":
            year_end = st.text_input("Year End (DD-MM)", placeholder = "31-Jan")

        if st.button("Add company"):
            if new_company_name.strip():
                add_company(new_company_name.strip(), category, year_end)
                st.success(f"Added {new_company_name}.")
                st.rerun()
            else:
                st.error("Enter a company name first.")

    with st.expander("🗑 Remove Previous Performance Record"):

        records = get_all_performance_records()

        if records.empty:
            st.info("No performance records.")

        else:

            record_options = {
                f"{row['company_name']} - {row['employee_name']} ({row['record_id']})":
                row["record_id"]
                for _, row in records.iterrows()
            }

            selected_record = st.selectbox("Select Record", record_options.keys())

            if st.button("Remove Record", type="primary"):
                record_id = record_options[selected_record]

                if delete_performance_record(record_id):
                    st.success("Record removed.")
                    st.rerun()
                else:
                    st.error("Failed to remove record.")

else:
    emp_names = employees["name"].tolist()
    selected_employee = st.selectbox(
        "Select Employee",
        emp_names
    )
    render_performance_chart(selected_employee)