
from pathlib import Path
import heapq

import pandas as pd


# ---------------------------------------------------------------------
# PATHS AND CONFIGURATION
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

SESSION_FILE = (
    BASE_DIR / "data" / "processed" / "eda_session_profile.csv"
)

WEEKLY_FILE = (
    BASE_DIR / "data" / "processed" / "capacity_pressure_weekly.csv"
)

RESULTS_FILE = (
    BASE_DIR / "data" / "processed" / "dwell_scenario_results.csv"
)

SUMMARY_FILE = (
    BASE_DIR / "data" / "processed" / "dwell_scenario_summary.csv"
)

MAX_CAPACITIES = {
    "Caltech": 54,
    "JPL": 52,
    "Office 1": 8,
}

PRIMARY_REGIMES = {
    "Pre-disruption",
    "Recovery",
}

DWELL_CAPS_MINUTES = {
    "Baseline": None,
    "30-minute cap": 30,
    "60-minute cap": 60,
    "120-minute cap": 120,
}

PRIMARY_REFERENCE_CAPACITY = {
    "Caltech": 54,
    "JPL": 52,
    "Office 1": 8,
}

SENSITIVITY_REFERENCE_CAPACITY = {
    "JPL": 50,
}


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def parse_boolean(series):
    """Convert CSV boolean strings into actual booleans."""

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
        })
    )


def prepare_sessions(sessions):
    """Validate and prepare session timestamps and inclusion flags."""

    sessions[
        "homogeneous_capacity_comparison_included"
    ] = parse_boolean(
        sessions[
            "homogeneous_capacity_comparison_included"
        ]
    )

    sessions["done_charging_time_valid"] = parse_boolean(
        sessions["done_charging_time_valid"]
    )

    if sessions[
        "homogeneous_capacity_comparison_included"
    ].isna().any():
        raise ValueError(
            "Invalid homogeneous capacity comparison flags."
        )

    if sessions["done_charging_time_valid"].isna().any():
        raise ValueError(
            "Invalid done_charging_time_valid flags."
        )

    timestamp_columns = [
        "connection_time_utc",
        "disconnect_time_utc",
        "done_charging_time_utc",
    ]

    for column in timestamp_columns:
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

    # Keep only the homogeneous capacity-comparison cohort.
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

    # Revalidate completion timestamps independently.
    valid_completion = (
        sessions["done_charging_time_valid"]
        & sessions["done_charging_time_utc"].notna()
        & (
            sessions["done_charging_time_utc"]
            >= sessions["connection_time_utc"]
        )
        & (
            sessions["done_charging_time_utc"]
            <= sessions["disconnect_time_utc"]
        )
    )

    sessions["valid_completion_for_policy"] = (
        valid_completion
    )

    # Derive local Monday week start.
    sessions["week_start"] = (
        sessions["arrival_date_local"]
        - pd.to_timedelta(
            sessions["arrival_date_local"].dt.day_of_week,
            unit="D",
        )
    ).dt.normalize()

    return sessions


def apply_dwell_cap(sessions, cap_minutes):
    """
    Create hypothetical disconnect timestamps.

    New disconnect:
        min(observed disconnect, completion time + dwell cap)

    Sessions without a valid completion timestamp retain their
    observed disconnect timestamp.
    """

    result = sessions.copy()

    result["scenario_disconnect_utc"] = (
        result["disconnect_time_utc"]
    )

    if cap_minutes is None:
        result["session_modified"] = False
        result["connected_hours_removed"] = 0.0
        return result

    valid = result["valid_completion_for_policy"]

    proposed_disconnect = (
        result.loc[valid, "done_charging_time_utc"]
        + pd.Timedelta(minutes=cap_minutes)
    )

    original_disconnect = (
        result.loc[valid, "disconnect_time_utc"]
    )

    capped_disconnect = pd.concat(
        [
            original_disconnect.rename("original"),
            proposed_disconnect.rename("proposed"),
        ],
        axis=1,
    ).min(axis=1)

    result.loc[
        valid,
        "scenario_disconnect_utc",
    ] = capped_disconnect

    removed_hours = (
        result["disconnect_time_utc"]
        - result["scenario_disconnect_utc"]
    ).dt.total_seconds() / 3600

    result["connected_hours_removed"] = (
        removed_hours.clip(lower=0)
    )

    result["session_modified"] = (
        result["connected_hours_removed"] > 0
    )

    # A policy must never create an invalid session interval.
    if (
        result["scenario_disconnect_utc"]
        <= result["connection_time_utc"]
    ).any():
        raise AssertionError(
            "Dwell cap created a non-positive session interval."
        )

    return result


