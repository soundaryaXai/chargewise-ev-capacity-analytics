
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION AND PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

st.title("Overview")

st.caption(
    "Workplace EV charging utilization and capacity analytics."
)


# --------------------------------------------------
# LOAD PROCESSED DATA
# --------------------------------------------------

@st.cache_data
def load_overview_data():

    files = {
        "quality": "data_quality_summary.csv",
        "regime": "eda_regime_summary.csv",
        "hourly": "eda_occupancy_hour_of_week.csv",
        "empirical": "empirical_capacity_summary.csv",
        "pressure": "capacity_pressure_summary.csv",
        "inventory": "station_inventory_summary.csv",
    }

    data = {}

    for key, filename in files.items():

        path = PROCESSED_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Required analytical output not found: {path}"
            )

        data[key] = pd.read_csv(path)

    return data


try:
    data = load_overview_data()

except (FileNotFoundError, pd.errors.ParserError) as error:

    st.error(
        f"Unable to load the processed analytical data: {error}"
    )

    st.stop()


quality = data["quality"]
regime = data["regime"]
hourly = data["hourly"]
empirical = data["empirical"]
pressure = data["pressure"]
inventory = data["inventory"]


# --------------------------------------------------
# SITE FILTER
# --------------------------------------------------

sites = sorted(quality["site"].dropna().unique().tolist())

filter_col, _ = st.columns([1, 2])

with filter_col:

    selected_site = st.selectbox(
        "Charging site",
        ["All sites"] + sites,
    )


if selected_site == "All sites":

    filtered_quality = quality.copy()
    filtered_regime = regime.copy()
    filtered_hourly = hourly.copy()
    filtered_empirical = empirical.copy()
    filtered_pressure = pressure.copy()
    filtered_inventory = inventory.copy()

else:

    filtered_quality = quality[
        quality["site"] == selected_site
    ].copy()

    filtered_regime = regime[
        regime["site"] == selected_site
    ].copy()

    filtered_hourly = hourly[
        hourly["site"] == selected_site
    ].copy()

    filtered_empirical = empirical[
        empirical["site"] == selected_site
    ].copy()

    filtered_pressure = pressure[
        pressure["site"] == selected_site
    ].copy()

    site_id_mapping = {
        "Caltech": "caltech",
        "JPL": "jpl",
        "Office 1": "office001",
    }

    selected_site_id = site_id_mapping.get(selected_site)

    filtered_inventory = inventory[
        inventory["site_id"] == selected_site_id
    ].copy()


if filtered_quality.empty:

    st.warning("No data available for the selected site.")
    st.stop()


# --------------------------------------------------
# DERIVED METRICS
# --------------------------------------------------

total_sessions = int(
    filtered_quality["total_records"].sum()
)

total_sites = int(
    filtered_quality["site"].nunique()
)

usable_sessions = int(
    filtered_quality["usable_records"].sum()
)

usable_percentage = (
    usable_sessions / total_sessions * 100
    if total_sessions > 0
    else 0
)

mean_hourly_occupancy = (
    filtered_hourly["mean_simultaneous_occupancy"].mean()
    if not filtered_hourly.empty
    else 0
)

maximum_weekly_peak = (
    filtered_empirical["maximum_weekly_peak"].max()
    if not filtered_empirical.empty
    else 0
)

total_station_ids = int(
    filtered_inventory["unique_station_ids"].sum()
)

earliest_date = pd.to_datetime(
    filtered_quality["earliest_connection_utc"],
    utc=True,
).min()

latest_date = pd.to_datetime(
    filtered_quality["latest_connection_utc"],
    utc=True,
).max()


# --------------------------------------------------
# KPI SUMMARY
# --------------------------------------------------

st.subheader("Utilization summary")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(
    "Total sessions",
    f"{total_sessions:,}",
    help="Total extracted sessions across the selected site or sites.",
)

kpi2.metric(
    "Charging sites",
    f"{total_sites}",
    help="Number of sites included in the selection.",
)

kpi3.metric(
    "Mean hourly occupancy",
    f"{mean_hourly_occupancy:.2f}",
    help=(
        "Mean of the available hour-of-week occupancy estimates. "
        "This is not a real-time occupancy measure."
    ),
)

kpi4.metric(
    "Maximum weekly peak",
    f"{int(maximum_weekly_peak):,}",
    help=(
        "Highest observed weekly peak occupancy across the "
        "available site-regime summaries."
    ),
)


st.caption(
    f"Observed connection-date range: "
    f"{earliest_date:%d %b %Y} – {latest_date:%d %b %Y}"
)


# --------------------------------------------------
# OCCUPANCY BY HOUR OF WEEK
# --------------------------------------------------

st.divider()

st.subheader("Occupancy profile")

st.caption(
    "Mean simultaneous connected vehicles by hour of the week, "
    "using reconstructed historical occupancy."
)

weekday_names = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

if not filtered_hourly.empty:

    hourly_profile = (
        filtered_hourly
        .groupby(
            "hour_of_week",
            as_index=False
        )["mean_simultaneous_occupancy"]
        .mean()
        .sort_values("hour_of_week")
    )

    tick_positions = list(range(0, 168, 24))

    tick_labels = weekday_names

    fig_hourly = px.line(
        hourly_profile,
        x="hour_of_week",
        y="mean_simultaneous_occupancy",
        labels={
            "hour_of_week": "Day of week",
            "mean_simultaneous_occupancy": (
                "Mean connected vehicles"
            ),
        },
    )

    fig_hourly.update_traces(
        line_color="#247D70",
        line_width=2.5,
    )

    fig_hourly.update_layout(
        height=360,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=25, b=35),
        showlegend=False,
        hovermode="x unified",
    )

    fig_hourly.update_xaxes(
        tickmode="array",
        tickvals=tick_positions,
        ticktext=tick_labels,
        showgrid=False,
    )

    fig_hourly.update_yaxes(
        rangemode="tozero",
        title="Mean connected vehicles",
    )

    st.plotly_chart(
        fig_hourly,
        use_container_width=True,
    )

