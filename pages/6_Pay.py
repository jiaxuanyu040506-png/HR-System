import streamlit as st
import pandas as pd
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login
from utils.sheets_client import read_table
from utils.pdf_generator import generate_payslip_pdf_bytes
from utils.ea_forms import get_ea_forms_for_employee, download_ea_form_bytes

inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])
st.title("Pay")

employees = read_table("Employees")
payslips = read_table("Payslips")
me = employees[employees["employee_id"] == st.session_state["employee_id"]]

if me.empty:
    st.error("Could not find your employee record.")
    st.stop()

my_employee = me.iloc[0].to_dict()
my_payslips = payslips[payslips["employee_id"] == st.session_state["employee_id"]] if not payslips.empty else payslips

c1, c2, c3 = st.columns(3)
if not my_payslips.empty:
    total_earnings = my_payslips["net_pay"].astype(float).sum()
    latest = my_payslips.sort_values("month", ascending=False).iloc[0]
    c1.metric("Total Earnings (YTD)", f"RM {total_earnings:,.2f}")
    c2.metric("Latest Payslip", latest["month"])
else:
    c1.metric("Total Earnings (YTD)", "RM 0.00")
    c2.metric("Latest Payslip", "—")
c3.metric("Next Payroll", "—")
st.caption("'Next Payroll' date isn't tracked yet — placeholder for now.")

st.divider()
st.subheader("Payslip History")
if my_payslips.empty:
    st.caption("No payslips yet.")
else:
    for idx, (_, row) in enumerate(my_payslips.sort_values("month", ascending=False).iterrows()):
        payslip = row.to_dict()
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{payslip['month']}** — Net pay: RM {float(payslip['net_pay']):.2f}")
            pdf_bytes = generate_payslip_pdf_bytes(my_employee, payslip)
            col2.download_button(
                "Download PDF", pdf_bytes,
                file_name=f"{my_employee['name']}_{payslip['month']}.pdf",
                mime="application/pdf",
                key=f"dl_{payslip['payslip_id']}_{idx}",
            )

st.divider()
st.subheader("EA Form")
my_ea_forms = get_ea_forms_for_employee(st.session_state["employee_id"])
if not my_ea_forms:
    st.caption("No EA Form uploaded by HR yet.")
else:
    for form in my_ea_forms:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**EA Form {form['year']}** — uploaded {form.get('uploaded_date', '')}")
        try:
            pdf_bytes = download_ea_form_bytes(form["drive_file_id"])
            col2.download_button(
                "Download", pdf_bytes,
                file_name=f"EA_{form['year']}_{my_employee['name']}.pdf",
                mime="application/pdf",
                key=f"ea_dl_{form['year']}",
            )
        except Exception:
            col2.error("Couldn't fetch file.")