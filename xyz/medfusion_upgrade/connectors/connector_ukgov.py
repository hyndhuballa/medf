"""
connector_ukgov.py
UK Government Health Statistics
Required by PDF: "UK Gov Health Statistics gov.uk"
Uses UK Health Security Agency (UKHSA) API — open access
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "UK Health Security Agency (UKHSA)"

# UKHSA open data endpoints
COVID_DASHBOARD = "https://api.ukhsa-dashboard.data.gov.uk/themes/infectious_disease/sub_themes/respiratory/topics/COVID-19/geography_types/Nation/geographies/England/metrics/COVID-19_cases_casesByDay"
FLU_DASHBOARD   = "https://api.ukhsa-dashboard.data.gov.uk/themes/infectious_disease/sub_themes/respiratory/topics/Influenza/geography_types/Nation/geographies/England/metrics/influenza_healthcare_ICUHDUadmissionRateByWeek"
EMERGENCY_ENDPOINT = "https://files.digital.nhs.uk/assets/ods/current/epraccur.zip"

# Fallback: NHS England open data
NHS_STATS_URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/ae-attendances-and-emergency-admissions-2024-25/"


def _fetch_ukhsa(url: str, limit: int = 5) -> list:
    try:
        r = requests.get(
            url,
            params={"page_size": limit},
            headers={"User-Agent": "MedFusion/1.0", "Accept": "application/json"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("results", data if isinstance(data, list) else [])
    except Exception:
        return []


def fetch_covid_uk() -> dict:
    """Fetch UK COVID-19 data from UKHSA dashboard"""
    records = _fetch_ukhsa(COVID_DASHBOARD, limit=7)

    if records:
        latest = records[0] if records else {}
        return {
            "source": SOURCE_NAME,
            "source_url": COVID_DASHBOARD,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "disease": "COVID-19",
                "geography": "England",
                "metric": "daily_cases",
                "latest_date": latest.get("date"),
                "latest_value": latest.get("metric_value"),
                "recent_7_days": [
                    {"date": r.get("date"), "cases": r.get("metric_value")}
                    for r in records[:7]
                ],
            },
        }

    # Graceful fallback with clear note
    return {
        "source":     SOURCE_NAME,
        "source_url": COVID_DASHBOARD,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "status":     "unavailable",
        "data":       None,
        "note":       "UKHSA API endpoint may require authentication or has changed. Visit https://ukhsa-dashboard.data.gov.uk for manual access.",
    }


def fetch_flu_uk() -> dict:
    """Fetch UK influenza data from UKHSA dashboard"""
    records = _fetch_ukhsa(FLU_DASHBOARD, limit=5)

    if records:
        return {
            "source": SOURCE_NAME,
            "source_url": FLU_DASHBOARD,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "disease": "Influenza",
                "geography": "England",
                "metric": "ICU_HDU_admission_rate_per_100k",
                "records": [
                    {"date": r.get("date"), "rate": r.get("metric_value")}
                    for r in records[:5]
                ],
            },
        }

    return {
        "source": SOURCE_NAME, "source_url": FLU_DASHBOARD,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "unavailable", "data": None,
        "note": "UKHSA flu data endpoint unavailable. Fallback: NHS England reports at england.nhs.uk/statistics",
    }


def fetch(disease: str = "covid") -> dict:
    dl = disease.lower()
    if "flu" in dl or "influenza" in dl:
        return fetch_flu_uk()
    return fetch_covid_uk()
