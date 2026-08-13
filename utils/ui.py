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
            st.page_link("pages/1_Employee_Management.py", label="👥 All Employees")
            st.page_link("pages/2_Leave_Management.py", label="🗓️ Leave Approvals")
            st.page_link("pages/5_Payroll_Management.py", label="💰 Payslips")
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
