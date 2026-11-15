
from pathlib import Path

import heapq
import numpy as np
import pandas as pd


# =====================================================================
# PATHS AND CONFIGURATION
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

SESSION_FILE = (
    BASE_DIR / "data" / "processed" / "eda_session_profile.csv"
)

WEEKLY_FILE = (
    BASE_DIR / "data" / "processed" / "capacity_pressure_weekly.csv"
)

OUTPUT_DIR = BASE_DIR / "data" / "processed"

REPLICATES_FILE = (
    OUTPUT_DIR / "bootstrap_capacity_replicates.csv"
)

SUMMARY_FILE = (
    OUTPUT_DIR / "bootstrap_capacity_summary.csv"
)

POLICY_FILE = (
    OUTPUT_DIR / "bootstrap_policy_effects.csv"
)

VALIDATION_FILE = (
    OUTPUT_DIR / "bootstrap_validation.csv"
)

MAX_CAPACITIES = {
    "Caltech": 54,
    "JPL": 52,
    "Office 1": 8,
}

REFERENCE_CAPACITY = {
    "Caltech": 54,
    "JPL": 52,
    "Office 1": 8,
}

SENSITIVITY_CAPACITY = {
    "JPL": 50,
}

PRIMARY_REGIMES = {
    "Pre-disruption",
    "Recovery",
}

DWELL_SCENARIOS = {
    "Baseline": None,
    "30-minute cap": 30,
    "60-minute cap": 60,
    "120-minute cap": 120,
}

BOOTSTRAP_REPLICATES = 2000
RANDOM_SEED = 42

BLOCK_LENGTHS = [1, 2, 4]

CONFIDENCE_LEVEL = 0.95


# =====================================================================
# HELPERS
# =====================================================================

def parse_boolean(series):
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
        })
    )


def resolve_column(df, candidates, description):
    for column in candidates:
        if column in df.columns:
            return column

    raise ValueError(
        f"Could not find {description}. "
        f"Expected one of: {candidates}"
    )


def create_contiguous_blocks(weeks, block_length):
    """
    Create blocks containing consecutive calendar weeks.

    A valid block must have exactly seven days between
    successive Monday week-start dates.
    """

    blocks = []

    for start in range(
        len(weeks) - block_length + 1
    ):

        indices = list(
            range(start, start + block_length)
        )

        valid = True

        for left, right in zip(
            indices[:-1],
            indices[1:],
        ):

            difference = (
                weeks[right] - weeks[left]
            ).days

            if difference != 7:
                valid = False
                break

        if valid:
            blocks.append(indices)

    if not blocks:
        raise ValueError(
            f"No valid contiguous blocks of "
            f"length {block_length}."
        )

    return blocks


def sample_week_indices(
    blocks,
    number_of_weeks,
    rng,
):
    """
    Sample contiguous blocks with replacement.

    The resulting sample contains exactly the original
    number of eligible weeks.
    """

    sampled = []

    while len(sampled) < number_of_weeks:

        selected = int(
            rng.integers(0, len(blocks))
        )

        sampled.extend(blocks[selected])

    return sampled[:number_of_weeks]


def percentile_interval(values):
    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[np.isfinite(values)]

    if len(values) == 0:
        return np.nan, np.nan

    alpha = (1 - CONFIDENCE_LEVEL) / 2

    lower = np.quantile(values, alpha)
    upper = np.quantile(values, 1 - alpha)

    return float(lower), float(upper)


# =====================================================================
# SESSION PREPARATION
# =====================================================================

