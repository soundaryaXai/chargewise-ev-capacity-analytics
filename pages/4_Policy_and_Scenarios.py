
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.page_header import render_page_header


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

DATA_DIR = Path("data/processed")

SCENARIO_ORDER = [
    "Baseline",
    "30-minute cap",
    "60-minute cap",
    "120-minute cap",
]

POLICY_ORDER = [
    "30-minute cap",
    "60-minute cap",
    "120-minute cap",
]

BLOCK_LENGTHS = [1, 2, 4]


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
        "dwell": load_csv(
            "dwell_scenario_summary.csv"
        ),
        "bootstrap_summary": load_csv(
            "bootstrap_policy_effects_summary.csv"
        ),
        "bootstrap_review": load_csv(
            "bootstrap_policy_effects_4week_review.csv"
        ),
        "validation": load_csv(
            "bootstrap_validation.csv"
        ),
    }


try:
    data = load_page_data()

except FileNotFoundError as error:
    st.error(str(error))
    st.info(
        "Run the dwell scenario and bootstrap scripts "
        "to generate the required processed data."
    )
    st.stop()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def numeric(frame, column):
    if column not in frame.columns:
        return pd.Series(
            index=frame.index,
            dtype="float64",
        )

    return pd.to_numeric(
        frame[column],
        errors="coerce",
    )


def filter_group(frame, site, regime):
    if frame.empty:
        return frame.copy()

    return frame[
        (frame["site"] == site)
        & (frame["regime"] == regime)
    ].copy()


def format_number(value, decimals=1):
    if pd.isna(value):
        return "—"

    return f"{value:,.{decimals}f}"


def format_percent(value, decimals=2):
    if pd.isna(value):
        return "—"

    return f"{value:,.{decimals}f}%"


def format_ci(lower, upper, decimals=2):
    if pd.isna(lower) or pd.isna(upper):
        return "—"

    return (
        f"[{lower:.{decimals}f}, "
        f"{upper:.{decimals}f}]"
    )


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Policy & Scenario Analysis",
    "Evaluate hypothetical post-charge dwell policies "
    "and their potential effects on charging capacity "
    "and modelled blocking.",
)

st.caption(
    "Policy scenarios are counterfactual simulations "
    "based on historical charging sessions. They do not "
    "represent observed driver compliance or real-world "
    "policy implementation."
)


# --------------------------------------------------
# FILTER OPTIONS
# --------------------------------------------------

dwell_data = data["dwell"].copy()
bootstrap_data = data["bootstrap_summary"].copy()

sites = sorted(
    dwell_data["site"].dropna().unique().tolist()
)

regimes = [
    "Pre-disruption",
    "Recovery",
]

if not sites:
    st.error(
        "No site information was found in the dwell "
        "scenario summary."
    )
    st.stop()


# --------------------------------------------------
# SCENARIO CONTROLS
# --------------------------------------------------

st.divider()

st.subheader("Scenario configuration")

control_col1, control_col2, control_col3 = (
    st.columns(3)
)

with control_col1:
    selected_site = st.selectbox(
        "Charging site",
        sites,
    )

site_regimes = sorted(
    dwell_data[
        dwell_data["site"] == selected_site
    ]["regime"].dropna().unique().tolist()
)

ordered_regimes = [
    regime
    for regime in regimes
    if regime in site_regimes
]

if not ordered_regimes:
    ordered_regimes = site_regimes

with control_col2:
    selected_regime = st.selectbox(
        "Operating regime",
        ordered_regimes,
    )

with control_col3:
    selected_block_length = st.selectbox(
        "Bootstrap block length",
        BLOCK_LENGTHS,
        index=2,
        format_func=lambda value: (
            f"{value}-week blocks"
        ),
    )


# --------------------------------------------------
# FILTER DATA
# --------------------------------------------------

site_dwell = filter_group(
    dwell_data,
    selected_site,
    selected_regime,
)

