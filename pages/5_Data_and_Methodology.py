
import streamlit as st
import pandas as pd
from pathlib import Path

from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Data & Methodology",
    "Dataset provenance, audit findings, analytical definitions, "
    "model assumptions, validation and reproducibility.",
)


# --------------------------------------------------
# FILE CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"


@st.cache_data
def load_csv(filename):
    path = DATA_DIR / filename

    if not path.exists():
        return None

    return pd.read_csv(path)


def display_dataset(filename, title):
    data = load_csv(filename)

    if data is None:
        st.warning(f"{title}: file not available.")
        return

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# DATASET OVERVIEW
# --------------------------------------------------

st.divider()
st.subheader("Dataset overview")

st.markdown(
    """
    **Primary source:** ACN-Data, California Institute of Technology.

    ACN-Data contains real-world electric vehicle charging
    session records from workplace charging environments.
    The dataset provides session connection, disconnection,
    charging completion, energy delivery and other session
    attributes.
    """
)

st.markdown(
    "[ACN-Data official dataset and documentation](https://ev.caltech.edu/dataset)"
)

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric("Extracted sessions", "66,745")
metric2.metric("Sites analysed", "3")
metric3.metric("Primary study regimes", "2")
metric4.metric("Data source", "ACN-Data")

site_summary = pd.DataFrame(
    {
        "Site": ["Caltech", "JPL", "Office 1"],
        "Extracted sessions": [31424, 33638, 1683],
        "Observed station IDs": [55, 52, 8],
        "Primary role": [
            "Primary capacity study",
            "Primary capacity study",
            "Descriptive comparison",
        ],
    }
)

st.markdown("#### Site coverage")

st.dataframe(
    site_summary,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Station IDs represent observed equipment identifiers, "
    "not independently verified commissioned capacity. "
    "Capacity assumptions are documented separately."
)


# --------------------------------------------------
# DATA QUALITY AUDIT
# --------------------------------------------------

st.divider()
st.subheader("Data quality and audit findings")

st.markdown(
    """
    The extraction was assessed for core timestamp validity,
    interval ordering, station identifiers, duplicate records
    and station-level overlap anomalies.

    Core-field usability does not imply that every record is
    free from all possible data quality issues.
    """
)

quality = load_csv("data_quality_summary.csv")

