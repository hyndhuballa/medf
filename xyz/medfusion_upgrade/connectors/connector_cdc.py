"""
Connector 4 — CDC Open Data (data.cdc.gov Socrata API)
Source: United States COVID-19 Cases and Deaths by State over Time
Dataset: https://data.cdc.gov/resource/9mfq-cb36.json
Returns: Recent US state-level COVID cases + deaths (last 30 days per state)
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "CDC Open Data"
SOURCE_URL = "https://data.cdc.gov/resource/9mfq-cb36.json"
SOURCE_TYPE = "cdc_us_states"

HEADERS = {"Accept": "application/json"}


def fetch(limit: int = 100) -> dict:
    """Fetch latest US state-level COVID data from CDC Socrata API"""
    try:
        params = {
            "$limit": limit,
            "$order": "submission_date DESC",
            "$select": "submission_date,state,tot_cases,new_case,tot_death,new_death",
        }

        resp = requests.get(SOURCE_URL, params=params, headers=HEADERS, timeout=12, verify=False)
        resp.raise_for_status()
        records = resp.json()

        # Normalize
        cleaned = []
        for r in records:
            cleaned.append({
                "date": r.get("submission_date", "")[:10],
                "state": r.get("state"),
                "total_cases": _safe_int(r.get("tot_cases")),
                "new_cases": _safe_int(r.get("new_case")),
                "total_deaths": _safe_int(r.get("tot_death")),
                "new_deaths": _safe_int(r.get("new_death")),
            })

        # Aggregate to get most recent snapshot per state
        latest_by_state = {}
        for rec in cleaned:
            state = rec["state"]
            if state not in latest_by_state:
                latest_by_state[state] = rec

        # Top 10 states by new cases
        top_states = sorted(
            [v for v in latest_by_state.values() if v["new_cases"] is not None],
            key=lambda x: x["new_cases"],
            reverse=True,
        )[:10]

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "records_fetched": len(records),
                "states_covered": len(latest_by_state),
                "top_states_by_new_cases": top_states,
                "all_latest": list(latest_by_state.values()),
            },
        }

    except requests.exceptions.RequestException as e:
        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
            "data": None,
        }


def _safe_int(val) -> int | None:
    try:
        return int(float(val)) if val is not None else None
    except (ValueError, TypeError):
        return None
