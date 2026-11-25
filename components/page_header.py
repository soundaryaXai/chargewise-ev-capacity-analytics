
import streamlit as st


def render_page_header(title, description):
    """Render a consistent header across dashboard pages."""

    st.title(title)
    st.caption(description)
