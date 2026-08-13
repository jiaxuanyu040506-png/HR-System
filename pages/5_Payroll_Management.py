import streamlit as st
from datetime import date
import base64

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import (
    read_table,
    delete_row,
)
from utils.payroll_calc import (
    calculate_payslip,
    preview_payslip,
)
from utils.pdf_generator import generate_payslip_pdf_bytes
from utils.ea_forms import (
    upload_ea_form,
    get_all_ea_forms,
    download_ea_form_bytes,
)

# Page Setup
inject_css()
require_role(["hr_admin", "manager"])
render_nav_sidebar(st.session_state["role"])

st.title("Payroll Management")
employees = read_table("Employees")
payslips = read_table("Payslips")

# Payroll Summary
current_month = date.today().strftime("%Y-%m")
if not payslips.empty:
    this_month_slips = payslips[payslips["month"].astype(str) == current_month]
else:
    this_month_slips = payslips

if not this_month_slips.empty:
    total_payroll = (this_month_slips["net_pay"].astype(float).sum())
else:
    total_payroll = 0.0

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(f"Total Payroll ({current_month})", f"RM {total_payroll:,.2f}")
with c2:
    st.metric("Payroll Status", "Ready" if not this_month_slips.empty else "Not generated")
with c3:
    st.metric("Employees Paid This Month", len(this_month_slips))
st.caption(
    "Payroll calculations are generated from the employee records "
    "and configured contribution tables.")

# Sections
st.divider()
section = st.radio("Section", ["Generate Payslip", "Payroll History", "Upload EA Form",], horizontal=True, label_visibility="collapsed",)
st.divider()

