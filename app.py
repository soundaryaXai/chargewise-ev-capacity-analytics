
from pathlib import Path

import streamlit as st

from components.sidebar import render_sidebar


BASE_DIR = Path(__file__).parent


st.set_page_config(
    page_title="ChargeWise | EV Charging Analytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load global styles
css_path = BASE_DIR / "assets" / "styles.css"

with open(css_path, encoding="utf-8") as css_file:
    st.markdown(
        f"<style>{css_file.read()}</style>",
        unsafe_allow_html=True,
    )

# Sidebar branding
render_sidebar()

# Define dashboard navigation
overview = st.Page(
    "pages/1_Overview.py",
    title="Overview",
    default=True,
)

utilization = st.Page(
    "pages/2_Utilization_and_Behaviour.py",
    title="Utilization & Behaviour",
)

capacity = st.Page(
    "pages/3_Capacity_and_Queueing.py",
    title="Capacity & Queueing",
)

scenarios = st.Page(
    "pages/4_Policy_and_Scenarios.py",
    title="Policy & Scenarios",
)

methodology = st.Page(
    "pages/5_Data_and_Methodology.py",
    title="Data & Methodology",
)

navigation = st.navigation(
    [
        overview,
        utilization,
        capacity,
        scenarios,
        methodology,
    ],
    position="hidden",
)

navigation.run()
