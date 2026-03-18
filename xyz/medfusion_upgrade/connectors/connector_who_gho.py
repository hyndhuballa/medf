"""
Connector 3 — WHO Global Health Observatory (GHO) API
Source: https://ghoapi.azureedge.net/api/
Returns: WHO indicator data — uses WHOSIS_000001 (life expectancy) as a proxy
         and MORT_100 (deaths by cause) for disease burden data.
         Falls back gracefully if specific indicators unavailable.
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "WHO GHO API"
SOURCE_BASE = "https://ghoapi.azureedge.net/api"
SOURCE_TYPE = "who_indicators"

# Key indicator codes
INDICATORS = {
    "life_expectancy": "WHOSIS_000001",
    "ncd_deaths": "NCD_MORT_NCDPROP",
    "tobacco_age_std": "M_Est_smk_curr_std",
}


def _fetch_indicator(code: str, top: int = 50) -> list:
    """Fetch a single WHO GHO indicator, return list of records"""
    url = f"{SOURCE_BASE}/{code}"
    try:
        resp = requests.get(url, params={"$top": top}, timeout=12)
        resp.raise_for_status()
        records = resp.json().get("value", [])
        return records
    except Exception:
        return []


def fetch() -> dict:
    """Fetch WHO GHO indicator data"""
    try:
        # Fetch life expectancy data as primary indicator
        le_records = _fetch_indicator(INDICATORS["life_expectancy"], top=30)

        # Normalize records
        normalized = []
        for r in le_records:
            normalized.append({
                "country": r.get("SpatialDim"),
                "region": r.get("ParentLocation"),
                "year": r.get("TimeDim"),
                "sex": r.get("Dim1"),
                "value": r.get("NumericValue"),
                "indicator": "life_expectancy",
            })

        # Group by region for summary
        regions = {}
        for rec in normalized:
            reg = rec.get("region") or "Unknown"
            if reg not in regions:
                regions[reg] = []
            if rec.get("value"):
                regions[reg].append(rec["value"])

        region_summary = {
            reg: round(sum(vals) / len(vals), 1)
            for reg, vals in regions.items()
            if vals
        }

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_BASE,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "indicator": "life_expectancy",
                "indicator_code": INDICATORS["life_expectancy"],
                "records_fetched": len(normalized),
                "region_averages": region_summary,
                "records": normalized[:20],  # trim for response size
            },
        }

    except requests.exceptions.RequestException as e:
        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_BASE,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
            "data": None,
        }
