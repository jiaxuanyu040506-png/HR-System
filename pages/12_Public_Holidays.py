import streamlit as st
from datetime import date

from utils.ui import inject_css, render_nav_sidebar
from utils.auth import require_role
from utils.sheets_client import (
    read_table,
    append_row,
    update_row,
    delete_row,
)

# INITIALIZE
inject_css()
require_role(["hr_admin", "manager"])
render_nav_sidebar(st.session_state["role"])

st.title("📅 Holiday Management")
st.caption("Manage public and special holidays used in leave calculations.")

# CONSTANTS
HOLIDAY_TYPES = ["Public Holiday", "Special Holiday"]

# HELPER FUNCTIONS

def get_holidays():
    """Load all holidays from Google Sheets."""
    df = read_table("PublicHolidays")

    if df.empty:
        return df

    # Make sure expected columns exist
    for col in ["date", "holiday_name", "holiday_type", "year", "active",]:
        if col not in df.columns:
            df[col] = ""
    return df

def parse_holiday_date(value):
    """Safely convert a sheet date value into a Python date."""
    try:
        if isinstance(value, date):
            return value

        return date.fromisoformat(str(value)[:10])

    except Exception:
        return None


def get_active_holidays():
    """
    Return active holidays as a set of dates.

    This function can also be imported by leave_rules.py.
    """
    df = get_holidays()

    if df.empty:
        return set()

    active = df[df["active"].astype(str).str.lower().isin(["true", "yes", "1"])]
    holidays = set()
    for value in active["date"]:
        holiday_date = parse_holiday_date(value)

        if holiday_date:
            holidays.add(holiday_date)

    return holidays

df = get_holidays()                                         # LOAD DATA
tab_holidays, tab_add = st.tabs(["📋 Holiday List", "➕ Add Holiday",])
with tab_holidays:
    st.html('<div class="spacer-xs"></div>')
    st.html('<div class="section-heading">Holiday List</div>')
    st.caption("View and manage public holidays and special holidays.")

    current_year = date.today().year                        # YEAR FILTER
    if not df.empty:
        years = []
        for value in df["date"]:
            holiday_date = parse_holiday_date(value)
            if holiday_date:
                years.append(holiday_date.year)
        years = sorted(set(years), reverse=True)
    else:
        years = []

    if current_year not in years:
        years.insert(0, current_year)

    selected_year = st.selectbox("Year", years, index = 0, key = "holiday_year_filter",)
    st.html('<div class="spacer-xs"></div>')

    if df.empty:
        filtered_df = df

    else:
        temp_df = df.copy()
        temp_df["_parsed_date"] = temp_df["date"].apply(parse_holiday_date)

        filtered_df = temp_df[temp_df["_parsed_date"].apply(lambda x: x is not None and x.year == selected_year)].copy()
        filtered_df = filtered_df.sort_values("_parsed_date")

    # SUMMARY
    total_holidays = len(filtered_df)
    active_holidays = 0
    special_holidays = 0

    if not filtered_df.empty:
        active_holidays = int(filtered_df["active"].astype(str).str.lower().isin(["true", "yes", "1"]).sum())
        special_holidays = int((filtered_df["holiday_type"].astype(str) == "Special Holiday").sum())

    c1, c2, c3 = st.columns(3)
    with c1:
        st.html(
            f"""
            <div class="metric-card">
                <div class="metric-label">📅 Total Holidays</div>
                <div class="metric-value">{total_holidays}</div>
                <div class="metric-subtext">holidays in {selected_year}</div>
            </div>
            """)
    with c2:
        st.html(
            f"""
            <div class="metric-card">
                <div class="metric-label">✓ Active Holidays</div>
                <div class="metric-value">{active_holidays}</div>
                <div class="metric-subtext">used in leave calculations</div>
            </div>
            """)
    with c3:
        st.html(
            f"""
            <div class="metric-card">
                <div class="metric-label">⭐ Special Holidays</div>
                <div class="metric-value">{special_holidays}</div>
                <div class="metric-subtext">additional holidays</div>
            </div>
            """)

    # HOLIDAY LIST
    st.html('<div class="spacer-md"></div>')
    st.html('<div class="section-heading">Holidays</div>')

    if filtered_df.empty:
        st.info(f"No holidays have been added for {selected_year}.")
    else:
        for _, row in filtered_df.iterrows():
            holiday_date = parse_holiday_date(row["date"])
            holiday_name = str(row.get("holiday_name", ""))
            holiday_type = str(row.get("holiday_type", "Public Holiday"))
            is_active = (str(row.get("active", "True")).lower() in ["true", "yes", "1"])
            record_date = (holiday_date.strftime("%d %b %Y") if holiday_date else str(row["date"]))

            # HOLIDAY CARD
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 2, 1], vertical_alignment = "center",)
                with col1:
                    icon = ("⭐" if holiday_type == "Special Holiday" else "📅")
                    st.markdown(f"**{icon} {record_date}**")
                    st.caption(holiday_name)
                with col2:
                    st.markdown(f"**{holiday_type}**")
                    if is_active:
                        st.caption("✓ Active")
                    else:
                        st.caption("Inactive")
                with col3:
                    edit_key = (f"edit_holiday_{row.get('date')}_{holiday_name}")
                    if st.button("Edit", key = edit_key, use_container_width = True,):
                        st.session_state["editing_holiday"] = row.get("date")
                        st.rerun()

            # EDIT FORM
            if (st.session_state.get("editing_holiday") == row.get("date")):
                with st.container(border=True):
                    st.markdown("#### ✏️ Edit Holiday")
                    edit_date = st.date_input("Holiday Date", value = (holiday_date if holiday_date else date.today()), key = f"edit_date_{row.get('date')}",)
                    edit_name = st.text_input("Holiday Name", value = holiday_name, key = f"edit_name_{row.get('date')}",)
                    current_type_index = (HOLIDAY_TYPES.index(holiday_type) if holiday_type in HOLIDAY_TYPES else 0)
                    edit_type = st.selectbox("Holiday Type", HOLIDAY_TYPES, index = current_type_index, key = f"edit_type_{row.get('date')}",)
                    edit_active = st.checkbox("Active", value = is_active, key = f"edit_active_{row.get('date')}",)

                    save_col, cancel_col, delete_col = st.columns(3)
                    with save_col:
                        if st.button("Save Changes", type = "primary", use_container_width = True, key = f"save_holiday_{row.get('date')}",):
                            if not edit_name.strip():
                                st.error("Please enter a holiday name.")
                            else:
                                update_row("PublicHolidays", {"date": row["date"]},
                                    {"date": str(edit_date),
                                     "holiday_name": edit_name.strip(),
                                     "holiday_type": edit_type,
                                     "year": edit_date.year,
                                     "active": edit_active,
                                    },)
                                st.session_state.pop("editing_holiday", None,)
                                st.success("Holiday updated.")
                                st.rerun()
                    with cancel_col:
                        if st.button("Cancel", use_container_width=True, key = f"cancel_holiday_{row.get('date')}",):
                            st.session_state.pop("editing_holiday", None,)
                            st.rerun()
                    with delete_col:
                        if st.button("Delete", type = "secondary", use_container_width =True, key = f"delete_holiday_{row.get('date')}",):
                            delete_row("PublicHolidays", {"date": row["date"]},)

                            st.session_state.pop("editing_holiday", None,)
                            st.success("Holiday deleted.")
                            st.rerun()

    # LEGEND
    st.html('<div class="spacer-md"></div>')
    st.caption("💡 Only active holidays are excluded when calculating working days for leave.")

