
import json
from collections import Counter
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

SITES = {
    "caltech": "Caltech",
    "jpl": "JPL",
    "office001": "Office 1",
}


def load_sessions(site_id):
    file_path = RAW_DIR / f"{site_id}_sessions.jsonl"

    if not file_path.exists():
        raise FileNotFoundError(f"Missing file: {file_path}")

    df = pd.read_json(file_path, lines=True)

    # Convert timestamps to a consistent timezone for comparison.
    timestamp_columns = [
        "connectionTime",
        "disconnectTime",
        "doneChargingTime",
    ]

    for column in timestamp_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
                utc=True,
            )
        else:
            df[column] = pd.NaT

    return df


def get_nested_keys(value):
    """Collect keys from nested dictionaries and lists."""
    keys = set()

    if isinstance(value, dict):
        for key, nested_value in value.items():
            keys.add(str(key))
            keys.update(get_nested_keys(nested_value))

    elif isinstance(value, list):
        for item in value:
            keys.update(get_nested_keys(item))

    return keys


def audit_site(site_id, site_name):
    print(f"\nAuditing {site_name}...")

    df = load_sessions(site_id)
    total = len(df)

    connection = df["connectionTime"]
    disconnect = df["disconnectTime"]
    done_charging = df["doneChargingTime"]

    valid_connection = connection.notna()
    valid_disconnect = disconnect.notna()
    valid_station = (
        df["stationID"].notna()
        & df["stationID"].astype(str).str.strip().ne("")
    )

    valid_order = (
        valid_connection
        & valid_disconnect
        & (disconnect > connection)
    )

    usable = valid_order & valid_station

    # Duplicate identifiers.
    duplicate_session_ids = (
        int(df["sessionID"].duplicated(keep=False).sum())
        if "sessionID" in df.columns
        else 0
    )

    duplicate_record_ids = (
        int(df["_id"].duplicated(keep=False).sum())
        if "_id" in df.columns
        else 0
    )

    # Connected duration.
    connected_hours = (
        (disconnect - connection).dt.total_seconds() / 3600
    )

    # Charging-time consistency.
    done_charging_present = done_charging.notna()

    charging_within_connection = (
        done_charging_present
        & valid_order
        & (done_charging >= connection)
        & (done_charging <= disconnect)
    )

    post_charge_dwell_minutes = (
        (disconnect - done_charging).dt.total_seconds() / 60
    )

    # Date coverage.
    earliest = connection.min()
    latest = connection.max()

    # Unique stations: inventory clue only, not verified capacity.
    station_inventory = (
        df.loc[valid_station, "stationID"]
        .astype(str)
        .value_counts()
        .rename_axis("stationID")
        .reset_index(name="session_count")
    )
    station_inventory.insert(0, "site", site_name)

    # Check for overlapping connection intervals at the same station.
    overlap_count = 0

    overlap_df = df.loc[
        usable,
        ["stationID", "connectionTime", "disconnectTime"],
    ].copy()

    if not overlap_df.empty:
        overlap_df = overlap_df.sort_values(
            ["stationID", "connectionTime"]
        )

        previous_max_end = (
            overlap_df.groupby("stationID")["disconnectTime"]
            .transform(lambda values: values.cummax().shift())
        )

        overlaps = (
            overlap_df["connectionTime"] < previous_max_end
        )

        overlap_count = int(overlaps.sum())

    # Inspect nested userInputs keys.
    user_input_keys = Counter()

    if "userInputs" in df.columns:
        for value in df["userInputs"]:
            user_input_keys.update(get_nested_keys(value))

    # Timezone coverage.
    if "timezone" in df.columns:
        timezone_counts = (
            df["timezone"]
            .fillna("Missing")
            .astype(str)
            .value_counts()
        )
    else:
        timezone_counts = pd.Series(dtype=int)

    summary = {
        "site": site_name,
        "total_records": total,
        "valid_connection_time": int(valid_connection.sum()),
        "valid_disconnect_time": int(valid_disconnect.sum()),
        "valid_station_id": int(valid_station.sum()),
        "valid_interval_order": int(valid_order.sum()),
        "usable_records": int(usable.sum()),
        "usable_percentage": round(
            usable.sum() / total * 100, 2
        ) if total else 0,
        "duplicate_session_id_rows": duplicate_session_ids,
        "duplicate_record_id_rows": duplicate_record_ids,
        "unique_stations": int(
            df.loc[valid_station, "stationID"].nunique()
        ),
        "overlapping_session_rows": overlap_count,
        "done_charging_present": int(done_charging_present.sum()),
        "done_charging_within_connection": int(
            charging_within_connection.sum()
        ),
        "earliest_connection_utc": str(earliest),
        "latest_connection_utc": str(latest),
        "median_connected_hours": round(
            connected_hours[usable].median(), 2
        ),
        "p95_connected_hours": round(
            connected_hours[usable].quantile(0.95), 2
        ),
        "median_post_charge_dwell_minutes": round(
            post_charge_dwell_minutes[
                charging_within_connection
            ].median(), 2
        ),
        "user_id_present": int(
            df["userID"].notna().sum()
        ) if "userID" in df.columns else 0,
        "user_inputs_present": int(
            df["userInputs"].notna().sum()
        ) if "userInputs" in df.columns else 0,
    }

    print(f"  Total records: {total:,}")
    print(
        f"  Usable records: {summary['usable_records']:,} "
        f"({summary['usable_percentage']}%)"
    )
    print(f"  Unique stations: {summary['unique_stations']}")
    print(f"  Overlapping session rows: {overlap_count}")
    print(f"  Duplicate session ID rows: {duplicate_session_ids}")
    print(f"  Date range: {earliest} to {latest}")

    print("\n  Timezones:")
    for timezone, count in timezone_counts.items():
        print(f"    {timezone}: {count:,}")

    print("\n  userInputs keys:")
    if user_input_keys:
        for key, count in user_input_keys.most_common():
            print(f"    {key}: {count:,} records")
    else:
        print("    No nested userInputs keys found.")

    return summary, station_inventory, user_input_keys


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    inventories = []
    all_input_keys = []

    for site_id, site_name in SITES.items():
        summary, inventory, input_keys = audit_site(
            site_id,
            site_name,
        )

        summaries.append(summary)
        inventories.append(inventory)

        for key, count in input_keys.items():
            all_input_keys.append({
                "site": site_name,
                "user_input_key": key,
                "records_containing_key": count,
            })

    summary_df = pd.DataFrame(summaries)
    inventory_df = pd.concat(inventories, ignore_index=True)
    input_keys_df = pd.DataFrame(all_input_keys)

    summary_path = OUTPUT_DIR / "data_quality_summary.csv"
    inventory_path = OUTPUT_DIR / "station_inventory.csv"
    keys_path = OUTPUT_DIR / "user_input_keys.csv"

    summary_df.to_csv(summary_path, index=False)
    inventory_df.to_csv(inventory_path, index=False)
    input_keys_df.to_csv(keys_path, index=False)

    print("\n" + "=" * 60)
    print("DATA QUALITY AUDIT COMPLETE")
    print("=" * 60)

    print(
        summary_df[
            [
                "site",
                "total_records",
                "usable_records",
                "usable_percentage",
                "unique_stations",
                "overlapping_session_rows",
            ]
        ].to_string(index=False)
    )

    print("\nGenerated files:")
    print(summary_path)
    print(inventory_path)
    print(keys_path)


if __name__ == "__main__":
    main()
