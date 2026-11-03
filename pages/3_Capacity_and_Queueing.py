
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from utils.sample_data import get_capacity_data
from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Capacity & Queueing Analysis",
    "Evaluate how available charging-port capacity relates "
    "to service availability and blocking risk.",
)

st.caption(
    "The charts on this page currently use illustrative "
    "development data. They are not ACN-Data findings."
)


# --------------------------------------------------
# DATA
# --------------------------------------------------

capacity_data, sites = get_capacity_data()


# --------------------------------------------------
# FILTERS
# --------------------------------------------------

filter_col1, filter_col2 = st.columns([1, 2])

with filter_col1:
    selected_site = st.selectbox(
        "Charging site",
        sites,
    )

with filter_col2:
    selected_target = st.selectbox(
        "Blocking target",
        ["1%", "5%", "10%"],
    )

target_value = float(selected_target.replace("%", ""))

site_data = capacity_data[
    capacity_data["site"] == selected_site
].copy()


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

st.divider()

st.subheader("Capacity indicators")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Verified port capacity",
    "—",
    help="Will be populated after site capacity verification.",
)

metric2.metric(
    "Observed peak occupancy",
    "—",
    help="Maximum simultaneous connected sessions.",
)

metric3.metric(
    "Required ports",
    "—",
    help=f"Capacity required for a {selected_target} blocking target.",
)

metric4.metric(
    "Estimated blocking",
    "—",
    help="Will be calculated from the validated session replay.",
)


# --------------------------------------------------
# BLOCKING VS PORT COUNT
# --------------------------------------------------

st.divider()

st.subheader("Blocking probability by available ports")

st.caption(
    "Illustrative comparison of an Erlang-B baseline and "
    "a placeholder replay curve. Lower blocking indicates "
    "a higher proportion of arrivals being accommodated."
)

fig_blocking = go.Figure()

fig_blocking.add_trace(
    go.Scatter(
        x=site_data["ports"],
        y=site_data["erlang_b_blocking"],
        mode="lines+markers",
        name="Erlang-B baseline",
        line=dict(
            color="#247D70",
            width=2.5,
        ),
    )
)

fig_blocking.add_trace(
    go.Scatter(
        x=site_data["ports"],
        y=site_data["replay_blocking"],
        mode="lines+markers",
        name="Replay placeholder",
        line=dict(
            color="#172B3A",
            width=2.5,
            dash="dash",
        ),
    )
)

fig_blocking.add_hline(
    y=target_value,
    line_dash="dot",
    line_color="#98A2B3",
    annotation_text=f"{selected_target} target",
    annotation_position="top right",
)

fig_blocking.update_layout(
    height=420,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=30, r=30, t=30, b=30),
    xaxis_title="Available charging ports",
    yaxis_title="Blocking probability (%)",
    legend_title_text="",
    hovermode="x unified",
)

fig_blocking.update_xaxes(
    dtick=2,
    showgrid=False,
)

fig_blocking.update_yaxes(
    rangemode="tozero",
    gridcolor="#EAECF0",
)

st.plotly_chart(
    fig_blocking,
    use_container_width=True,
)


# --------------------------------------------------
# BASELINE COMPARISON
# --------------------------------------------------

left_col, right_col = st.columns(2)

with left_col:

    st.subheader("Erlang-B baseline")

    st.markdown(
        """
        Erlang-B estimates blocking in a loss system where
        arriving sessions are either accepted immediately
        or blocked when all ports are occupied.

        **Model inputs**
        - Arrival rate, λ
        - Mean connected-session duration, E[S]
        - Number of available ports, c

        Offered load is calculated as:

        \\[
        A = \\lambda E[S]
        \\]
        """
    )

    st.caption(
        "The final model will estimate arrival rates separately "
        "for each hour-of-week slice."
    )

with right_col:

    st.subheader("Session replay")

    st.markdown(
        """
        The replay will process sessions in arrival order
        and test whether a port remains available for each
        session's observed connected duration.

        **Replay outputs**
        - Accepted sessions
        - Blocked sessions
        - Blocking probability
        - Required ports at selected targets
        """
    )

    st.caption(
        "Replay occupancy will use connection time through "
        "disconnection time, not charging duration alone."
    )


# --------------------------------------------------
# CAPACITY CURVE DATA TABLE
# --------------------------------------------------

st.divider()

st.subheader("Capacity comparison")

st.caption(
    "Illustrative values for layout testing only. "
    "Replace with validated model outputs."
)

display_data = site_data.rename(
    columns={
        "ports": "Available ports",
        "erlang_b_blocking": "Erlang-B blocking (%)",
        "replay_blocking": "Replay placeholder (%)",
    }
)

display_data = display_data[
    [
        "Available ports",
        "Erlang-B blocking (%)",
        "Replay placeholder (%)",
    ]
].copy()

display_data["Erlang-B blocking (%)"] = (
    display_data["Erlang-B blocking (%)"].round(2)
)

display_data["Replay placeholder (%)"] = (
    display_data["Replay placeholder (%)"].round(2)
)

st.dataframe(
    display_data,
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# METHODOLOGY NOTES
# --------------------------------------------------

st.divider()

st.subheader("Model assumptions")

assumption_col1, assumption_col2 = st.columns(2)

with assumption_col1:
    st.markdown(
        """
        **Erlang-B**
        - No waiting queue.
        - Blocked arrivals leave the system.
        - Mean service time represents connected duration.
        - Arrival rates are estimated by hour-of-week.
        """
    )

with assumption_col2:
    st.markdown(
        """
        **Session replay**
        - Sessions are processed chronologically.
        - Occupancy runs from connection to disconnection.
        - Blocked sessions are assumed to leave.
        - Observed arrivals and durations are retained.
        """
    )

st.info(
    "Interpretation note: Erlang-B and session replay are "
    "different modelling approaches. Their difference will "
    "be evaluated after the real data pipeline and replay "
    "validation are complete."
)
