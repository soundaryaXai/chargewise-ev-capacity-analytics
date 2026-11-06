
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

SESSION_FILE = BASE_DIR / "data" / "processed" / "eda_session_profile.csv"
WEEKLY_FILE = BASE_DIR / "data" / "processed" / "capacity_pressure_weekly.csv"

OUTPUT_FILE = BASE_DIR / "data" / "processed" / "erlang_b_summary.csv"

CAPACITIES = {
    "Caltech": [54],
    "JPL": [50, 52],
    "Office 1": [8],
}


def erlang_b(servers, traffic):
    blocking = 1.0

    for c in range(1, servers + 1):
        blocking = traffic * blocking / (c + traffic * blocking)

    return blocking


def main():
    sessions = pd.read_csv(SESSION_FILE, low_memory=False)
    weekly = pd.read_csv(WEEKLY_FILE, low_memory=False)

    required = {
        "site",
        "regime",
        "connected_hours",
        "homogeneous_capacity_comparison_included",
    }

    missing = required - set(sessions.columns)

    if missing:
        raise ValueError(f"Missing session columns: {sorted(missing)}")

    sessions["homogeneous_capacity_comparison_included"] = (
        sessions["homogeneous_capacity_comparison_included"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )

    if sessions["homogeneous_capacity_comparison_included"].isna().any():
        raise ValueError("Invalid capacity-comparison inclusion flags.")

    sessions["connected_hours"] = pd.to_numeric(
        sessions["connected_hours"], errors="coerce"
    )

    sessions = sessions[
        sessions["homogeneous_capacity_comparison_included"]
        & sessions["connected_hours"].gt(0)
        & sessions["connected_hours"].notna()
    ].copy()

    weekly["week_start"] = pd.to_datetime(
        weekly["week_start"], errors="raise"
    )

    week_counts = (
        weekly.groupby(["site", "regime"])["week_start"]
        .nunique()
        .rename("eligible_weeks")
        .reset_index()
    )

    duration = (
        sessions.groupby(["site", "regime"])
        .agg(
            observed_arrivals=("connected_hours", "size"),
            mean_connected_hours=("connected_hours", "mean"),
            median_connected_hours=("connected_hours", "median"),
        )
        .reset_index()
    )

    results = duration.merge(
        week_counts,
        on=["site", "regime"],
        how="inner",
        validate="one_to_one",
    )

    results["calendar_exposure_hours"] = (
        results["eligible_weeks"] * 168
    )

    results["lambda_per_hour"] = (
        results["observed_arrivals"]
        / results["calendar_exposure_hours"]
    )

    results["offered_traffic_erlangs"] = (
        results["lambda_per_hour"]
        * results["mean_connected_hours"]
    )

    rows = []

    for _, record in results.iterrows():
        site = record["site"]

        for capacity in CAPACITIES.get(site, []):
            rows.append(
                {
                    "site": site,
                    "regime": record["regime"],
                    "capacity_assumption": capacity,
                    "eligible_weeks": int(record["eligible_weeks"]),
                    "observed_arrivals": int(record["observed_arrivals"]),
                    "calendar_exposure_hours": record[
                        "calendar_exposure_hours"
                    ],
                    "lambda_per_hour": record["lambda_per_hour"],
                    "mean_connected_hours": record[
                        "mean_connected_hours"
                    ],
                    "offered_traffic_erlangs": record[
                        "offered_traffic_erlangs"
                    ],
                    "erlang_b_blocking_probability": erlang_b(
                        capacity,
                        record["offered_traffic_erlangs"],
                    ),
                    "primary_regime": record["regime"] in {
                        "Pre-disruption",
                        "Recovery",
                    },
                }
            )

    summary = pd.DataFrame(rows)

    if summary.empty:
        raise ValueError("No Erlang-B results generated.")

    summary.to_csv(OUTPUT_FILE, index=False)

    print("\nAGGREGATE ERLANG-B BASELINE")
    print("=" * 90)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
