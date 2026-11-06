
from pathlib import Path
from datetime import date, datetime, time, timedelta

import pandas as pd


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

TIMEZONE = "America/Los_Angeles"

BUSINESS_START = time(7, 0)
BUSINESS_END = time(19, 0)

PRESSURE_THRESHOLD = 0.80
PRESSURE_GATE_PERCENTAGE = 10.0

REGIMES = {
    "Pre-disruption": (date(2018, 1, 1), date(2020, 2, 29)),
    "Transition": (date(2020, 3, 1), date(2020, 3, 31)),
    "Disruption": (date(2020, 4, 1), date(2020, 10, 31)),
    "Recovery": (date(2020, 11, 1), date(2021, 9, 30)),
}

# These are analysis assumptions, not verified historical
# installed-capacity figures.
SITES = {
    "Caltech": {
        "file": "caltech_sessions.jsonl",
        "capacities": {
            "Provisional L2 capacity": 54,
        },
        "excluded_stations": {"2-39-81-4550"},
    },
    "JPL": {
        "file": "jpl_sessions.jsonl",
        "capacities": {
            "50-port scenario": 50,
            "52-port scenario": 52,
        },
        "excluded_stations": set(),
    },
    "Office 1": {
        "file": "office001_sessions.jsonl",
        "capacities": {
            "Provisional capacity": 8,
        },
        "excluded_stations": set(),
    },
}

# Known conflicting JPL records:
# Same station and connection timestamp, but different
# disconnect timestamps and energy delivered.
JPL_CONFLICT_STATION = "1-1-179-794"
JPL_CONFLICT_CONNECTION = pd.Timestamp("2021-07-19 13:11:16")

EXPECTED_JPL_CONFLICT_COUNT = 2


# ---------------------------------------------------------
# DATA LOADING AND VALIDATION
# ---------------------------------------------------------