site_bootstrap = filter_group(
    bootstrap_data,
    selected_site,
    selected_regime,
)

site_validation = filter_group(
    data["validation"],
    selected_site,
    selected_regime,
)

site_review = filter_group(
    data["bootstrap_review"],
    selected_site,
    selected_regime,
)


# --------------------------------------------------
# FILTER BOOTSTRAP BLOCK LENGTH
# --------------------------------------------------

bootstrap = site_bootstrap[
    numeric(
        site_bootstrap,
        "block_length",
    ) == selected_block_length
].copy()

if bootstrap.empty:
    st.warning(
        "No bootstrap policy-effect results were found "
        "for this block length."
    )


# --------------------------------------------------
# FILTER DWELL SCENARIOS
# --------------------------------------------------

site_dwell["scenario"] = (
    site_dwell["scenario"].astype(str)
)

site_dwell = site_dwell[
    site_dwell["scenario"].isin(
        POLICY_ORDER
    )
].copy()

site_dwell["scenario"] = pd.Categorical(
    site_dwell["scenario"],
    categories=POLICY_ORDER,
    ordered=True,
)

site_dwell = site_dwell.sort_values(
    "scenario"
)


# --------------------------------------------------
# BASELINE REFERENCE
# --------------------------------------------------

reference_capacity = None
baseline_zero_capacity = None

baseline_validation = site_validation[
    site_validation["scenario"] == "Baseline"
].copy()

if not baseline_validation.empty:

    if "policy_evaluation_capacity" in (
        baseline_validation.columns
    ):
        reference_capacity = numeric(
            baseline_validation,
            "policy_evaluation_capacity",
        ).iloc[0]

    if "full_sample_minimum_zero_capacity" in (
        baseline_validation.columns
    ):
        baseline_zero_capacity = numeric(
            baseline_validation,
            "full_sample_minimum_zero_capacity",
        ).iloc[0]


# --------------------------------------------------
# SCENARIO REFERENCE DETAILS
# --------------------------------------------------

reference_rows = site_dwell.copy()

if not reference_rows.empty:

    if reference_capacity is not None:
        reference_rows["reference_capacity"] = (
            numeric(
                reference_rows,
                "reference_capacity",
            )
        )

    if "reference_capacity" in (
        reference_rows.columns
    ):
        reference_capacity_values = (
            numeric(
                reference_rows,
                "reference_capacity",
            )
        )

        valid_reference = (
            reference_capacity_values.dropna()
        )

        if not valid_reference.empty:
            reference_capacity = (
                valid_reference.iloc[0]
            )


# --------------------------------------------------
# POLICY SUMMARY TABLE
# --------------------------------------------------

st.divider()

st.subheader("Policy scenario summary")

if site_dwell.empty:

    st.warning(
        "No dwell scenario summary results are available "
        "for the selected site and regime."
    )

