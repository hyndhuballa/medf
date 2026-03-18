"""
api/app.py
FastAPI application — all endpoints delegate to pipeline orchestrator
"""

from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import logging

import cache
from pipeline.orchestrator import run_disease_pipeline
from connectors import connector_promed as promed
from connectors import connector_healthmap as healthmap
from connectors import connector_fluview as fluview
from connectors import connector_diseasesh_countries as ds_countries
from connectors import connector_cdc as cdc
from connectors import connector_ecdc as ecdc
from connectors import connector_opentargets as opentargets
from connectors import connector_pubchem as pubchem
from connectors import connector_ihme as ihme
from connectors import connector_ukgov as ukgov
from services.query_intelligence import parse_query
from services.outbreak_risk import compute_outbreak_risk_all_countries, compute_outbreak_risk_for_disease

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="MedFusion Disease Intelligence API v4",
    description=(
        "8-stage pipeline | 12 sources | Multi-source fusion | "
        "XGBoost forecast | Z-Score+CUSUM anomaly | SIR risk | "
        "Open Targets genomics | PubChem therapeutics | "
        "Explainable intelligence for every output"
    ),
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now():
    return datetime.now(tz=timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════
# PRIMARY ENDPOINT: /disease/{name}
# Runs the full 8-stage pipeline
# ══════════════════════════════════════════════════════════════

@app.get("/disease/{name}")
async def get_disease(
    name: str = Path(..., description="Disease name or query (e.g. 'dengue', 'tb in india', 'covid-19')"),
    include_genomics:     bool = Query(default=True,  description="Include Open Targets gene associations"),
    include_therapeutics: bool = Query(default=True,  description="Include PubChem drug data"),
    days:                 int  = Query(default=30,    ge=7, le=90, description="Days of historical data"),
):
    """
    Full disease intelligence via 8-stage pipeline.
    Integrates: disease.sh / WHO GHO / CDC / FluView / ECDC /
                ProMED / HealthMap / Open Targets / PubChem / IHME India
    Every output includes formula explanation and data provenance.
    """
    try:
        return run_disease_pipeline(name, include_genomics, include_therapeutics, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


# ══════════════════════════════════════════════════════════════
# INSIGHTS ENDPOINT: /insights/{disease}
# ══════════════════════════════════════════════════════════════

@app.get("/insights/{disease}")
async def get_insights(disease: str = Path(...)):
    """
    Cross-domain intelligence insights only.
    Lighter version of /disease — skips timeline fetch.
    """
    result = run_disease_pipeline(
        disease,
        include_genomics=True,
        include_therapeutics=True,
        days=14,
    )
    return {
        "fetched_at":  _now(),
        "disease":     result.get("disease_name", disease),
        "insights":    result.get("insights", []),
        "risk":        (result.get("metrics") or {}).get("risk", {}),
        "cross_domain": {
            "genomics_top_gene":    ((result.get("genomics") or {}).get("data") or {}).get("top_genes", [{}])[0].get("gene_symbol") if isinstance((result.get("genomics") or {}).get("data"), dict) and (result.get("genomics") or {}).get("data", {}).get("top_genes") else None,
            "therapeutics_count":   len(((result.get("therapeutics") or {}).get("data") or {}).get("drugs", []) if isinstance((result.get("therapeutics") or {}).get("data"), dict) else []),
            "who_essential_count":  sum(1 for d in (((result.get("therapeutics") or {}).get("data") or {}).get("drugs",[]) if isinstance((result.get("therapeutics") or {}).get("data"),dict) else []) if d.get("who_essential")),
        },
        "pipeline_stages": result.get("pipeline", {}).get("log", []),
    }


# ══════════════════════════════════════════════════════════════
# TRENDS ENDPOINT: /trends/{disease}
# ══════════════════════════════════════════════════════════════

@app.get("/trends/{disease}")
async def get_trends(
    disease: str = Path(...),
    days:    int  = Query(default=90, ge=7, le=365),
):
    """
    Time-series analysis: trend + XGBoost forecast + Z-Score+CUSUM anomaly.
    All with formula explanations.
    """
    result = run_disease_pipeline(disease, include_genomics=False, include_therapeutics=False, days=min(days, 90))
    metrics = result.get("metrics", {})

    return {
        "fetched_at":  _now(),
        "disease":     result.get("disease_name", disease),
        "trend": {
            "direction":    metrics.get("trend_direction"),
            "pct_change_7d":metrics.get("pct_change_7d"),
            "symbol":       metrics.get("trend_symbol"),
            "explanation":  metrics.get("trend_explanation"),
            "r0":           metrics.get("r0_estimate"),
            "r0_explanation": metrics.get("r0_explanation"),
            "rt":           metrics.get("rt_effective"),
            "doubling_days":metrics.get("doubling_time_days"),
            "doubling_explanation": metrics.get("doubling_explanation"),
        },
        "forecast":    metrics.get("forecast", {}),
        "anomaly":     metrics.get("anomaly", {}),
        "timeline":    metrics.get("timeline", []),
        "smoothed_7d": metrics.get("smoothed_7d", []),
        "data_note":   "COVID-19 historical data from disease.sh. Other diseases: alert-based trend only.",
    }


# ══════════════════════════════════════════════════════════════
# COMPARE ENDPOINT: /compare/{d1}/{d2}
# ══════════════════════════════════════════════════════════════

@app.get("/compare/{disease1}/{disease2}")
async def compare_diseases(
    disease1: str = Path(...),
    disease2: str = Path(...),
):
    """
    Side-by-side comparison across all domains.
    Both diseases run through the full pipeline.
    """
    r1 = run_disease_pipeline(disease1, days=14)
    r2 = run_disease_pipeline(disease2, days=14)

    def _summary(r, name):
        epi     = r.get("epidemiology", {})
        metrics = r.get("metrics", {})
        risk    = (metrics.get("risk") or {})
        gen     = r.get("genomics", {})
        ther    = r.get("therapeutics", {})
        genes   = (gen.get("data") or {}).get("total_gene_associations", 0) if isinstance(gen.get("data"), dict) else 0
        drugs   = len((ther.get("data") or {}).get("drugs", []) if isinstance(ther.get("data"), dict) else [])
        who_d   = sum(1 for d in ((ther.get("data") or {}).get("drugs",[]) if isinstance(ther.get("data"),dict) else []) if d.get("who_essential"))
        return {
            "disease":              r.get("disease_name", name),
            "icd10":                r.get("icd10","N/A"),
            "total_cases":          epi.get("total_cases"),
            "cfr_percent":          epi.get("cfr_percent"),
            "risk_label":           risk.get("label","N/A"),
            "risk_score":           risk.get("composite_score"),
            "r0":                   metrics.get("r0_estimate"),
            "trend":                metrics.get("trend_direction","unknown"),
            "pct_change_7d":        metrics.get("pct_change_7d"),
            "gene_associations":    genes,
            "drugs_identified":     drugs,
            "who_essential_drugs":  who_d,
            "data_source":          epi.get("data_source",""),
            "full_data":            f"/disease/{name}",
        }

    s1 = _summary(r1, disease1)
    s2 = _summary(r2, disease2)

    # Comparative verdict
    higher_cfr    = disease1 if (s1.get("cfr_percent") or 0) > (s2.get("cfr_percent") or 0) else disease2
    higher_risk   = disease1 if (s1.get("risk_score") or 0) > (s2.get("risk_score") or 0) else disease2
    more_genes    = disease1 if s1["gene_associations"] > s2["gene_associations"] else disease2
    better_treated= disease1 if s1["who_essential_drugs"] >= s2["who_essential_drugs"] else disease2

    return {
        "fetched_at": _now(),
        disease1:     s1,
        disease2:     s2,
        "verdict": {
            "higher_cfr":              higher_cfr,
            "higher_composite_risk":   higher_risk,
            "more_gene_associations":  more_genes,
            "better_treatment_access": better_treated,
        },
        "comparative_insights": [
            f"{s1['disease']} CFR {s1.get('cfr_percent',0):.2f}% vs {s2['disease']} CFR {s2.get('cfr_percent',0):.2f}% — {higher_cfr} has higher mortality risk",
            f"{more_genes} has more gene associations in Open Targets ({max(s1['gene_associations'],s2['gene_associations'])} vs {min(s1['gene_associations'],s2['gene_associations'])})",
            f"{better_treated} has better WHO Essential Medicines coverage ({max(s1['who_essential_drugs'],s2['who_essential_drugs'])} drugs on EML)",
        ],
    }


# ══════════════════════════════════════════════════════════════
# GENOMICS: /genomics/{disease}
# ══════════════════════════════════════════════════════════════

@app.get("/genomics/{disease}")
async def get_genomics(disease: str = Path(...), top_n: int = Query(default=10, ge=1, le=20)):
    """Gene-disease associations from Open Targets Platform — ranked by evidence score"""
    cache_key = f"genomics_{disease.lower()}_{top_n}"
    cached = cache.get(cache_key)
    if cached: return cached
    result = opentargets.fetch_gene_associations(disease, top_n=top_n)
    result["fetched_at"] = _now()
    cache.set(cache_key, result, ttl=3600)
    return result


# ══════════════════════════════════════════════════════════════
# THERAPEUTICS: /therapeutics/{disease}
# ══════════════════════════════════════════════════════════════

@app.get("/therapeutics/{disease}")
async def get_therapeutics(disease: str = Path(...)):
    """Drug data from PubChem PUG-REST + WHO Essential Medicines List status"""
    cache_key = f"therapeutics_{disease.lower()}"
    cached = cache.get(cache_key)
    if cached: return cached
    result = pubchem.fetch_drugs_for_disease(disease, max_drugs=6)
    result["fetched_at"] = _now()
    cache.set(cache_key, result, ttl=3600)
    return result


# ══════════════════════════════════════════════════════════════
# ALERTS: /alerts
# ══════════════════════════════════════════════════════════════

@app.get("/alerts")
async def get_alerts(
    disease: str = Query(default="", description="Filter by disease"),
    limit:   int = Query(default=20, ge=1, le=50),
):
    """Real-time alerts from ProMED RSS + HealthMap + CDC FluView — filtered by disease"""
    cache_key = f"alerts_{disease.lower()}_{limit}"
    cached = cache.get(cache_key)
    if cached: return cached

    p  = promed.fetch(max_items=limit)
    h  = healthmap.fetch(max_items=limit)
    fl = fluview.fetch()

    pd = (p.get("data") or {})
    hd = (h.get("data") or {})
    fd = (fl.get("data") or {})

    promed_alerts = pd.get("alerts", [])
    hmap_alerts   = hd.get("alerts", []) if hd else []

    if disease:
        query = parse_query(disease)
        from services.query_intelligence import filter_alerts_for_disease
        promed_alerts = filter_alerts_for_disease(promed_alerts, query)
        hmap_alerts   = filter_alerts_for_disease(hmap_alerts, query)

    result = {
        "fetched_at": _now(),
        "filter": disease or "all",
        "summary": {
            "promed_total":   len(promed_alerts),
            "healthmap_total":len(hmap_alerts),
            "high_severity":  len([a for a in promed_alerts + hmap_alerts if a.get("severity")=="high"]),
            "diseases_mentioned": pd.get("diseases_mentioned",[]),
        },
        "promed_alerts":    promed_alerts[:limit],
        "healthmap_alerts": hmap_alerts[:limit],
        "flu": {
            "ili_pct":  fd.get("latest_week_avg_ili_pct"),
            "network":  fd.get("network"),
            "source":   "CDC FluView ILINet (weekly)",
        },
    }
    cache.set(cache_key, result, ttl=180)
    return result


# ══════════════════════════════════════════════════════════════
# INDIA BURDEN: /india/{disease}
# ══════════════════════════════════════════════════════════════

@app.get("/india/{disease}")
async def get_india(disease: str = Path(...)):
    """India-specific disease burden from IHME GHDx / NVBDCP / MoHFW / WHO India"""
    cache_key = f"india_{disease.lower()}"
    cached = cache.get(cache_key)
    if cached: return cached
    result = ihme.fetch_india_burden(disease)
    result["fetched_at"] = _now()
    cache.set(cache_key, result, ttl=3600)
    return result


# ══════════════════════════════════════════════════════════════
# SPREAD: /spread
# ══════════════════════════════════════════════════════════════

@app.get("/spread")
async def get_spread():
    """COVID-19 geographic spread: top countries + continents + US states + Europe + UK"""
    cached = cache.get("spread_v4")
    if cached: return cached

    countries  = ds_countries.fetch_all_countries(sort="cases", limit=20)
    continents = ds_countries.fetch_continents()
    cdc_data   = cdc.fetch(limit=200)
    ecdc_data  = ecdc.fetch(top_n=10)
    uk_data    = ukgov.fetch_covid_uk()

    result = {
        "fetched_at":    _now(),
        "disease":       "COVID-19",
        "top_countries": (countries.get("data") or {}).get("countries", []),
        "by_continent":  (continents.get("data") or {}).get("continents", []),
        "us_states":     (cdc_data.get("data") or {}).get("top_states_by_new_cases", []),
        "europe":        (ecdc_data.get("data") or {}),
        "uk":            uk_data.get("data") or {"note": uk_data.get("note","UKHSA unavailable")},
    }
    cache.set("spread_v4", result, ttl=300)
    return result


# ══════════════════════════════════════════════════════════════
# WOW FEATURE: /hotspots — country-wise outbreak risk scoring
# ══════════════════════════════════════════════════════════════

@app.get("/hotspots")
async def get_hotspots(
    disease: str = Query(default="covid", description="Disease to score (covid for live country data, others use ProMED)"),
    top_n:   int = Query(default=20, ge=5, le=50),
):
    """
    Country-wise outbreak risk scoring (WOW FEATURE).
    For COVID: live disease.sh data → 5-component risk score per country.
    For others: ProMED alert frequency → risk proxy per country.
    Returns ranked countries with risk scores 0–1 and hotspot detection.
    """
    cache_key = f"hotspots_{disease.lower()}_{top_n}"
    cached = cache.get(cache_key)
    if cached: return cached
    dl = disease.lower().strip()
    if dl in ("covid", "covid-19", "coronavirus"):
        result = compute_outbreak_risk_all_countries(top_n=top_n)
    else:
        result = compute_outbreak_risk_for_disease(disease)
    result["fetched_at"] = _now()
    cache.set(cache_key, result, ttl=300)
    return result


# ══════════════════════════════════════════════════════════════
# SOURCES: /sources
# ══════════════════════════════════════════════════════════════

@app.get("/sources")
async def get_sources():
    return {
        "fetched_at": _now(),
        "total_sources": 12,
        "cache_stats": cache.stats(),
        "sources": [
            {"name":"disease.sh",            "url":"https://disease.sh",                            "update":"Live",     "domain":"Epidemiology",  "diseases":"COVID-19"},
            {"name":"WHO GHO OData",          "url":"https://ghoapi.azureedge.net/api",             "update":"Annual",   "domain":"Epidemiology",  "diseases":"Malaria/TB/Dengue"},
            {"name":"CDC Open Data",          "url":"https://data.cdc.gov",                         "update":"Daily",    "domain":"Epidemiology",  "diseases":"US COVID"},
            {"name":"CDC FluView",            "url":"https://gis.cdc.gov/grasp/flu2/",              "update":"Weekly",   "domain":"Epidemiology",  "diseases":"Influenza"},
            {"name":"ECDC Open Data",         "url":"https://opendata.ecdc.europa.eu",              "update":"Daily",    "domain":"Epidemiology",  "diseases":"Europe COVID"},
            {"name":"UKHSA Dashboard",        "url":"https://ukhsa-dashboard.data.gov.uk",         "update":"Daily",    "domain":"Epidemiology",  "diseases":"UK COVID/Flu"},
            {"name":"ProMED RSS",             "url":"https://promedmail.org/feed/",                 "update":"Realtime", "domain":"Alerts",        "diseases":"ALL diseases"},
            {"name":"HealthMap",              "url":"https://healthmap.org",                        "update":"Realtime", "domain":"Alerts",        "diseases":"ALL diseases"},
            {"name":"Open Targets (GraphQL)", "url":"https://api.platform.opentargets.org/api/v4", "update":"Quarterly","domain":"Genomics",      "diseases":"All mapped"},
            {"name":"PubChem PUG-REST",       "url":"https://pubchem.ncbi.nlm.nih.gov/rest/pug",   "update":"Frequent", "domain":"Therapeutics",  "diseases":"All drugs"},
            {"name":"IHME GHDx/NVBDCP",       "url":"https://ghdx.healthdata.org",                 "update":"Annual",   "domain":"India burden",  "diseases":"Malaria/TB/Dengue/HIV"},
            {"name":"WHO GHO India filter",   "url":"https://ghoapi.azureedge.net/api",             "update":"Annual",   "domain":"India specific","diseases":"All WHO India"},
        ],
        "pipeline_stages": [
            "STAGE 1: fetch_sources()",
            "STAGE 2: normalize_sources() → NormalizedCaseRecord",
            "STAGE 3: fuse_records() → weighted merge + conflict resolution",
            "STAGE 4: compute_metrics() → trend, R0, Rt, doubling time, CFR",
            "STAGE 5: run_ml() → XGBoost forecast, Z-Score+CUSUM anomaly, SIR risk",
            "STAGE 6: fetch_cross_domain() → Open Targets genomics, PubChem therapeutics",
            "STAGE 7: filter_alerts() → ProMED + HealthMap disease-filtered",
            "STAGE 8: generate_response() → explainable insights + unified JSON",
        ],
    }


@app.get("/")
def root():
    return {
        "name":    "MedFusion Disease Intelligence API v4",
        "version": "4.0.0",
        "sources": 12,
        "pipeline": "8-stage orchestrated pipeline — fetch→normalize→fuse→metrics→ml→cross-domain→alerts→insights",
        "key_endpoints": {
            "/disease/{name}":        "Full intelligence (8-stage pipeline) + confidence score",
            "/hotspots":               "★ WOW: Country-wise outbreak risk scoring (live)",
            "/insights/{disease}":    "Cross-domain insights",
            "/trends/{disease}":      "Trend + forecast + anomaly",
            "/compare/{d1}/{d2}":     "Side-by-side comparison",
            "/genomics/{disease}":    "Open Targets gene associations",
            "/therapeutics/{disease}":"PubChem drug data",
            "/alerts":                "ProMED + HealthMap real-time",
            "/india/{disease}":       "India burden (IHME/NVBDCP)",
            "/spread":                "Geographic COVID spread",
            "/sources":               "All 12 sources + pipeline stages",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": _now(), "version": "4.0.0", "sources": 12}
