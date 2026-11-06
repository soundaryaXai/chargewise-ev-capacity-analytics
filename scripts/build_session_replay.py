
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

OUTPUT_FILE = (
    BASE_DIR / "data" / "processed" / "session_replay_results.csv"
)
SUMMARY_FILE = (
    BASE_DIR / "data" / "processed" / "session_replay_summary.csv"
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


def simulate_replay(
    sessions,
    capacity,
    target_regime,
    eligible_weeks,
):
    """
    Simulate a no-wait loss system using a min-heap.

    All site sessions are replayed chronologically. Sessions outside
    the target regime are included because they may occupy ports
    during the target observation window.

    Only target-regime arrivals in eligible weeks contribute to
    the reported blocking and acceptance statistics.

    Occupancy intervals are half-open:
        [connection_time, disconnect_time)

    A port is available when its previous session disconnects
    at or before the next arrival.
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
        departure = row.disconnect_time_utc

        # Release ports whose sessions have ended.
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
            if target_sessions > 0
            else 0.0
        ),
        "acceptance_rate": (
            accepted / target_sessions
            if target_sessions > 0
            else 0.0
        ),
        "other_sessions_accepted": other_accepted,
        "other_sessions_blocked": other_blocked,
    }


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

    # -----------------------------------------------------------------
    # Validate required columns
    # -----------------------------------------------------------------

    required_sessions = {
        "site",
        "regime",
        "source_record_index",
        "connection_time_utc",
        "disconnect_time_utc",
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

    # -----------------------------------------------------------------
    # Parse inclusion flags and timestamps
    # -----------------------------------------------------------------

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
            "Invalid homogeneous capacity comparison flags."
        )

    sessions["connection_time_utc"] = pd.to_datetime(
        sessions["connection_time_utc"],
        utc=True,
        errors="coerce",
    )

    sessions["disconnect_time_utc"] = pd.to_datetime(
        sessions["disconnect_time_utc"],
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

    # -----------------------------------------------------------------
    # Filter primary capacity-comparison cohort
    # -----------------------------------------------------------------

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

    print(
        f"Valid capacity-comparison sessions: "
        f"{len(sessions):,}"
    )

    # -----------------------------------------------------------------
    # Derive local Monday week start
    # -----------------------------------------------------------------

    sessions["week_start"] = (
        sessions["arrival_date_local"]
        - pd.to_timedelta(
            sessions["arrival_date_local"].dt.day_of_week,
            unit="D",
        )
    ).dt.normalize()

    weekly["week_start"] = pd.to_datetime(
        weekly["week_start"],
        errors="raise",
    ).dt.normalize()

    # Eligible full weeks, including weeks with zero sessions.
    eligible_week_lookup = (
        weekly.groupby(
            ["site", "regime"]
        )["week_start"]
        .apply(set)
        .to_dict()
    )

    # -----------------------------------------------------------------
    # Replay each site and target regime
    # -----------------------------------------------------------------

    results = []

    for site, all_site_sessions in sessions.groupby("site"):

        if site not in MAX_CAPACITIES:
            print(
                f"Skipping unknown site: {site}"
            )
            continue

        all_site_sessions = all_site_sessions.copy()

        max_capacity = MAX_CAPACITIES[site]

        for target_regime in sorted(PRIMARY_REGIMES):

            eligible_weeks = eligible_week_lookup.get(
                (site, target_regime),
                set(),
            )

            if not eligible_weeks:
                print(
                    f"Skipping {site} / {target_regime}: "
                    f"no eligible weeks."
                )
                continue

            # The target observation window ends after the final
            # eligible local calendar week.
            target_window_end = (
                max(eligible_weeks)
                + pd.Timedelta(days=7)
            )

            # Include ALL earlier site sessions, including sessions
            # from previous regimes. They may carry into the target
            # observation window and occupy ports.
            replay_cohort = all_site_sessions[
                all_site_sessions["arrival_date_local"]
                < target_window_end
            ].copy()

            target_arrivals = replay_cohort[
                (
                    replay_cohort["regime"]
                    == target_regime
                )
                & replay_cohort["week_start"].isin(
                    eligible_weeks
                )
            ].shape[0]

            if target_arrivals == 0:
                print(
                    f"Skipping {site} / {target_regime}: "
                    f"no target arrivals."
                )
                continue

            print(
                f"\nSimulating {site} / {target_regime}: "
                f"{len(replay_cohort):,} total arrivals; "
                f"{target_arrivals:,} target arrivals"
            )

            # Test every integer capacity.
            for capacity in range(
                1,
                max_capacity + 1,
            ):

                outcome = simulate_replay(
                    sessions=replay_cohort,
                    capacity=capacity,
                    target_regime=target_regime,
                    eligible_weeks=eligible_weeks,
                )

                # -----------------------------------------------------
                # Validation invariants
                # -----------------------------------------------------

                if (
                    outcome["target_sessions"]
                    != target_arrivals
                ):
                    raise AssertionError(
                        f"Target count mismatch for "
                        f"{site} / {target_regime} "
                        f"at capacity {capacity}."
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
                    capacity == 54
                    if site == "Caltech"
                    else capacity in {50, 52}
                    if site == "JPL"
                    else capacity == 8
                )

                results.append(
                    {
                        "site": site,
                        "regime": target_regime,
                        "capacity": capacity,
                        "is_reference_capacity": (
                            is_reference_capacity
                        ),
                        "eligible_weeks": len(
                            eligible_weeks
                        ),
                        **outcome,
                    }
                )

    # -----------------------------------------------------------------
    # Save detailed replay results
    # -----------------------------------------------------------------

    replay = pd.DataFrame(results)

    if replay.empty:
        raise ValueError(
            "No session replay results were generated."
        )

    replay = replay.sort_values(
        ["site", "regime", "capacity"]
    )

    replay.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # -----------------------------------------------------------------
    # Build summary
    # -----------------------------------------------------------------

    summary_rows = []

    for (site, regime), group in replay.groupby(
        ["site", "regime"]
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

        summary_rows.append(
            {
                "site": site,
                "regime": regime,
                "target_sessions": int(
                    maximum_result["target_sessions"]
                ),
                "minimum_zero_blocking_capacity": (
                    minimum_zero_capacity
                ),
                "maximum_tested_capacity": int(
                    maximum_result["capacity"]
                ),
                "blocked_at_maximum": int(
                    maximum_result["blocked_sessions"]
                ),
                "blocking_at_maximum": (
                    maximum_result["blocking_rate"]
                ),
                "other_sessions_accepted_at_maximum": int(
                    maximum_result[
                        "other_sessions_accepted"
                    ]
                ),
                "other_sessions_blocked_at_maximum": int(
                    maximum_result[
                        "other_sessions_blocked"
                    ]
                ),
            }
        )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        SUMMARY_FILE,
        index=False,
    )

    # -----------------------------------------------------------------
    # Print validation summary
    # -----------------------------------------------------------------

    print("\nCROSS-REGIME SESSION REPLAY VALIDATION")
    print("=" * 95)

    print(
        summary.to_string(
            index=False,
            formatters={
                "blocking_at_maximum": "{:.8f}".format,
            },
        )
    )

    print("\nFull replay:", OUTPUT_FILE)
    print("Summary:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
