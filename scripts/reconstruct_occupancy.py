
import json
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

SITES = {
    "Caltech": "caltech_sessions.jsonl",
    "JPL": "jpl_sessions.jsonl",
    "Office 1": "office001_sessions.jsonl",
}

# Screening window for workplace business-hour occupancy.
# This is an analysis definition, not a claim about official operating hours.
BUSINESS_START = time(7, 0)
BUSINESS_END = time(19, 0)


def load_sessions(filename):
    records = []

    with (RAW_DIR / filename).open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))

    return records


def parse_time(value):
    if not value:
        return None

    timestamp = pd.to_datetime(
        value,
        format="mixed",
        errors="coerce",
        utc=True,
    )

    if pd.isna(timestamp):
        return None

    return timestamp.to_pydatetime().astimezone(LOCAL_TZ)


def prepare_sessions(records):
    prepared = []

    for index, record in enumerate(records):
        start = parse_time(record.get("connectionTime"))
        end = parse_time(record.get("disconnectTime"))

        if start is None or end is None or end <= start:
            continue

        prepared.append(
            {
                "index": index,
                "session_id": record.get("sessionID"),
                "station_id": record.get("stationID"),
                "space_id": record.get("spaceID"),
                "start": start,
                "end": end,
            }
        )

    return prepared


def find_same_station_overlaps(sessions):
    """Return indices of all sessions involved in same-station overlaps."""
    by_station = defaultdict(list)

    for session in sessions:
        station = session["station_id"]
        if station:
            by_station[station].append(session)

    conflicted_indices = set()
    overlap_details = []

    for station, station_sessions in by_station.items():
        station_sessions.sort(key=lambda item: item["start"])
        active = []

        for current in station_sessions:
            active = [
                item for item in active
                if item["end"] > current["start"]
            ]

            for previous in active:
                conflicted_indices.add(previous["index"])
                conflicted_indices.add(current["index"])

                overlap_details.append(
                    {
                        "station": station,
                        "previous": previous,
                        "current": current,
                    }
                )

            active.append(current)

    return conflicted_indices, overlap_details


def weighted_quantile(values, quantile):
    """Quantile of occupancy weighted by the duration of each interval."""
    total_duration = sum(duration for _, duration in values)

    if total_duration <= 0:
        return 0

    target = total_duration * quantile
    cumulative = 0

    for occupancy, duration in sorted(values):
        cumulative += duration
        if cumulative >= target:
            return occupancy

    return max(occupancy for occupancy, _ in values)


def occupancy_profile(sessions):
    """Calculate time-weighted occupancy from connection to disconnect."""
    events = defaultdict(int)

    for session in sessions:
        events[session["start"]] += 1
        events[session["end"]] -= 1

    timestamps = sorted(events)
    occupancy = 0
    segments = []
    peak = 0

    for position, timestamp in enumerate(timestamps):
        occupancy += events[timestamp]
        peak = max(peak, occupancy)

        if position + 1 >= len(timestamps):
            continue

        next_timestamp = timestamps[position + 1]
        duration_hours = (
            next_timestamp - timestamp
        ).total_seconds() / 3600

        if duration_hours > 0:
            segments.append((occupancy, duration_hours))

    total_hours = sum(duration for _, duration in segments)

    if total_hours:
        mean_occupancy = sum(
            occupancy * duration
            for occupancy, duration in segments
        ) / total_hours
    else:
        mean_occupancy = 0

    return {
        "mean": mean_occupancy,
        "p95": weighted_quantile(segments, 0.95),
        "p99": weighted_quantile(segments, 0.99),
        "peak": peak,
        "observed_hours": total_hours,
    }


