
import streamlit as st
import plotly.express as px
import pandas as pd

from components.page_header import render_page_header


# --------------------------------------------------
# PAGE HEADER
# --------------------------------------------------

render_page_header(
    "Data & Methodology",
    "Understand the dataset, preparation workflow, "
    "analytical methods, validation strategy and limitations.",
)

st.warning(
    "Methodology prototype | Dataset statistics and "
    "validation results will be populated after the "
    "ACN-Data extraction and audit."
)


# --------------------------------------------------
# DATASET OVERVIEW
# --------------------------------------------------

st.divider()

st.subheader("Dataset overview")

st.markdown(
    """
    **Primary source:** ACN-Data

    ACN-Data contains real-world EV charging session
    records from workplace and other charging environments.
    It provides connection, charging and disconnection
    timestamps alongside session-level attributes.
    """
)

st.markdown(
    "[ACN-Data official dataset and documentation](https://ev.caltech.edu/dataset)"
)

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric("Total sessions", "—")
metric2.metric("Selected sites", "—")
metric3.metric("Analysis period", "—")
metric4.metric("Usable sessions", "—")


# --------------------------------------------------
# DATA QUALITY
# --------------------------------------------------

st.divider()

st.subheader("Data quality and preparation")

st.caption(
    "The following checks will be calculated from the "
    "extracted dataset. No results are assumed in this prototype."
)

quality_checks = pd.DataFrame({
    "Validation check": [
        "Missing connection timestamps",
        "Missing disconnection timestamps",
        "Invalid timestamp ordering",
        "Missing station identifiers",
        "Duplicate session records",
        "Overlapping station sessions",
        "Sessions with charging completion time",
        "Sessions with requested departure",
    ],
    "Status": [
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
    ],
})

