
from pathlib import Path
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent.parent


def render_sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div class="brand">
                <div class="brand-name">CHARGEWISE</div>
                <div class="brand-subtitle">
                    EV CHARGING ANALYTICS
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.caption("RESEARCH DASHBOARD")

        pages = [
            ("Overview", "pages/1_Overview.py"),
            ("Utilization & Behaviour", "pages/2_Utilization_and_Behaviour.py"),
            ("Capacity & Queueing", "pages/3_Capacity_and_Queueing.py"),
            ("Policy & Scenarios", "pages/4_Policy_and_Scenarios.py"),
            ("Data & Methodology", "pages/5_Data_and_Methodology.py"),
        ]

        for label, relative_path in pages:
            page_path = BASE_DIR / relative_path

            st.page_link(
                str(page_path),
                label=label,
            )

        st.divider()
        st.caption("DATA CONTEXT")

        st.markdown(
            """
            <div class="sidebar-context">
                <span>Dataset</span>
                <strong>ACN-Data</strong>
                <span>Analysis type</span>
                <strong>Historical research</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        st.markdown(
            """
            <div class="sidebar-footer">
                ChargeWise<br>
                EV Capacity & Queueing Analytics
            </div>
            """,
            unsafe_allow_html=True,
        )
