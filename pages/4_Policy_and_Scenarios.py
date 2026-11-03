
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from utils.sample_data import get_scenario_data
from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Policy & Scenario Analysis",
    "Explore hypothetical capacity reductions and "
    "post-charge dwell policies.",
)

st.warning(
    "Scenario prototype | All results are illustrative. "
    "They are not observed driver behaviour or validated "
    "ACN-Data simulation results."
)


# --------------------------------------------------
# DATA
# --------------------------------------------------

scenario_data, sites = get_scenario_data()


# --------------------------------------------------
# SCENARIO CONTROLS
# --------------------------------------------------

st.subheader("Scenario configuration")

control_col1, control_col2, control_col3 = st.columns(3)

with control_col1:
    selected_site = st.selectbox(
        "Charging site",
        sites,
    )

with control_col2:
    selected_ports = st.slider(
        "Available charging ports",
        min_value=8,
        max_value=32,
        value=16,
        step=1,
    )

with control_col3:
    selected_dwell_cap = st.selectbox(
        "Post-charge dwell cap",
        ["No cap", "30 minutes", "60 minutes", "120 minutes"],
    )


# --------------------------------------------------
# FILTER SCENARIO DATA
# --------------------------------------------------

site_data = scenario_data[
    scenario_data["site"] == selected_site
].copy()

reference_ports = int(
    site_data["reference_ports"].iloc[0]
)

baseline_row = site_data[
    (site_data["ports"] == reference_ports)
    & (site_data["dwell_cap"] == "No cap")
]

capacity_row = site_data[
    (site_data["ports"] == selected_ports)
    & (site_data["dwell_cap"] == "No cap")
]

scenario_row = site_data[
    (site_data["ports"] == selected_ports)
    & (site_data["dwell_cap"] == selected_dwell_cap)
]

baseline_blocking = float(
    baseline_row["blocking_probability"].iloc[0]
)

capacity_blocking = float(
    capacity_row["blocking_probability"].iloc[0]
)

scenario_blocking = float(
    scenario_row["blocking_probability"].iloc[0]
)

capacity_change = selected_ports - reference_ports

blocking_change = scenario_blocking - baseline_blocking


# --------------------------------------------------
# SCENARIO SUMMARY
# --------------------------------------------------

st.divider()

st.subheader("Scenario impact summary")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Reference capacity",
    f"{reference_ports} ports",
)

metric2.metric(
    "Scenario capacity",
    f"{selected_ports} ports",
    delta=f"{capacity_change:+d} ports",
)

metric3.metric(
    "Baseline blocking",
    f"{baseline_blocking:.2f}%",
)

metric4.metric(
    "Scenario blocking",
    f"{scenario_blocking:.2f}%",
    delta=f"{blocking_change:+.2f} pp",
    delta_color="inverse",
)


# --------------------------------------------------
# CAPACITY REDUCTION ANALYSIS
# --------------------------------------------------

st.divider()

st.subheader("Impact of available port capacity")

st.caption(
    "Illustrative blocking estimates across different "
    "available-port counts, with no dwell cap applied."
)

capacity_curve = site_data[
    site_data["dwell_cap"] == "No cap"
].copy()

fig_capacity = px.line(
    capacity_curve,
    x="ports",
    y="blocking_probability",
    labels={
        "ports": "Available charging ports",
        "blocking_probability": "Blocking probability (%)",
    },
)

fig_capacity.add_vline(
    x=reference_ports,
    line_dash="dot",
    line_color="#98A2B3",
    annotation_text="Reference capacity",
)

fig_capacity.add_vline(
    x=selected_ports,
    line_dash="dash",
    line_color="#247D70",
    annotation_text="Selected capacity",
)

fig_capacity.update_traces(
    line=dict(
        color="#247D70",
        width=2.5,
    ),
    mode="lines+markers",
)

fig_capacity.update_layout(
    height=360,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=30, r=30, t=35, b=30),
    showlegend=False,
)

fig_capacity.update_yaxes(
    rangemode="tozero",
    gridcolor="#EAECF0",
)

fig_capacity.update_xaxes(
    dtick=2,
    showgrid=False,
)

st.plotly_chart(
    fig_capacity,
    use_container_width=True,
)


# --------------------------------------------------
# DWELL CAP SENSITIVITY
# --------------------------------------------------

st.divider()

st.subheader("Post-charge dwell sensitivity")

st.caption(
    "Compare illustrative blocking estimates under "
    "different hypothetical post-charge dwell caps."
)

dwell_data = site_data[
    (site_data["ports"] == selected_ports)
].copy()

dwell_order = [
    "No cap",
    "30 minutes",
    "60 minutes",
    "120 minutes",
]

dwell_data["dwell_cap"] = (
    dwell_data["dwell_cap"].astype(str)
)

dwell_data["dwell_cap"] = (
    dwell_data["dwell_cap"].astype(
        "category"
    ).cat.set_categories(
        dwell_order,
        ordered=True,
    )
)

dwell_data = dwell_data.sort_values("dwell_cap")

fig_dwell = px.bar(
    dwell_data,
    x="dwell_cap",
    y="blocking_probability",
    labels={
        "dwell_cap": "Hypothetical dwell cap",
        "blocking_probability": "Blocking probability (%)",
    },
)

fig_dwell.update_traces(
    marker_color="#247D70",
)

fig_dwell.update_layout(
    height=340,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=30, r=30, t=25, b=30),
    showlegend=False,
)

fig_dwell.update_yaxes(
    rangemode="tozero",
    gridcolor="#EAECF0",
)

st.plotly_chart(
    fig_dwell,
    use_container_width=True,
)


# --------------------------------------------------
# SCENARIO COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Baseline and selected scenario")

comparison = {
    "Scenario": [
        "Reference capacity, no dwell cap",
        "Selected capacity, no dwell cap",
        "Selected capacity and dwell cap",
    ],
    "Blocking probability (%)": [
        baseline_blocking,
        capacity_blocking,
        scenario_blocking,
    ],
}

comparison_fig = go.Figure()

comparison_fig.add_trace(
    go.Bar(
        x=comparison["Scenario"],
        y=comparison["Blocking probability (%)"],
        marker_color=[
            "#98A2B3",
            "#172B3A",
            "#247D70",
        ],
    )
)

comparison_fig.update_layout(
    height=330,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=25, r=25, t=25, b=70),
    yaxis_title="Blocking probability (%)",
    showlegend=False,
)

comparison_fig.update_yaxes(
    rangemode="tozero",
    gridcolor="#EAECF0",
)

st.plotly_chart(
    comparison_fig,
    use_container_width=True,
)

comparison_table = {
    "Scenario": comparison["Scenario"],
    "Blocking probability (%)": [
        round(value, 2)
        for value in comparison["Blocking probability (%)"]
    ],
}

st.dataframe(
    comparison_table,
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# INTERPRETATION
# --------------------------------------------------

st.divider()

st.subheader("Interpretation and limitations")

st.markdown(
    """
    **Capacity reduction**

    Reducing available ports can increase the proportion
    of arrivals that cannot be accommodated. The actual
    impact depends on arrival patterns and connected-session
    durations.

    **Post-charge dwell policy**

    A dwell cap is a hypothetical intervention. Its
    effectiveness depends on whether drivers can and do
    move their vehicles after charging is complete.

    **Important distinction**

    The current prototype applies illustrative load
    adjustments to demonstrate the interface. It does not
    calculate modified session departure times or replay
    actual ACN-Data sessions.
    """
)

st.caption(
    "Final analysis will report modified session counts, "
    "connected hours removed, replay blocking changes, "
    "and uncertainty intervals using validated session data."
)
