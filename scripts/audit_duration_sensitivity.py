
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "eda_session_profile.csv"
OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "duration_sensitivity_summary.csv"
)

THRESHOLDS = {
    "No exclusion": None,
    "24 hours": 24,
    "48 hours": 48,
    "72 hours": 72,
}

CALTECH_UNCLASSIFIED_STATION = "2-39-81-4550"
JPL_CONFLICT_STATION = "1-1-179-794"
JPL_CONFLICT_CONNECTION_UTC = "2021-07-19T20:11:16+00:00"


def classify_regime(connection_time):
    if connection_time < pd.Timestamp("2020-03-01", tz="UTC"):
        return "Pre-disruption"
    if connection_time < pd.Timestamp("2020-04-01", tz="UTC"):
        return "Transition"
    if connection_time < pd.Timestamp("2020-11-01", tz="UTC"):
        return "Disruption"
    if connection_time < pd.Timestamp("2021-10-01", tz="UTC"):
        return "Recovery"
    return "Outside study regimes"


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, low_memory=False)
    raw_record_count = len(df)

    required_columns = [
        "site",
        "session_id",
        "station_id",
        "connection_time_utc",
        "connected_hours",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["connection_time_utc"] = pd.to_datetime(
        df["connection_time_utc"],
        utc=True,
        errors="coerce",
    )

    df["connected_hours"] = pd.to_numeric(
        df["connected_hours"],
        errors="coerce",
    )

    # Retain only valid connected intervals.
    df = df[
        df["connection_time_utc"].notna()
        & df["connected_hours"].notna()
        & (df["connected_hours"] > 0)
    ].copy()

    # Recalculate regimes from connection timestamps.
    df["regime"] = df["connection_time_utc"].apply(classify_regime)

    # Exclude the unclassified Caltech station from homogeneous
    # capacity-comparison analysis.
    caltech_extra = (
        (df["site"] == "Caltech")
        & (df["station_id"] == CALTECH_UNCLASSIFIED_STATION)
    )

    # Exclude the two known conflicting JPL records.
    jpl_conflict = (
        (df["site"] == "JPL")
        & (df["station_id"] == JPL_CONFLICT_STATION)
        & (
            df["connection_time_utc"]
            == pd.Timestamp(JPL_CONFLICT_CONNECTION_UTC)
        )
    )

    print("EXCLUSION AUDIT")
    print("----------------")
    print(
    "Invalid/missing connected intervals excluded before analysis: "
    f"{raw_record_count - len(df)}")
    print(f"Caltech unclassified station records excluded: {caltech_extra.sum()}")
    print(f"JPL conflicting records excluded: {jpl_conflict.sum()}")

    if jpl_conflict.sum() != 2:
        raise ValueError(
            "Expected exactly two known JPL conflicting records; "
            f"found {jpl_conflict.sum()}."
        )

    df = df[~(caltech_extra | jpl_conflict)].copy()

    results = []

    for site in ["Caltech", "JPL", "Office 1"]:
        site_df = df[df["site"] == site]

        for regime in [
            "Pre-disruption",
            "Transition",
            "Disruption",
            "Recovery",
        ]:
            group = site_df[site_df["regime"] == regime]

            if group.empty:
                continue

            for scenario, threshold in THRESHOLDS.items():
                if threshold is None:
                    retained = group.copy()
                else:
                    retained = group[
                        group["connected_hours"] <= threshold
                    ].copy()

                excluded = group[
                    group["connected_hours"] > threshold
                ] if threshold is not None else group.iloc[0:0]

                durations = retained["connected_hours"]

                results.append({
                    "site": site,
                    "regime": regime,
                    "scenario": scenario,
                    "threshold_hours": threshold,
                    "original_sessions": len(group),
                    "retained_sessions": len(retained),
                    "excluded_sessions": len(excluded),
                    "excluded_session_pct": (
                        100 * len(excluded) / len(group)
                    ),
                    "original_connected_hours": group[
                        "connected_hours"
                    ].sum(),
                    "retained_connected_hours": durations.sum(),
                    "excluded_connected_hours": excluded[
                        "connected_hours"
                    ].sum(),
                    "mean_connected_hours": durations.mean(),
                    "median_connected_hours": durations.median(),
                    "p95_connected_hours": durations.quantile(0.95),
                    "p99_connected_hours": durations.quantile(0.99),
                })

    output = pd.DataFrame(results)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_FILE, index=False)

    print("\nDURATION SENSITIVITY AUDIT")
    print("-------------------------")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Summary rows: {len(output)}")
    print("\nOverall retained session counts by scenario:")

    overall = (
        output.groupby("scenario", sort=False)
        [["original_sessions", "retained_sessions", "excluded_sessions"]]
        .sum()
    )
    print(overall.to_string())

    print("\nAudit completed successfully.")


if __name__ == "__main__":
    main()
