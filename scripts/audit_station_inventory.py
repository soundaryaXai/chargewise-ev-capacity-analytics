import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"

SITES = {
    "caltech": RAW_DIR / "caltech_sessions.jsonl",
    "jpl": RAW_DIR / "jpl_sessions.jsonl",
    "office001": RAW_DIR / "office001_sessions.jsonl",
}


def load_site_records(path):
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def audit_site(site_id, path):
    stations = defaultdict(
        lambda: {
            "sessions": 0,
            "spaces": set(),
            "first_connection": None,
            "last_connection": None,
        }
    )

    cluster_station_pairs = set()
    total_sessions = 0

    for record in load_site_records(path):
        total_sessions += 1

        cluster = record.get("clusterID") or "Unknown"
        station = record.get("stationID") or "Unknown"
        space = record.get("spaceID")

        key = (cluster, station)
        cluster_station_pairs.add(key)

        item = stations[key]
        item["sessions"] += 1

        if space:
            item["spaces"].add(space)

        timestamp = pd.to_datetime(
            record.get("connectionTime"),
            utc=True,
            errors="coerce",
        )

        if pd.notna(timestamp):
            if (
                item["first_connection"] is None
                or timestamp < item["first_connection"]
            ):
                item["first_connection"] = timestamp

            if (
                item["last_connection"] is None
                or timestamp > item["last_connection"]
            ):
                item["last_connection"] = timestamp

    rows = []

    for (cluster, station), item in sorted(stations.items(), key=lambda entry: (str(entry[0][0]), str(entry[0][1])),):
        rows.append(
            {
                "site_id": site_id,
                "cluster_id": cluster,
                "station_id": station,
                "session_count": item["sessions"],
                "unique_space_ids": len(item["spaces"]),
                "first_connection_utc": item["first_connection"],
                "last_connection_utc": item["last_connection"],
            }
        )

    summary = {
        "site_id": site_id,
        "total_sessions": total_sessions,
        "unique_station_ids": len(
            {station for _, station in cluster_station_pairs}
        ),
        "unique_cluster_station_pairs": len(cluster_station_pairs),
        "unique_clusters": len(
            {cluster for cluster, _ in cluster_station_pairs}
        ),
    }

    return rows, summary


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    summaries = []

    for site_id, path in SITES.items():
        print(f"\nAuditing {site_id}...")

        rows, summary = audit_site(site_id, path)

        all_rows.extend(rows)
        summaries.append(summary)

        print(f"  Sessions: {summary['total_sessions']:,}")
        print(f"  Unique station IDs: {summary['unique_station_ids']}")
        print(
            "  Cluster-station combinations: "
            f"{summary['unique_cluster_station_pairs']}"
        )
        print(f"  Unique clusters: {summary['unique_clusters']}")

    inventory = pd.DataFrame(all_rows)
    summary_df = pd.DataFrame(summaries)

    inventory_path = OUTPUT_DIR / "station_inventory_observed.csv"
    summary_path = OUTPUT_DIR / "station_inventory_summary.csv"

    inventory.to_csv(inventory_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print("\nCluster-level station counts:")

    cluster_counts = (
        inventory.groupby(["site_id", "cluster_id"])["station_id"]
        .nunique()
        .reset_index(name="unique_station_ids")
    )

    print(cluster_counts.to_string(index=False))

    print("\nSaved:")
    print(inventory_path)
    print(summary_path)


if __name__ == "__main__":
    main()