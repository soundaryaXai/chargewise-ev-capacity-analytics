import json
from pathlib import Path

import pandas as pd

FILES = {
    "Caltech": "data/raw/caltech_sessions.jsonl",
    "JPL": "data/raw/jpl_sessions.jsonl",
    "Office 1": "data/raw/office001_sessions.jsonl",
}

all_data = []

for site, filepath in FILES.items():
    records = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            session = json.loads(line)

            records.append({
                "site": site,
                "stationID": session.get("stationID"),
                "connectionTime": session.get("connectionTime"),
            })

    site_df = pd.DataFrame(records)

    site_df["connectionTime"] = pd.to_datetime(
        site_df["connectionTime"],
        errors="coerce",
        utc=True,
    )

    site_df = site_df.dropna(subset=["connectionTime", "stationID"])

    site_df["month"] = (
        site_df["connectionTime"]
        .dt.tz_convert("America/Los_Angeles")
        .dt.to_period("M")
    )

    all_data.append(site_df)

df = pd.concat(all_data, ignore_index=True)

monthly = (
    df.groupby(["site", "month"])
    .agg(
        sessions=("stationID", "size"),
        active_stations=("stationID", "nunique"),
    )
    .reset_index()
)

print("=" * 75)
print("MONTHLY ACTIVITY AND POTENTIAL OPERATING REGIMES")
print("=" * 75)

for site in FILES:
    site_monthly = (
        monthly[monthly["site"] == site]
        .set_index("month")
        .drop(columns="site")
    )

    full_months = pd.period_range(
        site_monthly.index.min(),
        site_monthly.index.max(),
        freq="M",
    )

    site_monthly = site_monthly.reindex(full_months, fill_value=0)

    print(f"\n{site.upper()}")
    print("-" * 75)
    print(site_monthly.to_string())

    print("\nSummary:")
    print(f"Months in date range: {len(site_monthly)}")
    print(f"Months with zero sessions: {(site_monthly['sessions'] == 0).sum()}")
    print(f"Highest monthly sessions: {site_monthly['sessions'].max():,}")
    print(f"Lowest non-zero monthly sessions: "
          f"{site_monthly.loc[site_monthly['sessions'] > 0, 'sessions'].min():,}")