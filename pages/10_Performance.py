import streamlit as st
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.dashboard import render_performance_chart
from utils.performance import get_companies, add_company, submit_performance_record, \
    CATEGORIES, COMPANY_TYPES

inject_css()
require_role(["hr_admin"])
render_nav_sidebar(st.session_state["role"])
st.title("📌 Log Work Performance")

employees = read_table("Employees")

section = st.radio(
    "Section", ["Log Record", "Performance — Completed Tasks by Employee"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

if section == "Log Record":
    companies = get_companies()
    category = st.selectbox("Company Type", CATEGORIES, key="perf_category")

    company_type = ""
    if category == "Normal Company":
        company_type = st.selectbox("Business Type", COMPANY_TYPES, key="perf_company_type")

    matching = [c for c in companies if c.get("category") == category]
    company_names = [c["company_name"] for c in matching]

    if not company_names:
        st.caption("No companies under this category yet — add one below.")
        selected_company = None
    else:
        with st.form("performance_form"):
            selected_company = st.selectbox("Company Name", company_names)
            emp_names = employees["name"].tolist() if not employees.empty else []
            selected_emp_name = st.selectbox("Employee Name", emp_names)
            col1, col2 = st.columns(2)
            due = col1.date_input("Due Date")
            not_done_yet = st.checkbox("Not completed yet", value=True)
            completion = None
            if not not_done_yet:
                completion = col2.date_input("Completion Date")
            submitted = st.form_submit_button("Log Record")

        if submitted:
            emp_row = employees[employees["name"] == selected_emp_name].iloc[0]
            submit_performance_record(
                selected_company, emp_row["employee_id"], selected_emp_name, due, completion
            )
            st.success("Recorded.")
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("➕ Add a new company"):
        new_company_name = st.text_input("New company name", key="new_company_name")
        if st.button("Add company"):
            if new_company_name.strip():
                add_company(new_company_name.strip(), category, company_type)
                st.success(f"Added {new_company_name}.")
                st.rerun()
            else:
                st.error("Enter a company name first.")

else:
    render_performance_chart()