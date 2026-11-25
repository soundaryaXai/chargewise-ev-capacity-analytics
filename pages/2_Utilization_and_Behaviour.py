
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Utilization & Behaviour",
    "Explore historical workplace charging patterns, occupancy "
    "variation and connected-session behaviour.",
)


# --------------------------------------------------
# PATHS AND CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

DAY_TYPE_MAP = {
    "Weekdays": [0, 1, 2, 3, 4],
    "Weekends": [5, 6],
}

COLORS = {
    "primary": "#247D70",
    "secondary": "#172B3A",
    "muted": "#98A2B3",
    "light": "#A9CFC8",
}

REGIME_ORDER = [
    "Pre-disruption",
    "Transition",
    "Disruption",
    "Recovery",
]


# --------------------------------------------------
# LOAD PROCESSED DATA
# --------------------------------------------------

@st.cache_data
def load_utilization_data():

    filenames = {
        "arrivals_hourly": "eda_arrivals_hourly.csv",
        "arrivals_how": "eda_arrivals_hour_of_week.csv",
        "occupancy": "eda_occupancy_hour_of_week.csv",
        "weekday_weekend": "eda_weekday_weekend.csv",
        "duration": "eda_duration_summary.csv",
        "sensitivity": "duration_sensitivity_summary.csv",
    }

    frames = {}

    for key, filename in filenames.items():

        path = PROCESSED_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Required analytical output not found: {path}"
            )

        frames[key] = pd.read_csv(path)

    return frames


try:
    data = load_utilization_data()

except (FileNotFoundError, pd.errors.ParserError) as error:

    st.error(
        f"Unable to load utilization data: {error}"
    )

    st.stop()


arrivals_hourly = data["arrivals_hourly"]
arrivals_how = data["arrivals_how"]
occupancy = data["occupancy"]
weekday_weekend = data["weekday_weekend"]
duration = data["duration"]
sensitivity = data["sensitivity"]


# --------------------------------------------------
# DATA VALIDATION
# --------------------------------------------------

required_columns = {
    "arrivals_hourly": {
        "site", "local_hour", "arrival_sessions"
    },
    "arrivals_how": {
        "site", "weekday_number", "weekday_name",
        "local_hour", "hour_of_week", "arrival_sessions"
    },
    "occupancy": {
        "site", "weekday_number", "local_hour",
        "hour_of_week", "mean_simultaneous_occupancy"
    },
    "weekday_weekend": {
        "site", "day_type", "sessions",
        "mean_connected_hours", "median_connected_hours",
        "median_charging_hours",
        "median_post_charge_dwell_hours"
    },
    "duration": {
        "site", "regime", "duration_type",
        "valid_sessions", "mean_hours", "median_hours",
        "p75_hours", "p90_hours", "p95_hours"
    },
    "sensitivity": {
        "site", "regime", "scenario",
        "retained_sessions", "excluded_sessions",
        "excluded_session_pct", "p95_connected_hours"
    },
}

for key, columns in required_columns.items():

    missing = columns.difference(data[key].columns)

    if missing:
        st.error(
            f"Missing columns in {key}: {', '.join(sorted(missing))}"
        )
        st.stop()


# --------------------------------------------------
# FILTERS
# --------------------------------------------------

sites = sorted(
    occupancy["site"].dropna().unique().tolist()
)

filter_col1, filter_col2 = st.columns(2)

with filter_col1:

    selected_site = st.selectbox(
        "Charging site",
        ["All sites"] + sites,
    )

with filter_col2:

    selected_day_type = st.selectbox(
        "Day type",
        ["All days", "Weekdays", "Weekends"],
        index=1,
    )


def filter_site(frame):

    if selected_site == "All sites":
        return frame.copy()

    return frame[
        frame["site"] == selected_site
    ].copy()


filtered_arrivals = filter_site(arrivals_how)
filtered_occupancy = filter_site(occupancy)
filtered_weekday_weekend = filter_site(weekday_weekend)
filtered_duration = filter_site(duration)
filtered_sensitivity = filter_site(sensitivity)


if selected_day_type in DAY_TYPE_MAP:

    allowed_days = DAY_TYPE_MAP[selected_day_type]

    filtered_arrivals = filtered_arrivals[
        filtered_arrivals["weekday_number"].isin(allowed_days)
    ]

    filtered_occupancy = filtered_occupancy[
        filtered_occupancy["weekday_number"].isin(allowed_days)
    ]

    filtered_weekday_weekend = filtered_weekday_weekend[
        filtered_weekday_weekend["day_type"]
        == selected_day_type.rstrip("s")
    ]


# --------------------------------------------------
# SUMMARY METRICS
# --------------------------------------------------

st.divider()

st.subheader("Session behaviour summary")

