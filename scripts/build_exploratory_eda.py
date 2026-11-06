
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


# ---------------------------------------------------------------------
# PATHS AND CONFIGURATION
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc

SITES = {
    "Caltech": "caltech_sessions.jsonl",
    "JPL": "jpl_sessions.jsonl",
    "Office 1": "office001_sessions.jsonl",
}

# Regime boundaries use the session's local connection date.
REGIME_BOUNDARIES = [
    (datetime(2020, 3, 1).date(), "Pre-disruption"),
    (datetime(2020, 4, 1).date(), "Transition"),
    (datetime(2020, 11, 1).date(), "Disruption"),
    (datetime(2021, 10, 1).date(), "Recovery"),
]

# Caltech station with unclassified equipment type.
CALTECH_UNCLASSIFIED_STATION = "2-39-81-4550"

# Known JPL conflicting pair.
JPL_CONFLICT_STATION = "1-1-179-794"
JPL_CONFLICT_START_UTC = datetime(
    2021, 7, 19, 20, 11, 16, tzinfo=UTC
)

# Local weekday business-hour screening window.
BUSINESS_START_HOUR = 7
BUSINESS_END_HOUR = 19


# ---------------------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------------------

def parse_timestamp(value):
    """Parse a timestamp into an aware UTC datetime."""
    if value is None or value == "":
        return None

    timestamp = pd.to_datetime(
        value,
        format="mixed",
        errors="coerce",
        utc=True,
    )

    if pd.isna(timestamp):
        return None

    return timestamp.to_pydatetime()


def load_sessions(filename):
    """Load JSONL session records."""
    records = []

    path = RAW_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))

    return records


def get_regime(local_date):
    """Assign an operating regime using local connection date."""
    if local_date < REGIME_BOUNDARIES[0][0]:
        return "Pre-disruption"

    if local_date < REGIME_BOUNDARIES[1][0]:
        return "Transition"

    if local_date < REGIME_BOUNDARIES[2][0]:
        return "Disruption"

    if local_date < REGIME_BOUNDARIES[3][0]:
        return "Recovery"

    return "Outside study regimes"


def percentile(series, quantile):
    """Return a percentile, or NaN when no valid values exist."""
    values = pd.to_numeric(series, errors="coerce").dropna()

    if values.empty:
        return float("nan")

    return values.quantile(quantile)


def write_csv(rows, filename):
    """Write a list of dictionaries to the processed-data directory."""
    output_path = PROCESSED_DIR / filename
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"  Created: {output_path.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------
# SESSION PREPARATION
# ---------------------------------------------------------------------

def prepare_site_sessions(site_name, records):
    """
    Preserve valid session records and add analytical fields.

    Elapsed durations are calculated using UTC timestamps.
    Local timestamps are used only for calendar classifications.
    """
    prepared = []

    for index, record in enumerate(records):
        start = parse_timestamp(record.get("connectionTime"))
        end = parse_timestamp(record.get("disconnectTime"))
        done = parse_timestamp(record.get("doneChargingTime"))

        valid_interval = (
            start is not None
            and end is not None
            and end > start
        )

        if not valid_interval:
            continue

        local_start = start.astimezone(LOCAL_TZ)
        local_end = end.astimezone(LOCAL_TZ)

        connected_hours = (
            end - start
        ).total_seconds() / 3600

        valid_done_time = (
            done is not None
            and start <= done <= end
        )

        charging_hours = (
            (done - start).total_seconds() / 3600
            if valid_done_time
            else None
        )

        post_charge_dwell_hours = (
            (end - done).total_seconds() / 3600
            if valid_done_time
            else None
        )

        station_id = record.get("stationID")
        session_id = record.get("sessionID")

        regime = get_regime(local_start.date())

        # Preserve the source record index for traceability.
        prepared.append(
            {
                "site": site_name,
                "source_record_index": index,
                "session_id": session_id,
                "station_id": station_id,
                "space_id": record.get("spaceID"),
                "cluster_id": record.get("clusterID"),
                "user_id": record.get("userID"),
                "connection_time_utc": start.isoformat(),
                "disconnect_time_utc": end.isoformat(),
                "done_charging_time_utc": (
                    done.isoformat() if done is not None else None
                ),
                "connection_time_local": local_start.isoformat(),
                "disconnect_time_local": local_end.isoformat(),
                "connected_hours": connected_hours,
                "charging_hours": charging_hours,
                "post_charge_dwell_hours": post_charge_dwell_hours,
                "done_charging_time_valid": valid_done_time,
                "arrival_date_local": local_start.date().isoformat(),
                "arrival_hour": local_start.hour,
                "weekday_number": local_start.weekday(),
                "weekday_name": local_start.strftime("%A"),
                "hour_of_week": (
                    local_start.weekday() * 24 + local_start.hour
                ),
                "day_type": (
                    "Weekend"
                    if local_start.weekday() >= 5
                    else "Weekday"
                ),
                "regime": regime,
                "is_business_hour_arrival": (
                    local_start.weekday() < 5
                    and BUSINESS_START_HOUR
                    <= local_start.hour
                    < BUSINESS_END_HOUR
                ),
                "same_station_overlap": False,
                "jpl_conflicting_record": False,
                "caltech_unclassified_station": (
                    site_name == "Caltech"
                    and station_id == CALTECH_UNCLASSIFIED_STATION
                ),
            }
        )

    return prepared


