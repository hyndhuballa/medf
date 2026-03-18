"""
fusion/merger.py  — UPGRADED
True weighted multi-source fusion with conflict resolution + confidence scoring.

Source weights (normalized to sum to 1.0 per fusion pool):
  WHO GHO   → 0.50  (gold standard, peer-reviewed estimates)
  CDC       → 0.30  (authoritative national data)
  ECDC      → 0.20  (regional authority)
  disease.sh→ 0.20  (aggregator, medium trust)
  CDC FluView→0.15  (surveillance proxy)
  IHME      → 0.15  (modeled estimate)
  ProMED    → 0.10  (alert-based, not case counts)
  HealthMap → 0.10

Confidence score formula:
  completeness  = filled_fields / total_fields          (0–1)
  agreement     = 1 - (std_dev / mean) across sources   (0–1, 1=perfect agreement)
  freshness     = 1.0 if live, 0.7 if daily, 0.4 if annual
  overall       = 0.4*completeness + 0.35*agreement + 0.25*freshness
"""

import math
from typing import Optional
from schemas.models import NormalizedCaseRecord, DataQuality, FusedDiseaseRecord
from datetime import datetime, timezone


# ─── True source weights (PHASE 1 requirement) ───────────────────────────────
TRUE_WEIGHTS = {
    "WHO GHO":      0.50,
    "CDC Open Data":0.30,
    "ECDC":         0.20,
    "disease.sh":   0.20,
    "CDC FluView":  0.15,
    "IHME":         0.15,
    "UKHSA":        0.15,
    "ProMED":       0.10,
    "HealthMap":    0.10,
}

FRESHNESS_SCORE = {
    "live":    1.00,   # disease.sh ~10min
    "daily":   0.70,   # CDC, ECDC daily
    "weekly":  0.50,   # FluView weekly
    "annual":  0.25,   # WHO, IHME annual estimates
    "unknown": 0.30,
}

KEY_FIELDS = ["total_cases", "active_cases", "total_deaths", "cfr_percent",
              "today_cases", "cases_per_million"]


# ─── Weighted average ─────────────────────────────────────────────────────────
def _weighted_avg(pairs: list[tuple[float, float]]) -> Optional[float]:
    """
    True weighted average: Σ(value × weight) / Σ(weight)
    """
    valid = [(v, w) for v, w in pairs if v is not None and not math.isnan(float(v))]
    if not valid:
        return None
    total_w = sum(w for _, w in valid)
    return sum(v * w for v, w in valid) / total_w if total_w > 0 else None


# ─── PHASE 1: Conflict resolution functions ──────────────────────────────────

def resolve_cases_conflict(records: list[NormalizedCaseRecord]) -> tuple[Optional[int], str, str]:
    """
    Resolve conflicting case counts across sources.
    
    Strategy:
    1. Compute weighted average using TRUE_WEIGHTS
    2. Detect outliers (>2 std devs from mean) and downweight them
    3. Return final value + provenance string + method used
    
    Formula: weighted_cases = Σ(source_cases × TRUE_WEIGHT[source]) / Σ(weights)
    """
    candidates = [
        (r.total_cases, TRUE_WEIGHTS.get(r.source_name, 0.10), r.source_name)
        for r in records if r.total_cases is not None
    ]
    if not candidates:
        return None, "none", "no_data"

    if len(candidates) == 1:
        v, w, src = candidates[0]
        return int(v), src, "single_source"

    # Outlier detection: flag values >2σ from unweighted mean
    values    = [v for v, _, _ in candidates]
    mean_val  = sum(values) / len(values)
    std_val   = math.sqrt(sum((v - mean_val)**2 for v in values) / len(values)) if len(values) > 1 else 0

    filtered  = []
    outliers  = []
    for v, w, src in candidates:
        if std_val > 0 and abs(v - mean_val) > 2 * std_val:
            outliers.append(src)
            filtered.append((v, w * 0.3, src))   # downweight outlier by 70%
        else:
            filtered.append((v, w, src))

    result = _weighted_avg([(v, w) for v, w, _ in filtered])
    method = "weighted_avg_true_weights" + (f"_outliers_downweighted({','.join(outliers)})" if outliers else "")
    sources = "+".join(s for _, _, s in filtered)
    return int(result) if result else None, sources, method


