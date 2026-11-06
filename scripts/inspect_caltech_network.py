import inspect

from acnportal.acnsim import sites

print("CALTECH ACN-SIM NETWORK")
print("=" * 55)

print("\nFunction signature:")
print(inspect.signature(sites.caltech_acn))

network = sites.caltech_acn(
    basic_evse=True,
    voltage=208,
)

station_ids = network.station_ids

print("\nConfigured station count:", len(station_ids))
print("\nConfigured station IDs:")

for station_id in sorted(station_ids):
    print(station_id)

print("\nNetwork object type:", type(network).__name__)