# ADD HOLIDAY
with tab_add:
    st.html('<div class="spacer-xs"></div>')
    st.html('<div class="section-heading">Add Holiday</div>')
    st.caption("Add a public holiday or a special holiday announced by the government.")

    with st.container(border=True):
        holiday_date = st.date_input("Holiday Date", value = date.today(), key = "new_holiday_date",)
        holiday_name = st.text_input("Holiday Name", placeholder = "e.g. Special Hari Raya Holiday", key = "new_holiday_name",)
        holiday_type = st.selectbox("Holiday Type", HOLIDAY_TYPES, key = "new_holiday_type",)
        active = st.checkbox("Active", value = True, key = "new_holiday_active",)

        st.html('<div class="spacer-xs"></div>')
        if st.button("Add Holiday", type = "primary", use_container_width = True, key = "add_holiday_btn",):
            if not holiday_name.strip():
                st.error("Please enter a holiday name.")
            else:
                # Check duplicate date
                existing = get_holidays()
                duplicate = False

                if not existing.empty:
                    for existing_date in existing["date"]:
                        parsed = parse_holiday_date(existing_date)
                        if parsed == holiday_date:
                            duplicate = True
                            break

                if duplicate:
                    st.error(f"A holiday already exists on {holiday_date.strftime('%d %b %Y')}.")
                else:
                    append_row("PublicHolidays",
                        {"date": str(holiday_date),
                         "holiday_name": holiday_name.strip(),
                         "holiday_type": holiday_type,
                         "year": holiday_date.year,
                         "active": active,
                        },)

                    st.success(f"{holiday_name.strip()} has been added for {holiday_date.strftime('%d %b %Y')}.")
                    st.rerun()