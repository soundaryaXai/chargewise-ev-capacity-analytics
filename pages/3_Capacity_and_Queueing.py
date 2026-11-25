
from pathlib import Path
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.page_header import render_page_header


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

DATA_DIR = Path("data/processed")

PRIMARY_REGIMES = ["Pre-disruption", "Recovery"]
REGIME_ORDER = [
    "Pre-disruption",
    "Transition",
    "Disruption",
    "Recovery",
]


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

@st.cache_data
def load_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required data file was not found: {path}"
        )

    return pd.read_csv(path)


@st.cache_data
def load_page_data():
    return {
        "empirical": load_csv(
            "empirical_capacity_summary.csv"
        ),
        "erlang_summary": load_csv(
            "erlang_b_summary.csv"
        ),
        "erlang_hourly": load_csv(
            "erlang_b_hourly.csv"
        ),
        "replay_summary": load_csv(
            "session_replay_summary.csv"
        ),
        "replay": load_csv(
            "session_replay_results.csv"
        ),
        "pressure": load_csv(
            "capacity_pressure_summary.csv"
        ),
    }


try:
    data = load_page_data()

except FileNotFoundError as error:
    st.error(str(error))
    st.info(
        "Run the corresponding capacity-analysis scripts "
        "to generate the required processed CSV files."
    )
    st.stop()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def erlang_b_probability(offered_load, capacity):
    """
    Calculate Erlang-B blocking probability using
    the stable recursive formulation.
    """

    if capacity <= 0:
        return 1.0

    if offered_load <= 0:
        return 0.0

    blocking = 1.0

    for ports in range(1, int(capacity) + 1):
        blocking = (
            offered_load * blocking
        ) / (
            ports + offered_load * blocking
        )

    return blocking


def calculate_hourly_erlang_curve(
    hourly_data,
    capacities,
):
    """
    Calculate an arrival-weighted Erlang-B estimate
    across hour-of-week slices.

    Each slice uses its own arrival rate and the
    regime-level mean connected duration supplied
    by the modelling output.
    """

    rows = []

    hourly_data = hourly_data.copy()

    hourly_data["arrival_sessions"] = to_numeric(
        hourly_data["arrival_sessions"]
    ).fillna(0)

    hourly_data["lambda_per_hour"] = to_numeric(
        hourly_data["lambda_per_hour"]
    ).fillna(0)

    hourly_data["mean_connected_hours"] = to_numeric(
        hourly_data["mean_connected_hours"]
    )

    hourly_data = hourly_data[
        hourly_data["arrival_sessions"] > 0
    ].copy()

    total_arrivals = hourly_data[
        "arrival_sessions"
    ].sum()

    for capacity in capacities:

        if total_arrivals <= 0:
            estimated_blocking = 0.0

        else:
            weighted_blocking = 0.0

            for _, row in hourly_data.iterrows():

                arrival_rate = row["lambda_per_hour"]
                mean_duration = row[
                    "mean_connected_hours"
                ]

                if pd.isna(mean_duration):
                    continue

                offered_load = (
                    arrival_rate * mean_duration
                )

                slice_blocking = (
                    erlang_b_probability(
                        offered_load,
                        capacity,
                    )
                )

                weighted_blocking += (
                    row["arrival_sessions"]
                    * slice_blocking
                )

            estimated_blocking = (
                weighted_blocking / total_arrivals
            )

        rows.append(
            {
                "capacity": int(capacity),
                "erlang_b_blocking": (
                    estimated_blocking * 100
                ),
            }
        )

    return pd.DataFrame(rows)


def format_number(value, decimals=1):
    if pd.isna(value):
        return "—"

    return f"{value:,.{decimals}f}"


def filter_site_regime(frame, site, regime):
    return frame[
        (frame["site"] == site)
        & (frame["regime"] == regime)
    ].copy()


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Capacity & Queueing Analysis",
    "Evaluate how available charging-port capacity "
    "relates to service availability and modelled "
    "blocking risk.",
)

st.caption(
    "Results are based on observed successful ACN-Data "
    "sessions and modelled capacity scenarios. The dataset "
    "does not contain observed rejected arrivals or "
    "customer waiting times."
)


# --------------------------------------------------
# SITE AND REGIME FILTERS
# --------------------------------------------------

replay_data = data["replay"].copy()

sites = sorted(
    replay_data["site"].dropna().unique().tolist()
)

if not sites:
    st.error(
        "No sites were found in session_replay_results.csv."
    )
    st.stop()


filter_col1, filter_col2, filter_col3 = st.columns(
    [1.2, 1.2, 1]
)