else:

    display_summary = site_dwell[
        [
            "scenario",
            "target_sessions",
            "target_sessions_modified",
            "target_sessions_modified_pct",
            "target_connected_hours_removed",
            "minimum_zero_blocking_capacity",
            "reference_capacity",
            "blocking_at_reference_capacity",
        ]
    ].copy()

    display_summary = display_summary.rename(
        columns={
            "scenario": "Policy",
            "target_sessions": "Target sessions",
            "target_sessions_modified": (
                "Sessions modified"
            ),
            "target_sessions_modified_pct": (
                "Sessions modified (%)"
            ),
            "target_connected_hours_removed": (
                "Connected hours removed"
            ),
            "minimum_zero_blocking_capacity": (
                "Minimum zero-blocking capacity"
            ),
            "reference_capacity": (
                "Reference capacity"
            ),
            "blocking_at_reference_capacity": (
                "Blocking at reference (%)"
            ),
        }
    )

    display_summary[
        "Sessions modified (%)"
    ] = display_summary[
        "Sessions modified (%)"
    ].round(2)

    display_summary[
        "Connected hours removed"
    ] = display_summary[
        "Connected hours removed"
    ].round(2)

    display_summary[
        "Blocking at reference (%)"
    ] = display_summary[
        "Blocking at reference (%)"
    ].round(2)

    st.dataframe(
        display_summary,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# POLICY IMPACT INDICATORS
# --------------------------------------------------

st.divider()

st.subheader("Policy impact indicators")

if site_dwell.empty:

    st.info(
        "Policy impact indicators are unavailable."
    )

else:

    selected_policy = st.selectbox(
        "Policy to inspect",
        POLICY_ORDER,
        index=0,
    )

    selected_policy_row = site_dwell[
        site_dwell["scenario"]
        == selected_policy
    ]

    if selected_policy_row.empty:

        st.warning(
            "No scenario result was found for "
            "the selected policy."
        )

    else:

        policy_row = selected_policy_row.iloc[0]

        metric1, metric2, metric3, metric4 = (
            st.columns(4)
        )

        metric1.metric(
            "Sessions modified",
            format_number(
                policy_row[
                    "target_sessions_modified"
                ],
                0,
            ),
        )

        metric2.metric(
            "Modified sessions",
            format_percent(
                policy_row[
                    "target_sessions_modified_pct"
                ],
                2,
            ),
        )

        metric3.metric(
            "Connected hours removed",
            format_number(
                policy_row[
                    "target_connected_hours_removed"
                ],
                1,
            ),
        )

        metric4.metric(
            "Minimum zero-blocking capacity",
            format_number(
                policy_row[
                    "minimum_zero_blocking_capacity"
                ],
                0,
            ),
        )


# --------------------------------------------------
# MODIFIED SESSION COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Sessions affected by each policy")

st.caption(
    "The count and proportion of target-regime sessions "
    "whose hypothetical disconnect time is shortened "
    "under each dwell cap."
)

if not site_dwell.empty:

    fig_modified = go.Figure()

    fig_modified.add_trace(
        go.Bar(
            x=site_dwell["scenario"],
            y=site_dwell[
                "target_sessions_modified_pct"
            ],
            name="Sessions modified (%)",
            marker_color="#247D70",
        )
    )

    fig_modified.update_layout(
        height=350,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(
            l=30,
            r=30,
            t=30,
            b=30,
        ),
        xaxis_title="Hypothetical dwell cap",
        yaxis_title="Sessions modified (%)",
        showlegend=False,
    )

    fig_modified.update_yaxes(
        rangemode="tozero",
        gridcolor="#EAECF0",
    )

    st.plotly_chart(
        fig_modified,
        use_container_width=True,
    )


# --------------------------------------------------
# CONNECTED HOURS REMOVED
# --------------------------------------------------

st.divider()

st.subheader("Connected hours removed")

st.caption(
    "Total connected hours removed from the target "
    "sessions under each hypothetical dwell policy."
)

if not site_dwell.empty:

    fig_hours = go.Figure()

    fig_hours.add_trace(
        go.Bar(
            x=site_dwell["scenario"],
            y=site_dwell[
                "target_connected_hours_removed"
            ],
            marker_color="#172B3A",
        )
    )

    fig_hours.update_layout(
        height=350,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(
            l=30,
            r=30,
            t=30,
            b=30,
        ),
        xaxis_title="Hypothetical dwell cap",
        yaxis_title="Connected hours removed",
        showlegend=False,
    )

    fig_hours.update_yaxes(
        rangemode="tozero",
        gridcolor="#EAECF0",
    )

    st.plotly_chart(
        fig_hours,
        use_container_width=True,
    )


# --------------------------------------------------
# CAPACITY SENSITIVITY
# --------------------------------------------------

st.divider()

st.subheader("Minimum zero-blocking capacity")

st.caption(
    "The minimum tested port count that accommodated "
    "all target-regime sessions in the full chronological "
    "replay for each dwell scenario."
)

if not site_dwell.empty:

    fig_capacity = go.Figure()

    fig_capacity.add_trace(
        go.Bar(
            x=site_dwell["scenario"],
            y=site_dwell[
                "minimum_zero_blocking_capacity"
            ],
            marker_color="#247D70",
        )
    )

    if baseline_zero_capacity is not None:

        fig_capacity.add_hline(
            y=baseline_zero_capacity,
            line_dash="dot",
            line_color="#98A2B3",
            annotation_text=(
                "Baseline zero-blocking capacity"
            ),
        )

    fig_capacity.update_layout(
        height=350,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(
            l=30,
            r=30,
            t=35,
            b=30,
        ),
        xaxis_title="Hypothetical dwell cap",
        yaxis_title="Required tested ports",
        showlegend=False,
    )

    fig_capacity.update_yaxes(
        rangemode="tozero",
        gridcolor="#EAECF0",
    )

    st.plotly_chart(
        fig_capacity,
        use_container_width=True,
    )


# --------------------------------------------------
# BOOTSTRAP POLICY EFFECTS
# --------------------------------------------------

st.divider()

st.subheader("Bootstrap policy effects")

st.caption(
    "Paired policy effects evaluated at the fixed "
    "baseline 5% blocking-capacity benchmark. The "
    "benchmark is selected from the full-sample baseline "
    "replay and held constant across policy scenarios "
    "and bootstrap replicates."
)

if bootstrap.empty:

    st.warning(
        "Bootstrap results are unavailable for "
        "the selected block length."
    )

else:

    bootstrap["scenario"] = (
        bootstrap["scenario"].astype(str)
    )

    bootstrap = bootstrap[
        bootstrap["scenario"].isin(
            POLICY_ORDER
        )
    ].copy()

    bootstrap["scenario"] = pd.Categorical(
        bootstrap["scenario"],
        categories=POLICY_ORDER,
        ordered=True,
    )

    bootstrap = bootstrap.sort_values(
        "scenario"
    )

    bootstrap["median_blocking_rate_reduction_pct"] = (
        numeric(
            bootstrap,
            "median_blocking_rate_reduction",
        ) * 100
    )

    bootstrap["blocking_ci_lower_pct"] = (
        numeric(
            bootstrap,
            "blocking_reduction_ci_lower",
        ) * 100
    )

    bootstrap["blocking_ci_upper_pct"] = (
        numeric(
            bootstrap,
            "blocking_reduction_ci_upper",
        ) * 100
    )

    bootstrap["median_capacity_reduction"] = (
        numeric(
            bootstrap,
            "median_capacity_reduction",
        )
    )

    bootstrap["capacity_ci_lower"] = (
        numeric(
            bootstrap,
            "capacity_reduction_ci_lower",
        )
    )

    bootstrap["capacity_ci_upper"] = (
        numeric(
            bootstrap,
            "capacity_reduction_ci_upper",
        )
    )

    bootstrap["policy_evaluation_capacity"] = (
        numeric(
            bootstrap,
            "policy_evaluation_capacity",
        )
    )

    if not bootstrap.empty:

        evaluation_capacity = (
            bootstrap[
                "policy_evaluation_capacity"
            ].dropna()
        )

        if not evaluation_capacity.empty:

            st.metric(
                "Fixed policy evaluation capacity",
                f"{int(evaluation_capacity.iloc[0])} ports",
            )

        st.markdown(
            "**Estimated blocking-rate reduction**"
        )

        fig_blocking_effect = go.Figure()

        fig_blocking_effect.add_trace(
            go.Bar(
                x=bootstrap["scenario"],
                y=bootstrap[
                    "median_blocking_rate_reduction_pct"
                ],
                marker_color="#247D70",
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(
                        bootstrap[
                            "blocking_ci_upper_pct"
                        ]
                        - bootstrap[
                            "median_blocking_rate_reduction_pct"
                        ]
                    ),
                    arrayminus=(
                        bootstrap[
                            "median_blocking_rate_reduction_pct"
                        ]
                        - bootstrap[
                            "blocking_ci_lower_pct"
                        ]
                    ),
                ),
            )
        )

        fig_blocking_effect.update_layout(
            height=380,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(
                l=30,
                r=30,
                t=30,
                b=30,
            ),
            xaxis_title="Hypothetical dwell cap",
            yaxis_title=(
                "Blocking-rate reduction "
                "(percentage points)"
            ),
            showlegend=False,
        )

        fig_blocking_effect.update_yaxes(
            gridcolor="#EAECF0",
        )

        st.plotly_chart(
            fig_blocking_effect,
            use_container_width=True,
        )

        st.markdown(
            "**Estimated reduction in required capacity**"
        )

        fig_capacity_effect = go.Figure()

        fig_capacity_effect.add_trace(
            go.Bar(
                x=bootstrap["scenario"],
                y=bootstrap[
                    "median_capacity_reduction"
                ],
                marker_color="#172B3A",
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=(
                        bootstrap[
                            "capacity_ci_upper"
                        ]
                        - bootstrap[
                            "median_capacity_reduction"
                        ]
                    ),
                    arrayminus=(
                        bootstrap[
                            "median_capacity_reduction"
                        ]
                        - bootstrap[
                            "capacity_ci_lower"
                        ]
                    ),
                ),
            )
        )

        fig_capacity_effect.update_layout(
            height=380,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(
                l=30,
                r=30,
                t=30,
                b=30,
            ),
            xaxis_title="Hypothetical dwell cap",
            yaxis_title="Capacity reduction (ports)",
            showlegend=False,
        )

        fig_capacity_effect.update_yaxes(
            gridcolor="#EAECF0",
        )

        st.plotly_chart(
            fig_capacity_effect,
            use_container_width=True,
        )


