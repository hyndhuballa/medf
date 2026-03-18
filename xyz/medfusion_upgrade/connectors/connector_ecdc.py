"""
connectors/connector_ecdc.py
ECDC European COVID data - open CSV, no key required
Source: https://opendata.ecdc.europa.eu
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "ECDC Open Data"
SOURCE_URL  = "https://opendata.ecdc.europa.eu/covid19/nationalcasedeath_eueea_daily_ei/csv"


def fetch(top_n: int = 10) -> dict:
    try:
        r = requests.get(SOURCE_URL, timeout=15)
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        headers = [h.strip().strip('"') for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) >= len(headers):
                rows.append(dict(zip(headers, [v.strip().strip('"') for v in vals])))

        dates = sorted({r.get("dateRep", "") for r in rows if r.get("dateRep")}, reverse=True)
        latest = dates[0] if dates else ""
        latest_rows = [r for r in rows if r.get("dateRep") == latest]

        def safe_int(v):
            try: return int(float(v))
            except: return 0

        by_country = {}
        for row in latest_rows:
            c = row.get("countriesAndTerritories", "")
            by_country[c] = {
                "country": c,
                "country_code": row.get("countryterritoryCode", ""),
                "new_cases": safe_int(row.get("cases", 0)),
                "new_deaths": safe_int(row.get("deaths", 0)),
                "date": latest,
            }

        top = sorted(by_country.values(), key=lambda x: x["new_cases"], reverse=True)[:top_n]

        return {
            "source": SOURCE_NAME, "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "latest_date": latest,
                "countries_covered": len(by_country),
                "top_by_new_cases": top,
                "total_new_cases":  sum(c["new_cases"]  for c in by_country.values()),
                "total_new_deaths": sum(c["new_deaths"] for c in by_country.values()),
            },
        }
    except Exception as e:
        return {
            "source": SOURCE_NAME, "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error", "error": str(e), "data": None,
        }