if not filtered_weekday_weekend.empty:

    total_sessions = int(
        filtered_weekday_weekend["sessions"].sum()
    )

    weighted_mean_connected = (
        (
            filtered_weekday_weekend["sessions"]
            * filtered_weekday_weekend["mean_connected_hours"]
        ).sum()
        / total_sessions
        if total_sessions > 0
        else 0
    )

    if selected_day_type == "All days":

        median_charging = None
        median_dwell = None

    else:

        median_charging = (
            filtered_weekday_weekend[
                "median_charging_hours"
            ].median()
        )

        median_dwell = (
            filtered_weekday_weekend[
                "median_post_charge_dwell_hours"
            ].median()
        )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Sessions",
        f"{total_sessions:,}",
    )

    metric2.metric(
        "Mean connected time",
        f"{weighted_mean_connected:.2f} hrs",
    )

    metric3.metric(
        "Median charging time",
        (
            f"{median_charging:.2f} hrs"
            if median_charging is not None
            else "Select one day type"
        ),
    )

    metric4.metric(
        "Median post-charge dwell",
        (
            f"{median_dwell:.2f} hrs"
            if median_dwell is not None
            else "Select one day type"
        ),
    )

    st.caption(
        "Connected-time mean is weighted by session counts. "
        "Charging and dwell medians are shown only for a single "
        "day type because subgroup medians cannot be combined "
        "to produce an overall median."
    )

else:

    st.info(
        "No session behaviour data is available for this selection."
    )


# --------------------------------------------------
# OCCUPANCY HEATMAP
# --------------------------------------------------

st.divider()

st.subheader("Occupancy by day and hour")

st.caption(
    "Mean simultaneous connected vehicles for each local "
    "hour-of-week, reconstructed from connection-to-disconnect "
    "intervals."
)

if not filtered_occupancy.empty:

    heatmap_data = filtered_occupancy.copy()

    heatmap_data["weekday_name"] = heatmap_data[
        "weekday_number"
    ].map(
        dict(enumerate(DAY_NAMES))
    )

    heatmap_pivot = heatmap_data.pivot_table(
        index="weekday_name",
        columns="local_hour",
        values="mean_simultaneous_occupancy",
        aggfunc="mean",
    )

    selected_days = (
        DAY_NAMES
        if selected_day_type == "All days"
        else (
            DAY_NAMES[:5]
            if selected_day_type == "Weekdays"
            else DAY_NAMES[5:]
        )
    )

    heatmap_pivot = heatmap_pivot.reindex(
        selected_days
    )

    fig_heatmap = px.imshow(
        heatmap_pivot,
        labels={
            "x": "Hour of day",
            "y": "Day of week",
            "color": "Mean connected vehicles",
        },
        color_continuous_scale=[
            "#F4F6F7",
            "#A9CFC8",
            "#247D70",
            "#172B3A",
        ],
        aspect="auto",
    )

    fig_heatmap.update_layout(
        height=340,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        coloraxis_colorbar_title="Vehicles",
    )

    fig_heatmap.update_xaxes(
        tickmode="linear",
        dtick=2,
    )

    st.plotly_chart(
        fig_heatmap,
        use_container_width=True,
    )

else:

    st.info("No occupancy observations are available.")


# --------------------------------------------------
# ARRIVAL PATTERNS
# --------------------------------------------------

st.divider()

st.subheader("Historical arrival patterns")

st.caption(
    "Recorded session arrivals by local hour. "
    "These are historical counts, not arrival rates or forecasts."
)

if not filtered_arrivals.empty:

    arrival_profile = (
        filtered_arrivals
        .groupby(
            "local_hour",
            as_index=False
        )["arrival_sessions"]
        .sum()
        .sort_values("local_hour")
    )

    fig_arrivals = px.bar(
        arrival_profile,
        x="local_hour",
        y="arrival_sessions",
        labels={
            "local_hour": "Local arrival hour",
            "arrival_sessions": "Recorded arrivals",
        },
        color_discrete_sequence=[
            COLORS["primary"]
        ],
    )

    fig_arrivals.update_layout(
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )

    fig_arrivals.update_xaxes(
        tickmode="linear",
        dtick=2,
        range=[-0.5, 23.5],
        showgrid=False,
    )

    fig_arrivals.update_yaxes(
        rangemode="tozero",
        title="Recorded sessions",
    )

    st.plotly_chart(
        fig_arrivals,
        use_container_width=True,
    )

else:

    st.info("No arrival observations are available.")


# --------------------------------------------------
# WEEKDAY / WEEKEND COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Weekday and weekend behaviour")

st.caption(
    "Comparison of the historical occupancy profiles "
    "and connected-session duration summaries."
)

left_col, right_col = st.columns(2)

