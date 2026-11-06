import json
import pandas as pd

FILE = "data/raw/jpl_sessions.jsonl"

records = []

with open(FILE, "r", encoding="utf-8") as f:
    for line in f:
        session = json.loads(line)

        records.append({
            "stationID": session.get("stationID"),
            "clusterID": str(session.get("clusterID")),
            "spaceID": session.get("spaceID"),
            "connectionTime": session.get("connectionTime"),
            "disconnectTime": session.get("disconnectTime"),
        })

df = pd.DataFrame(records)

df["connectionTime"] = pd.to_datetime(
    df["connectionTime"], errors="coerce", utc=True
)

df["disconnectTime"] = pd.to_datetime(
    df["disconnectTime"], errors="coerce", utc=True
)

print("=" * 75)
print("JPL STATION INVENTORY — ACTIVITY TIMELINE")
print("=" * 75)

print(f"Total sessions: {len(df):,}")
print(f"Unique station IDs: {df['stationID'].nunique()}")
print(f"Unique parking spaces: {df['spaceID'].nunique()}")
print(f"Unique cluster IDs: {df['clusterID'].nunique()}")

summary = (
    df.groupby("stationID", dropna=False)
    .agg(
        sessions=("stationID", "size"),
        first_connection=("connectionTime", "min"),
        last_connection=("connectionTime", "max"),
        unique_spaces=("spaceID", "nunique"),
        clusters=("clusterID", "nunique"),
    )
    .reset_index()
    .sort_values("first_connection")
)

print("\nSTATION-BY-STATION TIMELINE")
print("-" * 75)

for _, row in summary.iterrows():
    print(
        f"{row['stationID']} | "
        f"sessions={row['sessions']:>5} | "
        f"spaces={row['unique_spaces']:>2} | "
        f"clusters={row['clusters']} | "
        f"first={row['first_connection']} | "
        f"last={row['last_connection']}"
    )

print("\nSTATION ACTIVITY BY YEAR")
print("-" * 75)

df["year"] = df["connectionTime"].dt.year

yearly = (
    df.groupby("year")
    .agg(
        sessions=("stationID", "size"),
        active_stations=("stationID", "nunique"),
    )
)

print(yearly.to_string())

print("\nSTATIONS WITH FEWER THAN 20 SESSIONS")
print("-" * 75)

print(
    summary.loc[
        summary["sessions"] < 20,
        ["stationID", "sessions", "first_connection", "last_connection"]
    ].to_string(index=False)
)