def simulate_replay(
    sessions,
    capacity,
    target_regime,
    eligible_weeks,
):
    """
    Replay all arrivals chronologically.

    All sessions can occupy ports, including arrivals outside the
    target regime. Only target-regime arrivals in eligible weeks
    contribute to the reported blocking rate.
    """

    release_times = []

    accepted = 0
    blocked = 0

    other_accepted = 0
    other_blocked = 0

    ordered = sessions.sort_values(
        [
            "connection_time_utc",
            "source_record_index",
        ],
        kind="mergesort",
    )

    for row in ordered.itertuples(index=False):

        arrival = row.connection_time_utc
        departure = row.scenario_disconnect_utc

        # Half-open intervals: release at disconnect <= arrival.
        while (
            release_times
            and release_times[0] <= arrival
        ):
            heapq.heappop(release_times)

        is_target = (
            row.regime == target_regime
            and row.week_start in eligible_weeks
        )

        if len(release_times) < capacity:

            heapq.heappush(
                release_times,
                departure,
            )

            if is_target:
                accepted += 1
            else:
                other_accepted += 1

        else:

            if is_target:
                blocked += 1
            else:
                other_blocked += 1

    target_sessions = accepted + blocked

    return {
        "accepted_sessions": accepted,
        "blocked_sessions": blocked,
        "target_sessions": target_sessions,
        "blocking_rate": (
            blocked / target_sessions
            if target_sessions
            else 0.0
        ),
        "acceptance_rate": (
            accepted / target_sessions
            if target_sessions
            else 0.0
        ),
        "other_sessions_accepted": other_accepted,
        "other_sessions_blocked": other_blocked,
    }


