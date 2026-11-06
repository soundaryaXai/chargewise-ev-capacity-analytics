import json
import pandas as pd

FILE = "data/raw/jpl_sessions.jsonl"

records = []

with open(FILE, "r", encoding="utf-8") as f:
    for line in f:
        session = json.loads(line)

        records.append({
            "stationID": session.get("stationID"),
            "connectionTime": session.get("connectionTime"),
        })

df = pd.DataFrame(records)

df["connectionTime"] = pd.to_datetime(
    df["connectionTime"], errors="coerce", utc=True
)

df = df.dropna(subset=["stationID", "connectionTime"])

df["month"] = (
    df["connectionTime"]
    .dt.tz_convert("America/Los_Angeles")
    .dt.to_period("M")
)

monthly = (
    df.groupby("month")
    .agg(
        sessions=("stationID", "size"),
        active_stations=("stationID", "nunique"),
    )
)

print("=" * 65)
print("JPL MONTHLY STATION ACTIVITY")
print("=" * 65)

print(monthly.to_string())

print("\nSUMMARY")
print("-" * 65)
print(f"Months observed: {len(monthly)}")
print(f"Minimum active stations in a month: {monthly['active_stations'].min()}")
print(f"Maximum active stations in a month: {monthly['active_stations'].max()}")
print(f"Months with all 52 stations recording sessions: "
      f"{(monthly['active_stations'] == 52).sum()}")

print("\nMONTHS WITH FEWER THAN 50 ACTIVE STATIONS")
print("-" * 65)
print(monthly[monthly["active_stations"] < 50].to_string())