
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.sample_data import get_overview_data


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

st.title("Overview")

st.caption(
    "Workplace EV charging utilization and capacity analytics."
)

st.info(
    "UI prototype | Illustrative data only. "
    "Not actual ACN-Data results."
)


# --------------------------------------------------
# DATA AND FILTERS
# --------------------------------------------------

data = get_overview_data()

filter_col1, filter_col2 = st.columns([1, 1])

with filter_col1:
    selected_site = st.selectbox(
        "Charging site",
        ["All sites"] + data["sites"],
    )

with filter_col2:
    selected_period = st.selectbox(
        "Analysis period",
        [
            "All available dates",
            "Last 7 days",
            "Last 14 days",
        ],
    )


# Filter occupancy data
occupancy = data["occupancy"].copy()

if selected_site != "All sites":
    occupancy = occupancy[
        occupancy["site"] == selected_site
    ]

if selected_period == "Last 7 days":
    occupancy = occupancy[
        occupancy["date"]
        >= occupancy["date"].max() - pd.Timedelta(days=6)
    ]

elif selected_period == "Last 14 days":
    occupancy = occupancy[
        occupancy["date"]
        >= occupancy["date"].max() - pd.Timedelta(days=13)
    ]


# Aggregate occupancy by date
occupancy_trend = (
    occupancy.groupby("date", as_index=False)[
        ["average_occupancy", "peak_occupancy"]
    ]
    .mean()
)


# Filter hourly data
hourly = data["hourly"].copy()

if selected_site != "All sites":
    hourly = hourly[
        hourly["site"] == selected_site
    ]

hourly = (
    hourly.groupby("hour", as_index=False)["occupancy"]
    .mean()
)


# Site comparison data
occupancy_site = (
    data["occupancy"]
    .groupby("site", as_index=False)["average_occupancy"]
    .mean()
)

if selected_site != "All sites":
    occupancy_site = occupancy_site[
        occupancy_site["site"] == selected_site
    ]


# --------------------------------------------------
# KPI SUMMARY
# --------------------------------------------------

st.subheader("Utilization summary")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(
    "Total sessions",
    "—",
    help="Number of valid charging sessions.",
)

kpi2.metric(
    "Charging sites",
    "—",
    help="Number of sites included in the analysis.",
)

kpi3.metric(
    "Average occupancy",
    "—",
    help="Average number of simultaneously connected vehicles.",
)

kpi4.metric(
    "Peak occupancy",
    "—",
    help="Maximum simultaneous connected vehicles.",
)


# --------------------------------------------------
# OCCUPANCY TREND
# --------------------------------------------------

st.divider()

st.subheader("Occupancy trend")

st.caption(
    "Daily average and peak connected vehicles "
    "for the selected site and period."
)

fig_occupancy = px.line(
    occupancy_trend,
    x="date",
    y=["average_occupancy", "peak_occupancy"],
    labels={
        "date": "Date",
        "value": "Connected vehicles",
        "variable": "Occupancy metric",
    },
    color_discrete_sequence=[
        "#247D70",
        "#172B3A",
    ],
)

fig_occupancy.update_layout(
    height=340,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=20, r=20, t=25, b=20),
    legend_title_text="",
    hovermode="x unified",
)

fig_occupancy.update_xaxes(
    showgrid=False,
)

fig_occupancy.update_yaxes(
    rangemode="tozero",
    title="Connected vehicles",
)

st.plotly_chart(
    fig_occupancy,
    use_container_width=True,
)


# --------------------------------------------------
# SITE UTILIZATION
# --------------------------------------------------

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Site utilization")

    st.caption(
        "Average connected vehicles by charging site."
    )

    fig_sites = px.bar(
        occupancy_site,
        x="site",
        y="average_occupancy",
        labels={
            "site": "Charging site",
            "average_occupancy": "Average connected vehicles",
        },
        color_discrete_sequence=["#247D70"],
    )

    fig_sites.update_layout(
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        margin=dict(l=20, r=20, t=25, b=20),
    )

    fig_sites.update_xaxes(
        showgrid=False,
    )

    fig_sites.update_yaxes(
        rangemode="tozero",
    )

    st.plotly_chart(
        fig_sites,
        use_container_width=True,
    )


# --------------------------------------------------
# HOURLY OCCUPANCY
# --------------------------------------------------

with right_col:
    st.subheader("Hourly occupancy profile")

    st.caption(
        "Illustrative average occupancy by hour of day."
    )

    fig_hourly = px.area(
        hourly,
        x="hour",
        y="occupancy",
        labels={
            "hour": "Hour of day",
            "occupancy": "Connected vehicles",
        },
    )

    fig_hourly.update_traces(
        line_color="#247D70",
        fillcolor="rgba(36, 125, 112, 0.12)",
    )

    fig_hourly.update_layout(
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        margin=dict(l=20, r=20, t=25, b=20),
    )

    fig_hourly.update_xaxes(
        tickmode="linear",
        tick0=0,
        dtick=3,
        range=[0, 23],
        showgrid=False,
    )

    fig_hourly.update_yaxes(
        rangemode="tozero",
    )

    st.plotly_chart(
        fig_hourly,
        use_container_width=True,
    )


# --------------------------------------------------
# DATA QUALITY
# --------------------------------------------------

st.divider()

st.subheader("Data quality")

quality_col1, quality_col2 = st.columns(2)

with quality_col1:
    st.metric(
        "Usable sessions",
        "—",
        help="Sessions passing the agreed data-quality checks.",
    )

with quality_col2:
    st.metric(
        "Data coverage",
        "—",
        help="Verified date coverage of the selected dataset.",
    )

st.caption(
    "Data-quality statistics will populate after the "
    "ACN-Data extraction and validation pipeline is implemented."
)
