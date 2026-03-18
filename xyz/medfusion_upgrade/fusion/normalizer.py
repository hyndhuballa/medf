"""
fusion/normalizer.py
PHASE 2 — Normalization Layer

Converts raw API responses from each source into NormalizedCaseRecord.
This is the adapter layer between raw data and fusion logic.
Every source has its own normalizer function.
"""

from schemas.models import NormalizedCaseRecord, DataQuality, SOURCE_WEIGHTS
from datetime import datetime, timezone


def _weight(source: str) -> float:
    return SOURCE_WEIGHTS.get(source, 0.70)


def normalize_diseasesh(raw: dict, disease: str = "COVID-19") -> NormalizedCaseRecord:
    """
    Normalize disease.sh /v3/covid-19/all response.
    Live data — high freshness, medium authority (aggregates multiple sources).
    """
    cases  = raw.get("cases") or 0
    deaths = raw.get("deaths") or 0
    pop    = raw.get("population") or 1

    # CFR formula: deaths / total_cases * 100
    cfr = round(deaths / max(cases, 1) * 100, 3) if cases else None

    return NormalizedCaseRecord(
        disease         = disease,
        source_name     = "disease.sh",
        source_url      = "https://disease.sh/v3/covid-19/all",
        data_quality    = DataQuality.MEDIUM,
        weight          = _weight("disease.sh"),
        total_cases     = raw.get("cases"),
        active_cases    = raw.get("active"),
        total_deaths    = raw.get("deaths"),
        recovered       = raw.get("recovered"),
        today_cases     = raw.get("todayCases"),
        today_deaths    = raw.get("todayDeaths"),
        cfr_percent     = cfr,
        cases_per_million = raw.get("casesPerOneMillion"),
        region          = "global",
        is_live         = True,
        is_estimate     = False,
        data_freshness  = "Live — disease.sh updates every ~10 minutes",
    )


def normalize_who_malaria(raw: dict) -> NormalizedCaseRecord:
    """
    Normalize WHO GHO malaria response.
    Uses MALARIA_EST_CASES (absolute counts) not MALARIA_EST_INCIDENCE (rate).
    CFR = estimated_deaths / estimated_cases * 100
    """
    cases  = raw.get("estimated_cases")   # None if missing — no false zeros
    deaths = raw.get("estimated_deaths")
    cfr    = round(deaths / max(cases, 1) * 100, 4) if cases and deaths else raw.get("cfr_percent")
    year   = raw.get("latest_year")

    return NormalizedCaseRecord(
        disease           = "Malaria",
        source_name       = "WHO GHO",
        source_url        = "https://ghoapi.azureedge.net/api/MALARIA_EST_CASES",
        data_quality      = DataQuality.HIGH,
        weight            = _weight("WHO GHO"),
        total_cases       = cases,
        total_deaths      = deaths,
        cfr_percent       = cfr,
        cases_per_million = raw.get("cases_per_million"),
        region_breakdown  = raw.get("cases_by_region", {}),
        data_year         = int(year) if year else None,
        is_estimate       = True,
        is_live           = False,
        data_freshness    = f"WHO annual estimate ({year or 'latest'})",
    )


def normalize_who_tb(raw: dict) -> NormalizedCaseRecord:
    """
    Normalize WHO GHO TB incidence.
    Formula: estimated_cases = (incidence_per_100k / 100000) * world_population
    """
    world_pop  = 8_000_000_000
    incidence  = raw.get("incidence_per_100k") or 127
    cases      = int(incidence / 100000 * world_pop)
    deaths     = raw.get("estimated_deaths") or 0
    cfr        = round(deaths / max(cases, 1) * 100, 4) if cases else None
    year       = raw.get("latest_year")

    return NormalizedCaseRecord(
        disease          = "Tuberculosis",
        source_name      = "WHO GHO",
        source_url       = "https://ghoapi.azureedge.net/api/MDG_0000000020",
        data_quality     = DataQuality.HIGH,
        weight           = _weight("WHO GHO"),
        total_cases       = cases,
        total_deaths      = deaths,
        cfr_percent       = cfr,
        cases_per_million = raw.get("cases_per_million"),
        region_breakdown  = raw.get("incidence_by_region", {}),
        data_year         = int(year) if year else None,
        is_estimate       = True,
        is_live           = False,
        data_freshness    = f"WHO annual estimate ({year or 'latest'})",
    )