with filter_col1:
    selected_site = st.selectbox(
        "Charging site",
        sites,
    )

site_replay = replay_data[
    replay_data["site"] == selected_site
].copy()

available_regimes = (
    site_replay["regime"].dropna().unique().tolist()
)

ordered_regimes = [
    regime
    for regime in REGIME_ORDER
    if regime in available_regimes
]

if not ordered_regimes:
    ordered_regimes = sorted(available_regimes)

default_regime_index = (
    ordered_regimes.index("Pre-disruption")
    if "Pre-disruption" in ordered_regimes
    else 0
)

with filter_col2:
    selected_regime = st.selectbox(
        "Operating regime",
        ordered_regimes,
        index=default_regime_index,
    )

with filter_col3:
    selected_target = st.selectbox(
        "Blocking target",
        ["1%", "5%", "10%"],
        index=1,
    )

target_value = (
    float(selected_target.replace("%", "")) / 100
)


# --------------------------------------------------
# FILTER DATA
# --------------------------------------------------

empirical = filter_site_regime(
    data["empirical"],
    selected_site,
    selected_regime,
)

erlang_summary = filter_site_regime(
    data["erlang_summary"],
    selected_site,
    selected_regime,
)

erlang_hourly = filter_site_regime(
    data["erlang_hourly"],
    selected_site,
    selected_regime,
)

replay_summary = filter_site_regime(
    data["replay_summary"],
    selected_site,
    selected_regime,
)

replay = filter_site_regime(
    data["replay"],
    selected_site,
    selected_regime,
)

pressure = filter_site_regime(
    data["pressure"],
    selected_site,
    selected_regime,
)

if replay.empty:
    st.warning(
        "No session-replay capacity results are available "
        "for this site and regime."
    )
    st.stop()


# --------------------------------------------------
# PRIMARY REGIME NOTICE
# --------------------------------------------------

if selected_regime not in PRIMARY_REGIMES:
    st.warning(
        "This is a contextual regime, not a primary "
        "capacity-sizing regime. Interpret results cautiously "
        "because the number of eligible weeks or observed "
        "sessions may be limited."
    )


# --------------------------------------------------
# CAPACITY AND OCCUPANCY REFERENCES
# --------------------------------------------------

assumed_capacity = None
observed_peak = None
eligible_weeks = None
weeks_with_sessions = None

if not erlang_summary.empty:

    assumed_capacity = int(
        to_numeric(
            erlang_summary["capacity_assumption"]
        ).iloc[0]
    )

    eligible_weeks = int(
        to_numeric(
            erlang_summary["eligible_weeks"]
        ).iloc[0]
    )

if not empirical.empty:

    observed_peak = to_numeric(
        empirical["maximum_weekly_peak"]
    ).iloc[0]

    if "eligible_weeks" in empirical.columns:
        eligible_weeks = int(
            to_numeric(
                empirical["eligible_weeks"]
            ).iloc[0]
        )

    if "weeks_with_sessions" in empirical.columns:
        weeks_with_sessions = int(
            to_numeric(
                empirical["weeks_with_sessions"]
            ).iloc[0]
        )

if assumed_capacity is None and not pressure.empty:
    assumed_capacity = int(
        to_numeric(
            pressure["assumed_capacity"]
        ).iloc[0]
    )


# --------------------------------------------------
# REPLAY CAPACITY CURVE
# --------------------------------------------------

replay["capacity"] = to_numeric(
    replay["capacity"]
)

replay["blocking_rate"] = to_numeric(
    replay["blocking_rate"]
)

replay["target_sessions"] = to_numeric(
    replay["target_sessions"]
)

replay = replay.dropna(
    subset=["capacity", "blocking_rate"]
).sort_values("capacity")

replay["replay_blocking_pct"] = (
    replay["blocking_rate"] * 100
)

available_capacities = sorted(
    replay["capacity"].astype(int).unique().tolist()
)

if not available_capacities:
    st.error(
        "No valid capacity values are available "
        "in the replay output."
    )
    st.stop()


# --------------------------------------------------
# ERLANG-B CAPACITY CURVE
# --------------------------------------------------

erlang_curve = calculate_hourly_erlang_curve(
    erlang_hourly,
    available_capacities,
)


# --------------------------------------------------
# REQUIRED PORTS AT TARGET
# --------------------------------------------------

eligible_replay = replay[
    replay["blocking_rate"] <= target_value
].copy()

if eligible_replay.empty:
    required_ports = None
else:
    required_ports = int(
        eligible_replay["capacity"].min()
    )


