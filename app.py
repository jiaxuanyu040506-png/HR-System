import streamlit as st
from utils.auth import login, logout, change_password, restore_login_from_query
from utils.ui import inject_css, render_nav_sidebar
from utils.dashboard import render_hr_dashboard, render_personal_dashboard

inject_css()
st.set_page_config(page_title="HR System", page_icon="🗂️", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    if restore_login_from_query():
        st.rerun()
    st.markdown(
        """
        <div class="auth-card-shell">
            <h1 class="auth-header-title">HR Management System</h1>
            <p class="auth-header-subtitle">Welcome! Please sign in to your account</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        with st.form("login_form"):
            st.markdown("<div class='auth-form-shell'>", unsafe_allow_html=True)
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            remember = st.checkbox("Remember me")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    if submitted:
        if login(email, password):
            st.session_state["logged_in"] = True
            if remember:
                st.session_state["remember_me"] = True
            st.rerun()
        else:
            st.error("Incorrect email or password, or your account is inactive.")
    st.stop()

if st.session_state.get("force_password_reset"):
    st.title("Set a New Password")
    st.info("This is your first login. Please set a new password before continuing.")
    with st.form("change_password_form"):
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password")
    if submitted:
        if new_password != confirm_password:
            st.error("Passwords do not match.")
        elif len(new_password) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            change_password(st.session_state["employee_id"], new_password)
            st.success("Password updated. You can now use the system.")
            st.rerun()
    st.stop()

role = st.session_state["role"]
render_nav_sidebar(role)
if role == "hr_admin":
    render_hr_dashboard()
else:
    render_personal_dashboard(role)