def resolve_deaths_conflict(records: list[NormalizedCaseRecord],
                            fused_cases: Optional[int]) -> tuple[Optional[int], str, str]:
    """
    Resolve conflicting death counts.
    Additional consistency check: deaths cannot exceed 60% of cases (biological upper bound).
    Formula same as resolve_cases_conflict + CFR consistency check.
    """
    candidates = [
        (r.total_deaths, TRUE_WEIGHTS.get(r.source_name, 0.10), r.source_name)
        for r in records if r.total_deaths is not None
    ]
    if not candidates:
        return None, "none", "no_data"

    result = _weighted_avg([(v, w) for v, w, _ in candidates])
    if result and fused_cases and result > fused_cases * 0.60:
        result = fused_cases * 0.10   # hard cap at 10% CFR as biological sanity
        method = "weighted_avg_capped_biological_limit"
    else:
        method = "weighted_avg_true_weights"
    sources = "+".join(s for _, _, s in candidates)
    return int(result) if result else None, sources, method


def merge_time_series(series_list: list[list[dict]]) -> list[dict]:
    """
    Merge multiple time-series from different sources.
    Strategy: for each date, take weighted average of available values.
    Sources closer to WHO weight higher.
    Currently we have one time-series source (disease.sh).
    Returns merged series with smoothed values.
    """
    if not series_list:
        return []
    if len(series_list) == 1:
        return series_list[0]

    # Build date → {source: value} map
    date_map: dict[str, list[tuple[float, float]]] = {}
    for i, series in enumerate(series_list):
        weight = max(0.10, 0.50 - i * 0.15)   # diminishing weight per source
        for pt in series:
            date = pt.get("date","")
            if date not in date_map:
                date_map[date] = []
            if pt.get("cases") is not None:
                date_map[date].append((float(pt["cases"]), weight))

    merged = []
    for date in sorted(date_map.keys()):
        fused_val = _weighted_avg(date_map[date])
        merged.append({"date": date, "cases": int(fused_val) if fused_val else 0})
    return merged


# ─── PHASE 4: Confidence scoring ─────────────────────────────────────────────

def compute_confidence_score(records: list[NormalizedCaseRecord],
                              fused: "FusedDiseaseRecord") -> dict:
    """
    Confidence score for the fused output.

    Components:
      completeness = filled_key_fields / total_key_fields          (weight 0.40)
      agreement    = 1 - coefficient_of_variation(case_values)     (weight 0.35)
      freshness    = weighted avg of source freshness scores        (weight 0.25)

    Overall = 0.40*completeness + 0.35*agreement + 0.25*freshness

    Returns dict with all three components + overall (0–1).
    """
    # Completeness
    filled = sum(1 for f in KEY_FIELDS if getattr(fused, f, None) is not None)
    completeness = filled / len(KEY_FIELDS)

    # Agreement — CV of case values across sources
    case_vals = [r.total_cases for r in records if r.total_cases is not None]
    if len(case_vals) >= 2:
        mean_c = sum(case_vals) / len(case_vals)
        std_c  = math.sqrt(sum((v - mean_c)**2 for v in case_vals) / len(case_vals))
        cv     = std_c / mean_c if mean_c > 0 else 1.0
        agreement = max(0.0, 1.0 - cv)
    elif len(case_vals) == 1:
        agreement = 0.70   # single source — moderate agreement by definition
    else:
        agreement = 0.30   # no case data

    # Freshness
    def _freshness(rec: NormalizedCaseRecord) -> float:
        if rec.is_live:          return FRESHNESS_SCORE["live"]
        fresh = rec.data_freshness.lower()
        if "10 min" in fresh or "live" in fresh: return FRESHNESS_SCORE["live"]
        if "daily" in fresh or "day" in fresh:   return FRESHNESS_SCORE["daily"]
        if "week" in fresh:                       return FRESHNESS_SCORE["weekly"]
        if "annual" in fresh or "year" in fresh:  return FRESHNESS_SCORE["annual"]
        return FRESHNESS_SCORE["unknown"]

    freshness_vals = [(_freshness(r), TRUE_WEIGHTS.get(r.source_name, 0.10)) for r in records]
    freshness = _weighted_avg(freshness_vals) or 0.30

    overall = round(0.40 * completeness + 0.35 * agreement + 0.25 * freshness, 3)

    return {
        "overall":      overall,
        "label":        "HIGH" if overall >= 0.7 else "MEDIUM" if overall >= 0.4 else "LOW",
        "completeness": round(completeness, 3),
        "agreement":    round(agreement, 3),
        "freshness":    round(freshness, 3),
        "source_count": len(records),
        "explanation":  (
            f"Confidence {overall:.0%}: "
            f"completeness {completeness:.0%} ({filled}/{len(KEY_FIELDS)} key fields), "
            f"source agreement {agreement:.0%} across {len(case_vals)} sources with case data, "
            f"data freshness {freshness:.0%}."
        ),
    }