# --------------------------------------------------
# REPLAY BLOCKING AT REFERENCE CAPACITY
# --------------------------------------------------

reference_replay = pd.DataFrame()

if assumed_capacity is not None:

    reference_replay = replay[
        replay["capacity"] == assumed_capacity
    ]

if reference_replay.empty:
    reference_replay = replay[
        replay["capacity"] == replay["capacity"].max()
    ]

if not reference_replay.empty:
    estimated_blocking = (
        float(
            reference_replay["blocking_rate"].iloc[0]
        ) * 100
    )
else:
    estimated_blocking = None


# --------------------------------------------------
# CAPACITY INDICATORS
# --------------------------------------------------

st.divider()

st.subheader("Capacity indicators")

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Capacity assumption",
    (
        f"{assumed_capacity:,}"
        if assumed_capacity is not None
        else "—"
    ),
    help=(
        "Historical or provisional site capacity "
        "assumption used by the model. It is not "
        "independently verified engineering capacity."
    ),
)

metric2.metric(
    "Observed weekly peak",
    (
        f"{int(observed_peak):,}"
        if pd.notna(observed_peak)
        else "—"
    ),
    help=(
        "Maximum weekly simultaneous occupancy "
        "in the selected site and regime."
    ),
)

metric3.metric(
    "Required ports",
    (
        f"{required_ports:,}"
        if required_ports is not None
        else f">{max(available_capacities):,}"
    ),
    help=(
        f"Minimum tested replay capacity with blocking "
        f"at or below {selected_target}."
    ),
)

metric4.metric(
    "Replay blocking",
    (
        f"{estimated_blocking:.2f}%"
        if estimated_blocking is not None
        else "—"
    ),
    help=(
        "Modelled blocking at the reference capacity "
        "when that capacity is included in the replay. "
        "Otherwise, the maximum tested capacity is shown."
    ),
)

if eligible_weeks is not None:
    st.caption(
        f"Selected regime: {selected_regime} · "
        f"Eligible weeks: {eligible_weeks} · "
        f"Weeks with sessions: "
        f"{weeks_with_sessions if weeks_with_sessions is not None else '—'}"
    )


# --------------------------------------------------
# BLOCKING VS AVAILABLE PORTS
# --------------------------------------------------

st.divider()

st.subheader("Blocking probability by available ports")

st.caption(
    "The Erlang-B curve is calculated from hour-of-week "
    "arrival rates and regime-level mean connected duration. "
    "The replay curve uses the chronological session-replay "
    "results."
)

fig_blocking = go.Figure()

fig_blocking.add_trace(
    go.Scatter(
        x=erlang_curve["capacity"],
        y=erlang_curve["erlang_b_blocking"],
        mode="lines",
        name="Erlang-B baseline",
        line=dict(
            color="#247D70",
            width=2.5,
        ),
    )
)

fig_blocking.add_trace(
    go.Scatter(
        x=replay["capacity"],
        y=replay["replay_blocking_pct"],
        mode="lines+markers",
        name="Session replay",
        line=dict(
            color="#172B3A",
            width=2.5,
        ),
        marker=dict(size=5),
    )
)

fig_blocking.add_hline(
    y=target_value * 100,
    line_dash="dot",
    line_color="#98A2B3",
    annotation_text=f"{selected_target} target",
    annotation_position="top right",
)

if assumed_capacity is not None:
    fig_blocking.add_vline(
        x=assumed_capacity,
        line_dash="dash",
        line_color="#D97706",
        annotation_text="Capacity assumption",
        annotation_position="top left",
    )