if quality is not None:
    st.markdown("#### Audit summary")

    st.dataframe(
        quality,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning("Data quality summary is unavailable.")

with st.expander("Site-specific audit notes"):

    st.markdown(
        """
        **Caltech**

        - 31,424 extracted sessions.
        - 55 observed station identifiers.
        - An additional station identifier,
          `2-39-81-4550`, accounts for 1,130 sessions.
        - The additional station is unclassified for the
          primary capacity analysis and is excluded from that
          comparison.
        - The primary capacity assumption is 54 Level 2 ports.

        **JPL**

        - 33,638 extracted sessions.
        - 52 observed station identifiers.
        - Two conflicting records were identified at the
          same station, space and connection timestamp.
        - Both records are excluded from the primary replay
          analysis rather than selecting one arbitrarily.
        - 52 is the primary historical observed station-count
          assumption; 50 is examined as a sensitivity.

        **Office 1**

        - 1,683 extracted sessions.
        - Eight observed station identifiers.
        - Used primarily for descriptive comparison rather
          than the primary capacity-pressure study.
        """
    )

with st.expander("JPL conflicting record treatment"):

    st.markdown(
        """
        Two records share the same station, parking space,
        connection timestamp and charging completion
        timestamp, but have different disconnect times and
        energy delivery values.

        Neither record is treated as definitively correct.
        Both are excluded from the primary JPL replay.

        This avoids arbitrarily choosing one version of
        a conflicting observation.
        """
    )


# --------------------------------------------------
# DATA PREPARATION
# --------------------------------------------------

st.divider()
st.subheader("Data preparation workflow")

preparation_steps = [
    (
        "01",
        "Data extraction",
        "Retrieve session records from the ACN-Data API.",
    ),
    (
        "02",
        "Data validation",
        "Validate core timestamps, interval ordering, "
        "identifiers, duplicate records and overlap anomalies.",
    ),
    (
        "03",
        "Equipment review",
        "Review site-specific station identifiers and "
        "capacity assumptions.",
    ),
    (
        "04",
        "Regime selection",
        "Separate pre-disruption and recovery periods "
        "to avoid pooling materially different usage conditions.",
    ),
    (
        "05",
        "Occupancy reconstruction",
        "Reconstruct occupancy from connection to disconnection.",
    ),
    (
        "06",
        "Exploratory analysis",
        "Analyse hourly, weekday and hour-of-week patterns "
        "and session-duration behaviour.",
    ),
    (
        "07",
        "Capacity modelling",
        "Compare empirical capacity, Erlang-B and "
        "chronological session replay.",
    ),
    (
        "08",
        "Policy evaluation",
        "Evaluate hypothetical post-charge dwell caps "
        "and reduced-port capacity scenarios.",
    ),
    (
        "09",
        "Uncertainty analysis",
        "Use complete-week block bootstrap resampling "
        "for selected capacity and policy outcomes.",
    ),
]

for number, title, description in preparation_steps:

    with st.container(border=True):

        col1, col2 = st.columns([0.12, 0.88])

        with col1:
            st.markdown(f"### {number}")

        with col2:
            st.markdown(f"**{title}**")
            st.caption(description)


# --------------------------------------------------
# OCCUPANCY DEFINITIONS
# --------------------------------------------------

st.divider()
st.subheader("Occupancy reconstruction")

st.markdown(
    """
    Port occupancy is defined by the interval between
    vehicle connection and disconnection, rather than
    the duration of active energy delivery.
    """
)

time_col1, time_col2, time_col3 = st.columns(3)

with time_col1:
    st.markdown("**Connection time**")
    st.caption("Vehicle connects to a charging port.")

with time_col2:
    st.markdown("**Charging completion**")
    st.caption("Energy delivery finishes, if recorded.")

with time_col3:
    st.markdown("**Disconnection time**")
    st.caption("Vehicle releases the charging port.")

st.info(
    "Connected duration = disconnectTime − connectionTime. "
    "Post-charge dwell = disconnectTime − doneChargingTime, "
    "when charging completion is valid."
)

st.markdown(
    """
    Occupancy intervals use the half-open interval
    **[connection time, disconnection time)**.

    A session ending at the same timestamp as another
    session's arrival releases its port before that arrival
    is processed. This avoids counting touching endpoints
    as simultaneous occupancy.
    """
)

with st.expander("Additional time handling"):

    st.markdown(
        """
        - Timestamps are handled in the site timezone,
          America/Los_Angeles.
        - Business-hour analyses use weekdays from
          07:00 to 19:00 local time.
        - Week-based analyses use Monday as the
          start of the week.
        - Charging completion timestamps are only used
          when valid for the session interval.
        - Requested departure is a user-input field,
          not an observed disconnection time.
        """
    )


# --------------------------------------------------
# REGIME SELECTION
# --------------------------------------------------

st.divider()
st.subheader("Regime selection")

regime_table = pd.DataFrame(
    {
        "Regime": [
            "Pre-disruption",
            "Transition",
            "Disruption",
            "Recovery",
        ],
        "Period": [
            "Through February 2020",
            "March 2020",
            "April–October 2020",
            "November 2020–September 2021",
        ],
        "Analytical role": [
            "Primary study",
            "Excluded from primary comparisons",
            "Excluded from primary comparisons",
            "Secondary study",
        ],
    }
)

st.dataframe(
    regime_table,
    use_container_width=True,
    hide_index=True,
)

st.markdown(
    """
    The pre-disruption and recovery periods are analysed
    separately because usage conditions changed materially
    during the disruption period.

    The primary study focuses on Caltech and JPL.
    Office 1 remains a descriptive comparison because its
    observed usage and capacity-pressure evidence are
    more limited.
    """
)

with st.expander("Regime feasibility audit"):

    st.markdown(
        """
        Initial feasibility gates required:

        - At least 1,000 usable sessions.
        - At least 20 eligible full weeks with sessions.

        **Pre-disruption:** Caltech, JPL and Office 1
        satisfy the initial session and week gates.

        **Recovery:** Caltech and JPL satisfy the initial
        gates. Office 1 does not meet the session-count gate.

        **Disruption:** Caltech and JPL do not meet the
        minimum weeks-with-sessions gate.

        These gates are screening criteria, not universal
        standards. Eligible weeks do not independently
        confirm complete monitoring or operational availability.
        """
    )


# --------------------------------------------------
# CAPACITY ASSUMPTIONS
# --------------------------------------------------

st.divider()
st.subheader("Capacity assumptions")

capacity_table = pd.DataFrame(
    {
        "Site": ["Caltech", "JPL", "Office 1"],
        "Primary assumption": [54, 52, 8],
        "Sensitivity assumption": [
            "Equipment classification review",
            50,
            "Descriptive",
        ],
        "Interpretation": [
            "Provisional Level 2 assumption",
            "Historical observed station-count assumption",
            "Observed station-count assumption",
        ],
    }
)

st.dataframe(
    capacity_table,
    use_container_width=True,
    hide_index=True,
)

st.markdown(
    """
    Capacity assumptions are not equivalent to verified
    engineering inventory.

    - Caltech uses a provisional 54-port Level 2 assumption.
    - JPL uses 52 as its primary historical observed
      station-count assumption and 50 as sensitivity.
    - Office 1 uses eight observed station identifiers
      for descriptive analysis.

    The JPL discrepancy between historical station counts
    and published site capacity is retained as an explicit
    sensitivity rather than resolved by deleting observations.
    """
)


# --------------------------------------------------
# CAPACITY PRESSURE SCREENING
# --------------------------------------------------

st.divider()
st.subheader("Capacity-pressure screening")

pressure = load_csv("capacity_pressure_summary.csv")

if pressure is not None:

    st.markdown("#### Capacity-pressure audit results")

    st.dataframe(
        pressure,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.warning("Capacity-pressure summary is unavailable.")

st.markdown(
    """
    The capacity-pressure screening used:

    - Weekday business hours: 07:00–19:00 local time.
    - Occupancy: connection to disconnection.
    - Pressure threshold: weekly peak occupancy
      at or above 80% of the assumed capacity.
    - Screening gate: at least 10% of eligible
      business-hour weeks with sessions meeting the
      pressure threshold.

    The pressure gate is a screening rule, not evidence
    of queues, rejected drivers or a guaranteed service level.
    """ 
)


# --------------------------------------------------
# CAPACITY MODELLING
# --------------------------------------------------

st.divider()
st.subheader("Capacity modelling approaches")

model_col1, model_col2 = st.columns(2)

with model_col1:

    st.markdown("### Erlang-B")

    st.markdown(
        """
        Analytical loss-system baseline.

        - Poisson arrivals.
        - Independent service durations.
        - No waiting queue.
        - Blocked arrivals leave.

        Offered load:

        \\[
        A = \\lambda E[S]
        \\]

        Blocking probability is evaluated across
        available port counts.
        """
    )

with model_col2:

    st.markdown("### Session replay")

    st.markdown(
        """
        Chronological simulation using observed sessions.

        - Arrivals are processed in timestamp order.
        - Session intervals retain observed durations.
        - Sessions are accepted when a port is available.
        - Sessions that cannot be accommodated are blocked.

        This retains observed arrival and duration patterns
        rather than assuming Poisson arrivals.
        """
    )


# --------------------------------------------------
# EMPIRICAL BASELINES
# --------------------------------------------------

st.divider()
st.subheader("Empirical capacity baselines")

st.markdown(
    """
    Capacity results are compared against descriptive
    historical baselines:

    - **Historical peak occupancy:** maximum simultaneous
      occupancy observed.
    - **Hour-of-week occupancy:** empirical occupancy
      distributions for hour-of-week slices.
    - **Weekly peak occupancy:** observed weekly peaks
      across eligible weeks.

    These measures describe observed utilization and do
    not establish guaranteed service-level capacity.
    """
)

empirical = load_csv("empirical_capacity_summary.csv")

if empirical is not None:

    st.markdown("#### Empirical capacity summary")

    st.dataframe(
        empirical,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# DWELL SCENARIOS
# --------------------------------------------------

st.divider()
st.subheader("Hypothetical post-charge dwell scenarios")

st.markdown(
    """
    Dwell scenarios modify session disconnection times
    using hypothetical post-charge caps.

    For sessions with valid charging-completion timestamps:

    \\[
    t_{new} = \\min(t_{disconnect},\\,
    t_{charging\\ completion}+cap)
    \\]

    Sessions without valid completion timestamps are
    not modified by the dwell-cap rule.
    """
)

dwell_summary = load_csv("dwell_scenario_summary.csv")

if dwell_summary is not None:

    st.markdown("#### Scenario summary")

    st.dataframe(
        dwell_summary,
        use_container_width=True,
        hide_index=True,
    )

st.markdown(
    """
    The scenarios are hypothetical policy sensitivities.
    They do not establish that drivers would comply with
    a dwell cap, nor that charging completion reflects
    purely idle driver behaviour.
    """
)


# --------------------------------------------------
# BOOTSTRAP UNCERTAINTY
# --------------------------------------------------

st.divider()
st.subheader("Bootstrap uncertainty analysis")

st.markdown(
    """
    Uncertainty is assessed using complete-week moving-block
    resampling within site and regime.

    - Bootstrap repetitions: 2,000.
    - Random seed: 42.
    - Block lengths: 1, 2 and 4 weeks.
    - Confidence intervals: 95%.
    - Regimes are resampled separately.
    - Policy comparisons use paired baseline-versus-policy
      outcomes at a fixed baseline evaluation capacity.
    """
)

bootstrap_summary = load_csv("bootstrap_policy_effects_summary.csv")

if bootstrap_summary is not None:

    st.markdown("#### Bootstrap policy-effect summary")

    st.dataframe(
        bootstrap_summary,
        use_container_width=True,
        hide_index=True,
    )

bootstrap_validation = load_csv("bootstrap_validation.csv")

if bootstrap_validation is not None:

    with st.expander("Bootstrap validation output"):

        st.dataframe(
            bootstrap_validation,
            use_container_width=True,
            hide_index=True,
        )

bootstrap_review = load_csv(
    "bootstrap_policy_effects_4week_review.csv"
)

if bootstrap_review is not None:

    with st.expander("Four-week block sensitivity review"):

        st.dataframe(
            bootstrap_review,
            use_container_width=True,
            hide_index=True,
        )

st.warning(
    "Bootstrap confidence intervals are conditional on the "
    "original chronological replay and its carry-in state. "
    "They do not include uncertainty from selecting the "
    "baseline evaluation capacity."
)


# --------------------------------------------------
# VALIDATION STRATEGY
# --------------------------------------------------

st.divider()
st.subheader("Model validation strategy")

validation_items = [
    "Validate required timestamps and session interval ordering.",
    "Check station-level overlap anomalies.",
    "Validate occupancy reconstruction against session intervals.",
    "Verify replay behaviour at the reference capacity.",
    "Test replay behaviour with synthetic examples.",
    "Test boundary timestamps and touching intervals.",
    "Compare Erlang-B estimates with chronological replay.",
    "Check capacity results across port-count assumptions.",
    "Repeat key outcomes across bootstrap block lengths.",
    "Retain identified conflicting records as documented exclusions.",
]

for item in validation_items:
    st.markdown(f"- {item}")


# --------------------------------------------------
# LIMITATIONS
# --------------------------------------------------

st.divider()
st.subheader("Limitations and interpretation")

limitations = [
    (
        "Observed sessions only",
        "The dataset records sessions that obtained a charging "
        "port. It does not directly identify drivers who "
        "arrived and were turned away.",
    ),
    (
        "No observed waiting queue",
        "Blocking is estimated through modelling rather than "
        "measured from actual queue or denial records.",
    ),
    (
        "Site inventory uncertainty",
        "Observed station identifiers and published capacity "
        "figures may differ. Capacity assumptions are "
        "documented and tested where appropriate.",
    ),
    (
        "Site and setting coverage",
        "Workplace and campus charging results should not "
        "automatically be generalized to public fast charging.",
    ),
    (
        "Dwell interpretation",
        "Time between charging completion and disconnection "
        "may reflect operational or scheduling factors, "
        "not only driver behaviour.",
    ),
    (
        "Electrical constraints",
        "Port occupancy does not independently model "
        "site-level transformer capacity or electrical "
        "energy-management constraints.",
    ),
    (
        "Scenario assumptions",
        "Dwell caps and reduced-port scenarios are hypothetical "
        "interventions, not observed driver compliance.",
    ),
    (
        "Bootstrap scope",
        "Confidence intervals are conditional on the "
        "original replay and do not capture every source "
        "of modelling or capacity-selection uncertainty.",
    ),
]

for title, description in limitations:

    with st.expander(title):
        st.write(description)


# --------------------------------------------------
# REPRODUCIBILITY
# --------------------------------------------------

st.divider()
st.subheader("Reproducibility")

repro_col1, repro_col2 = st.columns(2)

with repro_col1:

    st.markdown(
        """
        **Analysis configuration**

        - Fixed bootstrap random seed.
        - Complete-week block resampling.
        - Regime-specific analysis.
        - Documented session-cleaning rules.
        - Explicit site-capacity assumptions.
        """
    )

with repro_col2:

    st.markdown(
        """
        **Reporting**

        - Point estimates and confidence intervals.
        - Bootstrap repetition counts.
        - Block-length sensitivity.
        - Capacity assumptions.
        - Exclusions and methodological limitations.
        """
    )


# --------------------------------------------------
# SOURCE AND DATA HANDLING
# --------------------------------------------------

st.divider()
st.subheader("Source and data handling")

st.markdown(
    """
    - Source: ACN-Data, California Institute of Technology.
    - Dataset access: official registration and API access.
    - Raw session data and API credentials are excluded
      from the public repository.
    - Derived results are produced from local processing
      scripts and processed datasets.
    - Dataset use should comply with the applicable
      source terms.

    [Official ACN-Data documentation](https://ev.caltech.edu/dataset)
    """
)

st.caption(
    "ChargeWise | EV Charging Capacity & Queueing Analytics"
)