# ─── Main fusion function ─────────────────────────────────────────────────────

def fuse_records(records: list[NormalizedCaseRecord], disease: str,
                 icd10: Optional[str] = None) -> "FusedDiseaseRecord":
    """
    Multi-source fusion with conflict resolution and confidence scoring.
    All upgrade phases applied here.
    """
    if not records:
        empty = FusedDiseaseRecord(
            disease=disease, icd10=icd10,
            total_cases=None, active_cases=None, total_deaths=None,
            cfr_percent=None, today_cases=None, cases_per_million=None,
            region_breakdown={}, source_count=0,
            fusion_method="no_sources",
        )
        empty.confidence = compute_confidence_score([], empty)
        return empty

    # STEP 1: Resolve cases (conflict resolution)
    total_cases, cases_src, cases_method = resolve_cases_conflict(records)

    # STEP 2: Resolve deaths (with biological consistency check)
    total_deaths, deaths_src, deaths_method = resolve_deaths_conflict(records, total_cases)

    # STEP 3: CFR — compute from fused data first, else weighted avg
    cfr: Optional[float] = None
    cfr_method = "no_data"
    if total_cases and total_deaths and total_cases > 0:
        cfr = round(total_deaths / total_cases * 100, 4)
        cfr_method = "computed_from_fused_cases_deaths"
    else:
        cfr_pairs = [(r.cfr_percent, TRUE_WEIGHTS.get(r.source_name, 0.10))
                     for r in records if r.cfr_percent is not None]
        if cfr_pairs:
            cfr_avg = _weighted_avg(cfr_pairs)
            cfr = round(cfr_avg, 4) if cfr_avg else None
            cfr_method = "weighted_avg_source_cfrs"

    # STEP 4: Active — live source priority
    live_recs   = sorted([r for r in records if r.is_live and r.active_cases is not None],
                          key=lambda r: TRUE_WEIGHTS.get(r.source_name, 0.10), reverse=True)
    active_cases = live_recs[0].active_cases if live_recs else None
    active_src   = live_recs[0].source_name if live_recs else "not_available"

    # STEP 5: Today's cases
    today_recs  = sorted([r for r in records if r.today_cases is not None],
                          key=lambda r: TRUE_WEIGHTS.get(r.source_name, 0.10), reverse=True)
    today_cases = today_recs[0].today_cases if today_recs else None

    # STEP 6: Cases per million
    cpm_recs = sorted([r for r in records if r.cases_per_million is not None],
                       key=lambda r: TRUE_WEIGHTS.get(r.source_name, 0.10), reverse=True)
    cases_per_million = cpm_recs[0].cases_per_million if cpm_recs else None

    # STEP 7: Region breakdown — highest-weight source wins per region
    region_best: dict[str, tuple] = {}
    for rec in sorted(records, key=lambda r: TRUE_WEIGHTS.get(r.source_name, 0.10), reverse=True):
        for region, value in rec.region_breakdown.items():
            w = TRUE_WEIGHTS.get(rec.source_name, 0.10)
            if region not in region_best or w > region_best[region][1]:
                region_best[region] = (value, w)
    region_breakdown = {r: v for r, (v, _) in region_best.items()}

    freshness = sorted(records, key=lambda r: (r.is_live, TRUE_WEIGHTS.get(r.source_name,0.10)),
                        reverse=True)[0].data_freshness

    fused = FusedDiseaseRecord(
        disease          = disease,
        icd10            = icd10,
        total_cases      = total_cases,
        active_cases     = active_cases,
        total_deaths     = total_deaths,
        cfr_percent      = cfr,
        today_cases      = today_cases,
        cases_per_million = cases_per_million,
        region_breakdown = region_breakdown,
        provenance       = {
            "total_cases":  {"source": cases_src,  "method": cases_method},
            "total_deaths": {"source": deaths_src, "method": deaths_method},
            "cfr_percent":  {"method": cfr_method},
            "active_cases": {"source": active_src, "method": "live_highest_weight"},
        },
        sources_used     = list({r.source_name for r in records}),
        source_count     = len(records),
        fusion_method    = cases_method,
        data_freshness   = freshness,
    )

    # STEP 8: Confidence score (PHASE 4 requirement)
    fused.confidence = compute_confidence_score(records, fused)
    return fused
