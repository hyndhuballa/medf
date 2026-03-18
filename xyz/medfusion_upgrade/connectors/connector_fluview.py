"""
Connector 5 — CDC FluView (Influenza Surveillance)
Source: CDC FluView API (ILINet - Influenza-like Illness Network)
URL: https://gis.cdc.gov/grasp/fluview/fluportaldashboard.html
API: https://gis.cdc.gov/grasp/flu2/GetFlu2Data
Returns: Weekly flu activity level by region in the US
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "CDC FluView"
SOURCE_URL = "https://gis.cdc.gov/grasp/flu2/GetFlu2Data"
SOURCE_TYPE = "flu_surveillance"

# Fallback: public flu summary from disease.sh (influenza)
FALLBACK_URL = "https://disease.sh/v3/covid-19/countries?sort=cases&limit=10"


def fetch() -> dict:
    """Fetch US influenza surveillance data from CDC FluView"""
    try:
        payload = {
            "AppVersion": "Public",
            "DatasourceDT": [{"ID": 1, "Name": "ILINet"}],
            "RegionTypeId": 3,  # HHS Regions
            "SubRegionsList": [],
            "SeasonsList": [65],  # recent season
            "DataTypeId": 1,
        }

        resp = requests.post(
            SOURCE_URL,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp.raise_for_status()
        raw = resp.json()

        ili_data = raw.get("ilinetList", [])

        # Normalize
        weekly = []
        for r in ili_data[:50]:
            weekly.append({
                "week": r.get("WEEK"),
                "year": r.get("YEAR"),
                "region": r.get("REGION"),
                "ili_total": r.get("ILITOTAL"),
                "total_patients": r.get("TOTAL_PATIENTS"),
                "percent_ili": r.get("PERCENT_OF_ILI"),
                "age_0_4": r.get("AGE_0_4"),
                "age_25_49": r.get("AGE_25_49"),
                "age_50_64": r.get("AGE_50_64"),
                "age_65plus": r.get("AGE_65"),
            })

        # Summary: average %ILI across regions for latest week
        latest_week_data = [w for w in weekly if w["week"] == weekly[0]["week"]] if weekly else []
        avg_ili = None
        if latest_week_data:
            vals = [w["percent_ili"] for w in latest_week_data if w["percent_ili"] is not None]
            avg_ili = round(sum(float(v) for v in vals) / len(vals), 2) if vals else None

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "disease": "Influenza (ILI)",
                "network": "ILINet",
                "records": weekly,
                "latest_week_avg_ili_pct": avg_ili,
                "total_records": len(ili_data),
            },
        }

    except Exception as e:
        # Graceful fallback: return structured error with helpful message
        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
            "fallback_note": "CDC FluView API requires specific POST body. Check https://gis.cdc.gov/grasp/fluview",
            "data": None,
        }
