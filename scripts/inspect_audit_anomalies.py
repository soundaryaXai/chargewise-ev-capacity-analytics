
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

FILES = {
    "caltech": RAW_DIR / "caltech_sessions.jsonl",
    "jpl": RAW_DIR / "jpl_sessions.jsonl",
}


def inspect_user_inputs(site_id, path):
    print(f"\n{'=' * 60}")
    print(f"{site_id.upper()} — USER INPUTS")
    print("=" * 60)

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)

            inputs = record.get("userInputs")

            if inputs is not None:
                print("Python type:", type(inputs).__name__)
                print("Value preview:", repr(inputs)[:1200])

                if isinstance(inputs, str):
                    try:
                        parsed = json.loads(inputs)
                        print("Parsed string type:", type(parsed).__name__)
                        print("Parsed keys:", list(parsed.keys()) if isinstance(parsed, dict) else "Not a dictionary")
                    except json.JSONDecodeError as error:
                        print("String is not valid JSON:", error)

                elif isinstance(inputs, dict):
                    print("Dictionary keys:", list(inputs.keys()))

                break


def inspect_jpl_overlap(path):
    print(f"\n{'=' * 60}")
    print("JPL — OVERLAPPING SESSION RECORDS")
    print("=" * 60)

    target_station = "1-1-179-794"
    target_date = "2021-07-19"

    matching = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)

            if record.get("stationID") != target_station:
                continue

            connection = str(record.get("connectionTime", ""))

            if target_date in connection:
                matching.append(record)

    for index, record in enumerate(matching, start=1):
        print(f"\nRecord {index}")

        for field in [
            "_id",
            "sessionID",
            "stationID",
            "spaceID",
            "connectionTime",
            "doneChargingTime",
            "disconnectTime",
            "kWhDelivered",
            "timezone",
        ]:
            print(f"{field}: {record.get(field)}")

    print(f"\nMatching records found: {len(matching)}")


def main():
    for site_id, path in FILES.items():
        inspect_user_inputs(site_id, path)

    inspect_jpl_overlap(FILES["jpl"])


if __name__ == "__main__":
    main()
