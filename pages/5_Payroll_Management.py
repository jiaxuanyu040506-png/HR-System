import streamlit as st
from datetime import date
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import read_table, delete_row
from utils.payroll_calc import calculate_payslip, preview_payslip
from utils.pdf_generator import generate_payslip_pdf_bytes
from utils.ea_forms import upload_ea_form, get_all_ea_forms, download_ea_form_bytes

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
section = st.radio(
    "Section", ["Generate Payslip", "Payroll History", "Upload EA Form"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

# ---------- Generate Payslip ----------
if section == "Generate Payslip":
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
            allowance = st.number_input("Bonus (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
            red_packet = st.number_input("Red Packet (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")  # Updated 7 Aug, 2026 - Separate red packet from allowance
            bik = st.number_input("BIK (RM)", min_value=0.0, step=50.0, value=None, placeholder="0.00")
            skbbk_option = st.radio("SKBBK Contribution", ["Yes", "No"], horizontal=True)
            pcb = st.number_input("PCB (RM)", min_value=0.0, step=1.0, value=None, placeholder="0.00")
            preview_clicked = st.form_submit_button("Preview Payslip")
            # submitted = st.form_submit_button("Generate Payslip")

        # Preview
        if preview_clicked:
            emp_id = name_to_id[selected_name]
            employee = employees[employees["employee_id"] == emp_id].iloc[0].to_dict()

            try:
                preview = preview_payslip(
                    employee_id=emp_id,
                    month=month,
                    basic_salary=basic_salary,
                    allowance=allowance or 0.0,
                    bik=bik or 0.0,
                    red_packet=red_packet or 0.0,
                    date_of_birth=employee["date_of_birth"],
                    pcb=pcb or 0.0,
                    include_skbbk=(skbbk_option=="Yes"),
                    join_date=employee.get("join_date"),
                )

                # store preview in session
                st.session_state["payslip_preview"] = preview
                st.session_state["payslip_employee"] = employee
                st.session_state["payslip_emp_id"] = emp_id
                st.session_state["payslip_month"] = month
                st.session_state["payslip_basic"] = basic_salary or 0.0
                st.session_state["payslip_allowance"] = allowance or 0.0
                st.session_state["payslip_red_packet"] = red_packet or 0.0  # Updated 7 Aug, 2026 - Store red packet separately
                st.session_state["payslip_bik"] = bik or 0.0
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

            c4, c5, c6, c7 = st.columns(4)
            c4.metric("EPF", f"RM {preview['epf_employee']:.2f}")
            c5.metric("SOCSO", f"RM {preview['socso_employee']:.2f}")
            c6.metric("EIS", f"RM {preview['eis_employee']:.2f}")
            c7.metric("BIK", f"RM {preview.get('bik', st.session_state.get('payslip_bik', 0.0)):.2f}")

            c8, c9, c10, c11 = st.columns(4)
            c8.metric("SKBBK", f"RM {preview['skbbk']:.2f}")
            c9.metric("PCB", f"RM {preview['pcb']:.2f}")
            c10.metric("Bonus", f"RM {preview['allowance']:.2f}")
            c11.metric("Red Packet", f"RM {preview.get('red_packet', 0.0):.2f}")  # Updated 7 Aug, 2026 - Show red packet separately


            st.success(f"Net Pay: RM {preview['net_pay']:.2f}")
            st.divider()

            # Final Generate
            if st.button("Generate Payslip", type="primary"):
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
                        include_skbbk=st.session_state["payslip_skbbk"],
                        red_packet=st.session_state["payslip_red_packet"],  # Updated 7 Aug, 2026 - Pass red packet separately
                        bik=st.session_state["payslip_bik"],
                        join_date=employee.get("join_date"),
                    )

                    if "bik" not in payslip:
                        payslip["bik"] = st.session_state["payslip_bik"]

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

# ---------- Payroll History ----------
elif section == "Payroll History":
    if payslips.empty:
        st.caption("No payslips generated yet.")
    else:
        # summary = payslips.groupby("month").agg(
        #     employees=("employee_id", "count"),
        #     total_amount=("net_pay", lambda s: s.astype(float).sum()),
        # ).reset_index().sort_values("month", ascending=False)
        # st.dataframe(summary, use_container_width=True)

        # Updated 7 Aug, 2026 - Add month filter for Payroll History
        month_options = sorted(payslips["month"].dropna().unique(), reverse=True)
        month_options = ["All Months"] + month_options
        selected_month = st.selectbox("Filter by month", month_options, index=0)

        filtered_payslips = (
            payslips
            if selected_month == "All Months"
            else payslips[payslips["month"] == selected_month]
        )

        total_employees = filtered_payslips["employee_id"].nunique()
        total_amount = filtered_payslips["net_pay"].astype(float).sum() if not filtered_payslips.empty else 0.0

        c1, c2 = st.columns(2)
        c1.metric("Total Employees", total_employees)
        c2.metric("Total Payroll", f"RM {total_amount:,.2f}")

        if selected_month == "All Months":
            summary = filtered_payslips.groupby("month").agg(
                employees=("employee_id", "count"),
                total_amount=("net_pay", lambda s: s.astype(float).sum()),
            ).reset_index().sort_values("month", ascending=False)

            st.subheader("Payroll summary by month")
            st.dataframe(summary, use_container_width=True)
        else:
            st.subheader(f"Payslip details for {selected_month}")
            detail_cols = [
                col for col in ["employee_name", "employee_id", "month", "basic_salary", "allowance", "bik","net_pay"]
                if col in filtered_payslips.columns
            ]
            st.dataframe(filtered_payslips[detail_cols], use_container_width=True)


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
                delete_row("Payslips", {"payslip_id": options[selected_label]})
                st.success("Payslip deleted.")
                st.rerun()

# ---------- Upload EA Form ----------
else:

    st.markdown("#### Upload EA Form")

    st.caption(
        "Upload each employee's annual EA Form (income statement) here. "
        "It will appear under their 'My EA Forms' page for them to download. "
        "Uploading again for the same employee + year replaces the previous file."
    )

    if employees.empty:

        st.caption("No employees found yet.")

    else:

        name_to_id = dict(
            zip(
                employees["name"],
                employees["employee_id"]
            )
        )

        with st.form("ea_form_upload"):

            selected_name = st.selectbox(
                "Employee",
                list(name_to_id.keys()),
                key="ea_employee"
            )

            year = st.text_input(
                "Year",
                value=str(date.today().year - 1),
                placeholder="2025",
                key="ea_year"
            )

            pdf_file = st.file_uploader(
                "EA Form PDF",
                type=["pdf"],
                key="ea_pdf_upload"
            )

            submitted_ea = st.form_submit_button(
                "Upload EA Form"
            )

            if submitted_ea:

                # -------------------------
                # Validation
                # -------------------------

                if pdf_file is None:

                    st.error(
                        "Please choose a PDF file first."
                    )

                elif not year.strip():

                    st.error(
                        "Please enter the year this EA Form is for."
                    )

                elif not year.strip().isdigit():

                    st.error(
                        "Year must contain numbers only."
                    )

                elif len(year.strip()) != 4:

                    st.error(
                        "Please enter a valid 4-digit year."
                    )

                else:

                    emp_id = name_to_id[selected_name]

                    try:

                        upload_ea_form(
                            employee_id=emp_id,
                            employee_name=selected_name,
                            year=year.strip(),
                            file_bytes=pdf_file.getvalue(),
                        )

                        st.success(
                            f"EA Form for {selected_name} "
                            f"({year.strip()}) uploaded successfully. "
                            "They can now download it under My EA Forms."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Failed to upload EA Form: {e}"
                        )


    # ============================================================
    # Part 2: Uploaded EA Forms
    # ============================================================

    st.divider()

    st.markdown("#### Uploaded EA Forms")

    all_forms = get_all_ea_forms()


    if not all_forms:

        st.caption(
            "No EA Forms uploaded yet."
        )

    else:

        # --------------------------------------------------------
        # Year Filter
        # --------------------------------------------------------

        available_years = sorted(
            {
                str(form["year"])
                for form in all_forms
                if form.get("year")
            },
            reverse=True
        )

        selected_year = st.selectbox(
            "Filter by Year",
            options=["All Years"] + available_years,
            key="ea_year_filter"
        )


        # --------------------------------------------------------
        # Apply Filter
        # --------------------------------------------------------

        if selected_year == "All Years":

            filtered_forms = all_forms

        else:

            filtered_forms = [
                form
                for form in all_forms
                if str(form["year"]) == selected_year
            ]


        st.caption(
            f"Showing {len(filtered_forms)} EA Form(s)"
        )


        # --------------------------------------------------------
        # Display EA Forms
        # --------------------------------------------------------

        if not filtered_forms:

            st.info(
                f"No EA Forms found for {selected_year}."
            )

        else:

            for form in filtered_forms:

                employee_id = str(
                    form["employee_id"]
                )

                employee_name = str(
                    form["employee_name"]
                )

                year = str(
                    form["year"]
                )

                uploaded_date = str(
                    form.get("uploaded_date", "-")
                )

                storage_path = form.get(
                    "storage_path"
                )


                # ------------------------------------------------
                # One expander per employee/year
                # ------------------------------------------------

                with st.expander(
                    f"{employee_name} "
                    f"({employee_id}) — EA Form {year}"
                ):

                    # -------------------------
                    # Information
                    # -------------------------

                    col1, col2, col3 = st.columns(3)

                    with col1:

                        st.caption("Employee")

                        st.write(
                            employee_name
                        )

                    with col2:

                        st.caption("Year")

                        st.write(
                            year
                        )

                    with col3:

                        st.caption("Uploaded")

                        st.write(
                            uploaded_date
                        )


                    st.divider()


                    # -------------------------
                    # Storage path
                    # -------------------------

                    if not storage_path:

                        st.error(
                            "Storage path is missing for this EA Form."
                        )

                        continue


                    # -------------------------
                    # Load PDF
                    # -------------------------

                    try:

                        pdf_bytes = download_ea_form_bytes(
                            storage_path
                        )

                    except Exception as e:

                        st.error(
                            "Unable to load this EA Form."
                        )

                        st.caption(
                            f"Error: {e}"
                        )

                        continue


                    # -------------------------
                    # Preview / Download
                    # -------------------------

                    col_preview, col_download = st.columns(
                        [1, 1]
                    )


                    # =========================
                    # Preview
                    # =========================

                    with col_preview:

                        preview_key = (
                            f"preview_ea_"
                            f"{employee_id}_"
                            f"{year}"
                        )

                        preview = st.toggle(
                            "Preview PDF",
                            key=preview_key
                        )


                    # =========================
                    # Download
                    # =========================

                    with col_download:

                        st.download_button(
                            label="Download EA Form",
                            data=pdf_bytes,
                            file_name=(
                                f"EA_{year}_"
                                f"{employee_id}.pdf"
                            ),
                            mime="application/pdf",
                            key=(
                                f"download_ea_"
                                f"{employee_id}_"
                                f"{year}"
                            ),
                            use_container_width=True,
                        )


                    # -------------------------
                    # PDF Preview
                    # -------------------------

                    if preview:

                        st.markdown(
                            "##### EA Form Preview"
                        )

                        import base64

                        base64_pdf = base64.b64encode(
                            pdf_bytes
                        ).decode("utf-8")

                        pdf_display = f"""
                        <iframe
                            src="data:application/pdf;base64,{base64_pdf}"
                            width="100%"
                            height="700"
                            style="border: 1px solid #ddd;
                                border-radius: 8px;"
                            type="application/pdf">
                        </iframe>
                        """

                        st.markdown(
                            pdf_display,
                            unsafe_allow_html=True
                        )
