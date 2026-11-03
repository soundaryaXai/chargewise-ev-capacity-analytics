
import streamlit as st


def render_page_header(title, description, prototype=True):
    """Render a consistent header across dashboard pages."""

    st.title(title)
    st.caption(description)

    if prototype:
        st.info(
            "UI prototype | Illustrative data only. "
            "Not actual ACN-Data results."
        )
