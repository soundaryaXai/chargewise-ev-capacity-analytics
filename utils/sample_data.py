
import numpy as np
import pandas as pd


def get_overview_data():
    """Generate deterministic synthetic data for UI development."""

    rng = np.random.default_rng(42)

    sites = ["Caltech", "JPL", "Office Site C"]

    dates = pd.date_range(
        start="2025-01-06",
        periods=28,
        freq="D",
    )

    records = []

    site_baselines = {
        "Caltech": 24,
        "JPL": 19,
        "Office Site C": 15,
    }

    for site in sites:
        baseline = site_baselines[site]

        for date in dates:
            records.append({
                "date": date,
                "site": site,
                "average_occupancy": max(
                    0,
                    baseline + rng.normal(0, 3),
                ),
                "peak_occupancy": max(
                    0,
                    baseline * 2 + rng.normal(0, 5),
                ),
            })

    occupancy = pd.DataFrame(records)

    hourly_records = []

    for site, baseline in site_baselines.items():
        for hour in range(24):
            daytime_pattern = np.exp(
                -((hour - 13) ** 2) / 30
            )

            hourly_records.append({
                "site": site,
                "hour": hour,
                "occupancy": max(
                    0,
                    baseline * 0.2
                    + baseline * daytime_pattern,
                ),
            })

    hourly = pd.DataFrame(hourly_records)

    return {
        "occupancy": occupancy,
        "hourly": hourly,
        "sites": sites,
    }


def get_capacity_data():
    """
    Generate illustrative capacity curves for UI development.
    These are not actual ACN-Data results.
    """

    import numpy as np
    import pandas as pd

    port_counts = np.arange(8, 33)

    site_parameters = {
        "Caltech": {
            "offered_load": 18.0,
            "replay_adjustment": 0.0,
        },
        "JPL": {
            "offered_load": 13.0,
            "replay_adjustment": 0.8,
        },
        "Office Site C": {
            "offered_load": 9.0,
            "replay_adjustment": 1.5,
        },
    }

    records = []

    for site, parameters in site_parameters.items():

        offered_load = parameters["offered_load"]
        replay_adjustment = parameters["replay_adjustment"]

        blocking_probability = 1.0

        for ports in port_counts:

            blocking_probability = (
                offered_load * blocking_probability
            ) / (
                ports + offered_load * blocking_probability
            )

            erlang_b = blocking_probability

            # Illustrative placeholder, not a real replay.
            replay = min(
                1.0,
                erlang_b * 1.25
                + replay_adjustment / 100,
            )

            records.append({
                "site": site,
                "ports": int(ports),
                "erlang_b_blocking": erlang_b * 100,
                "replay_blocking": replay * 100,
            })

    return pd.DataFrame(records), list(site_parameters.keys())
