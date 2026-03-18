"""
pipeline/orchestrator.py  — SHOWSTOPPER VERSION

8-stage pipeline producing a judge-facing intelligence report.

STAGE 1: fetch_sources()        — parallel fetch all relevant sources
STAGE 2: normalize_sources()    — every source → NormalizedCaseRecord
STAGE 3: fuse_records()         — weighted merge (WHO=0.5, CDC=0.3, others=0.2)
STAGE 4: compute_metrics()      — trend (advanced), R0, Rt, doubling time, CFR
STAGE 5: run_ml()               — XGBoost forecast, Z-Score+CUSUM anomaly, SIR risk
STAGE 6: fetch_cross_domain()   — Open Targets genomics, PubChem therapeutics
STAGE 6b: outbreak_risk()       — country-wise outbreak risk leaderboard (WOW)
STAGE 7: filter_alerts()        — ProMED + HealthMap disease-filtered
STAGE 8: assemble_report()      — headline + ML + insights + explanations

Example flow for "dengue in india":
  S1: fetch WHO GHO dengue + ProMED 50 alerts + HealthMap
  S2: normalize WHO GHO → NormalizedCaseRecord(weight=0.50)
  S3: single source → direct, confidence computed
  S4: no timeline → trend unknown; CFR = 26000/5200000 = 0.5%
  S5: no timeline → forecast skipped, ProMED anomaly proxy
  S6: Open Targets NS1 gene (score 0.78), PubChem Paracetamol
  S6b: ProMED frequency → India rank 1 (8 alerts), Brazil rank 2
  S7: 8 alerts match "dengue" in title/body
  S8: headline "⚠️ Dengue surging in India — 22% in 7 days"
      insights: 8 data-driven statements
      explanation: risk/trend/forecast WHY blocks
"""

import time
import logging
from typing import Optional
from datetime import datetime, timezone

import cache
from services.query_intelligence   import parse_query, filter_alerts_for_disease
from services.epidemiology         import (
    compute_pct_change_7d, detect_trend, estimate_r0, estimate_rt,
    estimate_doubling_time, compute_risk_score, moving_average,
    classify_trend_advanced,
)
from services.explainability       import explain_data_fusion
from services.intelligence_report  import assemble_intelligence_report
from services.outbreak_risk        import (
    compute_outbreak_risk_all_countries,
    compute_outbreak_risk_for_disease,
)
from fusion.normalizer import (
    normalize_diseasesh, normalize_who_malaria, normalize_who_tb,
    normalize_who_dengue, normalize_cdc_flu, normalize_ecdc,
)
from fusion.merger    import fuse_records
from ml.forecast      import forecast_xgboost
from ml.anomaly       import detect_anomalies

logger = logging.getLogger("medfusion.pipeline")


# ── STAGE 1: Fetch ────────────────────────────────────────────────────────────