with left_col:

    st.markdown("**Average hourly occupancy**")

    profile_data = filter_site(occupancy).copy()

    profile_data["day_type"] = profile_data[
        "weekday_number"
    ].apply(
        lambda day: (
            "Weekday" if day < 5 else "Weekend"
        )
    )

    profile = (
        profile_data
        .groupby(
            ["day_type", "local_hour"],
            as_index=False
        )["mean_simultaneous_occupancy"]
        .mean()
    )

    if selected_site != "All sites":
        profile_data = profile_data[
            profile_data["site"] == selected_site
        ]

    if selected_day_type != "All days":

        profile = profile[
            profile["day_type"]
            == selected_day_type.rstrip("s")
        ]

    if not profile.empty:

        fig_profile = px.line(
            profile,
            x="local_hour",
            y="mean_simultaneous_occupancy",
            color="day_type",
            labels={
                "local_hour": "Local hour",
                "mean_simultaneous_occupancy": (
                    "Mean connected vehicles"
                ),
                "day_type": "Day type",
            },
            color_discrete_map={
                "Weekday": COLORS["primary"],
                "Weekend": COLORS["secondary"],
            },
        )

        fig_profile.update_layout(
            height=320,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=20, b=20),
            legend_title_text="",
        )

        fig_profile.update_xaxes(
            tickmode="linear",
            dtick=3,
            range=[0, 23],
        )

        fig_profile.update_yaxes(
            rangemode="tozero",
        )

        st.plotly_chart(
            fig_profile,
            use_container_width=True,
        )

    else:

        st.info("No occupancy profile is available.")


with right_col:

    st.markdown("**Connected-session duration**")

    if not filtered_weekday_weekend.empty:

        comparison = filtered_weekday_weekend[
            [
                "day_type",
                "median_connected_hours",
                "median_charging_hours",
                "median_post_charge_dwell_hours",
            ]
        ].melt(
            id_vars="day_type",
            var_name="duration_type",
            value_name="hours",
        )

        comparison["duration_type"] = (
            comparison["duration_type"].map({
                "median_connected_hours": "Connected",
                "median_charging_hours": "Charging",
                "median_post_charge_dwell_hours": "Post-charge dwell",
            })
        )

        comparison["day_type"] = comparison[
            "day_type"
        ].replace({
            "Weekday": "Weekday",
            "Weekend": "Weekend",
        })

        fig_comparison = px.bar(
            comparison,
            x="duration_type",
            y="hours",
            color="day_type",
            barmode="group",
            labels={
                "duration_type": "Duration component",
                "hours": "Median duration (hours)",
                "day_type": "Day type",
            },
            color_discrete_map={
                "Weekday": COLORS["primary"],
                "Weekend": COLORS["secondary"],
            },
        )

        fig_comparison.update_layout(
            height=320,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=20, b=20),
            legend_title_text="",
        )

        fig_comparison.update_xaxes(
            showgrid=False,
        )

        fig_comparison.update_yaxes(
            rangemode="tozero",
        )

        st.plotly_chart(
            fig_comparison,
            use_container_width=True,
        )

    else:

        st.info(
            "Select All days to view both weekday and weekend "
            "duration summaries."
        )


# --------------------------------------------------
# DURATION DISTRIBUTION BY REGIME
# --------------------------------------------------

st.divider()

st.subheader("Connected-session duration by operating regime")

st.caption(
    "Historical duration percentiles. The chart uses aggregated "
    "statistics rather than fabricated session-level distributions."
)

if not filtered_duration.empty:

    regime_options = [
        regime
        for regime in REGIME_ORDER
        if regime in filtered_duration["regime"].unique()
    ]

    selected_regime = st.selectbox(
        "Operating regime",
        regime_options,
        key="duration_regime",
    )

    duration_regime = filtered_duration[
        filtered_duration["regime"] == selected_regime
    ].copy()

    duration_labels = {
        "connected_hours": "Connected",
        "charging_hours": "Charging",
        "post_charge_dwell_hours": "Post-charge dwell",
    }

    duration_regime["duration_label"] = (
        duration_regime["duration_type"].map(
            duration_labels
        )
    )

    duration_regime = duration_regime.dropna(
        subset=["duration_label"]
    )

    duration_chart = duration_regime.melt(
        id_vars=["site", "duration_label"],
        value_vars=[
            "median_hours",
            "p90_hours",
            "p95_hours",
        ],
        var_name="percentile",
        value_name="hours",
    )

    duration_chart["percentile"] = (
        duration_chart["percentile"].map({
            "median_hours": "Median",
            "p90_hours": "90th percentile",
            "p95_hours": "95th percentile",
        })
    )

    if not duration_chart.empty:

        fig_duration = px.bar(
            duration_chart,
            x="duration_label",
            y="hours",
            color="percentile",
            barmode="group",
            facet_col=(
                "site"
                if selected_site == "All sites"
                else None
            ),
            labels={
                "duration_label": "Duration component",
                "hours": "Duration (hours)",
                "percentile": "Statistic",
                "site": "Site",
            },
            color_discrete_map={
                "Median": COLORS["primary"],
                "90th percentile": COLORS["light"],
                "95th percentile": COLORS["secondary"],
            },
        )

        fig_duration.update_layout(
            height=360,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=40, b=20),
            legend_title_text="",
        )

        fig_duration.update_xaxes(
            showgrid=False,
        )

        fig_duration.update_yaxes(
            rangemode="tozero",
        )

        st.plotly_chart(
            fig_duration,
            use_container_width=True,
        )

    else:

        st.info("No valid duration summaries are available.")

