
import json
from collections import Counter
from pathlib import Path

import pandas as pd
from dateutil import parser


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

SITES = {
    "caltech": "Caltech",
    "jpl": "JPL",
    "office001": "Office 1",
}


def robust_parse(value):
    if not value:
        return None

    try:
        return parser.parse(str(value), fuzzy=False)
    except (ValueError, TypeError, OverflowError):
        return None


def inspect_site(site_id, site_name):
    path = RAW_DIR / f"{site_id}_sessions.jsonl"

    values = []
    modified_values = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)
            inputs = record.get("userInputs", [])

            if isinstance(inputs, dict):
                inputs = [inputs]

            if not isinstance(inputs, list):
                continue

            for item in inputs:
                if not isinstance(item, dict):
                    continue

                requested = item.get("requestedDeparture")
                modified = item.get("modifiedAt")

                if requested:
                    values.append(str(requested))

                if modified:
                    modified_values.append(str(modified))

    pandas_parsed = pd.to_datetime(
        pd.Series(values),
        errors="coerce",
        utc=True,
        format="mixed",
    )

    robust_parsed = [robust_parse(value) for value in values]

    pandas_success = int(pandas_parsed.notna().sum())
    robust_success = sum(value is not None for value in robust_parsed)

    print("\n" + "=" * 60)
    print(f"{site_name.upper()} — REQUESTED DEPARTURE FORMATS")
    print("=" * 60)

    print(f"Total requested departure values: {len(values):,}")
    print(f"Pandas mixed-format parsed: {pandas_success:,}")
    print(f"Dateutil parsed: {robust_success:,}")

    failures = [
        value
        for value, parsed in zip(values, robust_parsed)
        if parsed is None
    ]

    print(f"Unparseable values after fallback: {len(failures):,}")

    print("\nMost common requested departure formats:")

    for value, count in Counter(values).most_common(10):
        print(f"{count:>7,} | {value}")

    print("\nExamples of values pandas could not parse:")

    failed_pandas = [
        value
        for value, parsed in zip(values, pandas_parsed)
        if pd.isna(parsed)
    ]

    for value in failed_pandas[:10]:
        print(repr(value))

    print("\nExamples still unparseable by dateutil:")

    for value in failures[:10]:
        print(repr(value))

    print("\nModifiedAt values:", len(modified_values))
    print(
        "ModifiedAt parseable with dateutil:",
        sum(robust_parse(value) is not None for value in modified_values),
    )


def main():
    for site_id, site_name in SITES.items():
        inspect_site(site_id, site_name)


if __name__ == "__main__":
    main()