def prepare_sessions(sessions):

    required = {
        "site",
        "regime",
        "source_record_index",
        "connection_time_utc",
        "disconnect_time_utc",
        "arrival_date_local",
        "homogeneous_capacity_comparison_included",
    }

    missing = required - set(sessions.columns)

    if missing:
        raise ValueError(
            f"Missing session columns: {sorted(missing)}"
        )

    done_column = resolve_column(
        sessions,
        [
            "done_charging_time_utc",
            "done_charging_time",
        ],
        "completion timestamp column",
    )

    sessions[
        "homogeneous_capacity_comparison_included"
    ] = parse_boolean(
        sessions[
            "homogeneous_capacity_comparison_included"
        ]
    )

    if sessions[
        "homogeneous_capacity_comparison_included"
    ].isna().any():

        raise ValueError(
            "Invalid homogeneous capacity inclusion flags."
        )

    for column in [
        "connection_time_utc",
        "disconnect_time_utc",
        done_column,
    ]:

        sessions[column] = pd.to_datetime(
            sessions[column],
            utc=True,
            errors="coerce",
        )

    sessions["arrival_date_local"] = pd.to_datetime(
        sessions["arrival_date_local"],
        errors="coerce",
    )

    sessions["source_record_index"] = pd.to_numeric(
        sessions["source_record_index"],
        errors="raise",
    )

    sessions = sessions[
        sessions[
            "homogeneous_capacity_comparison_included"
        ]
        & sessions["connection_time_utc"].notna()
        & sessions["disconnect_time_utc"].notna()
        & sessions["arrival_date_local"].notna()
        & (
            sessions["disconnect_time_utc"]
            > sessions["connection_time_utc"]
        )
    ].copy()

    sessions["week_start"] = (
        sessions["arrival_date_local"]
        - pd.to_timedelta(
            sessions["arrival_date_local"].dt.day_of_week,
            unit="D",
        )
    ).dt.normalize()

    sessions["done_charging_time_utc"] = (
        sessions[done_column]
    )

    return sessions


# =====================================================================
# APPLY DWELL POLICY
# =====================================================================

def apply_dwell_policy(sessions, cap_minutes):

    result = sessions.copy()

    result["replay_disconnect_utc"] = (
        result["disconnect_time_utc"]
    )

    if cap_minutes is None:
        return result

    valid_completion = (
        result["done_charging_time_utc"].notna()
        & (
            result["done_charging_time_utc"]
            >= result["connection_time_utc"]
        )
        & (
            result["done_charging_time_utc"]
            <= result["disconnect_time_utc"]
        )
    )

    capped_departure = (
        result["done_charging_time_utc"]
        + pd.Timedelta(minutes=cap_minutes)
    )

    result.loc[
        valid_completion,
        "replay_disconnect_utc",
    ] = np.minimum(
        result.loc[
            valid_completion,
            "disconnect_time_utc",
        ],
        capped_departure.loc[valid_completion],
    )

    if (
        result["replay_disconnect_utc"]
        <= result["connection_time_utc"]
    ).any():

        raise AssertionError(
            "Dwell policy created a non-positive session."
        )

    return result


# =====================================================================
# WEEKLY CHRONOLOGICAL REPLAY
# =====================================================================

def replay_weekly_outcomes(
    sessions,
    capacity,
    target_regime,
    eligible_weeks,
):
    """
    Replay the entire historical cohort chronologically.

    All sessions before the end of the target observation
    window can occupy ports.

    Only target-regime arrivals in eligible weeks contribute
    to weekly target statistics.

    Carry-in sessions are retained naturally.

    Important:
    The resulting weekly outcomes are conditional on this
    original chronological replay. Bootstrap sampling later
    resamples these weekly outcomes; it does not regenerate
    the chronological queue state.
    """

    weekly_counts = {
        week: {
            "arrivals": 0,
            "accepted": 0,
            "blocked": 0,
        }
        for week in eligible_weeks
    }

    release_times = []

    ordered = sessions.sort_values(
        [
            "connection_time_utc",
            "source_record_index",
        ],
        kind="mergesort",
    )

    for row in ordered.itertuples(index=False):

        arrival = row.connection_time_utc
        departure = row.replay_disconnect_utc

        while (
            release_times
            and release_times[0] <= arrival
        ):
            heapq.heappop(release_times)

        is_target = (
            row.regime == target_regime
            and row.week_start in weekly_counts
        )

        if len(release_times) < capacity:

            heapq.heappush(
                release_times,
                departure,
            )

            if is_target:
                weekly_counts[
                    row.week_start
                ]["arrivals"] += 1

                weekly_counts[
                    row.week_start
                ]["accepted"] += 1

        elif is_target:

            weekly_counts[
                row.week_start
            ]["arrivals"] += 1

            weekly_counts[
                row.week_start
            ]["blocked"] += 1

    return weekly_counts


# =====================================================================
# CAPACITY METRICS
# =====================================================================

