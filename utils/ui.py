"""
ui.py

Shared visual styling — call inject_css() at the top of every page so
the look is consistent everywhere.
"""

import streamlit as st

def inject_css():
    try:
        st.set_option("client.showSidebarNavigation", False)
    except Exception:
        pass

    st.markdown(
        """
        <style>

        /* ========================================================
        QUICK ACCESS CARDS
        Only applies to the main page — NOT Sidebar
        ======================================================== */

        .main [data-testid="stPageLink"] {
            border: 1px solid #e2e8f0 !important;
            border-radius: 14px !important;
            background: #ffffff !important;
            padding: 18px 20px !important;
            min-height: 70px !important;
            box-sizing: border-box !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03) !important;
        }

        /* Hover */
        .main [data-testid="stPageLink"]:hover {
            border-color: #5b8def !important;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08) !important;
            transform: translateY(-1px);
        }

        /* Link itself */
        .main [data-testid="stPageLink"] a {
            text-decoration: none !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            width: 100% !important;
        }

        /* ============================================================
           GLOBAL
        ============================================================ */

        .stApp {
            background: #f5f7fb;
        }

        [data-testid="stSidebarNav"] {
            display: none !important;
        }

        html,
        body,
        [class*="css"] {
            font-size: 17px !important;
        }

        h1 {font-size: 2.2rem !important;}
        h2 {font-size: 1.7rem !important;}
        h3 {font-size: 1.35rem !important;}
        h4 {font-size: 1.15rem !important;}

        [data-testid="stTabs"] button p {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        /* ============================================================
           SIDEBAR
        ============================================================ */

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #dfe7f5;
            min-width: 280px !important;
            max-width: 320px !important;
        }

        [data-testid="stSidebar"] > div {
            background: #ffffff;
            border: 1px solid #dfe7f5;
            border-radius: 18px;
            padding: 1rem 0.95rem;
            box-shadow: 0 6px 24px rgba(15, 23, 42, 0.06);
            width: 100%;
            box-sizing: border-box;
        }

        [data-testid="stSidebar"] .st-emotion-cache-1v0mbdj,
        [data-testid="stSidebar"] .st-emotion-cache-16idsys {
            background: #f7faff;
            border: 1px solid #e3ebf9;
            border-radius: 12px;
            padding: 0.55rem 0.7rem;
            margin-bottom: 0.55rem;
        }

        [data-testid="stSidebar"] a {
            color: #16326e !important;
            border-radius: 10px;
            padding: 0.5rem 0.6rem;
            margin: 0.15rem 0;
            font-weight: 500;
        }

        [data-testid="stSidebar"] a:hover {
            background: #eef5ff;
        }

        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5 {
            color: #16326e !important;
            margin-bottom: 0.35rem;
        }

        /* ============================================================
           PHASE 3 — UI STANDARDIZATION
        ============================================================ */

        .page-welcome,
        .pay-welcome,
        .leave-welcome {
            background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
            border: 1px solid #dbeafe;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
        }

        .page-welcome-title,
        .pay-welcome-title,
        .leave-welcome-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 4px;
        }

        .page-welcome-text,
        .pay-welcome-text,
        .leave-welcome-text {
            font-size: 0.9rem;
            color: #64748b;
            line-height: 1.5;
        }

        .kpi-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
            min-height: 105px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .kpi-label {
            font-size: 0.86rem;
            color: #6b7280;
            font-weight: 600;
            margin-bottom: 6px;
        }

        .kpi-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #111827;
            line-height: 1.2;
        }

        .info-note,
        .pay-document-note {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 10px;
            padding: 11px 14px;
            color: #1e40af;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .info-note.warning-note {
            background: #fff7f7;
            border-color: #f5d0d0;
            color: #475569;
        }

        .info-note-spaced {
            margin-top: 14px;
        }

        .calendar-legend {
            margin-top: 12px;
            padding: 10px 14px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            font-size: 0.88rem;
            color: #475569;
        }

        .spacer-xs { height: 8px; }
        .spacer-sm { height: 18px; }
        .spacer-md { height: 20px; }
        .spacer-lg { height: 22px; }

        .calendar-note {
            margin-top: 0.5rem;
            line-height: 1.8;
            font-size: 0.95rem;
            color: #475569;
        }

        .calendar-note .muted {
            color: #64748b;
        }

        .pdf-preview {
            border: 1px solid #ddd;
            border-radius: 8px;
            width: 100%;
            height: 600px;
        }

        .calendar-legend span {
            color: #64748b;
        }

        .pay-document-title {
            font-size: 1rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 3px;
        }

        .pay-document-subtitle {
            font-size: 0.84rem;
            color: #64748b;
        }

        .pay-net-pay {
            font-size: 1.05rem;
            font-weight: 700;
            color: #172033;
        }

        .pay-preview-title {
            font-size: 1rem;
            font-weight: 700;
            color: #172033;
            margin-top: 12px;
            margin-bottom: 8px;
        }

        .section-title,
        .dashboard-section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 10px;
        }

        .metric-card {
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 18px 20px;
            background: #ffffff;
            min-height: 120px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
        }

        .metric-label {
            font-size: 0.9rem;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .metric-value {
            font-size: 1.9rem;
            font-weight: 700;
            color: #172033;
            line-height: 1.1;
        }

        .metric-subtext {
            font-size: 0.82rem;
            color: #64748b;
            margin-top: 7px;
        }

        .notice-box,
        .info-box {
            margin-top: 8px;
            padding: 11px 15px;
            border-radius: 10px;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .notice-box {
            background: #fffaf0;
            border: 1px solid #fde68a;
            color: #92400e;
        }

        .info-box {
            background: #f8fbff;
            border: 1px solid #dbeafe;
            color: #172033;
        }

        .deadline-box {
            margin-top: 12px;
            padding: 12px 16px;
            background: #f8fbff;
            border: 1px solid #dbeafe;
            border-radius: 12px;
        }

        .deadline-label {
            font-size: 0.82rem;
            color: #64748b;
            margin-bottom: 3px;
        }

        .deadline-date {
            font-size: 1.05rem;
            font-weight: 700;
            color: #172033;
        }

        .profile-shell {
            margin: 0;
            padding: 12px 0 8px 0;
        }

        .profile-header {
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 0;
        }

        .profile-avatar {
            width: 46px;
            height: 46px;
            border-radius: 50%;
            background: #1e4a9e;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            font-weight: 700;
            flex-shrink: 0;
        }

        .profile-name {
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.25;
            margin: 0;
            padding: 0;
            overflow-wrap: anywhere;
            word-break: break-word;
            color: #172033;
        }

        .profile-role {
            font-size: 0.92rem;
            color: #64748b;
            margin-top: 3px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .panel-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 12px;
        }

        .auth-card-shell {
            max-width: 520px;
            margin: 2.5rem auto 1rem auto;
            padding: 2rem 2.2rem;
            border-radius: 24px;
            background: #ffffff;
            box-shadow: 0 10px 35px rgba(15, 23, 42, 0.08);
        }

        .auth-form-shell {
            max-width: 520px;
            margin: 0 auto;
            padding: 1.4rem 1.6rem;
            border-radius: 20px;
            background: #ffffff;
            box-shadow: 0 6px 24px rgba(15, 23, 42, 0.06);
        }

        .dashboard-welcome {
            background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
            border: 1px solid #dbeafe;
            border-radius: 16px;
            padding: 20px 22px;
            margin-bottom: 22px;
        }

        .dashboard-welcome-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 5px;
        }

        .dashboard-welcome-text {
            font-size: 0.92rem;
            color: #64748b;
            line-height: 1.5;
        }

        .dashboard-kpi {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 18px 19px;
            min-height: 125px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
        }

        .dashboard-kpi-label {
            font-size: 0.84rem;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 9px;
        }

        .dashboard-kpi-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #172033;
            line-height: 1.2;
            margin-bottom: 5px;
        }

        .dashboard-kpi-sub {
            font-size: 0.78rem;
            color: #94a3b8;
        }

        .dashboard-quick-card {
            position: relative;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 18px;
            min-height: 105px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
            transition: 0.2s ease;
        }

        .dashboard-quick-icon {
            font-size: 1.45rem;
            margin-bottom: 10px;
        }

        .dashboard-quick-title {
            font-size: 0.98rem;
            font-weight: 650;
            color: #172033;
        }

        .dashboard-quick-arrow {
            position: absolute;
            right: 16px;
            bottom: 14px;
            color: #94a3b8;
            font-size: 1.1rem;
        }

        .dashboard-leave-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 17px 18px;
            margin-bottom: 10px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.035);
        }

        .dashboard-leave-type {
            font-size: 0.96rem;
            font-weight: 650;
            color: #172033;
            margin-bottom: 4px;
        }

        .dashboard-leave-date {
            font-size: 0.83rem;
            color: #64748b;
        }

        .dashboard-leave-days {
            font-size: 0.82rem;
            color: #94a3b8;
            margin-top: 4px;
        }

        .dashboard-request-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 9px;
        }

        .dashboard-request-title {
            font-size: 0.9rem;
            font-weight: 650;
            color: #172033;
        }

        .dashboard-request-date {
            font-size: 0.78rem;
            color: #64748b;
            margin-top: 3px;
        }

        .dashboard-reminder {
            background: #fff5f5;
            border: 1px solid #fecaca;
            border-radius: 14px;
            padding: 14px 17px;
            color: #991b1b;
            font-size: 0.9rem;
            line-height: 1.5;
            margin-top: 4px;
        }

        .dashboard-notice {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 16px 18px;
            color: #475569;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .dashboard-notice-title {
            color: #172033;
            font-weight: 650;
            margin-bottom: 5px;
        }

        .status-badge {
            display: inline-block;
            padding: 5px 11px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }

        .status-approved {
            background: #dcfce7;
            color: #166534;
        }

        .status-pending {
            background: #fef3c7;
            color: #92400e;
        }

        .status-rejected {
            background: #fee2e2;
            color: #991b1b;
        }

        .status-default {
            background: #f1f5f9;
            color: #475569;
        }

        .dashboard-quick-card + div button {
            margin-top: -4px;
            border-radius: 10px;
        }

        /* ============================================================
           BUTTONS
        ============================================================ */

        .stButton > button {
            border-radius: 10px;
        }

        button[aria-label="Approve"] {
            background: #d9f7ff !important;
            color: #0b4e68 !important;
            border: 1px solid #8cd8f7 !important;
        }

        button[aria-label="Reject"] {
            background: #ffe5e5 !important;
            color: #8a1f2b !important;
            border: 1px solid #f5c3c3 !important;
        }


        /* ============================================================
           LEAVE APPROVAL
        ============================================================ */

        .leave-approval-card {
            background: #ffffff;
            border: 1px solid #dfe7f5;
            border-radius: 18px;
            padding: 1.25rem;
            box-shadow: 0 6px 24px rgba(15, 23, 42, 0.05);
            margin-bottom: 1rem;
        }

        .leave-approval-card h3 {
            margin-bottom: 0.35rem;
        }

        .leave-approval-note {
            color: #475569;
            font-size: 0.95rem;
            margin-bottom: 0.85rem;
        }

        .leave-approval-meta {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            background: #f8fbff;
            border: 1px solid #dae8f8;
            border-radius: 16px;
            padding: 1rem 1rem 0.75rem;
            margin-bottom: 0.75rem;
        }

        .leave-approval-meta div {
            font-size: 0.97rem;
            line-height: 1.4;
        }

        .leave-approval-meta strong {
            display: block;
            margin-bottom: 0.35rem;
            color: #1f4f7a;
        }

        .leave-approval-actions {
            display: flex;
            gap: 0.75rem;
            margin-top: 0.75rem;
        }

        .leave-approval-actions .stButton button {
            min-height: 45px;
            border-radius: 12px;
            width: 100%;
        }

        .leave-approval-actions .stButton:nth-child(1) button {
            background: #d9f7ff !important;
            color: #0b4e68 !important;
            border: 1px solid #8cd8f7 !important;
        }

        .leave-approval-actions .stButton:nth-child(2) button {
            background: #ffe5e5 !important;
            color: #8a1f2b !important;
            border: 1px solid #f5c3c3 !important;
        }


        /* ============================================================
           EMPLOYEE - MY LEAVE
        ============================================================ */

        .leave-welcome {
            background: linear-gradient(
                135deg,
                #f8fbff 0%,
                #eef6ff 100%
            );
            border: 1px solid #dbeafe;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 18px;
        }

        .leave-welcome-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 4px;
        }

        .leave-welcome-text {
            font-size: 0.9rem;
            color: #64748b;
            line-height: 1.5;
        }


        /* ============================================================
           LEAVE BALANCE CARDS
        ============================================================ */

        .balance-card {
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 18px;
            background: #ffffff;
            min-height: 150px;
            margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
        }

        .balance-card-title {
            font-size: 0.9rem;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .balance-number {
            font-size: 1.9rem;
            font-weight: 700;
            color: #172033;
            line-height: 1.1;
        }

        .balance-label {
            font-size: 0.82rem;
            color: #64748b;
            margin-bottom: 12px;
        }

        .balance-detail {
            font-size: 0.8rem;
            color: #64748b;
        }

        .balance-progress {
            height: 6px;
            background: #e2e8f0;
            border-radius: 999px;
            margin-top: 10px;
            overflow: hidden;
        }


        /* ============================================================
           LEAVE HISTORY
        ============================================================ */

        .history-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 15px 18px;
            background: #ffffff;
            margin-bottom: 10px;
        }

        .history-date {
            font-weight: 700;
            color: #172033;
            font-size: 0.95rem;
        }

        .history-type {
            color: #475569;
            font-size: 0.88rem;
        }

        .history-meta {
            color: #64748b;
            font-size: 0.82rem;
        }


        /* ============================================================
           INFO / REMINDER
        ============================================================ */

        .info-note {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 10px;
            padding: 11px 14px;
            color: #1e40af;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .auth-header-title {
            text-align: center;
            margin-bottom: 0.25rem;
            color: #16326e;
        }

        .auth-header-subtitle {
            text-align: center;
            color: #64748b;
            margin-bottom: 1.5rem;
        }

        .panel-title-compact {
            margin-bottom: 4px;
        }

        .muted-text {
            font-size: 0.88rem;
            color: #64748b;
        }

        .profile-meta {
            min-width: 0;
            flex: 1;
        }

        .section-heading {
            font-size: 1.15rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 10px;
        }

        .dashboard-summary-card,
        .metric-card {
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 18px 20px;
            background: #ffffff;
            min-height: 120px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
        }

        .dashboard-card-label,
        .metric-label {
            font-size: 0.9rem;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .dashboard-card-value,
        .metric-value {
            font-size: 1.9rem;
            font-weight: 700;
            color: #172033;
            line-height: 1.1;
        }

        .dashboard-card-sub,
        .metric-subtext {
            font-size: 0.82rem;
            color: #64748b;
            margin-top: 7px;
        }

        .deadline-inline-box {
            margin: 8px 0 16px 0;
            padding: 11px 15px;
            background: #f8fbff;
            border: 1px solid #dbeafe;
            border-radius: 12px;
        }

        .deadline-inline-label {
            color: #64748b;
            font-size: 0.85rem;
        }

        .deadline-inline-date {
            color: #172033;
            font-size: 1rem;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .dashboard-notice {
            background: #f8fbff;
            border: 1px solid #dbeafe;
            border-radius: 12px;
            padding: 12px 14px;
            color: #172033;
            font-size: 0.88rem;
            line-height: 1.6;
        }

        .dashboard-notice-title {
            font-size: 0.96rem;
            font-weight: 700;
            color: #172033;
            margin-bottom: 4px;
        }

        .status-badge-approved {
            background: #dcfce7;
            color: #166534;
        }

        .status-badge-pending {
            background: #fef3c7;
            color: #92400e;
        }

        .status-badge-rejected {
            background: #fee2e2;
            color: #991b1b;
        }

        .status-badge-default {
            background: #f1f5f9;
            color: #475569;
        }


        /* ============================================================
           RESPONSIVE
        ============================================================ */

        @media (max-width: 768px) {

            .leave-approval-meta {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .leave-welcome {
                padding: 15px 16px;
            }

            .balance-card {
                padding: 16px;
            }

        }

        </style>
        """,
        unsafe_allow_html=True,
    )



