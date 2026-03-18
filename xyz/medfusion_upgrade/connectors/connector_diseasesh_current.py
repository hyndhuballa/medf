"""
Connector 1 — disease.sh (Current Global Stats)
Source: https://disease.sh/v3/covid-19/all
Returns: global COVID snapshot — cases, deaths, recovered, active, updated
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "disease.sh"
SOURCE_URL = "https://disease.sh/v3/covid-19/all"
SOURCE_TYPE = "current"


def fetch() -> dict:
    """Fetch current global COVID-19 stats from disease.sh"""
    try:
        resp = requests.get(SOURCE_URL, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        updated_ts = raw.get("updated", 0) / 1000  # ms → s
        updated_dt = datetime.fromtimestamp(updated_ts, tz=timezone.utc).isoformat()

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "data_updated_at": updated_dt,
            "status": "ok",
            "data": {
                "cases": raw.get("cases"),
                "today_cases": raw.get("todayCases"),
                "deaths": raw.get("deaths"),
                "today_deaths": raw.get("todayDeaths"),
                "recovered": raw.get("recovered"),
                "active": raw.get("active"),
                "critical": raw.get("critical"),
                "cases_per_million": raw.get("casesPerOneMillion"),
                "deaths_per_million": raw.get("deathsPerOneMillion"),
                "tests": raw.get("tests"),
                "population": raw.get("population"),
                "affected_countries": raw.get("affectedCountries"),
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
