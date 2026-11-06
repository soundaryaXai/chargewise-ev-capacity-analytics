from pathlib import Path
from collections import defaultdict

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "raw" / "jpl_sessions.jsonl"

TIMEZONE = "America/Los_Angeles"

df = pd.read_json(DATA_FILE, lines=True)

df["connectionTime"] = (
    pd.to_datetime(df["connectionTime"], utc=True)
    .dt.tz_convert(TIMEZONE)
)

df["disconnectTime"] = (
    pd.to_datetime(df["disconnectTime"], utc=True)
    .dt.tz_convert(TIMEZONE)
)

# Exclude the two conflicting records identified earlier.
conflict = (
    (df["stationID"].astype(str) == "1-1-179-794")
    & (
        df["connectionTime"].dt.tz_localize(None)
        == pd.Timestamp("2021-07-19 13:11:16")
    )
)

df = df.loc[~conflict].copy()

# Restrict to pre-disruption.
df = df[
    (df["connectionTime"].dt.year < 2020)
    | (
        (df["connectionTime"].dt.year == 2020)
        & (df["connectionTime"].dt.month <= 2)
    )
].copy()

# Build start and end events.
events = defaultdict(lambda: {"start": [], "end": []})

for row in df.itertuples(index=False):
    station = str(row.stationID)

    events[row.connectionTime]["start"].append(station)
    events[row.disconnectTime]["end"].append(station)

active = set()
maximum = 0
peak_records = []

for timestamp in sorted(events):

    # Half-open occupancy interval: [connection, disconnect).
    for station in events[timestamp]["end"]:
        active.discard(station)

    for station in events[timestamp]["start"]:
        active.add(station)

    if len(active) > maximum:
        maximum = len(active)
        peak_records = []

    if len(active) == maximum:
        peak_records.append(
            (timestamp, sorted(active))
        )

print("=" * 75)
print("JPL PRE-DISRUPTION PEAK OCCUPANCY")
print("=" * 75)

print(f"\nMaximum simultaneous occupied stations: {maximum}")
print(f"Number of timestamps at maximum: {len(peak_records)}")

for timestamp, stations in peak_records[:10]:
    print(f"\nTimestamp: {timestamp}")
    print(f"Occupied stations: {len(stations)}")

    for station in stations:
        print(" ", station)

print("\nUnique stations in source data:", df["stationID"].nunique())