def normalize_who_dengue(raw: dict) -> NormalizedCaseRecord:
    """Normalize WHO GHO dengue reported cases.
    Note: uses None (not 0) when cases are unavailable — 0 would be misleading.
    WHO NTDDEN001 indicator sometimes returns null for recent years;
    fallback is None so confidence scoring reflects missing data honestly.
    """
    cases = raw.get("reported_cases")   # None if missing — never fake 0
    year  = raw.get("latest_year")
    return NormalizedCaseRecord(
        disease          = "Dengue",
        source_name      = "WHO GHO",
        source_url       = "https://ghoapi.azureedge.net/api/NTDDEN001",
        data_quality     = DataQuality.HIGH,
        weight           = _weight("WHO GHO"),
        total_cases       = cases,
        cfr_percent       = raw.get("cfr_percent", 0.5),
        cases_per_million = raw.get("cases_per_million"),
        region_breakdown  = raw.get("cases_by_region", {}),
        data_year        = int(year) if year else None,
        is_estimate      = False,
        is_live          = False,
        data_freshness   = f"WHO reported ({year or 'latest'})",
    )


def normalize_cdc_flu(raw: dict) -> NormalizedCaseRecord:
    """
    Normalize CDC FluView ILI surveillance.
    Formula: estimated_global = 1_000_000_000 * (ili_pct / 5.0)
    Basis: WHO estimates 1B flu cases/year globally.
    5.0% ILI is used as the peak/reference baseline.
    """
    ili_pct   = raw.get("latest_week_avg_ili_pct") or 2.5
    est_cases = int(1_000_000_000 * (ili_pct / 5.0))

    return NormalizedCaseRecord(
        disease        = "Influenza",
        source_name    = "CDC FluView",
        source_url     = "https://gis.cdc.gov/grasp/flu2/GetFlu2Data",
        data_quality   = DataQuality.HIGH,
        weight         = _weight("CDC FluView"),
        total_cases    = est_cases,
        cfr_percent    = 0.1,
        region         = "US surveillance (global proxy)",
        is_estimate    = True,
        is_live        = False,
        data_freshness = "CDC FluView weekly (Fridays)",
        region_breakdown = {"ili_pct_us": ili_pct},
    )


def normalize_ecdc(raw: dict) -> NormalizedCaseRecord:
    """Normalize ECDC European COVID data"""
    return NormalizedCaseRecord(
        disease        = "COVID-19",
        source_name    = "ECDC",
        source_url     = "https://opendata.ecdc.europa.eu",
        data_quality   = DataQuality.HIGH,
        weight         = _weight("ECDC"),
        today_cases    = raw.get("total_new_cases"),
        region         = "Europe",
        region_breakdown = {c["country"]: c["new_cases"] for c in (raw.get("top_by_new_cases") or [])[:10]},
        is_live        = False,
        data_freshness = f"ECDC daily ({raw.get('latest_date','latest')})",
    )


def normalize_promed_alert(alert: dict) -> dict:
    """
    Normalize a ProMED alert into a structured record.
    Returns dict (not NormalizedCaseRecord — alerts are a different schema).
    """
    return {
        "source":      "ProMED",
        "title":       alert.get("title",""),
        "disease":     alert.get("disease"),
        "severity":    alert.get("severity","low"),
        "published_at":alert.get("published_at"),
        "url":         alert.get("link"),
        "summary":     (alert.get("summary") or "")[:200],
        "weight":      _weight("ProMED"),
    }


def normalize_healthmap_alert(alert: dict) -> dict:
    """Normalize a HealthMap alert"""
    return {
        "source":      "HealthMap",
        "title":       alert.get("title",""),
        "disease":     alert.get("disease"),
        "country":     alert.get("country"),
        "lat":         alert.get("lat"),
        "lon":         alert.get("lon"),
        "severity":    alert.get("severity","low"),
        "published_at":alert.get("published_at"),
        "url":         alert.get("url"),
        "weight":      _weight("HealthMap"),
    }


def normalize_who_published(raw: dict) -> NormalizedCaseRecord:
    """
    Normalize WHO-published burden figures.
    These are from official WHO reports — high quality, annual.
    """
    year = raw.get("latest_year")
    cases = raw.get("reported_cases") or raw.get("people_living_with_hiv")
    deaths = raw.get("annual_deaths")
    cfr = raw.get("cfr_percent", 0)

    return NormalizedCaseRecord(
        disease          = raw.get("disease", "Unknown"),
        source_name      = "WHO GHO",
        source_url       = "https://www.who.int",
        data_quality     = DataQuality.HIGH,
        weight           = _weight("WHO GHO"),
        total_cases      = cases,
        total_deaths     = deaths,
        cfr_percent      = cfr,
        cases_per_million= raw.get("cases_per_million"),
        region_breakdown = raw.get("cases_by_region", {}),
        data_year        = int(year) if year else None,
        is_estimate      = True,
        is_live          = False,
        data_freshness   = f"WHO published report ({year or 'latest'})",
    )


def normalize_who_cholera(raw: dict) -> NormalizedCaseRecord:
    return normalize_who_published(raw)


def normalize_who_measles(raw: dict) -> NormalizedCaseRecord:
    return normalize_who_published(raw)


def normalize_who_hiv(raw: dict) -> NormalizedCaseRecord:
    return normalize_who_published(raw)