def load_sessions(path):
    """Load sessions and convert timestamps to local time."""

    if not path.exists():
        raise FileNotFoundError(
            f"Session file not found: {path}"
        )

    df = pd.read_json(path, lines=True)

    required = {
        "connectionTime",
        "disconnectTime",
        "stationID",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: "
            f"{sorted(missing)}"
        )

    df["connectionTime"] = (
        pd.to_datetime(
            df["connectionTime"],
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert(TIMEZONE)
        .dt.tz_localize(None)
    )

    df["disconnectTime"] = (
        pd.to_datetime(
            df["disconnectTime"],
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert(TIMEZONE)
        .dt.tz_localize(None)
    )

    original_count = len(df)

    df = df.dropna(
        subset=[
            "connectionTime",
            "disconnectTime",
            "stationID",
        ]
    ).copy()

    df = df[
        df["disconnectTime"] > df["connectionTime"]
    ].copy()

    removed_count = original_count - len(df)

    print(
        f"Valid sessions retained: {len(df):,}"
    )
    print(
        f"Rows removed for missing/invalid core fields: "
        f"{removed_count:,}"
    )

    return df


def validate_station_overlaps(df, site_name):
    """
    Ensure that a station does not have overlapping sessions.

    Sessions are treated as half-open intervals:
    [connectionTime, disconnectTime)

    Touching endpoints are allowed.
    """

    ordered = df.sort_values(
        [
            "stationID",
            "connectionTime",
            "disconnectTime",
        ]
    ).copy()

    previous_max_end = (
        ordered.groupby("stationID")["disconnectTime"]
        .transform(
            lambda values: values.cummax().shift()
        )
    )

    overlaps = ordered[
        ordered["connectionTime"] < previous_max_end
    ]

    if not overlaps.empty:
        print(
            f"\n{site_name}: overlapping sessions detected."
        )

        print(
            overlaps[
                [
                    "stationID",
                    "connectionTime",
                    "disconnectTime",
                ]
            ].head(20).to_string(index=False)
        )

        raise ValueError(
            f"{site_name}: {len(overlaps)} same-station "
            "overlapping sessions detected. Investigate "
            "before calculating capacity pressure."
        )

    print(
        f"{site_name}: no same-station overlaps detected."
    )


# ---------------------------------------------------------
# DATE AND TIME HELPERS
# ---------------------------------------------------------

def monday_of(timestamp):
    return (
        timestamp.date()
        - timedelta(days=timestamp.weekday())
    )


def get_eligible_weeks(
    observed_start,
    observed_end,
    regime_start,
    regime_end,
):
    """
    Return complete Monday-Sunday weeks contained within
    both the observed date envelope and the regime.
    """

    lower = max(observed_start, regime_start)
    upper = min(observed_end, regime_end)

    last_monday = upper - timedelta(days=6)

    if lower > last_monday:
        return []

    first_monday = lower + timedelta(
        days=(7 - lower.weekday()) % 7
    )

    if first_monday > last_monday:
        return []

    return [
        timestamp.date()
        for timestamp in pd.date_range(
            start=first_monday,
            end=last_monday,
            freq="W-MON",
        )
    ]


# ---------------------------------------------------------
# WEEKLY BUSINESS-HOUR OCCUPANCY
# ---------------------------------------------------------

def calculate_weekly_peaks(
    all_sessions,
    eligible_weeks,
):
    """
    Calculate maximum simultaneous station occupancy
    during weekday business hours for each eligible week.

    Occupancy intervals:
        [connectionTime, disconnectTime)

    Business hours:
        Monday-Friday, 07:00-19:00 local time.

    All sessions are considered, including sessions that
    started before the regime but remained connected during it.
    """

    eligible_set = set(eligible_weeks)

    events_by_week = {
        week: [] for week in eligible_weeks
    }

    for row in all_sessions.itertuples(index=False):

        start = row.connectionTime
        end = row.disconnectTime

        current_day = start.date()
        last_day = end.date()

        while current_day <= last_day:

            if current_day.weekday() < 5:

                week_start = current_day - timedelta(
                    days=current_day.weekday()
                )

                if week_start in eligible_set:

                    window_start = datetime.combine(
                        current_day,
                        BUSINESS_START,
                    )

                    window_end = datetime.combine(
                        current_day,
                        BUSINESS_END,
                    )

                    clipped_start = max(
                        start,
                        window_start,
                    )

                    clipped_end = min(
                        end,
                        window_end,
                    )

                    if clipped_start < clipped_end:

                        events_by_week[week_start].append(
                            (clipped_start, 1)
                        )

                        events_by_week[week_start].append(
                            (clipped_end, -1)
                        )

            current_day += timedelta(days=1)

    weekly_peaks = {}

    for week, events in events_by_week.items():

        if not events:
            weekly_peaks[week] = 0
            continue

        event_df = pd.DataFrame(
            events,
            columns=["timestamp", "change"],
        )

        # Group simultaneous events before calculating
        # cumulative occupancy. This handles departures
        # and arrivals at the same timestamp correctly.
        grouped = (
            event_df.groupby("timestamp")["change"]
            .sum()
            .sort_index()
        )

        occupancy = grouped.cumsum()

        weekly_peaks[week] = int(
            occupancy.max()
        )

    return weekly_peaks


# ---------------------------------------------------------
# SITE AND REGIME AUDIT
# ---------------------------------------------------------

def audit_site(site_name, config):

    path = RAW_DIR / config["file"]

    print("\n" + "=" * 75)
    print(f"Loading {site_name}")
    print("=" * 75)

    df = load_sessions(path)

    # -----------------------------------------------------
    # EXCLUDE KNOWN CONFLICTING JPL RECORDS
    # -----------------------------------------------------

    conflicting_jpl_excluded_count = 0

    if site_name == "JPL":

        conflict_mask = (
            (
                df["stationID"].astype(str)
                == JPL_CONFLICT_STATION
            )
            &
            (
                df["connectionTime"]
                == JPL_CONFLICT_CONNECTION
            )
        )

        conflicting_jpl_excluded_count = int(
            conflict_mask.sum()
        )

        print(
            "Conflicting JPL records identified: "
            f"{conflicting_jpl_excluded_count}"
        )

        if (
            conflicting_jpl_excluded_count
            != EXPECTED_JPL_CONFLICT_COUNT
        ):
            raise ValueError(
                "Expected exactly "
                f"{EXPECTED_JPL_CONFLICT_COUNT} conflicting "
                "JPL records, but found "
                f"{conflicting_jpl_excluded_count}. "
                "Investigate the source records before proceeding."
            )

        df = df.loc[~conflict_mask].copy()

        print(
            "Conflicting JPL records excluded from "
            "primary analysis."
        )

    # -----------------------------------------------------
    # EXCLUDE UNCLASSIFIED EQUIPMENT
    # -----------------------------------------------------

    excluded_ids = config["excluded_stations"]

    excluded_mask = (
        df["stationID"].astype(str).isin(excluded_ids)
    )

    unclassified_excluded_count = int(
        excluded_mask.sum()
    )

    capacity_sessions = df.loc[
        ~excluded_mask
    ].copy()

    if unclassified_excluded_count:

        print(
            "Unclassified equipment sessions excluded: "
            f"{unclassified_excluded_count:,}"
        )

    # -----------------------------------------------------
    # SAME-STATION OVERLAP VALIDATION
    # -----------------------------------------------------

    validate_station_overlaps(
        capacity_sessions,
        site_name,
    )

    # -----------------------------------------------------
    # OBSERVED DATE ENVELOPE
    # -----------------------------------------------------

    observed_start = (
        df["connectionTime"].min().date()
    )

    observed_end = (
        df["disconnectTime"].max().date()
    )

    first_observed = df["connectionTime"].min()

    print(
        f"Observed start date: {observed_start}"
    )

    print(
        f"Observed end date:   {observed_end}"
    )

    # -----------------------------------------------------
    # REGIME ANALYSIS
    # -----------------------------------------------------

    weekly_rows = []
    summary_rows = []

    for regime_name, (
        regime_start,
        regime_end,
    ) in REGIMES.items():

        eligible_weeks = get_eligible_weeks(
            observed_start,
            observed_end,
            regime_start,
            regime_end,
        )

        # Exclude the first week if observations begin
        # partway through a Monday.
        if (
            first_observed.weekday() == 0
            and first_observed.time() > time(0, 0)
        ):

            first_week = first_observed.date()

            eligible_weeks = [
                week
                for week in eligible_weeks
                if week != first_week
            ]

        if not eligible_weeks:
            continue

        # Count sessions by their arrival/connection week.
        # This count is for the regime's weekly denominator.
        regime_sessions = capacity_sessions[
            capacity_sessions[
                "connectionTime"
            ].dt.date.between(
                regime_start,
                regime_end,
            )
        ].copy()

        regime_session_counts = (
            regime_sessions["connectionTime"]
            .map(monday_of)
            .value_counts()
            .to_dict()
        )

        # Important:
        # Calculate occupancy using ALL capacity_sessions.
        # Do not filter occupancy sessions by arrival regime.
        # A session that began earlier can still occupy a
        # station during the week being evaluated.
        weekly_peaks = calculate_weekly_peaks(
            capacity_sessions,
            eligible_weeks,
        )

        for week in eligible_weeks:

            weekly_rows.append({
                "site": site_name,
                "regime": regime_name,
                "week_start": week,
                "sessions_started": int(
                    regime_session_counts.get(week, 0)
                ),
                "weekly_peak_occupancy": (
                    weekly_peaks[week]
                ),
            })

        eligible_with_sessions = [
            week
            for week in eligible_weeks
            if regime_session_counts.get(week, 0) > 0
        ]

        zero_session_weeks = (
            len(eligible_weeks)
            - len(eligible_with_sessions)
        )

        observed_peaks = [
            weekly_peaks[week]
            for week in eligible_with_sessions
        ]

        # -------------------------------------------------
        # CAPACITY PRESSURE BY SCENARIO
        # -------------------------------------------------

        for (
            capacity_label,
            capacity,
        ) in config["capacities"].items():

            pressure_weeks = sum(
                peak >= PRESSURE_THRESHOLD * capacity
                for peak in observed_peaks
            )

            denominator = len(
                eligible_with_sessions
            )

            pressure_percentage = (
                100 * pressure_weeks / denominator
                if denominator
                else 0
            )

            summary_rows.append({

                "site": site_name,

                "regime": regime_name,

                "capacity_scenario": capacity_label,

                "assumed_capacity": capacity,

                "eligible_full_weeks": len(
                    eligible_weeks
                ),

                "weeks_with_sessions": denominator,

                "zero_session_weeks": (
                    zero_session_weeks
                ),

                "weeks_at_or_above_80pct": (
                    pressure_weeks
                ),

                "pressure_percentage": round(
                    pressure_percentage,
                    2,
                ),

                "median_weekly_peak": (
                    round(
                        pd.Series(
                            observed_peaks
                        ).median(),
                        2,
                    )
                    if observed_peaks
                    else None
                ),

                "p95_weekly_peak": (
                    round(
                        pd.Series(
                            observed_peaks
                        ).quantile(0.95),
                        2,
                    )
                    if observed_peaks
                    else None
                ),

                "maximum_weekly_peak": (
                    max(observed_peaks)
                    if observed_peaks
                    else None
                ),

                "passes_pressure_gate": (
                    pressure_percentage
                    >= PRESSURE_GATE_PERCENTAGE
                    if denominator
                    else False
                ),
            })

    return (
        weekly_rows,
        summary_rows,
        unclassified_excluded_count,
        conflicting_jpl_excluded_count,
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_weekly_rows = []
    all_summary_rows = []

    for site_name, config in SITES.items():

        (
            weekly,
            summary,
            unclassified_excluded_count,
            conflicting_jpl_excluded_count,
        ) = audit_site(
            site_name,
            config,
        )

        all_weekly_rows.extend(weekly)
        all_summary_rows.extend(summary)

        print(
            f"\n{site_name} audit summary:"
        )

        print(
            f"  Weekly records: "
            f"{len(weekly):,}"
        )

        print(
            f"  Unclassified equipment sessions excluded: "
            f"{unclassified_excluded_count:,}"
        )

        print(
            f"  Conflicting JPL records excluded: "
            f"{conflicting_jpl_excluded_count:,}"
        )

    # -----------------------------------------------------
    # SAVE OUTPUTS
    # -----------------------------------------------------

    weekly_df = pd.DataFrame(
        all_weekly_rows
    )

    summary_df = pd.DataFrame(
        all_summary_rows
    )

    weekly_path = (
        PROCESSED_DIR
        / "capacity_pressure_weekly.csv"
    )

    summary_path = (
        PROCESSED_DIR
        / "capacity_pressure_summary.csv"
    )

    weekly_df.to_csv(
        weekly_path,
        index=False,
    )

    summary_df.to_csv(
        summary_path,
        index=False,
    )

    # -----------------------------------------------------
    # DISPLAY SUMMARY
    # -----------------------------------------------------

    print("\n" + "=" * 100)
    print("CAPACITY PRESSURE AUDIT")
    print("=" * 100)

    columns = [
        "site",
        "regime",
        "capacity_scenario",
        "assumed_capacity",
        "eligible_full_weeks",
        "weeks_with_sessions",
        "zero_session_weeks",
        "weeks_at_or_above_80pct",
        "pressure_percentage",
        "median_weekly_peak",
        "p95_weekly_peak",
        "maximum_weekly_peak",
        "passes_pressure_gate",
    ]

    print(
        summary_df[columns].to_string(
            index=False
        )
    )

    # -----------------------------------------------------
    # OUTPUT FILES
    # -----------------------------------------------------

    print("\n" + "=" * 100)
    print("SAVED OUTPUTS")
    print("=" * 100)

    print(weekly_path)
    print(summary_path)

    # -----------------------------------------------------
    # INTERPRETATION
    # -----------------------------------------------------

    print("\n" + "=" * 100)
    print("INTERPRETATION")
    print("=" * 100)

    print(
        "The pressure gate passes when at least "
        f"{PRESSURE_GATE_PERCENTAGE:.0f}% of eligible "
        "weeks with observed sessions reach "
        f"{PRESSURE_THRESHOLD:.0%} of assumed capacity."
    )

    print(
        "This is a screening measure, not evidence "
        "of actual queues, rejected sessions, or "
        "unmet charging demand."
    )

    print(
        "Capacity figures are scenario assumptions. "
        "They should not be interpreted as verified "
        "historical installed capacity."
    )

    print(
        "Occupancy is calculated from connectionTime "
        "to disconnectTime using local time and "
        "half-open intervals."
    )


if __name__ == "__main__":
    main()
