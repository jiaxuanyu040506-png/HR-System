import streamlit as st
from utils.auth import require_login
from utils.sheets_client import read_table
from utils.ui import render_nav_sidebar
from utils.payroll_calc import calculate_payslip, preview_payslip
from utils.pdf_generator import generate_payslip_pdf_bytes

require_login()
render_nav_sidebar(st.session_state["role"])
st.title("Payslip Management")

role = st.session_state["role"]
employees = read_table("Employees")
if not employees.empty and "role" in employees.columns:
    employees = employees[employees["role"].astype(str).str.lower() != "manager"].copy()
current_employee_id = str(st.session_state.get("employee_id", ""))

if role == "employee":
    employees = employees[employees["employee_id"].astype(str) == current_employee_id].copy() if not employees.empty else employees.copy()

# ---------- HR: generate payslips ----------
if role == "hr_admin":
    st.subheader("Generate Payslip")
    st.caption(
        "EPF / SOCSO / BBK / EIS are calculated automatically from the rate tables. "
        "PCB is NOT auto-calculated — work it out on LHDN's official e-PCB calculator "
        "first, then enter the figure below (leave blank if not applicable)."
    )

    if employees.empty:
        st.caption("No employees found yet.")
    else:
        # Show employee NAME in the dropdown, but keep employee_id as the
        # actual value used internally (id_col is the source of truth).
        name_to_id = dict(zip(employees["name"], employees["employee_id"]))

        with st.form("payslip_form"):
            selected_name = st.selectbox("Employee", list(name_to_id.keys()))
            month = st.text_input("Month (YYYY-MM)", placeholder="2026-07")
            # value=None leaves the box empty instead of pre-filled with 0.0,
            # so you can type straight away without deleting anything first.
            basic_salary = st.number_input("Basic salary (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
            allowance = st.number_input("Allowance (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
            skbbk_option = st.radio("SKBBK Contribution", ["Yes", "No"], horizontal=True)
            # include_skbbk_flag = (True if skbbk_option == "Yes" else False)
            pcb = st.number_input("PCB (RM) — from LHDN e-PCB calculator", min_value=0.0, step=1.0, value=None, placeholder="0.00")
            preview_clicked = st.form_submit_button("Preview Payslip")
            
        # Preview
        if preview_clicked:
            emp_id = name_to_id[selected_name]
            employee = employees[employees["employee_id"] == emp_id].iloc[0].to_dict()

            try:
                preview = preview_payslip(employee_id=emp_id,month=month,
                basic_salary=basic_salary,allowance=allowance or 0.0,
                date_of_birth=employee["date_of_birth"], pcb=pcb or 0.0,
                include_skbbk=(skbbk_option=="Yes")
                )

                # store preview in session
                st.session_state["payslip_preview"] = preview
                st.session_state["payslip_employee"] = employee
                st.session_state["payslip_emp_id"] = emp_id
                st.session_state["payslip_month"] = month
                st.session_state["payslip_basic"] = basic_salary or 0.0
                st.session_state["payslip_allowance"] = allowance or 0.0
                st.session_state["payslip_pcb"] = pcb or 0.0
                st.session_state["payslip_skbbk"] = (
                    skbbk_option == "Yes"
                )

            except ValueError as e:
                st.error(str(e))
        
        # Display Preview
        if "payslip_preview" in st.session_state:
            preview = st.session_state["payslip_preview"]

            st.divider()
            st.subheader("Payroll Preview")

            c1,c2,c3 = st.columns(3)
            c1.metric("Gross Salary", f"RM {preview['gross_salary']:.2f}")
            c2.metric("Unpaid Leave", f'{preview["unpaid_leave_days"]:.1f} Days')
            c3.metric("UPL Deduction", f'-RM {preview["unpaid_leave_deduction"]:.2f}')

            c4,c5,c6 = st.columns(3)
            c4.metric("EPF", f"RM {preview['epf_employee']:.2f}")
            c5.metric("SOCSO", f"RM {preview['socso_employee']:.2f}")
            c6.metric("EIS", f"RM {preview['eis_employee']:.2f}")

            c7,c8 = st.columns(2)
            c7.metric("SKBBK", f"RM {preview['skbbk']:.2f}")
            c8.metric("PCB", f"RM {preview['pcb']:.2f}")

            st.success(f"Net Pay: RM {preview['net_pay']:.2f}")
            st.divider()

            # Final Generate
            if st.button("Generate Payslip", type="primary"):
                try:
                    employee = st.session_state["payslip_employee"]
                    payslip = calculate_payslip(st.session_state["payslip_emp_id"], employee["name"],
                        st.session_state["payslip_month"],
                        st.session_state["payslip_basic"],
                        st.session_state["payslip_allowance"],
                        employee["date_of_birth"],
                        st.session_state["payslip_pcb"],
                        include_skbbk=st.session_state["payslip_skbbk"]
                    )

                    st.success(
                        f"Payslip saved for {employee['name']} "
                        f"— Net pay: RM {payslip['net_pay']:.2f}"
                    )

                    pdf_bytes = generate_payslip_pdf_bytes(employee,payslip)

                    st.download_button("Download PDF",pdf_bytes,
                        file_name=f"{employee['name']}_{payslip['month']}.pdf",
                        mime="application/pdf"
                    )

                    # clear preview after successful generation
                    del st.session_state["payslip_preview"]

                except ValueError as e:
                    st.error(str(e))

st.divider()

# ---------- Everyone: view/download their own payslips ----------
st.subheader("My Payslips")
payslips = read_table("Payslips")
me = employees[employees["employee_id"] == st.session_state["employee_id"]]

if payslips.empty or me.empty:
    st.caption("No payslips yet.")
else:
    my_employee = me.iloc[0].to_dict()
    my_payslips = payslips[payslips["employee_id"] == st.session_state["employee_id"]]

    if my_payslips.empty:
        st.caption("No payslips yet.")
    else:
        for _, row in my_payslips.sort_values("month", ascending=False).iterrows():
            payslip = row.to_dict()
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{payslip['month']}** — Net pay: RM {float(payslip['net_pay']):.2f}")
            pdf_bytes = generate_payslip_pdf_bytes(my_employee, payslip)
            col2.download_button(
                "Download", pdf_bytes,
                file_name=f"{my_employee['name']}_{payslip['month']}.pdf",
                mime="application/pdf",
                key=f"dl_{payslip['payslip_id']}",
            )
