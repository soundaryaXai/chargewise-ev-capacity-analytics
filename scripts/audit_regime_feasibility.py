
import json
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "Caltech": ROOT / "data" / "raw" / "caltech_sessions.jsonl",
    "JPL": ROOT / "data" / "raw" / "jpl_sessions.jsonl",
    "Office 1": ROOT / "data" / "raw" / "office001_sessions.jsonl",
}

TIMEZONE = "America/Los_Angeles"

REGIMES = {
    "Pre-disruption": ("2018-01-01", "2020-02-29"),
    "Transition": ("2020-03-01", "2020-03-31"),
    "Disruption": ("2020-04-01", "2020-10-31"),
    "Recovery": ("2020-11-01", "2021-09-30"),
}

# Known conflicting JPL records.
# These are retained in this raw feasibility audit.
# They are excluded from the primary capacity replay.
JPL_CONFLICT_STATION = "1-1-179-794"
JPL_CONFLICT_CONNECTION = pd.Timestamp(
    "2021-07-19 13:11:16"
)
EXPECTED_JPL_CONFLICT_COUNT = 2


# ---------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------

def load_raw_sessions(filepath):
    """Load raw session records and parse connection timestamps."""

    if not filepath.exists():
        raise FileNotFoundError(
            f"Session file not found: {filepath}"
        )

    records = []

    invalid_timestamp_count = 0

    with open(filepath, "r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            try:
                session = json.loads(line)

            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {filepath.name}, "
                    f"line {line_number}: {exc}"
                ) from exc

            timestamp = pd.to_datetime(
                session.get("connectionTime"),
                errors="coerce",
                utc=True,
            )

            if pd.isna(timestamp):
                invalid_timestamp_count += 1
                continue

            local_timestamp = (
                timestamp
                .tz_convert(TIMEZONE)
                .tz_localize(None)
            )

            records.append({
                "stationID": session.get("stationID"),
                "connection": local_timestamp,
            })

    df = pd.DataFrame(
        records,
        columns=["stationID", "connection"],
    )

    df = df.dropna(
        subset=["stationID", "connection"]
    ).copy()

    print(
        f"Raw records with valid connection timestamps: "
        f"{len(df):,}"
    )

    print(
        f"Records skipped for invalid connection timestamps: "
        f"{invalid_timestamp_count:,}"
    )

    return df


# ---------------------------------------------------------
# REGIME FEASIBILITY AUDIT
# ---------------------------------------------------------

def audit_site(site, filepath):

    print("\n" + "=" * 90)
    print(site.upper())
    print("=" * 90)

    df = load_raw_sessions(filepath)

    if df.empty:
        print("No valid session records found.")
        return

    observed_start = df["connection"].min()
    observed_end = df["connection"].max()

    print(f"Observed start: {observed_start}")
    print(f"Observed end:   {observed_end}")

    # Identify the known JPL conflict pair.
    # Do not remove these records from this raw feasibility audit.
    if site == "JPL":

        conflict_mask = (
            (
                df["stationID"].astype(str)
                == JPL_CONFLICT_STATION
            )
            &
            (
                df["connection"]
                == JPL_CONFLICT_CONNECTION
            )
        )

        conflict_count = int(conflict_mask.sum())

        print(
            "\nKnown conflicting JPL records present "
            f"in raw feasibility counts: {conflict_count}"
        )

        if conflict_count != EXPECTED_JPL_CONFLICT_COUNT:
            raise ValueError(
                "Expected exactly "
                f"{EXPECTED_JPL_CONFLICT_COUNT} known conflicting "
                f"JPL records, but found {conflict_count}. "
                "Investigate the raw data."
            )

        print(
            "Note: both records are retained in the raw "
            "feasibility counts. They are excluded from the "
            "primary capacity replay."
        )

    print("-" * 90)

    # -----------------------------------------------------
    # REGIME ANALYSIS
    # -----------------------------------------------------

    for regime, (start, end) in REGIMES.items():

        start = pd.Timestamp(start)

        # Use an exclusive upper boundary so the complete
        # final calendar day is included.
        end_exclusive = (
            pd.Timestamp(end)
            + pd.Timedelta(days=1)
        )

        subset = df[
            (df["connection"] >= start)
            &
            (df["connection"] < end_exclusive)
        ].copy()

        if subset.empty:
            print(f"\n{regime}: no sessions")
            continue

        subset["week"] = (
            subset["connection"]
            .dt.to_period("W-SUN")
        )

        # -------------------------------------------------
        # ELIGIBLE FULL CALENDAR WEEKS
        # -------------------------------------------------

        first_week = max(
            start.to_period("W-SUN"),
            observed_start.to_period("W-SUN"),
        )

        last_week = min(
            (
                end_exclusive
                - pd.Timedelta(nanoseconds=1)
            ).to_period("W-SUN"),
            observed_end.to_period("W-SUN"),
        )

        candidate_weeks = pd.period_range(
            first_week,
            last_week,
            freq="W-SUN",
        )

        # Retain weeks fully contained in:
        # 1. The selected regime.
        # 2. The site's observed connection-time envelope.
        eligible_weeks = [
            week
            for week in candidate_weeks
            if (
                week.start_time >= start
                and week.end_time < end_exclusive
                and week.start_time >= observed_start
                and week.end_time <= observed_end
            )
        ]

        weekly_counts = (
            subset.groupby("week")
            .size()
        )

        weeks_with_sessions = sum(
            week in weekly_counts.index
            for week in eligible_weeks
        )

        zero_session_weeks = (
            len(eligible_weeks)
            - weeks_with_sessions
        )

        # -------------------------------------------------
        # OUTPUT
        # -------------------------------------------------

        print(f"\n{regime}")

        print(
            f"  Raw session records: "
            f"{len(subset):,}"
        )

        print(
            f"  Active station IDs: "
            f"{subset['stationID'].nunique():,}"
        )

        print(
            f"  Weeks with sessions (all): "
            f"{subset['week'].nunique():,}"
        )

        print(
            f"  Full calendar weeks in observed envelope: "
            f"{len(eligible_weeks):,}"
        )

        print(
            f"  Eligible weeks with sessions: "
            f"{weeks_with_sessions:,}"
        )

        print(
            f"  Eligible weeks with zero sessions: "
            f"{zero_session_weeks:,}"
        )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    for site, filepath in FILES.items():

        audit_site(
            site,
            filepath,
        )

    print("\n" + "=" * 90)
    print("FEASIBILITY AUDIT NOTES")
    print("=" * 90)

    print(
        "Session counts are raw record counts. "
        "They are not cleaned primary replay counts."
    )

    print(
        "The two known conflicting JPL records remain "
        "included in this raw feasibility audit. "
        "They are excluded from the primary capacity replay."
    )

    print(
        "A full calendar week inside the observed date "
        "envelope does not prove complete data collection."
    )

    print(
        "Zero-session weeks require separate interpretation. "
        "They may reflect low demand, restricted site access, "
        "or incomplete data collection."
    )

    print(
        "Recovery ends on 2021-09-30 to match the "
        "capacity-pressure audit."
    )


if __name__ == "__main__":
    main()
