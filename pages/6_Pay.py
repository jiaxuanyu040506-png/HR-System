import streamlit as st
import pandas as pd
import base64
import re
from datetime import date

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login
from utils.sheets_client import read_table
from utils.pdf_generator import generate_payslip_pdf_bytes
from utils.ea_forms import (
    get_ea_forms_for_employee,
    download_ea_form_bytes,
)

# PAGE SETUP
inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])

st.title("Pay")

# LOAD DATA
employees = read_table("Employees")
payslips = read_table("Payslips")
employee_id = st.session_state["employee_id"]

# EMPLOYEE INFORMATION
me = employees[employees["employee_id"].astype(str) == str(employee_id)]

if me.empty:
    st.error("Could not find your employee record.")
    st.stop()
my_employee = me.iloc[0].to_dict()

# LOAD EMPLOYEE PAYSLIPS
if not payslips.empty:
    my_payslips = payslips[payslips["employee_id"].astype(str) == str(employee_id)].copy()
else:
    my_payslips = pd.DataFrame()

# HELPER FUNCTIONS
def get_payslip_year(value):
    """
    Extract year from different month formats.

    Examples:
        2026-06     -> 2026
        2026/06     -> 2026
        Jun 2026    -> 2026
        June 2026   -> 2026
        2026        -> 2026
    """

    if value is None:
        return None

    try:
        text = str(value).strip()
        parsed = pd.to_datetime(text, errors="coerce")

        if not pd.isna(parsed):
            return int(parsed.year)

        match = re.search(r"(20\d{2})", text)
        if match:
            return int(match.group(1))

    except Exception:
        pass

    return None

def format_money(value):
    try:
        return f"RM {float(value):,.2f}"

    except Exception:
        return "RM 0.00"


def format_payslip_month(value):
    if value is None or value == "":
        return "-"

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%B %Y")

    except Exception:
        pass

    return str(value)


def get_payslip_sort_date(value):
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if not pd.isna(parsed):
            return parsed

    except Exception:
        pass

    return pd.Timestamp.min

# PAGE INTRO
st.html(
    """
    <div class="pay-welcome">

        <div class="pay-welcome-title">
            Your Pay & Documents
        </div>

        <div class="pay-welcome-text">
            View your payslips and annual tax documents
            in one place.
        </div>

    </div>
    """
)

# PAYSLIP YEAR SELECTION
st.subheader("Payslips")
current_year = date.today().year            # Determine available years

payslip_years = []
if (not my_payslips.empty and "month" in my_payslips.columns):
    my_payslips["_year"] = (my_payslips["month"].apply(get_payslip_year))
    payslip_years = sorted(my_payslips["_year"].dropna().astype(int).unique().tolist(),reverse=True,)

# Always keep current year available
if not payslip_years:
    payslip_years = [current_year]

selected_payslip_year = st.selectbox("Year", payslip_years, index=0, key="payslip_year",)

# FILTER PAYSLIPS
if not my_payslips.empty:
    selected_payslips = my_payslips[my_payslips["_year"] == selected_payslip_year].copy()
else:
    selected_payslips = pd.DataFrame()

# SORT PAYSLIPS
if not selected_payslips.empty:
    selected_payslips["_sort_date"] = (selected_payslips["month"].apply(get_payslip_sort_date))
    selected_payslips = (selected_payslips.sort_values("_sort_date", ascending=False,))

# CALCULATE PAYSLIP SUMMARY
if not selected_payslips.empty:
    total_net_pay = (pd.to_numeric(selected_payslips["net_pay"], errors="coerce").fillna(0).sum())
    latest_payslip = (selected_payslips.iloc[0])
    latest_month = format_payslip_month(latest_payslip["month"])
    payslip_count = len(selected_payslips)
else:
    total_net_pay = 0
    latest_month = "—"
    payslip_count = 0