# ---------------------------------------------------------------------
# OVERLAP AND CONFLICT FLAGS
# ---------------------------------------------------------------------

def flag_same_station_overlaps(sessions):
    """
    Flag every session involved in a same-station overlap.

    Intervals are half-open: [connection, disconnect).
    Touching endpoints are not overlaps.
    """
    by_station = defaultdict(list)

    for session in sessions:
        station = session["station_id"]

        if station:
            by_station[station].append(session)

    overlap_pairs = []

    for station, station_sessions in by_station.items():
        station_sessions.sort(
            key=lambda item: item["connection_time_utc"]
        )

        active = []

        for current in station_sessions:
            current_start = datetime.fromisoformat(
                current["connection_time_utc"]
            )

            active = [
                previous
                for previous in active
                if datetime.fromisoformat(
                    previous["disconnect_time_utc"]
                ) > current_start
            ]

            for previous in active:
                previous["same_station_overlap"] = True
                current["same_station_overlap"] = True

                overlap_pairs.append(
                    {
                        "site": current["site"],
                        "station_id": station,
                        "session_a": previous["session_id"],
                        "session_b": current["session_id"],
                    }
                )

            active.append(current)

    return overlap_pairs


def flag_jpl_conflicts(sessions):
    """
    Identify the known JPL pair using station and exact UTC start time.

    Fail rather than silently changing the exclusion rule if the expected
    two records are not found.
    """
    matches = []

    for session in sessions:
        if session["site"] != "JPL":
            continue

        start = datetime.fromisoformat(
            session["connection_time_utc"]
        )

        if (
            session["station_id"] == JPL_CONFLICT_STATION
            and start == JPL_CONFLICT_START_UTC
        ):
            matches.append(session)

    if len(matches) != 2:
        raise ValueError(
            "Expected exactly two known conflicting JPL records, "
            f"but found {len(matches)}. Review the conflict rule."
        )

    for session in matches:
        session["jpl_conflicting_record"] = True

    return matches


def add_analysis_flags(sessions):
    """Add separate inclusion flags for different analytical purposes."""
    for session in sessions:
        session["primary_occupancy_included"] = (
            not session["same_station_overlap"]
            and not session["jpl_conflicting_record"]
        )

        session["homogeneous_capacity_comparison_included"] = (
            session["primary_occupancy_included"]
            and not session["caltech_unclassified_station"]
        )


# ---------------------------------------------------------------------
# ARRIVAL ANALYSIS
# ---------------------------------------------------------------------

def build_arrival_outputs(sessions):
    hourly = defaultdict(int)
    hour_of_week = defaultdict(int)

    for session in sessions:
        site = session["site"]
        hour = session["arrival_hour"]
        weekday = session["weekday_number"]

        hourly[(site, hour)] += 1
        hour_of_week[(site, weekday, hour)] += 1

    hourly_rows = []

    for site in SITES:
        for hour in range(24):
            hourly_rows.append(
                {
                    "site": site,
                    "local_hour": hour,
                    "arrival_sessions": hourly[(site, hour)],
                }
            )

    hour_of_week_rows = []

    for site in SITES:
        for weekday in range(7):
            for hour in range(24):
                hour_of_week_rows.append(
                    {
                        "site": site,
                        "weekday_number": weekday,
                        "weekday_name": datetime(
                            2024, 1, 1
                        ).replace(
                            day=1 + weekday
                        ).strftime("%A"),
                        "local_hour": hour,
                        "hour_of_week": weekday * 24 + hour,
                        "arrival_sessions": hour_of_week[
                            (site, weekday, hour)
                        ],
                    }
                )

    return hourly_rows, hour_of_week_rows


# ---------------------------------------------------------------------
# DURATION AND WEEKDAY/WEEKEND ANALYSIS
# ---------------------------------------------------------------------