# Helper: PDF Preview
def show_pdf_preview(pdf_bytes: bytes, height: int = 700,):
    """
    Display a PDF inside Streamlit.
    """

    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f"""
    <iframe
        src="data:application/pdf;base64,{base64_pdf}"
        width="100%"
        height="{height}"
        style="
            border: 1px solid #ddd;
            border-radius: 8px;
        "
        type="application/pdf">
    </iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)

# GENERATE PAYSLIP
if section == "Generate Payslip":
    st.subheader("Generate Payslip")
    st.caption(
        "Enter the payroll information below. "
        "You can preview the calculated figures first, "
        "then preview the actual PDF before saving the payslip.")

    # Employee Selection
    if employees.empty:
        st.info("No employees found yet.")
    else:
        name_to_id = dict(zip(employees["name"], employees["employee_id"]))
        employee_options = list(name_to_id.keys())

        # Payroll Input Form
        with st.form("payslip_form"):
            st.markdown("#### Employee & Payroll Period")
            col1, col2 = st.columns(2)
            with col1:
                selected_name = st.selectbox("Employee",list(name_to_id.keys()),key="generate_employee",)
            with col2:
                month = st.text_input("Month", placeholder="2026-07", key="generate_month",)

            st.markdown("#### Salary Details")
            col1, col2 = st.columns(2)
            with col1:
                basic_salary = st.number_input("Basic Salary (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00", key="generate_basic",)
                allowance = st.number_input("Bonus (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00", key="generate_bonus",)
            with col2:
                red_packet = st.number_input("Red Packet (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00", key="generate_red_packet",)
                bik = st.number_input( "BIK (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00", key="generate_bik",)

            st.markdown("#### Contributions")
            col1, col2 = st.columns(2)
            with col1:
                skbbk_option = st.radio("SKBBK Contribution", ["Yes", "No"], horizontal=True,  key="generate_skbbk",)
            with col2:
                pcb = st.number_input("PCB (RM)", min_value=0.0, step=1.0, value=None, placeholder="0.00", key="generate_pcb",)

            st.divider()
            preview_clicked = st.form_submit_button("Preview Payslip", type="primary", use_container_width=True,)

        # Calculate Preview
        if preview_clicked:
            emp_id = name_to_id[selected_name]
            employee = employees[employees["employee_id"] == emp_id].iloc[0].to_dict()

            # Basic validation
            if not month.strip():
                st.error("Please enter the payroll month.")
            elif basic_salary is None:
                st.error("Please enter the basic salary.")
            else:
                try:
                    preview = preview_payslip(
                        employee_id = emp_id,
                        month = month.strip(),
                        basic_salary = basic_salary,
                        allowance = allowance or 0.0,
                        bik = bik or 0.0,
                        red_packet = red_packet or 0.0,
                        date_of_birth = employee["date_of_birth"],
                        pcb = pcb or 0.0,
                        include_skbbk = (skbbk_option == "Yes"),
                        join_date = employee.get("join_date"),)

                    # Store preview
                    st.session_state["payslip_preview"] = preview
                    st.session_state["payslip_employee"] = employee
                    st.session_state["payslip_emp_id"] = emp_id
                    st.session_state["payslip_month"] = month.strip()
                    st.session_state["payslip_basic"] = basic_salary or 0.0
                    st.session_state["payslip_allowance"] = allowance or 0.0
                    st.session_state["payslip_red_packet"] = red_packet or 0.0
                    st.session_state["payslip_bik"] = bik or 0.0
                    st.session_state["payslip_pcb"] = pcb or 0.0
                    st.session_state["payslip_skbbk"] = (skbbk_option == "Yes")
                    st.success("Payroll calculated successfully.")

                except ValueError as e:
                    st.error(str(e))

        # Payroll Preview
        if ("payslip_preview" in st.session_state):
            preview = st.session_state["payslip_preview"]
            employee = st.session_state["payslip_employee"]

            st.divider()

            st.subheader("Payroll Preview")
            st.caption(f"{employee['name']} • " f"{st.session_state['payslip_month']}")

            # Salary summary
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Gross Salary", f"RM {preview['gross_salary']:.2f}")
            with c2:
                st.metric("Unpaid Leave", f"{preview['unpaid_leave_days']:.1f} Days")
            with c3:
                st.metric("UPL Deduction", f"-RM {preview['unpaid_leave_deduction']:.2f}")

            # Contributions
            c4, c5, c6, c7 = st.columns(4)
            with c4:
                st.metric("EPF", f"RM {preview['epf_employee']:.2f}")
            with c5:
                st.metric("SOCSO", f"RM {preview['socso_employee']:.2f}")
            with c6:
                st.metric("EIS", f"RM {preview['eis_employee']:.2f}")
            with c7:
                st.metric("BIK", f"RM {preview.get('bik', st.session_state.get('payslip_bik', 0.0)):.2f}")

            c8, c9, c10, c11 = st.columns(4)
            with c8:
                st.metric("SKBBK", f"RM {preview['skbbk']:.2f}")
            with c9:
                st.metric("PCB", f"RM {preview['pcb']:.2f}")
            with c10:
                st.metric("Bonus", f"RM {preview['allowance']:.2f}")
            with c11:
                st.metric("Red Packet", f"RM {preview.get('red_packet', 0.0):.2f}")
            st.success(f"Net Pay: RM {preview['net_pay']:.2f}")

            # PDF Preview
            st.divider()
            st.subheader("Payslip PDF Preview")
            st.caption("This is the actual PDF that will be generated.")

            try:
                # Generate a temporary payslip record
                # for PDF preview only.
                preview_record = {**preview, "payslip_id": (
                        f"PS-{st.session_state['payslip_month']}-"
                        f"{st.session_state['payslip_emp_id']}"),
                    "employee_id": st.session_state[ "payslip_emp_id"],
                    "employee_name": employee["name"],
                    "month": st.session_state["payslip_month"],
                    "basic_salary": st.session_state["payslip_basic"],
                    "allowance": st.session_state["payslip_allowance"],
                    "red_packet": st.session_state["payslip_red_packet"],
                    "bik": st.session_state["payslip_bik"],
                    "pcb": st.session_state["payslip_pcb"],}

                pdf_preview_bytes = (generate_payslip_pdf_bytes(employee, preview_record))
                preview_key = ("preview_generated_payslip")
                show_pdf = st.toggle("Preview PDF", key = preview_key)
                if show_pdf:
                    show_pdf_preview(pdf_preview_bytes, height=700)

            except Exception as e:
                st.error("Unable to generate PDF preview.")
                st.caption(f"Error: {e}")

            # Final Generate
            st.divider()
            st.subheader("Save Payslip")
            st.caption(
                "Click Generate Payslip to save this payroll "
                "record to the Payslips sheet.")

            if st.button("Generate Payslip", type="primary", use_container_width=True,):
                try:
                    employee = st.session_state["payslip_employee"]
                    payslip = calculate_payslip(
                        st.session_state["payslip_emp_id"], 
                        employee["name"],
                        st.session_state["payslip_month"],
                        st.session_state["payslip_basic"],
                        st.session_state["payslip_allowance"],
                        employee["date_of_birth"],
                        st.session_state["payslip_pcb"],
                        include_skbbk = st.session_state["payslip_skbbk"],
                        red_packet = st.session_state["payslip_red_packet"],
                        bik = st.session_state["payslip_bik"],
                        join_date = employee.get("join_date"),)

                    if "bik" not in payslip:
                        payslip["bik"] = (st.session_state["payslip_bik"])
                    st.success(f"Payslip saved for " f"{employee['name']} — " f"Net pay: " f"RM {payslip['net_pay']:.2f}")

                    pdf_bytes = (generate_payslip_pdf_bytes(employee, payslip))
                    st.download_button("Download Payslip PDF",
                        pdf_bytes, file_name=(
                            f"{employee['name']}_"
                            f"{payslip['month']}.pdf"),
                        mime="application/pdf", use_container_width=True,)

                    # Clear preview
                    for key in [
                        "payslip_preview",
                        "payslip_employee", "payslip_emp_id",
                        "payslip_month", "payslip_basic",
                        "payslip_allowance", "payslip_red_packet",
                        "payslip_bik", "payslip_pcb",
                        "payslip_skbbk", "preview_generated_payslip",]:
                        st.session_state.pop(key, None)

                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Failed to generate payslip: {e}")

# PAYROLL HISTORY
elif section == "Payroll History":
    st.subheader("Payroll History")
    if payslips.empty:
        st.info("No payslips generated yet.")
    else:
        st.markdown("#### 🔍 Filter Payslips")              # FILTERS
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:                                   # Month Filter
            month_options = sorted(payslips["month"].dropna().astype(str).unique(), reverse=True,)
            month_options = ["All Months"] + month_options
            selected_month = st.selectbox("Payroll Month", month_options, key="payroll_history_month",)

        with filter_col2:                                   # Employee ID Filter
            employee_options = sorted(payslips["employee_id"].dropna().astype(str).unique())
            employee_options = ["All Employees"] + employee_options
            selected_employee_id = st.selectbox("Employee ID", employee_options, key="payroll_history_employee",)

        # APPLY FILTERS
        filtered_payslips = payslips.copy()
        if selected_month != "All Months":
            filtered_payslips = filtered_payslips[filtered_payslips["month"].astype(str) == selected_month]

        if selected_employee_id != "All Employees":
            filtered_payslips = filtered_payslips[filtered_payslips["employee_id"].astype(str) == selected_employee_id]

        # SUMMARY
        total_employees = (filtered_payslips["employee_id"].nunique() if not filtered_payslips.empty else 0)
        total_amount = (filtered_payslips["net_pay"].astype(float).sum() if not filtered_payslips.empty else 0.0)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Employees",total_employees,)
        with c2:
            st.metric("Total Net Payroll", f"RM {total_amount:,.2f}",)
        st.divider()

        # PAYROLL SUMMARY
        if (selected_month == "All Months" and selected_employee_id == "All Employees" and not filtered_payslips.empty):
            summary = (filtered_payslips.groupby("month").agg(
                employees=("employee_id", "nunique",),
                total_amount=("net_pay", lambda s: s.astype(float).sum(),),).reset_index().sort_values("month", ascending=False,))
            summary["total_amount"] = (summary["total_amount"].map(lambda x: f"RM {x:,.2f}"))
            st.markdown("#### 📊 Payroll Summary")
            st.dataframe(summary, use_container_width=True, hide_index=True,)
            st.divider()

        # PAYSLIP DETAILS
        st.markdown("#### 📄 Payslips")
        if filtered_payslips.empty:
            st.info("No payslips found for the selected filters.")
        else:
            for _, row in filtered_payslips.iterrows():
                payslip_id = str(row.get("payslip_id", "",))
                employee_name = str(
                    row.get("employee_name", row.get("employee_id", "Unknown",),))
                employee_id = str(row.get("employee_id", "",))
                month = str(row.get("month", "-",))
                net_pay = float(row.get("net_pay", 0,) or 0)

                # Find employee information
                employee_match = employees[employees["employee_id"].astype(str) == employee_id]
                employee_data = (employee_match.iloc[0].to_dict() if not employee_match.empty else None)

                # Generate PDF
                pdf_bytes = None
                if employee_data:
                    try:
                        pdf_bytes = (generate_payslip_pdf_bytes(employee_data, row.to_dict(),))
                    except Exception:
                        pdf_bytes = None

                # PAYSLIP CARD
                with st.container(border=True):
                    col1, col2, col3 = st.columns([4, 2, 3])

                    # Employee information
                    with col1:
                        st.markdown(f"### {employee_name}")
                        st.caption(f"Employee ID: {employee_id}")
                        st.caption(f"Payroll Month: {month}")

                    # Net Pay
                    with col2:
                        st.metric("Net Pay", f"RM {net_pay:,.2f}",)

                    # Actions
                    with col3:
                        action_col1, action_col2 = st.columns(2)
                        # Edit
                        with action_col1:                            
                            if st.button("✏️ Edit", key=f"edit_{payslip_id}", use_container_width=True,):
                                st.session_state["editing_payslip_id"] = payslip_id
                                st.session_state["editing_payslip"] = row.to_dict()
                                st.rerun()

                        # PDF Download
                        with action_col2:
                            if pdf_bytes:
                                st.download_button("📄 PDF",
                                    data=pdf_bytes, file_name=(
                                        f"{employee_name}_"
                                        f"{month}.pdf"
                                    ), mime="application/pdf",
                                    key=(
                                        f"download_history_"
                                        f"{payslip_id}"),
                                    use_container_width=True,)
                            else:
                                st.button("📄 PDF", disabled=True,
                                    key=(
                                        f"pdf_disabled_"
                                        f"{payslip_id}"
                                    ), use_container_width=True,)

                    # PDF PREVIEW
                    if pdf_bytes:
                        preview_key = (f"preview_pdf_" f"{payslip_id}")
                        preview_pdf = st.toggle("👁️ Preview PDF", key = preview_key,)

                        if preview_pdf:
                            import base64
                            base64_pdf = (base64.b64encode(pdf_bytes).decode("utf-8"))
                            pdf_display = f"""
                            <iframe
                                src="data:application/pdf;base64,{base64_pdf}"
                                width="100%"
                                height="700"
                                style="
                                    border: 1px solid #ddd;
                                    border-radius: 8px;
                                    margin-top: 10px;
                                "
                                type="application/pdf">
                            </iframe>
                            """

                            st.markdown(pdf_display, unsafe_allow_html=True,)

                    # PAYROLL DETAILS
                    with st.expander("View payroll details"):
                        detail_cols = [
                            "basic_salary", "allowance",
                            "red_packet", "bik",
                            "unpaid_leave_days", "unpaid_leave_deduction",
                            "pre_join_days", "pre_join_deduction",
                            "gross_salary",
                            "epf_employee", "epf_employer",
                            "socso_employee", "socso_employer",
                            "eis_employee", "eis_employer",
                            "skbbk", "skbbk_status",
                            "pcb", "net_pay",]
                        details = {}

                        for col in detail_cols:
                            if col in row.index:
                                details[col] = row[col]
                        if details:
                            import pandas as pd
                            detail_df = pd.DataFrame([{"Item": key.replace("_", " ",).title(), "Amount": value,} for key, value in details.items()])
                            st.dataframe(detail_df, use_container_width=True, hide_index=True,)

                # EDIT PAYSLIP
                if (st.session_state.get("editing_payslip_id") == payslip_id):
                    st.divider()
                    st.subheader("✏️ Edit Payslip")
                    edit_data = (st.session_state["editing_payslip"])
                    edit_employee_id = str(edit_data["employee_id"])
                    employee_match = employees[employees["employee_id"].astype(str) == edit_employee_id]
                    if employee_match.empty:
                        st.error("Employee record not found.")
                    else:
                        employee_data = (employee_match.iloc[0].to_dict())
                        st.info(
                            f"Editing payslip for "
                            f"**{employee_data['name']}** "
                            f"({edit_employee_id}) "
                            f"— **{edit_data['month']}**"
                        )

                        with st.form(f"edit_payslip_form_{payslip_id}"):
                            col1, col2 = st.columns(2)

                            # LEFT
                            with col1:
                                edit_basic = st.number_input("Basic Salary (RM)",min_value=0.0,value=float(edit_data.get("basic_salary", 0,) or 0),step=50.0,)
                                edit_allowance = st.number_input("Bonus (RM)", min_value=0.0, value=float(edit_data.get("allowance", 0,) or 0), step=50.0,)
                                edit_red_packet = st.number_input("Red Packet (RM)", min_value=0.0, value=float(edit_data.get("red_packet", 0, ) or 0), step=50.0,)

                            # RIGHT
                            with col2:
                                edit_bik = st.number_input("BIK (RM)", min_value=0.0,value=float(edit_data.get("bik", 0,) or 0), step=50.0,)
                                edit_pcb = st.number_input("PCB (RM)", min_value=0.0, value=float(edit_data.get("pcb", 0,) or 0),step=1.0,)
                                existing_skbbk = (str(edit_data.get("skbbk_status", "Yes",)).strip().lower() == "yes")
                                edit_skbbk = st.radio("SKBBK Contribution", ["Yes", "No"], index=(0 if existing_skbbk else 1), horizontal=True,)

                            st.divider()
                            save_col, cancel_col = st.columns(2)
                            with save_col:
                                save_edit = (st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True,))
                            with cancel_col:
                                cancel_edit = (st.form_submit_button("Cancel", use_container_width=True,))

                        # CANCEL
                        if cancel_edit:
                            st.session_state.pop("editing_payslip_id", None,)
                            st.session_state.pop("editing_payslip", None,)
                            st.rerun()

                        # SAVE
                        if save_edit:
                            try:
                                updated_payslip = (
                                    calculate_payslip(
                                        employee_id = edit_employee_id,
                                        employee_name = employee_data["name"],
                                        month = str(edit_data["month"]),
                                        basic_salary = edit_basic,
                                        allowance = edit_allowance,
                                        date_of_birth = employee_data["date_of_birth"],
                                        pcb = edit_pcb,
                                        include_skbbk = (edit_skbbk == "Yes"),
                                        red_packet = edit_red_packet,
                                        bik = edit_bik,
                                        join_date = employee_data.get("join_date"),))

                                st.success("Payslip updated successfully.")
                                st.session_state.pop("editing_payslip_id", None,)
                                st.session_state.pop("editing_payslip", None,)
                                st.rerun()

                            except ValueError as e:
                                st.error(str(e))
                            except Exception as e:
                                st.error(f"Unable to update payslip: {e}")

        # DELETE PAYSLIP
        st.divider()
        with st.expander("🗑️ Delete Payslip", expanded=False,):
            st.warning(
                "Use this only for testing or correcting "
                "data-entry mistakes. Deleting a payslip "
                "cannot be undone.")

            delete_options = {}
            for _, row in payslips.iterrows():
                label_name = (row.get("employee_name") or row.get("employee_id", "Unknown",))
                employee_id = row.get("employee_id", "-",)
                month_label = row.get("month", "-",)

                try:
                    net_pay_val = float(row.get("net_pay", 0,) or 0)
                except (ValueError, TypeError,):
                    net_pay_val = 0.0

                label = (
                    f"{label_name} "
                    f"({employee_id}) — "
                    f"{month_label} "
                    f"(RM {net_pay_val:.2f})")

                delete_options[label] = (row.get("payslip_id", "",))

            if delete_options:
                selected_delete = st.selectbox("Select payslip to delete", list(delete_options.keys()), key="delete_payslip_select",)
                confirm_delete = st.checkbox("Yes, permanently delete this payslip", key="confirm_delete_payslip",)
                if st.button("Delete Payslip",  disabled = not confirm_delete, key="delete_payslip_btn", type="primary",): 
                    delete_row("Payslips", {"payslip_id":delete_options[selected_delete]},)
                    st.success("Payslip deleted successfully.")
                    st.rerun()

# UPLOAD EA FORM
elif section == "Upload EA Form":
    st.subheader("EA Forms")
    st.caption("Upload and manage annual EA Forms for employees.")

    # Part 1 — Upload
    st.markdown("### 📤 Upload EA Form")
    st.caption(
        "Upload an employee's annual EA Form. "
        "Uploading the same employee + year again "
        "will replace the previous file.")
    
    if employees.empty:
        st.info("No employees found yet.")
    else:
        name_to_id = dict(zip(employees["name"], employees["employee_id"]))
        with st.form("ea_form_upload"):
            selected_name = st.selectbox("Employee", list(name_to_id.keys()), key="ea_employee")
            year = st.text_input("Year", value=str(date.today().year - 1), placeholder="2025", key="ea_year")
            pdf_file = st.file_uploader("EA Form PDF", type=["pdf"], key="ea_pdf_upload")
            submitted_ea = (st.form_submit_button("Upload EA Form", type="primary", use_container_width=True,))

        if submitted_ea:
            if pdf_file is None:
                st.error("Please choose a PDF file first.")
            elif not year.strip():
                st.error("Please enter the year.")
            elif not year.strip().isdigit():
                st.error("Year must contain numbers only.")
            elif len(year.strip()) != 4:
                st.error("Please enter a valid 4-digit year.")
            else:
                emp_id = name_to_id[selected_name]
                try:
                    upload_ea_form(
                        employee_id = emp_id, employee_name = selected_name,
                        year = year.strip(), file_bytes = pdf_file.getvalue(),)
                    
                    st.success(
                        f"EA Form for {selected_name} "
                        f"({year.strip()}) uploaded successfully.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Failed to upload EA Form: {e}")

    # Part 2 — Uploaded EA Forms
    st.divider()
    st.markdown("### 📁 Uploaded EA Forms")

    all_forms = get_all_ea_forms()
    if not all_forms:
        st.info("No EA Forms uploaded yet.")
    else:
        available_years = sorted({str(form["year"]) for form in all_forms if form.get("year")}, reverse=True)
        selected_year = st.selectbox("Filter by Year", ["All Years"] + available_years, key="ea_year_filter")

        if selected_year == "All Years":
            filtered_forms = all_forms
        else:
            filtered_forms = [form for form in all_forms if str(form["year"]) == selected_year]

        st.caption(f"Showing {len(filtered_forms)} EA Form(s)")

        for form in filtered_forms:
            employee_id = str(form["employee_id"])
            employee_name = str(form["employee_name"])
            year = str(form["year"])
            uploaded_date = str(form.get( "uploaded_date", "-"))
            storage_path = form.get("storage_path")
            with st.expander(
                f"{employee_name} "
                f"({employee_id}) — "
                f"EA Form {year}"):

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.caption("Employee")
                    st.write(employee_name)
                with c2:
                    st.caption("Year")
                    st.write(year)
                with c3:
                    st.caption("Uploaded")
                    st.write(uploaded_date)
                st.divider()

                if not storage_path:
                    st.error("Storage path is missing for this EA Form.")
                    continue

                try:
                    pdf_bytes = (download_ea_form_bytes(storage_path))
                except Exception as e:
                    st.error("Unable to load this EA Form.")
                    st.caption(f"Error: {e}")
                    continue

                col1, col2 = st.columns(2)
                with col1:
                    preview = st.toggle("Preview PDF", key=(
                            f"preview_ea_"
                            f"{employee_id}_"
                            f"{year}"),)
                with col2:
                    st.download_button("Download EA Form",
                        pdf_bytes, file_name=(
                            f"EA_{year}_"
                            f"{employee_id}.pdf"),
                        mime="application/pdf",key=(
                            f"download_ea_"
                            f"{employee_id}_"
                            f"{year}"),use_container_width=True,)

                if preview:
                    st.markdown("##### EA Form Preview")
                    show_pdf_preview(pdf_bytes, height=700)