st.dataframe(
    quality_checks,
    use_container_width=True,
    hide_index=True,
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
        "Retrieve session records from the ACN-Data API "
        "for selected sites and analysis periods.",
    ),
    (
        "02",
        "Data validation",
        "Check required timestamps, station identifiers, "
        "duplicates and invalid session intervals.",
    ),
    (
        "03",
        "Regime identification",
        "Separate relevant operational periods to account "
        "for changes in charging conditions and usage.",
    ),
    (
        "04",
        "Occupancy reconstruction",
        "Reconstruct port occupancy using connectionTime "
        "and disconnectTime.",
    ),
    (
        "05",
        "Exploratory analysis",
        "Examine hourly, daily and hour-of-week utilization "
        "patterns and session behaviour.",
    ),
    (
        "06",
        "Capacity modelling",
        "Compare empirical occupancy baselines, Erlang-B "
        "estimates and chronological session replay.",
    ),
    (
        "07",
        "Scenario evaluation",
        "Test hypothetical port reductions and post-charge "
        "dwell caps using modified session intervals.",
    ),
    (
        "08",
        "Uncertainty analysis",
        "Use complete-week bootstrap resampling to estimate "
        "uncertainty in key capacity and blocking metrics.",
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
# OCCUPANCY DEFINITION
# --------------------------------------------------

st.divider()

st.subheader("Occupancy reconstruction")

st.markdown(
    """
    Port occupancy is based on the period between
    connection and disconnection—not the period during
    which electricity is actively delivered.
    """
)

time_col1, time_col2, time_col3 = st.columns(3)

with time_col1:
    st.markdown("**Connection time**")
    st.caption("Vehicle connects to a charging port.")

with time_col2:
    st.markdown("**Charging completion**")
    st.caption("Energy delivery is complete, if recorded.")

with time_col3:
    st.markdown("**Disconnection time**")
    st.caption("Vehicle releases the charging port.")

st.info(
    "Connected duration = disconnectTime − connectionTime. "
    "Post-charge dwell = disconnectTime − doneChargingTime, "
    "where valid charging-completion timestamps are available."
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
        An analytical loss-system baseline.

        - Assumes Poisson arrivals.
        - Assumes independent service durations.
        - Has no waiting queue.
        - Blocked arrivals leave the system.

        Offered load:

        \\[
        A = \\lambda E[S]
        \\]

        Blocking probability is calculated recursively
        for the available number of ports.
        """
    )

with model_col2:
    st.markdown("### Session replay")

    st.markdown(
        """
        A chronological simulation using observed sessions.

        - Processes arrivals in timestamp order.
        - Uses connection and disconnection times.
        - Accepts sessions when a port is available.
        - Counts arrivals that cannot be accommodated.

        This allows observed arrival and duration patterns
        to be retained instead of assuming Poisson arrivals.
        """
    )


# --------------------------------------------------
# EMPIRICAL BASELINES
# --------------------------------------------------

st.divider()

st.subheader("Empirical capacity baselines")

st.markdown(
    """
    The model outputs will be compared against two
    descriptive baselines:

    1. **Historical peak occupancy:** the maximum number
       of simultaneously connected sessions observed.
    2. **Hour-of-week occupancy quantiles:** empirical
       occupancy distributions for each hour-of-week slice.

    These describe historical utilization and should not
    be interpreted as guaranteed service-level capacity.
    """
)


# --------------------------------------------------
# VALIDATION STRATEGY
# --------------------------------------------------

st.divider()

st.subheader("Model validation strategy")

validation_items = [
    "Check reconstructed occupancy against known station-level session intervals.",
    "Verify that replay blocking is approximately zero at verified actual capacity.",
    "Test replay behaviour using small synthetic session examples with known outcomes.",
    "Check duplicate, overlapping and boundary-time session handling.",
    "Compare Erlang-B estimates with replay blocking across available port counts.",
    "Repeat key analyses using complete-week bootstrap samples.",
]

for item in validation_items:
    st.markdown(f"- {item}")


# --------------------------------------------------
# FEASIBILITY GATES
# --------------------------------------------------

st.divider()

st.subheader("Project feasibility criteria")

st.caption(
    "Predefined screening criteria used to decide whether "
    "capacity analysis is sufficiently supported by the data."
)

feasibility = pd.DataFrame({
    "Criterion": [
        "Usable session records",
        "Complete weeks",
        "Usable sessions in selected regime",
        "Capacity pressure",
    ],
    "Project screening threshold": [
        "At least 95%",
        "At least 20",
        "At least 1,000",
        "At least 10% of business-hour weeks "
        "with peak occupancy at or above 80% "
        "of verified usable capacity",
    ],
    "Current status": [
        "Pending audit",
        "Pending audit",
        "Pending audit",
        "Pending audit",
    ],
})

st.dataframe(
    feasibility,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "These are project-specific feasibility gates, not "
    "universal industry standards. A site failing the "
    "capacity-pressure criterion may still support a "
    "utilization and behaviour analysis."
)


# --------------------------------------------------
# LIMITATIONS
# --------------------------------------------------

st.divider()

st.subheader("Limitations and interpretation")

limitations = [
    (
        "Observed sessions only",
        "The dataset records sessions that obtained a charging "
        "port. It does not directly identify drivers who arrived "
        "and were turned away.",
    ),
    (
        "No observed waiting queue",
        "Blocking is estimated through modelling rather than "
        "measured from actual queue or denial records.",
    ),
    (
        "Site and setting coverage",
        "Results from workplace and campus charging sites "
        "should not automatically be generalized to public "
        "fast-charging networks.",
    ),
    (
        "Dwell interpretation",
        "Time between charging completion and disconnection "
        "may reflect operational or scheduling factors, not "
        "only driver behaviour.",
    ),
    (
        "Electrical constraints",
        "Port-level occupancy does not independently model "
        "site-level electrical power limits or energy "
        "management constraints.",
    ),
    (
        "Scenario assumptions",
        "Dwell caps and reduced-port scenarios are hypothetical "
        "interventions, not evidence of actual driver compliance.",
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

        - Fixed random seed for bootstrap resampling.
        - Complete-week resampling.
        - Regime-specific analysis.
        - Documented session-cleaning rules.
        """
    )

with repro_col2:
    st.markdown(
        """
        **Reporting requirements**

        - Point estimates and 95% confidence intervals.
        - Number of complete weeks sampled.
        - Bootstrap repetition count.
        - Dataset extraction and analysis period.
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
    - Raw session data and API credentials must not be
      committed to the public repository.
    - Published derived results must comply with the
      dataset's applicable terms of use.
    """
)

st.caption(
    "ChargeWise | EV Charging Capacity & Queueing Analytics"
)