def build_duration_outputs(sessions):
    rows = []

    for site in SITES:
        for regime in [
            "Pre-disruption",
            "Transition",
            "Disruption",
            "Recovery",
        ]:
            subset = [
                session
                for session in sessions
                if session["site"] == site
                and session["regime"] == regime
            ]

            if not subset:
                continue

            frame = pd.DataFrame(subset)

            for metric in [
                "connected_hours",
                "charging_hours",
                "post_charge_dwell_hours",
            ]:
                values = pd.to_numeric(
                    frame[metric],
                    errors="coerce",
                ).dropna()

                rows.append(
                    {
                        "site": site,
                        "regime": regime,
                        "duration_type": metric,
                        "valid_sessions": len(values),
                        "mean_hours": (
                            values.mean() if len(values) else None
                        ),
                        "median_hours": (
                            values.median() if len(values) else None
                        ),
                        "p75_hours": percentile(values, 0.75),
                        "p90_hours": percentile(values, 0.90),
                        "p95_hours": percentile(values, 0.95),
                        "maximum_hours": (
                            values.max() if len(values) else None
                        ),
                    }
                )

    return rows


def build_weekday_weekend_outputs(sessions):
    rows = []

    for site in SITES:
        for day_type in ["Weekday", "Weekend"]:
            subset = [
                session
                for session in sessions
                if session["site"] == site
                and session["day_type"] == day_type
            ]

            frame = pd.DataFrame(subset)

            if frame.empty:
                continue

            connected = frame["connected_hours"].dropna()
            charging = frame["charging_hours"].dropna()
            dwell = frame["post_charge_dwell_hours"].dropna()

            rows.append(
                {
                    "site": site,
                    "day_type": day_type,
                    "sessions": len(frame),
                    "mean_connected_hours": connected.mean(),
                    "median_connected_hours": connected.median(),
                    "median_charging_hours": (
                        charging.median() if len(charging) else None
                    ),
                    "median_post_charge_dwell_hours": (
                        dwell.median() if len(dwell) else None
                    ),
                }
            )

    return rows


# ---------------------------------------------------------------------
# TIME-WEIGHTED OCCUPANCY BY LOCAL HOUR OF WEEK
# ---------------------------------------------------------------------

def floor_utc_hour(timestamp):
    """Return the start of the UTC hour containing a timestamp."""
    return timestamp.replace(minute=0, second=0, microsecond=0)


def build_occupancy_hour_of_week(sessions):
    """
    Calculate time-weighted mean occupancy for each local weekday/hour.

    Session intervals and hour bins are handled in UTC. Each UTC segment
    is classified by its midpoint in Los Angeles local time.

    Repeated local hours during the autumn DST transition contribute
    their actual elapsed exposure separately.
    """
    output_rows = []

    for site in SITES:
        subset = [
            session
            for session in sessions
            if session["site"] == site
            and session["primary_occupancy_included"]
        ]

        if not subset:
            continue

        intervals = [
            (
                datetime.fromisoformat(
                    session["connection_time_utc"]
                ),
                datetime.fromisoformat(
                    session["disconnect_time_utc"]
                ),
            )
            for session in subset
        ]

        observed_start = min(start for start, _ in intervals)
        observed_end = max(end for _, end in intervals)

        occupied_hours = defaultdict(float)
        exposure_hours = defaultdict(float)

        # Establish observed calendar exposure for each local
        # weekday/hour category.
        bucket = floor_utc_hour(observed_start)

        while bucket < observed_end:
            segment_start = max(bucket, observed_start)
            segment_end = min(
                bucket + timedelta(hours=1),
                observed_end,
            )

            if segment_start < segment_end:
                midpoint = segment_start + (
                    segment_end - segment_start
                ) / 2

                local_midpoint = midpoint.astimezone(LOCAL_TZ)
                key = (
                    local_midpoint.weekday(),
                    local_midpoint.hour,
                )

                exposure_hours[key] += (
                    segment_end - segment_start
                ).total_seconds() / 3600

            bucket += timedelta(hours=1)

        # Add session-hours to the matching local weekday/hour.
        for start, end in intervals:
            bucket = floor_utc_hour(start)

            while bucket < end:
                segment_start = max(bucket, start)
                segment_end = min(
                    bucket + timedelta(hours=1),
                    end,
                )

                if segment_start < segment_end:
                    midpoint = segment_start + (
                        segment_end - segment_start
                    ) / 2

                    local_midpoint = midpoint.astimezone(LOCAL_TZ)
                    key = (
                        local_midpoint.weekday(),
                        local_midpoint.hour,
                    )

                    occupied_hours[key] += (
                        segment_end - segment_start
                    ).total_seconds() / 3600

                bucket += timedelta(hours=1)

        for weekday in range(7):
            for hour in range(24):
                key = (weekday, hour)
                exposure = exposure_hours[key]
                occupied = occupied_hours[key]

                output_rows.append(
                    {
                        "site": site,
                        "weekday_number": weekday,
                        "local_hour": hour,
                        "hour_of_week": weekday * 24 + hour,
                        "calendar_span_hours": exposure,
                        "occupied_station_hours": occupied,
                        "mean_simultaneous_occupancy": (
                            occupied / exposure if exposure else None
                        ),
                    }
                )

    return output_rows