def calculate_capacity_metrics(
    sampled_indices,
    weekly_counts,
    weeks,
    max_capacity,
    reference_capacity,
    sensitivity_capacity=None,
    policy_evaluation_capacity=None,
):
    """
    Aggregate weekly outcomes using sampled week indices.

    Duplicate indices count as repeated sampled weeks.

    policy_evaluation_capacity is held fixed across baseline
    and dwell-policy scenarios for paired policy comparisons.
    """

    total_arrivals = {}
    total_blocked = {}

    for capacity in range(1, max_capacity + 1):

        counts = weekly_counts[capacity]

        arrivals = sum(
            counts[weeks[index]]["arrivals"]
            for index in sampled_indices
        )

        blocked = sum(
            counts[weeks[index]]["blocked"]
            for index in sampled_indices
        )

        total_arrivals[capacity] = arrivals
        total_blocked[capacity] = blocked

    reference_arrivals = total_arrivals[
        reference_capacity
    ]

    reference_blocked = total_blocked[
        reference_capacity
    ]

    reference_rate = (
        reference_blocked / reference_arrivals
        if reference_arrivals
        else np.nan
    )

    # -------------------------------------------------------------
    # Capacity thresholds
    # -------------------------------------------------------------

    minimum_zero = None
    capacity_1pct = None
    capacity_5pct = None

    for capacity in range(1, max_capacity + 1):

        arrivals = total_arrivals[capacity]
        blocked = total_blocked[capacity]

        rate = (
            blocked / arrivals
            if arrivals
            else np.nan
        )

        if blocked == 0 and minimum_zero is None:
            minimum_zero = capacity

        if (
            np.isfinite(rate)
            and rate <= 0.01
            and capacity_1pct is None
        ):
            capacity_1pct = capacity

        if (
            np.isfinite(rate)
            and rate <= 0.05
            and capacity_5pct is None
        ):
            capacity_5pct = capacity

    # -------------------------------------------------------------
    # JPL sensitivity capacity
    # -------------------------------------------------------------

    sensitivity_blocked = None
    sensitivity_rate = None

    if sensitivity_capacity is not None:

        sensitivity_blocked = total_blocked[
            sensitivity_capacity
        ]

        sensitivity_arrivals = total_arrivals[
            sensitivity_capacity
        ]

        sensitivity_rate = (
            sensitivity_blocked / sensitivity_arrivals
            if sensitivity_arrivals
            else np.nan
        )

    # -------------------------------------------------------------
    # Fixed policy-evaluation capacity
    # -------------------------------------------------------------

    policy_evaluation_blocked = None
    policy_evaluation_rate = None

    if policy_evaluation_capacity is not None:

        if not (
            1 <= policy_evaluation_capacity <= max_capacity
        ):
            raise ValueError(
                "Policy evaluation capacity is outside "
                "the tested capacity range."
            )

        policy_evaluation_blocked = total_blocked[
            policy_evaluation_capacity
        ]

        evaluation_arrivals = total_arrivals[
            policy_evaluation_capacity
        ]

        policy_evaluation_rate = (
            policy_evaluation_blocked / evaluation_arrivals
            if evaluation_arrivals
            else np.nan
        )

    # -------------------------------------------------------------
    # Return metrics
    # -------------------------------------------------------------

    return {
        "target_arrivals": int(reference_arrivals),

        "blocked_at_reference_capacity": int(
            reference_blocked
        ),

        "blocking_at_reference_capacity": float(
            reference_rate
        ),

        "minimum_zero_blocking_capacity": (
            minimum_zero
        ),

        "capacity_at_1pct_blocking": capacity_1pct,

        "capacity_at_5pct_blocking": capacity_5pct,

        "sensitivity_capacity": sensitivity_capacity,

        "blocked_at_sensitivity_capacity": (
            sensitivity_blocked
        ),

        "blocking_at_sensitivity_capacity": (
            sensitivity_rate
        ),

        "policy_evaluation_capacity": (
            policy_evaluation_capacity
        ),

        "blocked_at_policy_evaluation_capacity": (
            policy_evaluation_blocked
        ),

        "blocking_at_policy_evaluation_capacity": (
            policy_evaluation_rate
        ),
    }


