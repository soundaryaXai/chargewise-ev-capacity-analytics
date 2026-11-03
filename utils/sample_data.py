
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