else:

    st.info("No duration data is available.")


# --------------------------------------------------
# DURATION SENSITIVITY
# --------------------------------------------------

st.divider()

st.subheader("Long-session sensitivity analysis")

st.caption(
    "Shows how excluding unusually long connected sessions "
    "changes the observed 95th-percentile connected duration."
)

if not filtered_sensitivity.empty:

    sensitivity_regimes = [
        regime
        for regime in REGIME_ORDER
        if regime in filtered_sensitivity["regime"].unique()
    ]

    selected_sensitivity_regime = st.selectbox(
        "Sensitivity analysis regime",
        sensitivity_regimes,
        key="sensitivity_regime",
    )

    sensitivity_data = filtered_sensitivity[
        filtered_sensitivity["regime"]
        == selected_sensitivity_regime
    ].copy()

    scenario_order = [
        "No exclusion",
        "24 hours",
        "48 hours",
    ]

    sensitivity_data["scenario"] = pd.Categorical(
        sensitivity_data["scenario"],
        categories=scenario_order,
        ordered=True,
    )

    sensitivity_data = sensitivity_data.sort_values(
        "scenario"
    )

    if not sensitivity_data.empty:

        sensitivity_col1, sensitivity_col2 = st.columns(2)

        with sensitivity_col1:

            fig_sensitivity = px.bar(
                sensitivity_data,
                x="scenario",
                y="p95_connected_hours",
                labels={
                    "scenario": "Duration rule",
                    "p95_connected_hours": (
                        "95th-percentile connected hours"
                    ),
                },
                color_discrete_sequence=[
                    COLORS["primary"]
                ],
            )

            fig_sensitivity.update_layout(
                height=320,
                paper_bgcolor="white",
                plot_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )

            fig_sensitivity.update_xaxes(
                showgrid=False,
            )

            fig_sensitivity.update_yaxes(
                rangemode="tozero",
            )

            st.plotly_chart(
                fig_sensitivity,
                use_container_width=True,
            )

        with sensitivity_col2:

            sensitivity_display = sensitivity_data[
                [
                    "scenario",
                    "original_sessions",
                    "retained_sessions",
                    "excluded_sessions",
                    "excluded_session_pct",
                    "p95_connected_hours",
                ]
            ].copy()

            sensitivity_display = sensitivity_display.rename(
                columns={
                    "scenario": "Duration rule",
                    "original_sessions": "Original sessions",
                    "retained_sessions": "Retained sessions",
                    "excluded_sessions": "Excluded sessions",
                    "excluded_session_pct": "Excluded (%)",
                    "p95_connected_hours": "P95 connected hours",
                }
            )

            sensitivity_display["Excluded (%)"] = (
                sensitivity_display["Excluded (%)"].round(2)
            )

            sensitivity_display["P95 connected hours"] = (
                sensitivity_display[
                    "P95 connected hours"
                ].round(2)
            )

            st.dataframe(
                sensitivity_display,
                use_container_width=True,
                hide_index=True,
            )

else:

    st.info("No duration sensitivity results are available.")


# --------------------------------------------------
# INTERPRETATION
# --------------------------------------------------

st.divider()

st.subheader("Interpretation")

st.markdown(
    """
    - **Occupancy:** Measures simultaneous connected vehicles,
      not charging power or the number of rejected requests.
    - **Arrivals:** Historical session counts show when recorded
      charging sessions began. They are not forecasts or direct
      measurements of unmet demand.
    - **Connected duration:** Includes both active charging and
      post-charge time before vehicle disconnection.
    - **Post-charge dwell:** Is calculated from observed charging
      completion and disconnection timestamps where valid.
    - **Duration sensitivity:** Excluding unusually long sessions
      is a sensitivity test, not proof that those sessions are
      invalid or that a dwell policy would be followed.
    """
)

st.caption(
    "Source: ACN-Data. Historical observations from 2018–2021. "
    "Occupancy intervals use [connectionTime, disconnectTime) "
    "in America/Los_Angeles local time. Duration statistics are "
    "aggregated summaries; no synthetic session-level observations "
    "are generated on this page."
)