# =====================================================================
# MAIN
# =====================================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading session and weekly data...")

    sessions = pd.read_csv(
        SESSION_FILE,
        low_memory=False,
    )

    weekly = pd.read_csv(
        WEEKLY_FILE,
        low_memory=False,
    )

    sessions = prepare_sessions(sessions)

    weekly_required = {
        "site",
        "regime",
        "week_start",
    }

    missing_weekly = (
        weekly_required - set(weekly.columns)
    )

    if missing_weekly:
        raise ValueError(
            f"Missing weekly columns: {sorted(missing_weekly)}"
        )

    weekly["week_start"] = pd.to_datetime(
        weekly["week_start"],
        errors="raise",
    ).dt.normalize()

    eligible_lookup = (
        weekly.groupby(["site", "regime"])["week_start"]
        .apply(lambda values: set(values))
        .to_dict()
    )

    print(
        f"Valid capacity-comparison sessions: "
        f"{len(sessions):,}"
    )

    rng = np.random.default_rng(RANDOM_SEED)

    replicate_rows = []
    policy_rows = []
    validation_rows = []

    # -------------------------------------------------------------
    # Site and regime loops
    # -------------------------------------------------------------

    for site in sorted(MAX_CAPACITIES):

        site_sessions = sessions[
            sessions["site"] == site
        ].copy()

        if site_sessions.empty:
            print(f"Skipping {site}: no sessions.")
            continue

        max_capacity = MAX_CAPACITIES[site]
        reference_capacity = REFERENCE_CAPACITY[site]

        sensitivity_capacity = SENSITIVITY_CAPACITY.get(
            site
        )

        for regime in sorted(PRIMARY_REGIMES):

            eligible_weeks = eligible_lookup.get(
                (site, regime),
                set(),
            )

            if not eligible_weeks:
                continue

            weeks = sorted(eligible_weeks)

            target_end = (
                weeks[-1] + pd.Timedelta(days=7)
            )

            replay_cohort = site_sessions[
                site_sessions["arrival_date_local"]
                < target_end
            ].copy()

            target_sessions = replay_cohort[
                (
                    replay_cohort["regime"] == regime
                )
                & replay_cohort["week_start"].isin(
                    eligible_weeks
                )
            ]

            if target_sessions.empty:
                continue

            print(
                f"\n{site} / {regime}: "
                f"{len(weeks)} eligible weeks, "
                f"{len(target_sessions):,} target arrivals"
            )

            # -----------------------------------------------------
            # Generate weekly outcomes for every scenario/capacity
            # -----------------------------------------------------

            scenario_weekly = {}

            for scenario, cap_minutes in (
                DWELL_SCENARIOS.items()
            ):

                policy_sessions = apply_dwell_policy(
                    replay_cohort,
                    cap_minutes,
                )

                scenario_weekly[scenario] = {}

                for capacity in range(
                    1,
                    max_capacity + 1,
                ):

                    outcomes = replay_weekly_outcomes(
                        sessions=policy_sessions,
                        capacity=capacity,
                        target_regime=regime,
                        eligible_weeks=weeks,
                    )

                    scenario_weekly[scenario][
                        capacity
                    ] = outcomes

            # -----------------------------------------------------
            # Full-sample metrics: initial calculation
            # -----------------------------------------------------

            full_indices = list(range(len(weeks)))

            initial_full_metrics = {}

            for scenario in DWELL_SCENARIOS:

                metrics = calculate_capacity_metrics(
                    sampled_indices=full_indices,
                    weekly_counts=scenario_weekly[scenario],
                    weeks=weeks,
                    max_capacity=max_capacity,
                    reference_capacity=reference_capacity,
                    sensitivity_capacity=sensitivity_capacity,
                )

                initial_full_metrics[scenario] = metrics

            # -----------------------------------------------------
            # Establish one fixed policy comparison capacity
            # -----------------------------------------------------

            policy_evaluation_capacity = (
                initial_full_metrics["Baseline"][
                    "capacity_at_5pct_blocking"
                ]
            )

            if policy_evaluation_capacity is None:
                raise AssertionError(
                    f"No 5% blocking benchmark found for "
                    f"{site} / {regime}."
                )

            print(
                f"Policy evaluation capacity: "
                f"{policy_evaluation_capacity} ports"
            )

            # -----------------------------------------------------
            # Full-sample metrics with fixed comparison capacity
            # -----------------------------------------------------

            full_metrics = {}

            for scenario in DWELL_SCENARIOS:

                metrics = calculate_capacity_metrics(
                    sampled_indices=full_indices,
                    weekly_counts=scenario_weekly[scenario],
                    weeks=weeks,
                    max_capacity=max_capacity,
                    reference_capacity=reference_capacity,
                    sensitivity_capacity=sensitivity_capacity,
                    policy_evaluation_capacity=(
                        policy_evaluation_capacity
                    ),
                )

                full_metrics[scenario] = metrics

                validation_rows.append(
                    {
                        "site": site,
                        "regime": regime,
                        "scenario": scenario,
                        "eligible_weeks": len(weeks),
                        "target_arrivals": metrics[
                            "target_arrivals"
                        ],
                        "full_sample_blocked_at_reference": (
                            metrics[
                                "blocked_at_reference_capacity"
                            ]
                        ),
                        "full_sample_blocking_rate": (
                            metrics[
                                "blocking_at_reference_capacity"
                            ]
                        ),
                        "full_sample_minimum_zero_capacity": (
                            metrics[
                                "minimum_zero_blocking_capacity"
                            ]
                        ),
                        "full_sample_capacity_at_1pct": (
                            metrics[
                                "capacity_at_1pct_blocking"
                            ]
                        ),
                        "full_sample_capacity_at_5pct": (
                            metrics[
                                "capacity_at_5pct_blocking"
                            ]
                        ),
                        "policy_evaluation_capacity": (
                            policy_evaluation_capacity
                        ),
                        "full_sample_blocked_at_policy_evaluation_capacity": (
                            metrics[
                                "blocked_at_policy_evaluation_capacity"
                            ]
                        ),
                        "full_sample_blocking_at_policy_evaluation_capacity": (
                            metrics[
                                "blocking_at_policy_evaluation_capacity"
                            ]
                        ),
                        "sensitivity_capacity": (
                            sensitivity_capacity
                        ),
                        "full_sample_blocked_at_sensitivity_capacity": (
                            metrics[
                                "blocked_at_sensitivity_capacity"
                            ]
                        ),
                        "full_sample_blocking_at_sensitivity_capacity": (
                            metrics[
                                "blocking_at_sensitivity_capacity"
                            ]
                        ),
                    }
                )

            # -----------------------------------------------------
            # Bootstrap block lengths
            # -----------------------------------------------------

            for block_length in BLOCK_LENGTHS:

                blocks = create_contiguous_blocks(
                    weeks,
                    block_length,
                )

                print(
                    f"  Block length {block_length}: "
                    f"{len(blocks)} available blocks"
                )

                for replicate in range(
                    BOOTSTRAP_REPLICATES
                ):

                    sampled_indices = sample_week_indices(
                        blocks=blocks,
                        number_of_weeks=len(weeks),
                        rng=rng,
                    )

                    if len(sampled_indices) != len(weeks):
                        raise AssertionError(
                            "Bootstrap sample has incorrect size."
                        )

                    sampled_unique = len(
                        set(sampled_indices)
                    )

                    replicate_metrics = {}

                    for scenario in DWELL_SCENARIOS:

                        metrics = calculate_capacity_metrics(
                            sampled_indices=sampled_indices,
                            weekly_counts=scenario_weekly[
                                scenario
                            ],
                            weeks=weeks,
                            max_capacity=max_capacity,
                            reference_capacity=reference_capacity,
                            sensitivity_capacity=sensitivity_capacity,
                            policy_evaluation_capacity=(
                                policy_evaluation_capacity
                            ),
                        )

                        replicate_metrics[scenario] = metrics

                        replicate_rows.append(
                            {
                                "site": site,
                                "regime": regime,
                                "block_length": block_length,
                                "replicate": replicate + 1,
                                "scenario": scenario,
                                "sampled_weeks": len(
                                    sampled_indices
                                ),
                                "unique_sampled_weeks": (
                                    sampled_unique
                                ),
                                **metrics,
                            }
                        )

                    # -------------------------------------------------
                    # Paired policy effects
                    # -------------------------------------------------

                    baseline = replicate_metrics["Baseline"]

                    for scenario in DWELL_SCENARIOS:

                        if scenario == "Baseline":
                            continue

                        policy = replicate_metrics[scenario]

                        baseline_capacity = (
                            baseline[
                                "minimum_zero_blocking_capacity"
                            ]
                        )

                        policy_capacity = (
                            policy[
                                "minimum_zero_blocking_capacity"
                            ]
                        )

                        capacity_reduction = (
                            baseline_capacity - policy_capacity
                            if (
                                baseline_capacity is not None
                                and policy_capacity is not None
                            )
                            else np.nan
                        )

                        blocking_reduction = (
                            baseline[
                                "blocking_at_policy_evaluation_capacity"
                            ]
                            - policy[
                                "blocking_at_policy_evaluation_capacity"
                            ]
                        )

                        policy_rows.append(
                            {
                                "site": site,
                                "regime": regime,
                                "block_length": block_length,
                                "replicate": replicate + 1,
                                "scenario": scenario,
                                "policy_evaluation_capacity": (
                                    policy_evaluation_capacity
                                ),
                                "capacity_reduction": (
                                    capacity_reduction
                                ),
                                "blocking_rate_reduction": (
                                    blocking_reduction
                                ),
                            }
                        )

            # -----------------------------------------------------
            # Validate full-sample target arrival reconciliation
            # -----------------------------------------------------

            expected_target_count = len(target_sessions)

            for scenario in DWELL_SCENARIOS:

                observed = full_metrics[scenario][
                    "target_arrivals"
                ]

                if observed != expected_target_count:
                    raise AssertionError(
                        f"Target arrival mismatch: "
                        f"{site} / {regime} / {scenario}. "
                        f"Expected {expected_target_count}, "
                        f"observed {observed}."
                    )

    # =================================================================
    # SAVE OUTPUTS
    # =================================================================

    replicates = pd.DataFrame(replicate_rows)
    policies = pd.DataFrame(policy_rows)
    validation = pd.DataFrame(validation_rows)

    if replicates.empty:
        raise ValueError(
            "No bootstrap replicates were generated."
        )

    replicates.to_csv(
        REPLICATES_FILE,
        index=False,
    )

    policies.to_csv(
        POLICY_FILE,
        index=False,
    )

    validation.to_csv(
        VALIDATION_FILE,
        index=False,
    )

    # =================================================================
    # BOOTSTRAP SUMMARY
    # =================================================================

    summary_rows = []

    metrics_to_summarize = [
        "blocking_at_reference_capacity",
        "minimum_zero_blocking_capacity",
        "capacity_at_1pct_blocking",
        "capacity_at_5pct_blocking",
        "blocked_at_reference_capacity",
        "blocking_at_sensitivity_capacity",
        "blocked_at_sensitivity_capacity",
        "blocking_at_policy_evaluation_capacity",
        "blocked_at_policy_evaluation_capacity",
    ]

    grouping = [
        "site",
        "regime",
        "block_length",
        "scenario",
    ]

    for keys, group in replicates.groupby(
        grouping,
        dropna=False,
    ):

        site, regime, block_length, scenario = keys

        validation_match = validation[
            (validation["site"] == site)
            & (validation["regime"] == regime)
            & (validation["scenario"] == scenario)
        ]

        if len(validation_match) != 1:
            raise AssertionError(
                f"Expected exactly one full-sample validation "
                f"row for {site} / {regime} / {scenario}."
            )

        full_sample = validation_match.iloc[0]

        row = {
            "site": site,
            "regime": regime,
            "block_length": block_length,
            "scenario": scenario,
            "replicates": len(group),
            "full_sample_blocking_rate": (
                full_sample["full_sample_blocking_rate"]
            ),
            "full_sample_minimum_zero_capacity": (
                full_sample[
                    "full_sample_minimum_zero_capacity"
                ]
            ),
            "policy_evaluation_capacity": (
                full_sample[
                    "policy_evaluation_capacity"
                ]
            ),
        }

        for metric in metrics_to_summarize:

            values = pd.to_numeric(
                group[metric],
                errors="coerce",
            )

            lower, upper = percentile_interval(values)

            row[f"{metric}_median"] = (
                float(values.median())
                if values.notna().any()
                else np.nan
            )

            row[f"{metric}_ci_lower"] = lower
            row[f"{metric}_ci_upper"] = upper

        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # =================================================================
    # PAIRED POLICY EFFECT SUMMARY
    # =================================================================

    policy_summary_rows = []

    policy_grouping = [
        "site",
        "regime",
        "block_length",
        "scenario",
    ]

    for keys, group in policies.groupby(
        policy_grouping
    ):

        site, regime, block_length, scenario = keys

        capacity_lower, capacity_upper = (
            percentile_interval(
                group["capacity_reduction"]
            )
        )

        blocking_lower, blocking_upper = (
            percentile_interval(
                group["blocking_rate_reduction"]
            )
        )

        policy_summary_rows.append(
            {
                "site": site,
                "regime": regime,
                "block_length": block_length,
                "scenario": scenario,
                "replicates": len(group),
                "policy_evaluation_capacity": (
                    group[
                        "policy_evaluation_capacity"
                    ].iloc[0]
                ),
                "median_capacity_reduction": (
                    group["capacity_reduction"].median()
                ),
                "capacity_reduction_ci_lower": (
                    capacity_lower
                ),
                "capacity_reduction_ci_upper": (
                    capacity_upper
                ),
                "median_blocking_rate_reduction": (
                    group["blocking_rate_reduction"].median()
                ),
                "blocking_reduction_ci_lower": (
                    blocking_lower
                ),
                "blocking_reduction_ci_upper": (
                    blocking_upper
                ),
            }
        )

    policy_summary = pd.DataFrame(
        policy_summary_rows
    )

    policy_summary.to_csv(
        POLICY_FILE.with_name(
            "bootstrap_policy_effects_summary.csv"
        ),
        index=False,
    )

    # =================================================================
    # FINAL VALIDATION
    # =================================================================

    expected_replicates = BOOTSTRAP_REPLICATES

    replicate_check = (
        replicates.groupby(
            [
                "site",
                "regime",
                "scenario",
                "block_length",
            ]
        )["replicate"]
        .nunique()
    )

    if not (
        replicate_check == expected_replicates
    ).all():

        raise AssertionError(
            "Unexpected bootstrap replicate count."
        )

    if not (
        replicates["sampled_weeks"]
        == replicates.groupby(
            ["site", "regime", "block_length"]
        )["sampled_weeks"].transform("first")
    ).all():

        raise AssertionError(
            "Inconsistent sampled week counts."
        )

    # -------------------------------------------------------------
    # Blocking-rate range checks
    # -------------------------------------------------------------

    rate_columns = [
        "blocking_at_reference_capacity",
        "blocking_at_sensitivity_capacity",
        "blocking_at_policy_evaluation_capacity",
    ]

    for column in rate_columns:

        rates = pd.to_numeric(
            replicates[column],
            errors="coerce",
        )

        if (
            (rates.dropna() < 0).any()
            or (rates.dropna() > 1).any()
        ):

            raise AssertionError(
                f"Invalid bootstrap blocking rate: {column}"
            )

    # -------------------------------------------------------------
    # Policy comparison validation
    # -------------------------------------------------------------

    if policies.empty:
        raise AssertionError(
            "No paired policy effects were generated."
        )

    if policies["policy_evaluation_capacity"].isna().any():
        raise AssertionError(
            "Missing policy evaluation capacity."
        )

    policy_capacity_check = (
        policies.groupby(
            ["site", "regime"]
        )["policy_evaluation_capacity"]
        .nunique()
    )

    if not (policy_capacity_check == 1).all():
        raise AssertionError(
            "Policy evaluation capacity is not fixed "
            "within each site/regime."
        )

    # -------------------------------------------------------------
    # Output validation report
    # -------------------------------------------------------------

    print("\nBOOTSTRAP VALIDATION")
    print("=" * 80)

    print(
        f"Bootstrap replicates per block length: "
        f"{BOOTSTRAP_REPLICATES:,}"
    )

    print(
        f"Block lengths: {BLOCK_LENGTHS}"
    )

    print(
        f"Random seed: {RANDOM_SEED}"
    )

    print(
        f"Replicate rows: {len(replicates):,}"
    )

    print(
        f"Policy effect rows: {len(policies):,}"
    )

    print("\nFull-sample validation:")
    print(
        validation.to_string(index=False)
    )

    print("\nPolicy effect summary:")
    print(
        policy_summary.to_string(index=False)
    )

    print("\nGenerated files:")
    print(REPLICATES_FILE)
    print(SUMMARY_FILE)
    print(POLICY_FILE)
    print(VALIDATION_FILE)

    print(
        POLICY_FILE.with_name(
            "bootstrap_policy_effects_summary.csv"
        )
    )


if __name__ == "__main__":
    main()
