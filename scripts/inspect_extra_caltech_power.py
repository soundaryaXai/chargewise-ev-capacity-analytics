import json
import pandas as pd

FILE = "data/raw/caltech_sessions.jsonl"
TARGET = "2-39-81-4550"

records = []

with open(FILE, "r", encoding="utf-8") as f:
    for line in f:
        session = json.loads(line)

        if session.get("stationID") != TARGET:
            continue

        records.append({
            "connectionTime": session.get("connectionTime"),
            "doneChargingTime": session.get("doneChargingTime"),
            "disconnectTime": session.get("disconnectTime"),
            "kWhDelivered": session.get("kWhDelivered"),
        })

df = pd.DataFrame(records)

print("STATION CHARGING TIMESTAMP AUDIT")
print("=" * 55)
print(f"Total sessions: {len(df):,}")

for column in df.columns:
    print(f"{column} missing: {df[column].isna().sum():,}")

print("\nSAMPLE TIMESTAMPS")
print(df.head(15).to_string(index=False))

print("\nTIMESTAMP AVAILABILITY")
print(
    df[["connectionTime", "doneChargingTime", "disconnectTime"]]
    .notna()
    .all(axis=1)
    .value_counts()
)