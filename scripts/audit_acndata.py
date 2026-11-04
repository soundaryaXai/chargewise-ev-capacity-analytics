
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from acnportal.acndata import DataClient


# --------------------------------------------------
# PROJECT PATHS AND CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

SITES = {
    "caltech": "Caltech",
    "jpl": "JPL",
    "office001": "Office 1",
}


# --------------------------------------------------
# AUTHENTICATION
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
        raise RuntimeError(
            "Add your valid ACN-Data token to secrets.toml."
        )

    return DataClient(api_token=token)


# --------------------------------------------------
# DATASET AUDIT
# --------------------------------------------------

def audit_site(client, site_id, site_name):

    print(f"\nAuditing {site_name} ({site_id})...")

    total_count = client.count_sessions(site_id)

    print(f"Sessions reported by API: {int(total_count):,}")

    sample_records = []

    sessions = client.get_sessions(site_id)

    for index, session in enumerate(sessions):

        if index < 5:
            sample_records.append(session)

        if index == 4:
            break

    print(f"Sample records retrieved: {len(sample_records)}")

    if sample_records:
        print(
            "Available fields:",
            sorted(sample_records[0].keys()),
        )

    return {
        "site_id": site_id,
        "site_name": site_name,
        "api_session_count": total_count,
        "sample_records": sample_records,
    }


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("CHARGEWISE | ACN-DATA INITIAL AUDIT")
    print("=" * 60)

    client = create_client()

    audit_results = []

    for site_id, site_name in SITES.items():

        try:
            result = audit_site(
                client,
                site_id,
                site_name,
            )

            audit_results.append(result)

        except Exception as exc:
            print(
                f"ERROR while auditing {site_name}: {exc}"
            )

    if not audit_results:
        raise RuntimeError(
            "No sites could be audited. "
            "Check API access and credentials."
        )

    summary = pd.DataFrame([
        {
            "site_id": result["site_id"],
            "site_name": result["site_name"],
            "api_session_count": int(result["api_session_count"]),
        }
        for result in audit_results
    ])

    summary_path = DATA_DIR / "initial_site_audit.csv"

    summary.to_csv(
        summary_path,
        index=False,
    )

    sample_path = DATA_DIR / "sample_records.json"

    with open(sample_path, "w", encoding="utf-8") as file:
        json.dump(
            [
                {
                    "site_id": result["site_id"],
                    "site_name": result["site_name"],
                    "records": result["sample_records"],
                }
                for result in audit_results
            ],
            file,
            indent=2,
            default=str,
        )

    print("\n" + "=" * 60)
    print("INITIAL AUDIT SUMMARY")
    print("=" * 60)

    print(summary.to_string(index=False))

    print("\nFiles saved locally:")
    print(summary_path)
    print(sample_path)

    print(
        "\nAudit completed at:",
        datetime.now(timezone.utc).isoformat(),
    )

    print(
        "\nNote: This is an initial access and coverage check. "
        "It does not yet establish usable session counts, "
        "valid date coverage, or verified port capacity."
    )


if __name__ == "__main__":
    main()
