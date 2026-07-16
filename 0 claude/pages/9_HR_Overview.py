import streamlit as st
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.dashboard import render_hr_dashboard

inject_css()
require_role(["hr_admin"])
render_nav_sidebar(st.session_state["role"])
render_hr_dashboard()
