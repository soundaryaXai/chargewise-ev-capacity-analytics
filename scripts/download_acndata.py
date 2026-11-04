
import json
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from acnportal.acndata import DataClient


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

SITES = {
    "caltech": "Caltech",
    "jpl": "JPL",
    "office001": "Office 1",
}


# --------------------------------------------------
# API CLIENT
# --------------------------------------------------

def create_client():

    try:
        token = st.secrets["acndata"]["api_token"]

    except Exception as exc:
        raise RuntimeError(
            "ACN-Data API token not found. "
            "Check .streamlit/secrets.toml."
        ) from exc

    if not token or token.startswith("PASTE_"):
        raise RuntimeError("Invalid or missing API token.")

    return DataClient(api_token=token)


# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------

def download_site(client, site_id, site_name):

    output_path = DATA_DIR / f"{site_id}_sessions.jsonl"
    partial_path = DATA_DIR / f"{site_id}_sessions.jsonl.partial"

    print(f"\nDownloading {site_name}...")

    expected_count = int(client.count_sessions(site_id))

    print(f"API-reported sessions: {expected_count:,}")

    downloaded_count = 0

    try:
        with open(
            partial_path,
            "w",
            encoding="utf-8",
        ) as output_file:

            sessions = client.get_sessions(
                site_id,
                sort="connectionTime",
                timeseries=False,
            )

            for session in sessions:

                output_file.write(
                    json.dumps(
                        session,
                        default=str,
                    ) + "\n"
                )

                downloaded_count += 1

                if downloaded_count % 5000 == 0:
                    print(
                        f"Downloaded: {downloaded_count:,} "
                        f"/ {expected_count:,}"
                    )

        partial_path.replace(output_path)

    except Exception:
        print(
            f"Download interrupted for {site_name}. "
            "Partial file retained for inspection."
        )
        raise

    print(f"Completed: {downloaded_count:,} sessions")

    if downloaded_count != expected_count:
        print(
            "WARNING: Downloaded count differs from "
            "the API-reported count."
        )

    return {
        "site_id": site_id,
        "site_name": site_name,
        "expected_count": expected_count,
        "downloaded_count": downloaded_count,
        "file": str(output_path),
        "complete": downloaded_count == expected_count,
    }


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 60)
    print("CHARGEWISE | FULL ACN-DATA EXTRACTION")
    print("=" * 60)

    client = create_client()

    results = []

    for site_id, site_name in SITES.items():

        result = download_site(
            client,
            site_id,
            site_name,
        )

        results.append(result)

    metadata = {
        "extraction_time_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "sites": results,
    }

    metadata_path = DATA_DIR / "extraction_metadata.json"

    with open(
        metadata_path,
        "w",
        encoding="utf-8",
    ) as metadata_file:

        json.dump(
            metadata,
            metadata_file,
            indent=2,
        )

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    total_downloaded = sum(
        result["downloaded_count"]
        for result in results
    )

    total_expected = sum(
        result["expected_count"]
        for result in results
    )

    for result in results:
        print(
            f"{result['site_name']}: "
            f"{result['downloaded_count']:,} / "
            f"{result['expected_count']:,}"
        )

    print("-" * 60)
    print(f"Total downloaded: {total_downloaded:,}")
    print(f"Total expected:   {total_expected:,}")
    print(f"Metadata: {metadata_path}")

    if total_downloaded != total_expected:
        print("\nWARNING: Extraction requires investigation.")
    else:
        print("\nAll API-reported sessions downloaded.")


if __name__ == "__main__":
    main()
