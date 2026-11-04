
import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

SITES = {
    "Caltech": "caltech_sessions.jsonl",
    "JPL": "jpl_sessions.jsonl",
    "Office 1": "office001_sessions.jsonl",
}


def parse_timestamp(value):
    """Parse ACN timestamps consistently into UTC."""
    if value is None or value == "":
        return pd.NaT

    return pd.to_datetime(
        value,
        format="mixed",
        errors="coerce",
        utc=True,
    )


def load_sessions(filename):
    path = RAW_DIR / filename
    sessions = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                sessions.append(json.loads(line))

    return sessions


def profile_site(site_name, filename):
    sessions = load_sessions(filename)

    sessions_with_snapshots = 0
    sessions_with_latest_departure = 0

    after_connection = 0
    after_charging = 0
    after_disconnect = 0

    departure_minus_disconnect_hours = []
    snapshot_count = 0

    for session in sessions:
        snapshots = session.get("userInputs") or []

        if not isinstance(snapshots, list) or not snapshots:
            continue

        snapshots_with_dates = []

        for index, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, dict):
                continue

            snapshot_count += 1

            modified_at = parse_timestamp(
                snapshot.get("modifiedAt")
            )

            requested_departure = parse_timestamp(
                snapshot.get("requestedDeparture")
            )

            snapshots_with_dates.append(
                {
                    "index": index,
                    "modified_at": modified_at,
                    "requested_departure": requested_departure,
                }
            )

        if not snapshots_with_dates:
            continue

        sessions_with_snapshots += 1

        # Sort by modification time. Original index breaks timestamp ties.
        snapshots_with_dates.sort(
            key=lambda item: (
                pd.isna(item["modified_at"]),
                item["modified_at"]
                if not pd.isna(item["modified_at"])
                else pd.Timestamp.min.tz_localize("UTC"),
                item["index"],
            )
        )

        latest = snapshots_with_dates[-1]
        departure = latest["requested_departure"]

        if pd.isna(departure):
            continue

        sessions_with_latest_departure += 1

        connection = parse_timestamp(
            session.get("connectionTime")
        )
        charging_done = parse_timestamp(
            session.get("doneChargingTime")
        )
        disconnect = parse_timestamp(
            session.get("disconnectTime")
        )

        if not pd.isna(connection) and departure > connection:
            after_connection += 1

        if not pd.isna(charging_done) and departure > charging_done:
            after_charging += 1

        if not pd.isna(disconnect) and departure > disconnect:
            after_disconnect += 1
            departure_minus_disconnect_hours.append(
                (departure - disconnect).total_seconds() / 3600
            )

    print("\n" + "=" * 60)
    print(f"{site_name.upper()} — SESSION-LEVEL DEPARTURE PROFILE")
    print("=" * 60)

    print(f"Total sessions: {len(sessions):,}")
    print(f"Sessions with user-input snapshots: {sessions_with_snapshots:,}")
    print(f"Total snapshots inspected: {snapshot_count:,}")

    coverage = (
        sessions_with_latest_departure / len(sessions) * 100
        if sessions
        else 0
    )

    print(
        "Sessions with valid latest requested departure: "
        f"{sessions_with_latest_departure:,} ({coverage:.2f}%)"
    )

    print("\nLatest requested departure timing:")
    print(
        f"  Later than connection time: "
        f"{after_connection:,}"
    )
    print(
        f"  Later than done-charging time: "
        f"{after_charging:,}"
    )
    print(
        f"  Later than disconnect time: "
        f"{after_disconnect:,}"
    )

    if departure_minus_disconnect_hours:
        series = pd.Series(departure_minus_disconnect_hours)

        print("\nFor sessions with requested departure after disconnect:")
        print(
            f"  Median requested-departure minus disconnect: "
            f"{series.median():.2f} hours"
        )
        print(
            f"  25th percentile: {series.quantile(0.25):.2f} hours"
        )
        print(
            f"  75th percentile: {series.quantile(0.75):.2f} hours"
        )


def main():
    for site_name, filename in SITES.items():
        profile_site(site_name, filename)


if __name__ == "__main__":
    main()