# --------------------------------------------------
# BOOTSTRAP EFFECT TABLE
# --------------------------------------------------

st.divider()

st.subheader("Bootstrap uncertainty summary")

if not bootstrap.empty:

    bootstrap_table = bootstrap[
        [
            "scenario",
            "replicates",
            "policy_evaluation_capacity",
            "median_capacity_reduction",
            "capacity_ci_lower",
            "capacity_ci_upper",
            "median_blocking_rate_reduction_pct",
            "blocking_ci_lower_pct",
            "blocking_ci_upper_pct",
        ]
    ].copy()

    bootstrap_table = bootstrap_table.rename(
        columns={
            "scenario": "Policy",
            "replicates": "Bootstrap replicates",
            "policy_evaluation_capacity": (
                "Fixed evaluation capacity"
            ),
            "median_capacity_reduction": (
                "Median capacity reduction"
            ),
            "capacity_ci_lower": (
                "Capacity CI lower"
            ),
            "capacity_ci_upper": (
                "Capacity CI upper"
            ),
            "median_blocking_rate_reduction_pct": (
                "Median blocking reduction (pp)"
            ),
            "blocking_ci_lower_pct": (
                "Blocking CI lower (pp)"
            ),
            "blocking_ci_upper_pct": (
                "Blocking CI upper (pp)"
            ),
        }
    )

    numeric_columns = [
        "Median capacity reduction",
        "Capacity CI lower",
        "Capacity CI upper",
        "Median blocking reduction (pp)",
        "Blocking CI lower (pp)",
        "Blocking CI upper (pp)",
    ]

    bootstrap_table[numeric_columns] = (
        bootstrap_table[numeric_columns].round(3)
    )

    st.dataframe(
        bootstrap_table,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# FOUR-WEEK BLOCK SENSITIVITY
# --------------------------------------------------

st.divider()

st.subheader("Four-week block sensitivity")

st.caption(
    "Sensitivity check using the separate four-week "
    "block review export. Compare these intervals with "
    "the selected bootstrap block length above."
)

if site_review.empty:

    st.info(
        "No four-week review results are available "
        "for the selected site and regime."
    )

else:

    site_review["scenario"] = (
        site_review["scenario"].astype(str)
    )

    site_review = site_review[
        site_review["scenario"].isin(
            POLICY_ORDER
        )
    ].copy()

    site_review["scenario"] = pd.Categorical(
        site_review["scenario"],
        categories=POLICY_ORDER,
        ordered=True,
    )

    site_review = site_review.sort_values(
        "scenario"
    )

    site_review[
        "median_blocking_rate_reduction_pct"
    ] = numeric(
        site_review,
        "median_blocking_rate_reduction",
    ) * 100

    site_review[
        "blocking_reduction_ci_lower_pct"
    ] = numeric(
        site_review,
        "blocking_reduction_ci_lower",
    ) * 100

    site_review[
        "blocking_reduction_ci_upper_pct"
    ] = numeric(
        site_review,
        "blocking_reduction_ci_upper",
    ) * 100

    sensitivity_table = site_review[
        [
            "scenario",
            "policy_evaluation_capacity",
            "median_capacity_reduction",
            "capacity_reduction_ci_lower",
            "capacity_reduction_ci_upper",
            "median_blocking_rate_reduction_pct",
            "blocking_reduction_ci_lower_pct",
            "blocking_reduction_ci_upper_pct",
        ]
    ].copy()

    sensitivity_table = sensitivity_table.rename(
        columns={
            "scenario": "Policy",
            "policy_evaluation_capacity": (
                "Fixed evaluation capacity"
            ),
            "median_capacity_reduction": (
                "Median capacity reduction"
            ),
            "capacity_reduction_ci_lower": (
                "Capacity CI lower"
            ),
            "capacity_reduction_ci_upper": (
                "Capacity CI upper"
            ),
            "median_blocking_rate_reduction_pct": (
                "Median blocking reduction (pp)"
            ),
            "blocking_reduction_ci_lower_pct": (
                "Blocking CI lower (pp)"
            ),
            "blocking_reduction_ci_upper_pct": (
                "Blocking CI upper (pp)"
            ),
        }
    )

    numeric_columns = [
        "Median capacity reduction",
        "Capacity CI lower",
        "Capacity CI upper",
        "Median blocking reduction (pp)",
        "Blocking CI lower (pp)",
        "Blocking CI upper (pp)",
    ]

    sensitivity_table[numeric_columns] = (
        sensitivity_table[numeric_columns].round(3)
    )

    st.dataframe(
        sensitivity_table,
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
    **Post-charge dwell policy**

    A hypothetical dwell cap shortens the simulated
    connected interval for eligible sessions with valid
    charging-completion timestamps. Sessions without a
    valid completion timestamp remain unchanged.

    **Capacity effects**

    The minimum zero-blocking capacity describes the
    lowest tested capacity that accommodated all target
    arrivals in the replay. It is not a universal
    capacity requirement or an observed service level.

    **Bootstrap effects**

    Policy effects are paired differences evaluated
    at a fixed capacity selected from the full-sample
    baseline 5% blocking benchmark. The benchmark
    selection uncertainty is not included.

    **Four-week sensitivity**

    Longer resampling blocks preserve more weekly
    dependence than single-week resampling. Differences
    in uncertainty across block lengths are a sensitivity
    analysis, not proof that one block length is correct.

    **Real-world policy limitations**

    The scenario assumes drivers can move vehicles
    after charging completion. The dataset does not
    establish compliance, operational feasibility,
    or actual policy effectiveness.
    """
)

st.info(
    "Dwell-cap scenarios are hypothetical. ACN-Data "
    "contains successful charging sessions, not observed "
    "policy enforcement, rejected arrivals, or verified "
    "waiting times. Bootstrap intervals are conditional "
    "on the original replay and fixed-capacity evaluation "
    "benchmark; benchmark-selection uncertainty is not "
    "included."
)
