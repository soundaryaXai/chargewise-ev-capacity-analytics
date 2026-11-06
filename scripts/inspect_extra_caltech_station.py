import json
from pathlib import Path

import pandas as pd


DATA_FILE = Path("data/raw/caltech_sessions.jsonl")
TARGET_STATION = "2-39-81-4550"


def main():
    records = []

    with DATA_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)

            if str(record.get("stationID")) != TARGET_STATION:
                continue

            connection = pd.to_datetime(
                record.get("connectionTime"),
                utc=True,
                errors="coerce",
            )

            disconnect = pd.to_datetime(
                record.get("disconnectTime"),
                utc=True,
                errors="coerce",
            )

            done_charging = pd.to_datetime(
                record.get("doneChargingTime"),
                utc=True,
                errors="coerce",
            )

            connected_hours = (
                (disconnect - connection).total_seconds() / 3600
                if pd.notna(connection) and pd.notna(disconnect)
                else None
            )

            charging_hours = (
                (done_charging - connection).total_seconds() / 3600
                if pd.notna(connection) and pd.notna(done_charging)
                else None
            )

            dwell_hours = (
                (disconnect - done_charging).total_seconds() / 3600
                if pd.notna(disconnect) and pd.notna(done_charging)
                else None
            )

            records.append({
                "cluster_id": record.get("clusterID"),
                "space_id": record.get("spaceID"),
                "connection": connection,
                "disconnect": disconnect,
                "connected_hours": connected_hours,
                "charging_hours": charging_hours,
                "post_charge_dwell_hours": dwell_hours,
                "kwh_delivered": record.get("kWhDelivered"),
            })

    if not records:
        print("No sessions found for the target station.")
        return

    df = pd.DataFrame(records)

    print("\nADDITIONAL CALTECH STATION")
    print("=" * 55)
    print("Station ID:", TARGET_STATION)
    print("Sessions:", len(df))
    print("Original cluster IDs:", df["cluster_id"].value_counts().to_dict())
    print("Unique parking spaces:", df["space_id"].nunique())

    print("\nSESSION DATE RANGE")
    print("First connection:", df["connection"].min())
    print("Last connection:", df["connection"].max())

    print("\nSESSION CHARACTERISTICS")
    print(
        df[
            [
                "connected_hours",
                "charging_hours",
                "post_charge_dwell_hours",
                "kwh_delivered",
            ]
        ].describe(percentiles=[0.25, 0.5, 0.75, 0.95]).round(2)
    )

    print("\nPARKING SPACES")
    print(df["space_id"].value_counts().to_string())

    print("\nFIRST 10 SESSIONS")
    print(
        df.sort_values("connection")[
            [
                "connection",
                "disconnect",
                "connected_hours",
                "kwh_delivered",
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()