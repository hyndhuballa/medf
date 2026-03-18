"""
Connector 2 — disease.sh (Historical Timeline)
Source: https://disease.sh/v3/covid-19/historical/all?lastdays=90
Returns: 90-day time series for cases, deaths, recovered — for trend charts
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "disease.sh (historical)"
SOURCE_URL = "https://disease.sh/v3/covid-19/historical/all"
SOURCE_TYPE = "historical"


def fetch(lastdays: int = 90) -> dict:
    """Fetch historical global COVID-19 timeline from disease.sh"""
    try:
        resp = requests.get(SOURCE_URL, params={"lastdays": lastdays}, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        cases_ts = raw.get("cases", {})
        deaths_ts = raw.get("deaths", {})
        recovered_ts = raw.get("recovered", {})

        # Normalize into list of dicts for easy charting
        dates = list(cases_ts.keys())
        timeline = [
            {
                "date": d,
                "cases": cases_ts.get(d),
                "deaths": deaths_ts.get(d),
                "recovered": recovered_ts.get(d),
            }
            for d in dates
        ]

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "days": lastdays,
                "timeline": timeline,
                "latest_date": dates[-1] if dates else None,
                "earliest_date": dates[0] if dates else None,
                "total_points": len(timeline),
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