def render_nav_sidebar(role: str):
    with st.sidebar:
        st.markdown("### 🔍 Navigation")
        st.caption("Workforce and leave management")
        st.markdown("")

        if role in ("hr_admin", "manager"):
            st.markdown("#### 🏢 HR System")
            st.page_link("pages/9_HR_Overview.py", label="🏠 Dashboard")
            st.page_link("pages/1_Employee_Management.py", label="👥 Employee Management")
            st.page_link("pages/2_Leave_Management.py", label="🗓️ Leave Management")
            st.page_link("pages/5_Payroll_Management.py", label="💰 Payroll Management")
            st.page_link("pages/12_Public_Holidays.py", label="🏖️ Holiday Management")
            st.page_link("pages/11_Attendance.py", label="🕐 Attendance")
            st.page_link("pages/10_Performance.py", label="📌 Performance")
            st.page_link("pages/7_Reports.py", label="📊 Reports")

        st.markdown("#### 👤 My Workspace")
        st.page_link("pages/0_Dashboard.py", label="🏠 Dashboard")
        st.page_link("pages/8_Time.py", label="🗓️ My Leave")
        st.page_link("pages/6_Pay.py", label="💰 My Payslips")
        st.page_link("pages/4_My_Profile.py", label="👤 My Profile")

        st.divider()
        if st.button("Log out", use_container_width=True):
            from utils.auth import logout
            logout()
            st.rerun()