def _fetch_epi_sources(disease_canonical: str) -> dict:
    from connectors import (
        connector_diseasesh_current    as ds_current,
        connector_diseasesh_historical as ds_hist,
        connector_who_diseases         as who_diseases,
        connector_fluview              as fluview,
        connector_ecdc                 as ecdc,
        connector_cdc                  as cdc,
    )
    sources = {}
    if disease_canonical in ("covid-19",):
        for name, fn in [
            ("diseasesh_current",  lambda: ds_current.fetch()),
            ("diseasesh_hist",     lambda: ds_hist.fetch(lastdays=90)),
            ("cdc",                lambda: cdc.fetch(limit=200)),
            ("ecdc",               lambda: ecdc.fetch(top_n=10)),
        ]:
            try:    sources[name] = fn()
            except Exception as e: logger.warning(f"[S1] {name}: {e}")

    elif disease_canonical == "malaria":
        try: sources["who_malaria"] = who_diseases.fetch_malaria()
        except Exception as e: logger.warning(f"[S1] WHO malaria: {e}")

    elif disease_canonical == "tuberculosis":
        try: sources["who_tb"] = who_diseases.fetch_tuberculosis()
        except Exception as e: logger.warning(f"[S1] WHO tb: {e}")

    elif disease_canonical == "dengue":
        try: sources["who_dengue"] = who_diseases.fetch_dengue()
        except Exception as e: logger.warning(f"[S1] WHO dengue: {e}")

    elif disease_canonical in ("influenza", "flu"):
        try: sources["fluview"] = fluview.fetch()
        except Exception as e: logger.warning(f"[S1] FluView: {e}")

    elif disease_canonical == "cholera":
        try: sources["who_cholera"] = who_diseases.fetch_cholera()
        except Exception as e: logger.warning(f"[S1] WHO cholera: {e}")

    elif disease_canonical == "measles":
        try: sources["who_measles"] = who_diseases.fetch_measles()
        except Exception as e: logger.warning(f"[S1] WHO measles: {e}")

    elif disease_canonical == "hiv":
        try: sources["who_hiv"] = who_diseases.fetch_hiv()
        except Exception as e: logger.warning(f"[S1] WHO HIV: {e}")

    else:
        # All other diseases: ebola, mpox, nipah, h5n1, typhoid, yellow_fever, zika
        try:
            pub = who_diseases.fetch_published(disease_canonical)
            if pub.get("status") == "ok":
                sources["who_published"] = pub
        except Exception as e: logger.warning(f"[S1] WHO published {disease_canonical}: {e}")

    return sources


def _fetch_alerts_raw(limit: int = 30) -> tuple[list, list]:
    from connectors import connector_promed as promed
    from connectors import connector_healthmap as healthmap
    p_raw, h_raw = [], []
    try:
        p     = promed.fetch(max_items=limit)
        p_raw = (p.get("data") or {}).get("alerts", [])
    except Exception as e: logger.warning(f"[S1] ProMED: {e}")
    try:
        h     = healthmap.fetch(max_items=limit)
        h_raw = (h.get("data") or {}).get("alerts", []) if h.get("data") else []
    except Exception as e: logger.warning(f"[S1] HealthMap: {e}")
    return p_raw, h_raw


# ── STAGE 2: Normalize ────────────────────────────────────────────────────────

def _normalize(canonical: str, sources: dict) -> list:
    records = []
    mapping = {
        "diseasesh_current": lambda s: normalize_diseasesh((s.get("data") or {}), "COVID-19"),
        "who_malaria":       lambda s: normalize_who_malaria(s.get("data") or {}),
        "who_tb":            lambda s: normalize_who_tb(s.get("data") or {}),
        "who_dengue":        lambda s: normalize_who_dengue(s.get("data") or {}),
        "fluview":           lambda s: normalize_cdc_flu(s.get("data") or {}),
        "who_cholera":       lambda s: normalize_who_published(s.get("data") or {}),
        "who_measles":       lambda s: normalize_who_published(s.get("data") or {}),
        "who_hiv":           lambda s: normalize_who_published(s.get("data") or {}),
        "who_published":     lambda s: normalize_who_published(s.get("data") or {}),
        "ecdc":              lambda s: normalize_ecdc(s.get("data") or {}),
    }
    for key, fn in mapping.items():
        if key in sources and sources[key]:
            try:
                rec = fn(sources[key])
                if rec: records.append(rec)
            except Exception as e: logger.warning(f"[S2] normalize {key}: {e}")
    return records


# ── STAGE 4+5: Metrics + ML ───────────────────────────────────────────────────