def get_capacity_result(group, capacity):
    """Return blocking metrics for a specified capacity."""

    if capacity is None:
        return None, None

    matched = group[
        group["capacity"] == capacity
    ]

    if matched.empty:
        return None, None

    row = matched.iloc[0]

    return (
        int(row["blocked_sessions"]),
        float(row["blocking_rate"]),
    )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    print("Loading session and weekly audit data...")

    sessions = pd.read_csv(
        SESSION_FILE,
        low_memory=False,
    )

    weekly = pd.read_csv(
        WEEKLY_FILE,
        low_memory=False,
    )

    required_sessions = {
        "site",
        "regime",
        "source_record_index",
        "connection_time_utc",
        "disconnect_time_utc",
        "done_charging_time_utc",
        "done_charging_time_valid",
        "arrival_date_local",
        "homogeneous_capacity_comparison_included",
    }

    required_weekly = {
        "site",
        "regime",
        "week_start",
    }

    missing_sessions = (
        required_sessions - set(sessions.columns)
    )

    missing_weekly = (
        required_weekly - set(weekly.columns)
    )

    if missing_sessions or missing_weekly:
        raise ValueError(
            f"Missing session columns: "
            f"{sorted(missing_sessions)}; "
            f"missing weekly columns: "
            f"{sorted(missing_weekly)}"
        )

    sessions = prepare_sessions(sessions)

    weekly["week_start"] = pd.to_datetime(
        weekly["week_start"],
        errors="raise",
    ).dt.normalize()

    eligible_week_lookup = (
        weekly.groupby(
            ["site", "regime"]
        )["week_start"]
        .apply(set)
        .to_dict()
    )

    print(
        f"Valid capacity-comparison sessions: "
        f"{len(sessions):,}"
    )

    print(
        "Sessions with valid completion timestamps: "
        f"{sessions['valid_completion_for_policy'].sum():,}"
    )

    print(
        "Sessions without valid completion timestamps: "
        f"{(~sessions['valid_completion_for_policy']).sum():,}"
    )

    all_results = []
    all_summaries = []

    # -----------------------------------------------------------------
    # SITE AND REGIME LOOPS
    # -----------------------------------------------------------------

    for site, all_site_sessions in sessions.groupby("site"):

        if site not in MAX_CAPACITIES:
            continue

        max_capacity = MAX_CAPACITIES[site]

        for target_regime in sorted(PRIMARY_REGIMES):

            eligible_weeks = eligible_week_lookup.get(
                (site, target_regime),
                set(),
            )

            if not eligible_weeks:
                continue

            target_window_end = (
                max(eligible_weeks)
                + pd.Timedelta(days=7)
            )

            # Include all earlier sessions and sessions arriving
            # before the end of the target observation window.
            replay_cohort = all_site_sessions[
                all_site_sessions["arrival_date_local"]
                < target_window_end
            ].copy()

            target_mask = (
                (replay_cohort["regime"] == target_regime)
                & replay_cohort["week_start"].isin(
                    eligible_weeks
                )
            )

            target_arrivals = int(target_mask.sum())

            if target_arrivals == 0:
                continue

            print(
                f"\n{site} / {target_regime}: "
                f"{len(replay_cohort):,} replay arrivals; "
                f"{target_arrivals:,} target arrivals"
            )

            # ---------------------------------------------------------
            # BASELINE AND DWELL-CAP SCENARIOS
            # ---------------------------------------------------------

            for scenario_name, cap_minutes in (
                DWELL_CAPS_MINUTES.items()
            ):

                scenario_sessions = apply_dwell_cap(
                    replay_cohort,
                    cap_minutes,
                )

                scenario_target = scenario_sessions[
                    (
                        scenario_sessions["regime"]
                        == target_regime
                    )
                    & scenario_sessions["week_start"].isin(
                        eligible_weeks
                    )
                ]

                modified_target = int(
                    scenario_target["session_modified"].sum()
                )

                target_hours_removed = float(
                    scenario_target[
                        "connected_hours_removed"
                    ].sum()
                )

                target_modified_pct = (
                    modified_target / target_arrivals * 100
                )

                # All replay arrivals receive the policy, not just
                # the target arrivals. This preserves carryover.
                cohort_modified = int(
                    scenario_sessions["session_modified"].sum()
                )

                cohort_hours_removed = float(
                    scenario_sessions[
                        "connected_hours_removed"
                    ].sum()
                )

                print(
                    f"  {scenario_name}: "
                    f"{modified_target:,} target sessions modified; "
                    f"{target_hours_removed:.1f} target hours removed"
                )

                # -----------------------------------------------------
                # CAPACITY CURVE
                # -----------------------------------------------------

                for capacity in range(
                    1,
                    max_capacity + 1,
                ):

                    outcome = simulate_replay(
                        sessions=scenario_sessions,
                        capacity=capacity,
                        target_regime=target_regime,
                        eligible_weeks=eligible_weeks,
                    )

                    if (
                        outcome["target_sessions"]
                        != target_arrivals
                    ):
                        raise AssertionError(
                            f"Target count mismatch: {site}, "
                            f"{target_regime}, {scenario_name}, "
                            f"capacity {capacity}"
                        )

                    if (
                        outcome["accepted_sessions"]
                        + outcome["blocked_sessions"]
                        != target_arrivals
                    ):
                        raise AssertionError(
                            "Accepted + blocked does not equal "
                            "target arrivals."
                        )

                    is_reference_capacity = (
                        capacity
                        == PRIMARY_REFERENCE_CAPACITY[site]
                        or (
                            site in SENSITIVITY_REFERENCE_CAPACITY
                            and capacity
                            == SENSITIVITY_REFERENCE_CAPACITY[site]
                        )
                    )

                    all_results.append(
                        {
                            "site": site,
                            "regime": target_regime,
                            "scenario": scenario_name,
                            "dwell_cap_minutes": cap_minutes,
                            "capacity": capacity,
                            "is_reference_capacity": (
                                is_reference_capacity
                            ),
                            "eligible_weeks": len(
                                eligible_weeks
                            ),
                            "target_sessions_modified": (
                                modified_target
                            ),
                            "target_sessions_modified_pct": (
                                target_modified_pct
                            ),
                            "target_connected_hours_removed": (
                                target_hours_removed
                            ),
                            "cohort_sessions_modified": (
                                cohort_modified
                            ),
                            "cohort_connected_hours_removed": (
                                cohort_hours_removed
                            ),
                            **outcome,
                        }
                    )

    # -----------------------------------------------------------------
    # SAVE DETAILED RESULTS
    # -----------------------------------------------------------------

    results = pd.DataFrame(all_results)

    if results.empty:
        raise ValueError(
            "No dwell scenario results were generated."
        )

    results = results.sort_values(
        [
            "site",
            "regime",
            "scenario",
            "capacity",
        ]
    )

    results.to_csv(
        RESULTS_FILE,
        index=False,
    )

    # -----------------------------------------------------------------
    # BUILD SUMMARY
    # -----------------------------------------------------------------

    grouping = [
        "site",
        "regime",
        "scenario",
    ]

    for (site, regime, scenario), group in results.groupby(
        grouping
    ):

        group = group.sort_values("capacity")

        zero_blocking = group[
            group["blocked_sessions"] == 0
        ]

        minimum_zero_capacity = (
            int(zero_blocking["capacity"].min())
            if not zero_blocking.empty
            else None
        )

        maximum_result = group.iloc[-1]

        # Primary reference capacity:
        # Caltech = 54, JPL = 52, Office 1 = 8.
        reference_capacity = (
            PRIMARY_REFERENCE_CAPACITY[site]
        )

        (
            reference_blocked,
            reference_blocking_rate,
        ) = get_capacity_result(
            group,
            reference_capacity,
        )

        # Sensitivity reference capacity:
        # JPL = 50. Not applicable to other sites.
        sensitivity_capacity = (
            SENSITIVITY_REFERENCE_CAPACITY.get(site)
        )

        (
            sensitivity_blocked,
            sensitivity_blocking_rate,
        ) = get_capacity_result(
            group,
            sensitivity_capacity,
        )

        first = group.iloc[0]

        all_summaries.append(
            {
                "site": site,
                "regime": regime,
                "scenario": scenario,
                "dwell_cap_minutes": (
                    first["dwell_cap_minutes"]
                ),
                "target_sessions": int(
                    maximum_result["target_sessions"]
                ),
                "target_sessions_modified": int(
                    first["target_sessions_modified"]
                ),
                "target_sessions_modified_pct": float(
                    first["target_sessions_modified_pct"]
                ),
                "target_connected_hours_removed": float(
                    first["target_connected_hours_removed"]
                ),
                "cohort_sessions_modified": int(
                    first["cohort_sessions_modified"]
                ),
                "cohort_connected_hours_removed": float(
                    first["cohort_connected_hours_removed"]
                ),
                "minimum_zero_blocking_capacity": (
                    minimum_zero_capacity
                ),
                "reference_capacity": reference_capacity,
                "blocked_at_reference_capacity": (
                    reference_blocked
                ),
                "blocking_at_reference_capacity": (
                    reference_blocking_rate
                ),
                "sensitivity_capacity": sensitivity_capacity,
                "blocked_at_sensitivity_capacity": (
                    sensitivity_blocked
                ),
                "blocking_at_sensitivity_capacity": (
                    sensitivity_blocking_rate
                ),
                "blocked_at_maximum_capacity": int(
                    maximum_result["blocked_sessions"]
                ),
                "blocking_at_maximum_capacity": float(
                    maximum_result["blocking_rate"]
                ),
            }
        )

    summary = pd.DataFrame(all_summaries)

    summary = summary.sort_values(
        [
            "site",
            "regime",
            "scenario",
        ]
    )

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # -----------------------------------------------------------------
    # PRINT SUMMARY
    # -----------------------------------------------------------------

    print("\nDWELL-CAP SCENARIO SUMMARY")
    print("=" * 150)

    display_columns = [
        "site",
        "regime",
        "scenario",
        "target_sessions_modified",
        "target_sessions_modified_pct",
        "target_connected_hours_removed",
        "minimum_zero_blocking_capacity",
        "reference_capacity",
        "blocked_at_reference_capacity",
        "blocking_at_reference_capacity",
        "sensitivity_capacity",
        "blocked_at_sensitivity_capacity",
        "blocking_at_sensitivity_capacity",
    ]

    print(
        summary[display_columns].to_string(
            index=False,
            formatters={
                "target_sessions_modified_pct": (
                    "{:.2f}%".format
                ),
                "target_connected_hours_removed": (
                    "{:.1f}".format
                ),
                "blocking_at_reference_capacity": (
                    "{:.6f}".format
                ),
                "blocking_at_sensitivity_capacity": (
                    "{:.6f}".format
                ),
            },
        )
    )

    print("\nDetailed results:", RESULTS_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