# KPI CARDS
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Net Pay</div>
            <div class="kpi-value">{format_money(total_net_pay)}</div>
        </div>
        """,
        unsafe_allow_html=True,)
with c2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Latest Payslip</div>
            <div class="kpi-value">{latest_month}</div>
        </div>
        """,
        unsafe_allow_html=True,)
with c3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Payslips</div>
            <div class="kpi-value">{payslip_count}</div>
        </div>
        """,
        unsafe_allow_html=True,)

# PAYSLIP HISTORY
st.markdown("### Payslip History")
if selected_payslips.empty:
    st.info(f"No payslips available for " f"{selected_payslip_year}.")
    st.caption(
        "Your payslip will appear here once "
        "it has been uploaded by HR.")
else:
    for idx, (_, row) in enumerate(selected_payslips.iterrows()):
        payslip = row.to_dict()
        month_display = format_payslip_month(payslip.get("month"))
        net_pay = format_money(payslip.get("net_pay", 0))
        payslip_id = payslip.get("payslip_id", idx)

        # GENERATE PDF
        try:
            pdf_bytes = (generate_payslip_pdf_bytes(my_employee, payslip,))
        except Exception:
            pdf_bytes = None

        # PAYSLIP CARD
        with st.container(border=True):
            col_info, col_amount, col_action = (st.columns([3.2, 2, 2]))

            # Payslip Information
            with col_info:
                st.caption("Monthly Payslip")
                st.markdown(
                    f"""
                    <div class="pay-document-title">
                        {month_display}
                    </div>
                    """, unsafe_allow_html=True,)

            # Net Pay
            with col_amount:
                st.caption("Net Pay")
                st.markdown(
                    f"""
                    <div class="pay-net-pay">
                        {net_pay}
                    </div>
                    """, unsafe_allow_html=True,)

            # Action Buttons
            with col_action:
                if pdf_bytes is None:
                    st.error("Unable to generate PDF.")
                else:
                    button_col1, button_col2 = (st.columns(2))

                    # PREVIEW BUTTON
                    with button_col1:
                        preview_key = (f"preview_" f"{payslip_id}_" f"{selected_payslip_year}")
                        preview = st.button("Preview", key = preview_key,use_container_width = True,)

                    # DOWNLOAD BUTTON
                    with button_col2:
                        safe_name = str(my_employee.get("name", "Employee")).replace(" ", "_")
                        file_name = (f"{safe_name}_" f"{payslip.get('month')}.pdf")

                        st.download_button("Download", data = pdf_bytes, file_name = file_name,
                            mime = "application/pdf", key = (f"payslip_dl_" f"{payslip_id}_" f"{selected_payslip_year}"),
                            use_container_width=True,)

            # PDF PREVIEW
            preview_state_key = (f"show_preview_{payslip_id}")
            if preview:
                st.session_state[preview_state_key] = not st.session_state.get(preview_state_key, False)
            if st.session_state.get(preview_state_key, False):
                st.markdown(
                    """
                    <div class="pay-preview-title">
                        Payslip Preview
                    </div>
                    """, unsafe_allow_html=True,)

                # Convert PDF to Base64
                pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                pdf_display = f"""
                <iframe
                    src="data:application/pdf;base64,
                    {pdf_base64}"
                    width="100%"
                    height="700"
                    type="application/pdf"
                    style="
                        border:1px solid #dfe7f5;
                        border-radius:12px;
                        margin-top:8px;
                        background:#ffffff;
                    "
                >
                </iframe>
                """
                st.markdown(pdf_display, unsafe_allow_html=True,)

st.divider()

# EA FORM
st.subheader("EA Form")
st.caption("Download your annual EA Form uploaded by HR.")

# LOAD EA FORMS
try:
    my_ea_forms = (get_ea_forms_for_employee(employee_id))
except Exception:
    my_ea_forms = []

# DETERMINE EA YEARS
ea_years = []
for form in my_ea_forms:
    try:
        year_value = int(form.get("year"))
        ea_years.append(year_value)
    except Exception:
        continue

ea_years = sorted(list(set(ea_years)),reverse=True,)

# EA FORM YEAR FILTER
if not ea_years:
    st.info("No EA Form uploaded by HR yet.")
    st.caption(
        "Your EA Form will appear here "
        "once HR uploads it.")
else:
    selected_ea_year = st.selectbox("Year", ea_years, index = 0, key = "ea_year",)

    # FILTER EA FORMS
    selected_ea_forms = []
    for form in my_ea_forms:
        try:
            form_year = int(form.get("year"))
        except Exception:
            continue

        if form_year == selected_ea_year:
            selected_ea_forms.append(form)

    # DISPLAY EA FORM
    if not selected_ea_forms:
        st.info(f"No EA Form available for " f"{selected_ea_year}.")
    else:
        for idx, form in enumerate(selected_ea_forms):
            year = str(form.get("year", selected_ea_year,))
            uploaded_date = form.get("uploaded_date", "",)
            storage_path = form.get("storage_path")

            # EA FORM CARD
            with st.container(border=True):
                col_info, col_action = (st.columns([3.5, 2.2]))

                # EA FORM INFORMATION
                with col_info:
                    st.markdown(
                        f"""
                        <div class="pay-document-title">
                            EA Form {year}
                        </div>
                        """, unsafe_allow_html=True,)

                    if uploaded_date:
                        st.caption(f"Uploaded: {uploaded_date}")
                    else:
                        st.caption("Annual Income Tax Statement")

                # EA FORM ACTIONS
                with col_action:
                    if not storage_path:
                        st.error("File unavailable.")
                    else:
                        try:
                            pdf_bytes = (download_ea_form_bytes(storage_path))
                            employee_name = str(my_employee.get("name", "Employee")).replace(" ", "_")
                            file_name = (f"EA_{year}_" f"{employee_name}.pdf")
                            ea_preview_key = (f"ea_preview_" f"{employee_id}_" f"{year}_" f"{idx}")
                            ea_download_key = (f"ea_dl_" f"{employee_id}_" f"{year}_" f"{idx}")
                            button_col1, button_col2 = (st.columns(2))

                            # EA PREVIEW
                            with button_col1:
                                ea_preview = st.button("Preview", key = ea_preview_key, use_container_width = True,)

                            # EA DOWNLOAD
                            with button_col2:
                                st.download_button("Download", data = pdf_bytes,
                                    file_name = file_name, mime = "application/pdf",
                                    key = ea_download_key, use_container_width = True,)

                            # EA PREVIEW DISPLAY
                            ea_preview_state_key = (f"show_ea_preview_" f"{employee_id}_" f"{year}_" f"{idx}")
                            if ea_preview:
                                st.session_state[ea_preview_state_key] = not st.session_state.get(ea_preview_state_key, False)
                            if st.session_state.get(ea_preview_state_key,False):
                                st.markdown(
                                    """
                                    <div class="
                                        pay-preview-title
                                    ">
                                        EA Form Preview
                                    </div>
                                    """,unsafe_allow_html=True,)

                                ea_pdf_base64 = (base64.b64encode(pdf_bytes).decode("utf-8"))
                                ea_pdf_display = f"""
                                <iframe
                                    src="data:application/pdf;base64,
                                    {ea_pdf_base64}"
                                    width="100%"
                                    height="700"
                                    type="application/pdf"
                                    style="
                                        border:1px solid #dfe7f5;
                                        border-radius:12px;
                                        margin-top:8px;
                                        background:#ffffff;
                                    "
                                >
                                </iframe>
                                """
                                st.markdown(ea_pdf_display, unsafe_allow_html = True,)

                        except Exception:
                            st.error("Couldn't fetch file.")

# FOOTER NOTE
st.markdown(
    """
    <div class="pay-document-note">
        💡 <strong>Need help?</strong>
        Contact HR if your payslip or EA Form is missing.
    </div>
    """, unsafe_allow_html=True,)