else:

    st.info("No hourly occupancy data is available.")


# --------------------------------------------------
# SITE COMPARISON
# --------------------------------------------------

left_col, right_col = st.columns(2)

with left_col:

    st.subheader("Site occupancy")

    st.caption(
        "Average simultaneous occupancy across the "
        "168 hour-of-week observations."
    )

    if not hourly.empty:

        site_occupancy = (
            hourly
            .groupby("site", as_index=False)
            ["mean_simultaneous_occupancy"]
            .mean()
            .sort_values(
                "mean_simultaneous_occupancy",
                ascending=False,
            )
        )

        fig_sites = px.bar(
            site_occupancy,
            x="site",
            y="mean_simultaneous_occupancy",
            labels={
                "site": "Charging site",
                "mean_simultaneous_occupancy": (
                    "Mean connected vehicles"
                ),
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

    else:

        st.info("No site occupancy data is available.")


# --------------------------------------------------
# CAPACITY PRESSURE
# --------------------------------------------------

with right_col:

    st.subheader("Capacity pressure")

    st.caption(
        "Percentage of eligible full weeks with a peak "
        "at or above 80% of the assumed site capacity."
    )

    pressure_data = filtered_pressure[
        filtered_pressure["regime"].isin(
            ["Pre-disruption", "Recovery"]
        )
    ].copy()

    if not pressure_data.empty:

        pressure_data["display_label"] = (
            pressure_data["site"]
            + " — "
            + pressure_data["regime"]
        )

        fig_pressure = px.bar(
            pressure_data,
            x="display_label",
            y="pressure_percentage",
            color="regime",
            barmode="group",
            labels={
                "display_label": "Site and regime",
                "pressure_percentage": "Weeks under pressure (%)",
                "regime": "Operating regime",
            },
            color_discrete_map={
                "Pre-disruption": "#247D70",
                "Recovery": "#A6B7C4",
            },
        )

        fig_pressure.update_layout(
            height=320,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=25, b=20),
            showlegend=True,
            legend_title_text="",
        )

        fig_pressure.update_xaxes(
            showgrid=False,
            tickangle=-20,
        )

        fig_pressure.update_yaxes(
            rangemode="tozero",
            title="Eligible weeks (%)",
        )

        st.plotly_chart(
            fig_pressure,
            use_container_width=True,
        )

    else:

        st.info("No capacity-pressure data is available.")


# --------------------------------------------------
# REGIME SUMMARY
# --------------------------------------------------

st.divider()

st.subheader("Operating regime comparison")

st.caption(
    "Historical session volumes and connected-duration statistics "
    "across the observed operating regimes."
)

if not filtered_regime.empty:

    regime_display = filtered_regime[
        [
            "site",
            "regime",
            "sessions",
            "unique_stations",
            "median_connected_hours",
            "mean_connected_hours",
        ]
    ].copy()

    regime_display = regime_display.rename(
        columns={
            "site": "Site",
            "regime": "Operating regime",
            "sessions": "Sessions",
            "unique_stations": "Observed station IDs",
            "median_connected_hours": "Median connected hours",
            "mean_connected_hours": "Mean connected hours",
        }
    )

    regime_display["Median connected hours"] = (
        regime_display["Median connected hours"].round(2)
    )

    regime_display["Mean connected hours"] = (
        regime_display["Mean connected hours"].round(2)
    )

    st.dataframe(
        regime_display,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# DATA QUALITY
# --------------------------------------------------

st.divider()

st.subheader("Data quality")

quality_col1, quality_col2, quality_col3 = st.columns(3)

quality_col1.metric(
    "Core-valid sessions",
    f"{usable_sessions:,}",
)

quality_col2.metric(
    "Core-field usability",
    f"{usable_percentage:.1f}%",
)

quality_col3.metric(
    "Observed station IDs",
    f"{total_station_ids:,}",
)


quality_display = filtered_quality[
    [
        "site",
        "total_records",
        "usable_records",
        "unique_stations",
        "overlapping_session_rows",
        "earliest_connection_utc",
        "latest_connection_utc",
    ]
].copy()

quality_display = quality_display.rename(
    columns={
        "site": "Site",
        "total_records": "Total sessions",
        "usable_records": "Core-valid sessions",
        "unique_stations": "Unique station IDs",
        "overlapping_session_rows": "Overlap anomalies",
        "earliest_connection_utc": "First connection (UTC)",
        "latest_connection_utc": "Last connection (UTC)",
    }
)

st.dataframe(
    quality_display,
    use_container_width=True,
    hide_index=True,
)


st.warning(
    "Core-field usability validates required timestamps, station IDs "
    "and interval ordering. It does not establish complete data "
    "integrity or verified engineering capacity. JPL contains a "
    "known conflicting session pair excluded from the primary "
    "capacity replay. Station IDs are historical observed identifiers, "
    "not independently verified commissioned-port counts."
)


# --------------------------------------------------
# DATA COVERAGE NOTE
# --------------------------------------------------

st.caption(
    "Source: ACN-Data. Historical session records from 2018–2021. "
    "Occupancy is reconstructed from connection-to-disconnect "
    "intervals in the America/Los_Angeles local timezone. "
    "These observations do not include rejected charging requests "
    "or directly observed waiting times."
)
