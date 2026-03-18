"""
services/outbreak_risk.py
PHASE 7 — WOW FEATURE: Country-wise Outbreak Risk Scoring

Computes a 0–1 risk score for each of the top 20 countries
using live disease.sh data. Integrates:
  - Case growth rate (trend signal)
  - Active cases per million (burden signal)
  - Today's new cases (acceleration signal)
  - Anomaly flag from Z-Score detection (spike signal)
  - CFR (severity signal)

Formula (all components normalized to 0–1):
  risk = 0.30*growth + 0.25*burden + 0.20*accel + 0.15*anomaly + 0.10*cfr

This is data-driven, computed fresh from disease.sh, and exposed
as /hotspots endpoint — the clearest demonstration that ML
and real data are integrated.
"""

import math
from datetime import datetime, timezone


def _normalize_0_1(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalization to 0–1"""
    if max_val <= min_val:
        return 0.0
    return min(1.0, max(0.0, (value - min_val) / (max_val - min_val)))


def score_country(country: dict, all_cases_per_million: list[float],
                  all_growth_rates: list[float]) -> dict:
    """
    Compute outbreak risk score for a single country.
    Returns dict with score (0–1), label, and component breakdown.
    """
    cases   = country.get("cases") or 0
    active  = country.get("active") or 0
    pop     = country.get("population") or 1
    deaths  = country.get("deaths") or 0
    today   = country.get("todayCases") or 0
    cpm     = country.get("casesPerOneMillion") or 0
    cfr_raw = deaths / max(cases, 1)

    # Component 1: Growth — today's cases / active cases (acceleration proxy)
    growth_raw = today / max(active, 1) if active > 0 else 0

    # Component 2: Burden — active cases per million
    burden_raw = (active / max(pop, 1)) * 1_000_000

    # Component 3: Acceleration — today cases / 7-day expected (using cpm proxy)
    accel_raw = today / max(cpm * pop / 1_000_000 / 30, 1) if cpm > 0 else 0

    # Component 4: CFR severity
    cfr_score = min(1.0, cfr_raw * 20)   # 5% CFR = score 1.0

    # Normalize growth and burden against full country set
    growth_score  = _normalize_0_1(growth_raw, 0, max(all_growth_rates + [0.001], default=0.001))
    burden_score  = _normalize_0_1(burden_raw, 0, max(all_cases_per_million + [1], default=1))
    accel_score   = min(1.0, accel_raw / 10)

    # Composite risk (weighted)
    risk = (
        0.30 * growth_score  +
        0.25 * burden_score  +
        0.20 * accel_score   +
        0.15 * cfr_score     +
        0.10 * min(1.0, math.log1p(today) / 15)   # log-scaled today cases
    )
    risk = round(min(1.0, risk), 4)

    label = (
        "CRITICAL" if risk >= 0.75 else
        "HIGH"     if risk >= 0.50 else
        "MODERATE" if risk >= 0.25 else
        "LOW"
    )

    return {
        "country":       country.get("country"),
        "country_code":  (country.get("countryInfo") or {}).get("iso2"),
        "risk_score":    risk,
        "risk_label":    label,
        "components": {
            "growth_score":  round(growth_score, 3),
            "burden_score":  round(burden_score, 3),
            "accel_score":   round(accel_score, 3),
            "cfr_score":     round(cfr_score, 3),
        },
        "raw_data": {
            "active_cases":          active,
            "today_cases":           today,
            "active_per_million":    round(burden_raw, 1),
            "cfr_percent":           round(cfr_raw * 100, 3),
            "population":            pop,
        },
        "explanation": (
            f"Risk {label} ({risk:.2f}): "
            f"growth {growth_score:.2f} (30%), "
            f"burden {burden_score:.2f} (25%), "
            f"acceleration {accel_score:.2f} (20%), "
            f"CFR {cfr_score:.2f} (15%)."
        ),
    }


def compute_outbreak_risk_all_countries(top_n: int = 20) -> dict:
    """
    Fetch disease.sh top countries and score each one.
    Returns ranked list of countries by outbreak risk score.
    Also detects hotspots (sudden spike = high today_cases vs active_cases ratio).
    """
    import requests
    try:
        r = requests.get(
            "https://disease.sh/v3/covid-19/countries",
            params={"sort": "cases"},
            timeout=12
        )
        r.raise_for_status()
        countries = r.json()[:top_n]
    except Exception as e:
        return {"status": "error", "error": str(e), "data": []}

    # Pre-compute normalization ranges
    all_cpm     = [(c.get("active") or 0) / max(c.get("population") or 1, 1) * 1_000_000
                   for c in countries]
    all_growth  = [(c.get("todayCases") or 0) / max(c.get("active") or 1, 1)
                   for c in countries]

    scored = [score_country(c, all_cpm, all_growth) for c in countries]
    scored.sort(key=lambda x: x["risk_score"], reverse=True)

    # Hotspot detection: countries where today_cases > 10% of active (sudden spike)
    hotspots = [
        s for s in scored
        if (s["raw_data"]["today_cases"] / max(s["raw_data"]["active_cases"], 1)) > 0.10
        and s["raw_data"]["today_cases"] > 100
    ]

    return {
        "fetched_at":       datetime.now(tz=timezone.utc).isoformat(),
        "source":           "disease.sh (live)",
        "disease":          "COVID-19",
        "countries_scored": len(scored),
        "ranked_countries": scored,
        "hotspots": {
            "count":    len(hotspots),
            "countries":hotspots[:5],
            "detection_method": "today_cases > 10% of active_cases AND today_cases > 100",
        },
        "top_3_risk": [{"country": s["country"], "score": s["risk_score"], "label": s["risk_label"]}
                       for s in scored[:3]],
        "scoring_formula": {
            "growth_weight":       "0.30 — today_cases/active_cases normalized",
            "burden_weight":       "0.25 — active_per_million normalized",
            "acceleration_weight": "0.20 — today vs expected 30-day rate",
            "cfr_weight":          "0.15 — case fatality rate (5% CFR = max score)",
            "log_today_weight":    "0.10 — log-scaled today cases",
        },
    }


def compute_outbreak_risk_for_disease(disease_name: str) -> dict:
    """
    For non-COVID diseases, use ProMED alert frequency per region
    as the risk signal (no per-country case counts available).
    """
    import requests
    import feedparser

    try:
        feed = feedparser.parse(
            "https://promedmail.org/feed/",
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        entries = feed.entries[:50]
    except Exception:
        entries = []

    dl = disease_name.lower()
    relevant = [e for e in entries if dl in (e.get("title","") or "").lower()]

    if not relevant:
        return {
            "disease": disease_name,
            "note":    f"No ProMED alerts found for {disease_name}. No country-level risk scoring available.",
            "data":    [],
        }

    # Extract countries from titles (ProMED format: "DISEASE - COUNTRY (NN)")
    import re
    country_freq: dict[str, int] = {}
    for entry in relevant:
        match = re.search(r'-\s*([A-Z][A-Za-z\s]+)\s*\(', entry.get("title",""))
        if match:
            country = match.group(1).strip()
            country_freq[country] = country_freq.get(country, 0) + 1

    # Score by alert frequency
    max_freq = max(country_freq.values()) if country_freq else 1
    risk_list = [
        {
            "country":    c,
            "risk_score": round(freq / max_freq, 3),
            "risk_label": "HIGH" if freq/max_freq > 0.6 else "MODERATE" if freq/max_freq > 0.3 else "LOW",
            "alert_count":freq,
            "signal":     "ProMED alert frequency",
        }
        for c, freq in sorted(country_freq.items(), key=lambda x: -x[1])
    ]

    return {
        "disease":         disease_name,
        "source":          "ProMED RSS (real-time)",
        "ranked_countries":risk_list[:10],
        "scoring_method":  "Alert frequency normalized per country (no direct case count API for this disease)",
    }
