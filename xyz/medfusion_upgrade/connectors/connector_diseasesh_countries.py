"""
connector_diseasesh_countries.py
disease.sh - all countries COVID data + continental breakdown
Real live data, updates every ~10 minutes
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "disease.sh"
COUNTRIES_URL   = "https://disease.sh/v3/covid-19/countries"
CONTINENTS_URL  = "https://disease.sh/v3/covid-19/continents"


def fetch_all_countries(sort: str = "cases", limit: int = 20) -> dict:
    """Fetch top N countries by cases/deaths/active"""
    try:
        r = requests.get(COUNTRIES_URL, params={"sort": sort}, timeout=12)
        r.raise_for_status()
        data = r.json()

        countries = []
        for c in data[:limit]:
            countries.append({
                "country":          c.get("country"),
                "country_code":     (c.get("countryInfo") or {}).get("iso2"),
                "flag":             (c.get("countryInfo") or {}).get("flag"),
                "continent":        c.get("continent"),
                "cases":            c.get("cases"),
                "today_cases":      c.get("todayCases"),
                "deaths":           c.get("deaths"),
                "today_deaths":     c.get("todayDeaths"),
                "recovered":        c.get("recovered"),
                "active":           c.get("active"),
                "critical":         c.get("critical"),
                "cases_per_million":c.get("casesPerOneMillion"),
                "deaths_per_million":c.get("deathsPerOneMillion"),
                "population":       c.get("population"),
                "cfr":              round((c.get("deaths") or 0) / max(c.get("cases") or 1, 1) * 100, 3),
            })

        return {
            "source": SOURCE_NAME, "source_url": COUNTRIES_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "total_countries": len(data),
                "sorted_by": sort,
                "countries": countries,
            },
        }
    except Exception as e:
        return {
            "source": SOURCE_NAME, "source_url": COUNTRIES_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error", "error": str(e), "data": None,
        }


def fetch_continents() -> dict:
    """Fetch COVID data by continent"""
    try:
        r = requests.get(CONTINENTS_URL, timeout=10)
        r.raise_for_status()
        data = r.json()

        continents = []
        for c in data:
            continents.append({
                "continent":         c.get("continent"),
                "cases":             c.get("cases"),
                "today_cases":       c.get("todayCases"),
                "deaths":            c.get("deaths"),
                "recovered":         c.get("recovered"),
                "active":            c.get("active"),
                "critical":          c.get("critical"),
                "cases_per_million": c.get("casesPerOneMillion"),
                "population":        c.get("population"),
                "countries":         c.get("countries", []),
            })

        return {
            "source": SOURCE_NAME, "source_url": CONTINENTS_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {"continents": continents},
        }
    except Exception as e:
        return {
            "source": SOURCE_NAME, "source_url": CONTINENTS_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error", "error": str(e), "data": None,
        }