def _run_metrics_and_ml(canonical: str, fused, sources: dict, query) -> dict:
    # Extract timeline (COVID only currently)
    timeline = []
    if "diseasesh_hist" in sources:
        timeline = (sources["diseasesh_hist"].get("data") or {}).get("timeline", [])

    # Advanced trend (exponential/linear/plateau/volatile + velocity)
    adv = classify_trend_advanced(timeline) if timeline else {
        "direction": "unknown", "pct_change_7d": None,
        "growth_type": "unknown", "velocity": "stable",
        "smoothed_7d": [], "raw_last_7": [], "explanation": "No timeline",
    }
    pct_change = adv.get("pct_change_7d")
    trend_dir, _ = detect_trend(pct_change)

    # R0, Rt, doubling
    si = query.serial_int
    r0, r0_expl  = estimate_r0(timeline, si)
    rt, _        = estimate_rt(timeline, si)
    dbl, dbl_expl= estimate_doubling_time(timeline)

    # SIR risk score
    active = fused.active_cases or 0
    cfr_frac = (fused.cfr_percent or 0) / 100
    risk_dict, risk_expl = compute_risk_score(timeline, active, 8_000_000_000, cfr_frac, pct_change, r0)

    # XGBoost forecast
    forecast_result = {}
    if timeline:
        try:
            fcast = forecast_xgboost(timeline, key="cases", periods=14)
            next14    = fcast.get("forecast", [])
            growth_pct = round((next14[6] - next14[0]) / max(next14[0], 1) * 100, 1) if len(next14) > 6 else None
            forecast_result = {
                "model":             fcast.get("model", ""),
                "next_14_days":      next14,
                "upper_bound":       fcast.get("upper", []),
                "lower_bound":       fcast.get("lower", []),
                "future_dates":      fcast.get("future_dates", []),
                "predicted_day1":    next14[0] if next14 else None,
                "predicted_day7":    next14[6] if len(next14) > 6 else None,
                "predicted_7d_growth_pct": growth_pct,
            }
        except Exception as e:
            forecast_result = {"error": str(e)}

    # Z-Score + CUSUM anomaly
    anomaly_result = {}
    if timeline:
        try:
            vals    = [float(pt.get("cases") or 0) for pt in timeline]
            dates   = [pt.get("date", "") for pt in timeline]
            det     = detect_anomalies(vals)
            flagged = [dates[i] for i in det.get("anomaly_indices", []) if i < len(dates)]
            anomaly_result = {
                "method":        det.get("method", ""),
                "anomaly_count": det.get("anomaly_count", 0),
                "flagged_dates": flagged,
                "z_scores":      det.get("z_scores", [])[-7:],
            }
        except Exception as e:
            anomaly_result = {"error": str(e)}

    smooth_vals = []
    if timeline:
        vals = [float(pt.get("cases") or 0) for pt in timeline]
        smooth_vals = moving_average(vals, window=7)

    return {
        "timeline":           timeline[-14:] if timeline else [],
        "pct_change_7d":      pct_change,
        "trend_direction":    trend_dir.value,
        "trend_symbol":       "↑" if trend_dir.value=="rising" else "↓" if trend_dir.value=="declining" else "→",
        "growth_type":        adv.get("growth_type", "unknown"),
        "velocity":           adv.get("velocity", "stable"),
        "trend_explanation":  adv.get("explanation", ""),
        "r0_estimate":        r0,
        "r0_explanation":     r0_expl,
        "rt_effective":       rt,
        "doubling_time_days": dbl,
        "doubling_explanation":dbl_expl,
        "risk":               {**risk_dict, "explanation": risk_expl},
        "forecast":           forecast_result,
        "anomaly":            anomaly_result,
        "smoothed_7d":        smooth_vals[-14:] if smooth_vals else [],
    }


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────