fig_blocking.update_layout(
    height=440,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(
        l=30,
        r=30,
        t=35,
        b=35,
    ),
    xaxis_title="Available charging ports",
    yaxis_title="Modelled blocking probability (%)",
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
# MODEL COMPARISON
# --------------------------------------------------

left_col, right_col = st.columns(2)

with left_col:

    st.subheader("Erlang-B baseline")

    st.markdown(
        """
        Erlang-B represents a loss system. An arriving
        session is accepted immediately if a port is
        available; otherwise, it is blocked.

        **Model inputs**
        - Arrival rate for each hour-of-week slice
        - Mean connected-session duration
        - Number of available ports

        Offered traffic is:

        \\[
        A = \\lambda E[S]
        \\]

        Erlang-B provides a theoretical benchmark under
        its traffic assumptions. It does not reproduce
        the actual chronological arrival sequence.
        """
    )

with right_col:

    st.subheader("Chronological session replay")

    st.markdown(
        """
        Replay processes observed sessions in chronological
        arrival order and checks whether a port remains
        available for each session's connected duration.

        **Replay outputs**
        - Accepted sessions
        - Blocked sessions
        - Blocking rate
        - Required ports at selected targets

        Replay occupancy uses connection time through
        disconnection time, not charging duration alone.
        """)


# --------------------------------------------------
# CAPACITY COMPARISON TABLE
# --------------------------------------------------

st.divider()

st.subheader("Capacity comparison")

display_data = replay[
    [
        "capacity",
        "accepted_sessions",
        "blocked_sessions",
        "target_sessions",
        "blocking_rate",
        "acceptance_rate",
    ]
].copy()

display_data = display_data.rename(
    columns={
        "capacity": "Available ports",
        "accepted_sessions": "Accepted sessions",
        "blocked_sessions": "Blocked sessions",
        "target_sessions": "Target sessions",
        "blocking_rate": "Blocking rate",
        "acceptance_rate": "Acceptance rate",
    }
)

display_data["Blocking rate"] = (
    display_data["Blocking rate"] * 100
).round(2)

display_data["Acceptance rate"] = (
    display_data["Acceptance rate"] * 100
).round(2)

display_data["Available ports"] = (
    display_data["Available ports"].astype(int)
)

st.dataframe(
    display_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Blocking rate": st.column_config.NumberColumn(
            format="%.2f%%"
        ),
        "Acceptance rate": st.column_config.NumberColumn(
            format="%.2f%%"
        ),
    },
)


# --------------------------------------------------
# EMPIRICAL OCCUPANCY CONTEXT
# --------------------------------------------------

st.divider()

st.subheader("Historical occupancy context")

if not empirical.empty:

    empirical_row = empirical.iloc[0]

    context_col1, context_col2, context_col3 = (
        st.columns(3)
    )

    context_col1.metric(
        "Median weekly peak",
        format_number(
            empirical_row["p50_weekly_peak"],
            0,
        ),
    )

    context_col2.metric(
        "95th percentile weekly peak",
        format_number(
            empirical_row["p95_weekly_peak"],
            1,
        ),
    )

    context_col3.metric(
        "Maximum weekly peak",
        format_number(
            empirical_row["maximum_weekly_peak"],
            0,
        ),
    )

    st.caption(
        "These are empirical historical occupancy statistics. "
        "They describe observed connected sessions, not "
        "unmet demand or customer waiting."
    )

else:
    st.info(
        "No empirical weekly occupancy summary is available "
        "for this site and regime."
    )


# --------------------------------------------------
# CAPACITY PRESSURE CONTEXT
# --------------------------------------------------

if not pressure.empty:

    pressure_row = pressure.iloc[0]

    st.subheader("Capacity-pressure screening")

    pressure_col1, pressure_col2, pressure_col3 = (
        st.columns(3)
    )

    pressure_col1.metric(
        "Weeks at or above 80% capacity",
        (
            f"{int(pressure_row['weeks_at_or_above_80pct'])}"
            f" / {int(pressure_row['eligible_full_weeks'])}"
        ),
    )

    pressure_col2.metric(
        "Pressure-screening rate",
        f"{float(pressure_row['pressure_percentage']):.2f}%",
    )

    pressure_col3.metric(
        "Maximum weekly peak",
        format_number(
            pressure_row["maximum_weekly_peak"],
            0,
        ),
    )

    st.caption(
        "The 80% threshold is a screening definition used "
        "in this analysis. It is not evidence of actual "
        "queueing, congestion, or rejected charging requests."
    )


# --------------------------------------------------
# METHODOLOGY AND LIMITATIONS
# --------------------------------------------------

st.divider()

st.subheader("Model assumptions and limitations")

assumption_col1, assumption_col2 = st.columns(2)

with assumption_col1:

    st.markdown(
        """
        **Erlang-B baseline**
        - No waiting queue.
        - Blocked arrivals leave the system.
        - Mean connected duration represents service time.
        - Arrival rates are estimated by hour of week.
        - The curve is an analytical benchmark, not a
          reconstruction of the observed arrival sequence.
        """
    )

with assumption_col2:

    st.markdown(
        """
        **Session replay**
        - Sessions are processed chronologically.
        - Occupancy runs from connection to disconnection.
        - Blocked sessions are assumed to leave.
        - Observed arrivals and connected durations are retained.
        - Results depend on the historical session cohort
          and the tested capacity assumptions.
        """
    )

st.info(
    "ACN-Data records successful charging sessions. It does "
    "not provide a complete record of rejected arrivals, "
    "unmet demand, or actual waiting times. Blocking rates "
    "on this page are therefore modelled counterfactual "
    "estimates, not observed customer rejection rates."
)