# ---------------------------------------------------------------------
# REGIME SUMMARY
# ---------------------------------------------------------------------

def build_regime_summary(sessions):
    rows = []

    for site in SITES:
        for regime in [
            "Pre-disruption",
            "Transition",
            "Disruption",
            "Recovery",
        ]:
            subset = [
                session
                for session in sessions
                if session["site"] == site
                and session["regime"] == regime
            ]

            if not subset:
                continue

            frame = pd.DataFrame(subset)

            rows.append(
                {
                    "site": site,
                    "regime": regime,
                    "sessions": len(frame),
                    "unique_stations": frame[
                        "station_id"
                    ].nunique(),
                    "median_connected_hours": (
                        frame["connected_hours"].median()
                    ),
                    "mean_connected_hours": (
                        frame["connected_hours"].mean()
                    ),
                    "median_arrival_hour": (
                        frame["arrival_hour"].median()
                    ),
                    "weekday_sessions": int(
                        (frame["day_type"] == "Weekday").sum()
                    ),
                    "weekend_sessions": int(
                        (frame["day_type"] == "Weekend").sum()
                    ),
                    "sessions_with_valid_charging_end": int(
                        frame["done_charging_time_valid"].sum()
                    ),
                    "sessions_with_same_station_overlap": int(
                        frame["same_station_overlap"].sum()
                    ),
                    "jpl_conflicting_sessions": int(
                        frame["jpl_conflicting_record"].sum()
                    ),
                }
            )

    return rows


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("CHARGEWISE — CONSOLIDATED EXPLORATORY DATA ANALYSIS")
    print("=" * 72)

    all_sessions = []
    raw_counts = {}

    for site_name, filename in SITES.items():
        print(f"\nLoading {site_name}...")

        records = load_sessions(filename)
        raw_counts[site_name] = len(records)

        prepared = prepare_site_sessions(site_name, records)
        all_sessions.extend(prepared)

        print(f"  Raw records: {len(records):,}")
        print(f"  Valid connection intervals: {len(prepared):,}")

    print("\nChecking same-station overlaps...")
    overlap_pairs = flag_same_station_overlaps(all_sessions)

    print(f"  Overlapping pairs detected: {len(overlap_pairs):,}")

    print("\nChecking the known JPL conflicting records...")
    conflict_records = flag_jpl_conflicts(all_sessions)

    print(f"  JPL conflicting records flagged: {len(conflict_records):,}")

    add_analysis_flags(all_sessions)

    # Session-level profile.
    write_csv(
        all_sessions,
        "eda_session_profile.csv",
    )

    # Arrival distributions.
    hourly_rows, hour_of_week_rows = build_arrival_outputs(
        all_sessions
    )

    write_csv(
        hourly_rows,
        "eda_arrivals_hourly.csv",
    )

    write_csv(
        hour_of_week_rows,
        "eda_arrivals_hour_of_week.csv",
    )

    # Duration analysis.
    write_csv(
        build_duration_outputs(all_sessions),
        "eda_duration_summary.csv",
    )

    # Weekday/weekend analysis.
    write_csv(
        build_weekday_weekend_outputs(all_sessions),
        "eda_weekday_weekend.csv",
    )

    # Time-weighted occupancy.
    write_csv(
        build_occupancy_hour_of_week(all_sessions),
        "eda_occupancy_hour_of_week.csv",
    )

    # Regime analysis.
    write_csv(
        build_regime_summary(all_sessions),
        "eda_regime_summary.csv",
    )

    print("\n" + "=" * 72)
    print("VALIDATION SUMMARY")
    print("=" * 72)

    print(f"Total raw records: {sum(raw_counts.values()):,}")
    print(f"Total valid intervals: {len(all_sessions):,}")

    for site in SITES:
        site_sessions = [
            session
            for session in all_sessions
            if session["site"] == site
        ]

        print(f"\n{site}")
        print(f"  Raw records: {raw_counts[site]:,}")
        print(f"  Valid intervals: {len(site_sessions):,}")
        print(
            "  Same-station overlap sessions: "
            f"{sum(s['same_station_overlap'] for s in site_sessions):,}"
        )
        print(
            "  Primary occupancy records: "
            f"{sum(s['primary_occupancy_included'] for s in site_sessions):,}"
        )
        print(
            "  Capacity-comparison eligible records: "
            f"{sum(s['homogeneous_capacity_comparison_included'] for s in site_sessions):,}"
        )

    print("\nEDA generation completed.")
    print(f"Output directory: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
