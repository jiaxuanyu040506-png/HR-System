import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table
from utils.payroll_calc import calculate_payslip
from utils.pdf_generator import generate_payslip_pdf_bytes

inject_css()
require_role(["hr_admin"])
render_nav_sidebar(st.session_state["role"])
st.title("Payroll Management")

employees = read_table("Employees")
payslips = read_table("Payslips")

current_month = date.today().strftime("%Y-%m")
this_month_slips = payslips[payslips["month"] == current_month] if not payslips.empty else payslips
total_payroll = this_month_slips["net_pay"].astype(float).sum() if not this_month_slips.empty else 0.0

c1, c2, c3 = st.columns(3)
c1.metric(f"Total Payroll ({current_month})", f"RM {total_payroll:,.2f}")
c2.metric("Payroll Status", "Ready" if not this_month_slips.empty else "Not generated")
c3.metric("Employees Paid This Month", len(this_month_slips))
st.caption(
    "'Payroll Status' and 'Payment Date' are placeholders — there's no real "
    "approval/release workflow built yet. Let me know if you want that added."
)

st.divider()
st.subheader("Generate Payslip")
st.caption(
    "EPF / SOCSO / BBK / EIS are calculated automatically from the rate tables. "
    "PCB is NOT auto-calculated — enter the figure from LHDN's e-PCB calculator."
)

if employees.empty:
    st.caption("No employees found yet.")
else:
    name_to_id = dict(zip(employees["name"], employees["employee_id"]))

    with st.form("payslip_form"):
        selected_name = st.selectbox("Employee", list(name_to_id.keys()))
        month = st.text_input("Month (YYYY-MM)", placeholder="2026-07")
        basic_salary = st.number_input("Basic salary (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
        allowance = st.number_input("Allowance (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
        pcb = st.number_input("PCB (RM)", min_value=0.0, step=1.0, value=None, placeholder="0.00")
        submitted = st.form_submit_button("Calculate & Save")

    if submitted:
        emp_id = name_to_id[selected_name]
        employee = employees[employees["employee_id"] == emp_id].iloc[0].to_dict()
        try:
            payslip = calculate_payslip(
                emp_id, employee["name"], month,
                basic_salary or 0.0, allowance or 0.0,
                employee["date_of_birth"], pcb or 0.0,
            )
            st.success(f"Payslip saved for {employee['name']} — Net pay: RM {payslip['net_pay']:.2f}")
            pdf_bytes = generate_payslip_pdf_bytes(employee, payslip)
            st.download_button("Download PDF", pdf_bytes,
                                file_name=f"{employee['name']}_{month}.pdf", mime="application/pdf")
        except ValueError as e:
            st.error(str(e))

st.divider()
st.subheader("Payroll History")
if payslips.empty:
    st.caption("No payslips generated yet.")
else:
    summary = payslips.groupby("month").agg(
        employees=("employee_id", "count"),
        total_amount=("net_pay", lambda s: s.astype(float).sum()),
    ).reset_index().sort_values("month", ascending=False)
    st.dataframe(summary, use_container_width=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    with st.expander("🗑️ Delete a payslip record (testing / data-entry mistakes only)"):
        st.warning("This permanently removes the row from the Payslips sheet.")
        options = {}
        for _, row in payslips.iterrows():
            label_name = row.get("employee_name") or row.get("employee_id", "Unknown")
            month_label = row.get("month", "-")
            try:
                net_pay_val = float(row.get("net_pay", 0) or 0)
            except (ValueError, TypeError):
                net_pay_val = 0.0
            options[f"{label_name} — {month_label} (RM {net_pay_val:.2f})"] = row.get("payslip_id", "")
        selected_label = st.selectbox("Select payslip", list(options.keys()), key="delete_payslip_select")
        confirm = st.checkbox("Yes, permanently delete this payslip", key="confirm_delete_payslip")
        if st.button("Delete Payslip", disabled=not confirm, key="delete_payslip_btn"):
            from utils.sheets_client import delete_row
            delete_row("Payslips", {"payslip_id": options[selected_label]})
            st.success("Payslip deleted.")
            st.rerun()