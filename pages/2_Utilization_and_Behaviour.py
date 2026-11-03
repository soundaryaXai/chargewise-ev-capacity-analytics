
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Utilization & Behaviour",
    "Explore workplace charging patterns, occupancy "
    "variation and connected-session behaviour.",
)


# --------------------------------------------------
# SYNTHETIC DATA GENERATION
# --------------------------------------------------

@st.cache_data
def generate_utilization_data():

    rng = np.random.default_rng(21)

    sites = ["Caltech", "JPL", "Office Site C"]

    hourly_records = []

    site_factors = {
        "Caltech": 1.0,
        "JPL": 0.8,
        "Office Site C": 0.65,
    }

    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    for site in sites:
        factor = site_factors[site]

        for day_index, day in enumerate(day_names):
            for hour in range(24):

                weekday_factor = (
                    1.0 if day_index < 5 else 0.25
                )

                daytime_pattern = np.exp(
                    -((hour - 13) ** 2) / 30
                )

                occupancy = (
                    5 + 35 * daytime_pattern
                ) * factor * weekday_factor

                occupancy += rng.normal(0, 1.5)

                hourly_records.append({
                    "site": site,
                    "day": day,
                    "day_index": day_index,
                    "hour": hour,
                    "occupancy": max(0, occupancy),
                })

    hourly = pd.DataFrame(hourly_records)

    session_records = []

    for site in sites:
        for _ in range(300):

            charging_duration = rng.uniform(0.5, 4.5)
            dwell_duration = rng.uniform(0.1, 5.0)

            session_records.append({
                "site": site,
                "charging_duration": charging_duration,
                "dwell_duration": dwell_duration,
                "connected_duration": (
                    charging_duration + dwell_duration
                ),
                "day_type": rng.choice(
                    ["Weekday", "Weekend"],
                    p=[0.85, 0.15],
                ),
            })

    sessions = pd.DataFrame(session_records)

    return hourly, sessions, sites


hourly, sessions, sites = generate_utilization_data()


# --------------------------------------------------
# FILTERS
# --------------------------------------------------

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
    )


if selected_site != "All sites":
    hourly = hourly[
        hourly["site"] == selected_site
    ]

    sessions = sessions[
        sessions["site"] == selected_site
    ]


if selected_day_type == "Weekdays":
    hourly = hourly[
        hourly["day_index"] < 5
    ]

    sessions = sessions[
        sessions["day_type"] == "Weekday"
    ]

elif selected_day_type == "Weekends":
    hourly = hourly[
        hourly["day_index"] >= 5
    ]

    sessions = sessions[
        sessions["day_type"] == "Weekend"
    ]


# --------------------------------------------------
# SUMMARY METRICS
# --------------------------------------------------

st.divider()

st.subheader("Session behaviour summary")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Sessions",
    f"{len(sessions):,}",
)

metric2.metric(
    "Mean connected time",
    f"{sessions['connected_duration'].mean():.1f} hrs",
)

metric3.metric(
    "Mean charging time",
    f"{sessions['charging_duration'].mean():.1f} hrs",
)

metric4.metric(
    "Mean post-charge dwell",
    f"{sessions['dwell_duration'].mean():.1f} hrs",
)


# --------------------------------------------------
# OCCUPANCY HEATMAP
# --------------------------------------------------

st.divider()

st.subheader("Occupancy by day and hour")

st.caption(
    "Illustrative average connected vehicles across "
    "the hour-of-week profile."
)

heatmap_data = (
    hourly.groupby(
        ["day_index", "day", "hour"],
        as_index=False,
    )["occupancy"]
    .mean()
)

heatmap_pivot = heatmap_data.pivot(
    index="day",
    columns="hour",
    values="occupancy",
)

day_order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

heatmap_pivot = heatmap_pivot.reindex(day_order)

fig_heatmap = px.imshow(
    heatmap_pivot,
    labels={
        "x": "Hour of day",
        "y": "Day of week",
        "color": "Connected vehicles",
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
    margin=dict(l=20, r=20, t=20, b=20),
    coloraxis_colorbar_title="Vehicles",
)

st.plotly_chart(
    fig_heatmap,
    use_container_width=True,
)


# --------------------------------------------------
# WEEKDAY / WEEKEND COMPARISON
# --------------------------------------------------

left_col, right_col = st.columns(2)

with left_col:

    st.subheader("Average hourly occupancy")

    hourly_profile = (
        hourly.groupby(
            ["day_index", "hour"],
            as_index=False,
        )["occupancy"]
        .mean()
    )

    hourly_profile["day_type"] = np.where(
        hourly_profile["day_index"] < 5,
        "Weekday",
        "Weekend",
    )

    profile = (
        hourly_profile.groupby(
            ["day_type", "hour"],
            as_index=False,
        )["occupancy"]
        .mean()
    )

    fig_profile = px.line(
        profile,
        x="hour",
        y="occupancy",
        color="day_type",
        labels={
            "hour": "Hour of day",
            "occupancy": "Connected vehicles",
            "day_type": "Day type",
        },
        color_discrete_map={
            "Weekday": "#247D70",
            "Weekend": "#172B3A",
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


# --------------------------------------------------
# SESSION DURATION DISTRIBUTION
# --------------------------------------------------

with right_col:

    st.subheader("Connected-session duration")

    st.caption(
        "Distribution of connected time, charging time "
        "and post-charge dwell."
    )

    duration_data = sessions.melt(
        value_vars=[
            "charging_duration",
            "dwell_duration",
            "connected_duration",
        ],
        var_name="duration_type",
        value_name="hours",
    )

    duration_data["duration_type"] = (
        duration_data["duration_type"].map({
            "charging_duration": "Charging",
            "dwell_duration": "Post-charge dwell",
            "connected_duration": "Connected",
        })
    )

    fig_duration = px.box(
        duration_data,
        x="duration_type",
        y="hours",
        color="duration_type",
        labels={
            "duration_type": "Session component",
            "hours": "Duration (hours)",
        },
        color_discrete_map={
            "Charging": "#247D70",
            "Post-charge dwell": "#98A2B3",
            "Connected": "#172B3A",
        },
    )

    fig_duration.update_layout(
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
    )

    fig_duration.update_yaxes(
        rangemode="tozero",
    )

    st.plotly_chart(
        fig_duration,
        use_container_width=True,
    )


# --------------------------------------------------
# METHODOLOGY NOTE
# --------------------------------------------------

st.divider()

st.subheader("Interpretation")

st.markdown(
    """
    - **Occupancy patterns:** Identify periods of higher
      simultaneous port usage.
    - **Day-type differences:** Compare weekday and weekend
      utilization patterns.
    - **Connected duration:** Separate charging duration
      from post-charge dwell.
    """
)

st.caption(
    "All displayed values are synthetic and intended only "
    "for interface development. Actual ACN-Data results "
    "will replace them after data validation."
)
