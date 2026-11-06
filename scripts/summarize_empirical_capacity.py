
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "capacity_pressure_weekly.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "empirical_capacity_summary.csv"


def main():
    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "site",
        "regime",
        "week_start",
        "sessions_started",
        "weekly_peak_occupancy",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["sessions_started"] = pd.to_numeric(
        df["sessions_started"], errors="raise"
    )
    df["weekly_peak_occupancy"] = pd.to_numeric(
        df["weekly_peak_occupancy"], errors="raise"
    )

    if df["weekly_peak_occupancy"].isna().any():
        raise ValueError("Weekly peak occupancy contains missing values.")

    results = []

    for (site, regime), group in df.groupby(["site", "regime"]):
        active_weeks = group[group["sessions_started"] > 0]
        peaks = active_weeks["weekly_peak_occupancy"]

        if peaks.empty:
            continue

        results.append(
            {
                "site": site,
                "regime": regime,
                "eligible_weeks": len(group),
                "weeks_with_sessions": len(active_weeks),
                "zero_session_weeks": int(
                    (group["sessions_started"] == 0).sum()
                ),
                "median_sessions_per_week": active_weeks[
                    "sessions_started"
                ].median(),
                "p50_weekly_peak": peaks.quantile(0.50),
                "p75_weekly_peak": peaks.quantile(0.75),
                "p90_weekly_peak": peaks.quantile(0.90),
                "p95_weekly_peak": peaks.quantile(0.95),
                "p99_weekly_peak": peaks.quantile(0.99),
                "maximum_weekly_peak": peaks.max(),
            }
        )

    summary = pd.DataFrame(results).sort_values(["site", "regime"])
    summary.to_csv(OUTPUT_FILE, index=False)

    print("\nEMPIRICAL WEEKLY PEAK OCCUPANCY SUMMARY")
    print("=" * 75)
    print(summary.to_string(index=False))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