def run_disease_pipeline(
    raw_query:            str,
    include_genomics:     bool = True,
    include_therapeutics: bool = True,
    days:                 int  = 30,
) -> dict:
    """
    Full 8-stage pipeline → judge-facing intelligence report.
    """
    start_time = time.time()
    query      = parse_query(raw_query)
    cache_key  = f"pipe_{query.canonical}_{query.region}_{days}_{include_genomics}_{include_therapeutics}"
    cached     = cache.get(cache_key)
    if cached:
        cached["cache_hit"] = True
        return cached

    log = []

    # ── S1: FETCH ────────────────────────────────────────────────
    log.append("STAGE 1: Fetching sources")
    epi_sources       = _fetch_epi_sources(query.canonical)
    promed_raw, h_raw = _fetch_alerts_raw()
    log.append(f"  → {len(epi_sources)} epi sources | {len(promed_raw)} ProMED | {len(h_raw)} HealthMap alerts")

    # ── S2: NORMALIZE ────────────────────────────────────────────
    log.append("STAGE 2: Normalizing to unified schema")
    records = _normalize(query.canonical, epi_sources)
    log.append(f"  → {len(records)} normalized records")

    # ── S3: FUSE ─────────────────────────────────────────────────
    log.append("STAGE 3: Multi-source fusion (WHO=0.50, CDC=0.30, others=0.20)")
    fused      = fuse_records(records, query.disease, query.icd10)
    confidence = getattr(fused, "confidence", {})
    log.append(f"  → Fused from {fused.source_count} source(s) | method: {fused.fusion_method}")
    log.append(f"  → Confidence: {confidence.get('label','?')} ({confidence.get('overall',0):.0%}) | agreement: {confidence.get('agreement',0):.0%}")

    # ── S4+S5: METRICS + ML ──────────────────────────────────────
    log.append("STAGE 4: Computing epidemiological metrics (R0, Rt, CFR, doubling time)")
    log.append("STAGE 5: Running ML — XGBoost forecast + Z-Score+CUSUM anomaly + SIR risk")
    metrics = _run_metrics_and_ml(query.canonical, fused, epi_sources, query)
    fcast   = metrics.get("forecast") or {}
    anomaly = metrics.get("anomaly") or {}
    risk    = metrics.get("risk") or {}
    log.append(f"  → Trend: {metrics['trend_direction']} | growth_type: {metrics['growth_type']} | R0: {metrics['r0_estimate']}")
    log.append(f"  → Risk: {risk.get('label','?')} (score {risk.get('composite_score','?')}/100)")
    log.append(f"  → Forecast Day1: {fcast.get('predicted_day1','N/A')} | Anomalies: {anomaly.get('anomaly_count',0)}")

    # ── S6: CROSS-DOMAIN ─────────────────────────────────────────
    log.append("STAGE 6: Fetching cross-domain — Open Targets (genomics) + PubChem (therapeutics)")
    genomics_data, therapeutics_data = {}, {}
    if include_genomics:
        g_key = f"genomics_{query.canonical}"
        genomics_data = cache.get(g_key) or {}
        if not genomics_data:
            try:
                from connectors import connector_opentargets as ot
                genomics_data = ot.fetch_gene_associations(query.canonical, top_n=8)
                cache.set(g_key, genomics_data, ttl=86400)
            except Exception as e:
                genomics_data = {"status": "error", "error": str(e)}
    if include_therapeutics:
        t_key = f"therapeutics_{query.canonical}"
        therapeutics_data = cache.get(t_key) or {}
        if not therapeutics_data:
            try:
                from connectors import connector_pubchem as pc
                therapeutics_data = pc.fetch_drugs_for_disease(query.canonical, max_drugs=4)
                cache.set(t_key, therapeutics_data, ttl=86400)
            except Exception as e:
                therapeutics_data = {"status": "error", "error": str(e)}

    # ── S6b: OUTBREAK RISK LEADERBOARD ───────────────────────────
    log.append("STAGE 6b: Country-wise outbreak risk leaderboard")
    top_risk_regions = []
    try:
        if query.canonical in ("covid-19", "covid", "coronavirus"):
            r_data = compute_outbreak_risk_all_countries(top_n=15)
            top_risk_regions = r_data.get("ranked_countries", [])[:5]
        else:
            r_data = compute_outbreak_risk_for_disease(query.canonical)
            top_risk_regions = r_data.get("ranked_countries", [])[:5]
        log.append(f"  → {len(top_risk_regions)} regions scored for {query.canonical}")
    except Exception as e:
        logger.warning(f"[S6b] Leaderboard: {e}")

    # ── S7: ALERTS ───────────────────────────────────────────────
    log.append("STAGE 7: Filtering ProMED + HealthMap by disease + synonyms")
    f_promed = filter_alerts_for_disease(promed_raw, query)
    f_hmap   = filter_alerts_for_disease(h_raw, query)
    all_alerts = f_promed + f_hmap
    log.append(f"  → {len(f_promed)} ProMED + {len(f_hmap)} HealthMap matched")

    combined_alerts = {
        "summary": {
            "total_matching":    len(all_alerts),
            "high_severity":     len([a for a in all_alerts if a.get("severity") == "high"]),
            "diseases_mentioned":list({a.get("disease","") for a in promed_raw if a.get("disease")}),
        },
        "promed_alerts":    f_promed[:5],
        "healthmap_alerts": f_hmap[:5],
    }

    # India context
    india_data = {}
    try:
        from connectors import connector_ihme as ihme
        india_data = (ihme.fetch_india_burden(query.canonical).get("data") or {})
    except Exception as e:
        logger.warning(f"[S6] IHME: {e}")

    # ── S8: ASSEMBLE INTELLIGENCE REPORT ─────────────────────────
    log.append("STAGE 8: Assembling intelligence report — headline + ML + insights + explanations")
    report = assemble_intelligence_report(
        disease          = query.canonical,
        query            = raw_query,
        fused            = fused,
        metrics          = metrics,
        ml_predictions   = {},
        alerts           = combined_alerts,
        genomics         = genomics_data,
        therapeutics     = therapeutics_data,
        india_data       = india_data,
        top_risk_regions = top_risk_regions,
        confidence       = confidence,
    )
    log.append(f"  → Headline: {report['headline'][:70]}")
    log.append(f"  → {len(report['insights'])} insights generated")

    elapsed = round(time.time() - start_time, 3)

    result = {
        # ════════════════════════════════════════════════════════
        # INTELLIGENCE REPORT — judge-facing structure
        # ════════════════════════════════════════════════════════
        "fetched_at":  datetime.now(tz=timezone.utc).isoformat(),
        "query":       raw_query,
        "disease":     fused.disease,
        "icd10":       fused.icd10,

        # ★ 1. HEADLINE
        "headline":     report["headline"],
        "growth_signal":report["growth_signal"],

        # ★ 2. ML PREDICTIONS (centerpiece)
        "ml_predictions": report["ml_predictions"],

        # ★ 3. CORE METRICS
        "metrics": report["metrics"],

        # ★ 4. RISK SCORE
        "risk": report["risk"],

        # ★ 5. TOP RISK REGIONS (WOW)
        "top_risk_regions": report["top_risk_regions"],

        # ★ 6. SMART INSIGHTS
        "insights": report["insights"],

        # ★ 7. DEEP EXPLANATION
        "explanation": report["explanation"],

        # ★ 8. DATA CONFIDENCE
        "confidence": report["confidence"],

        # ─── Supporting detail ───────────────────────────────────
        "parsed_query": {
            "canonical":  query.canonical,
            "region":     query.region,
            "icd10":      query.icd10,
        },
        "epidemiology": {
            **fused.to_dict(),
            "data_fusion": explain_data_fusion(fused.provenance, fused.source_count),
        },
        "alerts":        combined_alerts,
        "genomics":      genomics_data,
        "therapeutics":  therapeutics_data,
        "india_context": india_data,
        "pipeline": {
            "stages": 8,
            "log":    log,
            "elapsed_seconds": elapsed,
            "sources_fetched": list(epi_sources.keys()),
            "cache_hit": False,
        },
    }

    cache.set(cache_key, result, ttl=300)
    return result
