import streamlit as st
from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_login
from utils.dashboard import render_personal_dashboard

inject_css()
require_login()
render_nav_sidebar(st.session_state["role"])
render_personal_dashboard(st.session_state["role"])
