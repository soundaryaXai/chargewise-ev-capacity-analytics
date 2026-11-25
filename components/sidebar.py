
import streamlit as st


def render_sidebar(pages):
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

        for label, page in pages:
            st.page_link(
                page,
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