def weekly_business_hour_peaks(sessions):
    """Maximum simultaneous occupancy during weekday 07:00–19:00."""
    weekly_events = defaultdict(lambda: defaultdict(int))

    for session in sessions:
        start = session["start"]
        end = session["end"]

        current_date = start.date()
        final_date = end.date()

        while current_date <= final_date:
            if current_date.weekday() < 5:
                window_start = datetime.combine(
                    current_date,
                    BUSINESS_START,
                    tzinfo=LOCAL_TZ,
                )
                window_end = datetime.combine(
                    current_date,
                    BUSINESS_END,
                    tzinfo=LOCAL_TZ,
                )

                clipped_start = max(start, window_start)
                clipped_end = min(end, window_end)

                if clipped_start < clipped_end:
                    iso = current_date.isocalendar()
                    week_key = f"{iso.year}-W{iso.week:02d}"

                    weekly_events[week_key][clipped_start] += 1
                    weekly_events[week_key][clipped_end] -= 1

            current_date += timedelta(days=1)

    weekly_peaks = {}

    for week_key, events in weekly_events.items():
        occupancy = 0
        peak = 0

        for timestamp in sorted(events):
            occupancy += events[timestamp]
            peak = max(peak, occupancy)

        weekly_peaks[week_key] = peak

    return weekly_peaks


def print_site_report(site_name, records):
    sessions = prepare_sessions(records)

    conflicted_indices, overlaps = find_same_station_overlaps(
        sessions
    )

    primary_sessions = [
        session for session in sessions
        if session["index"] not in conflicted_indices
    ]

    station_ids = sorted(
        {
            session["station_id"]
            for session in sessions
            if session["station_id"]
        }
    )

    space_ids = sorted(
        {
            session["space_id"]
            for session in sessions
            if session["space_id"]
        }
    )

    profile = occupancy_profile(primary_sessions)
    weekly_peaks = weekly_business_hour_peaks(primary_sessions)

    print("\n" + "=" * 68)
    print(f"{site_name.upper()} — OCCUPANCY RECONSTRUCTION")
    print("=" * 68)

    print(f"Raw session records: {len(records):,}")
    print(f"Valid connection/disconnection intervals: {len(sessions):,}")
    print(f"Unique station IDs: {len(station_ids):,}")
    print(f"Unique space IDs: {len(space_ids):,}")
    print(f"Same-station overlapping pairs: {len(overlaps):,}")
    print(f"Sessions involved in overlaps: {len(conflicted_indices):,}")
    print(f"Sessions retained for primary profile: {len(primary_sessions):,}")

    if sessions:
        starts = [item["start"] for item in sessions]
        ends = [item["end"] for item in sessions]

        print(
            "Local date range: "
            f"{min(starts).isoformat()} to {max(ends).isoformat()}"
        )

    print("\nPrimary occupancy profile (overlap records excluded):")
    print(f"  Time-weighted mean occupancy: {profile['mean']:.2f}")
    print(f"  Time-weighted p95 occupancy: {profile['p95']}")
    print(f"  Time-weighted p99 occupancy: {profile['p99']}")
    print(f"  Maximum simultaneous occupancy: {profile['peak']}")
    print(f"  Observed occupancy hours: {profile['observed_hours']:,.1f}")

    print("\nWeekday business-hour peaks (07:00–19:00 local):")
    print(f"  Weeks with observed sessions: {len(weekly_peaks):,}")

    if weekly_peaks:
        peak_values = list(weekly_peaks.values())

        print(f"  Mean weekly peak: {sum(peak_values) / len(peak_values):.2f}")
        print(f"  Median weekly peak: {pd.Series(peak_values).median():.1f}")
        print(f"  Highest weekly peak: {max(peak_values)}")

        print("\n  Ten highest weekly peaks:")
        for week, peak in sorted(
            weekly_peaks.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]:
            print(f"    {week}: {peak}")

    if overlaps:
        print("\nSame-station overlap details:")
        for pair in overlaps:
            previous = pair["previous"]
            current = pair["current"]

            overlap_start = max(
                previous["start"],
                current["start"],
            )
            overlap_end = min(
                previous["end"],
                current["end"],
            )

            print(f"  Station: {pair['station']}")
            print(f"    Session A: {previous['session_id']}")
            print(f"    Session B: {current['session_id']}")
            print(f"    Overlap: {overlap_start} to {overlap_end}")

    print("\nStation IDs (inventory candidates, not verified capacity):")
    for station in station_ids:
        print(f"  {station}")


def main():
    for site_name, filename in SITES.items():
        records = load_sessions(filename)
        print_site_report(site_name, records)


if __name__ == "__main__":
    main()
