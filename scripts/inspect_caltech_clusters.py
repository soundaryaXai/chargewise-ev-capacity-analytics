import json
from collections import Counter, defaultdict
from pathlib import Path

path = Path("data/raw/caltech_sessions.jsonl")

cluster_counts = Counter()
cluster_types = defaultdict(Counter)
cluster_stations = defaultdict(set)

with path.open("r", encoding="utf-8") as file:
    for line in file:
        record = json.loads(line)

        cluster = record.get("clusterID")
        station = record.get("stationID")

        key = repr(cluster)

        cluster_counts[key] += 1
        cluster_types[key][type(cluster).__name__] += 1

        if station is not None:
            cluster_stations[key].add(str(station))

print("\nCALTECH CLUSTER DETAILS")
print("=" * 50)

for cluster, count in cluster_counts.items():
    print(f"\nCluster: {cluster}")
    print(f"Sessions: {count:,}")
    print(f"Data types: {dict(cluster_types[cluster])}")
    print(f"Unique stations: {len(cluster_stations[cluster])}")

cluster_39 = cluster_stations.get("39", set())
cluster_0039 = cluster_stations.get("'0039'", set())

print("\nSTATION COMPARISON")
print("=" * 50)
print("Common station IDs:", len(cluster_39 & cluster_0039))
print("Only in 39:", sorted(cluster_39 - cluster_0039))
print("Only in 0039:", sorted(cluster_0039 - cluster_39))