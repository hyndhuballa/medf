"""
schemas/models.py
Unified normalized schema — every source converts to this before fusion.
This is the contract between ingestion and the rest of the pipeline.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class DataQuality(Enum):
    HIGH   = "high"    # WHO, CDC, ECDC — authoritative government sources
    MEDIUM = "medium"  # disease.sh, ProMED — reliable but secondary
    LOW    = "low"     # HealthMap scrape, inferred values


class TrendDirection(Enum):
    RISING   = "rising"
    DECLINING = "declining"
    STABLE   = "stable"
    UNKNOWN  = "unknown"


# ─── Source weights for fusion ────────────────────────────────────────────────
# Higher weight = more trusted in conflict resolution
SOURCE_WEIGHTS = {
    "WHO GHO":         1.0,
    "CDC Open Data":   1.0,
    "ECDC":            0.95,
    "UKHSA":           0.95,
    "CDC FluView":     0.90,
    "disease.sh":      0.85,
    "IHME":            0.85,
    "ProMED":          0.70,
    "HealthMap":       0.65,
    "Open Targets":    1.0,   # genomics — no conflict expected
    "PubChem":         1.0,   # therapeutic — no conflict expected
}


@dataclass
class NormalizedCaseRecord:
    """
    Single normalized record from any source.
    All sources produce this before fusion.
    """
    disease:         str
    source_name:     str
    source_url:      str
    data_quality:    DataQuality
    weight:          float               # SOURCE_WEIGHTS[source_name]

    # Core epidemiological fields
    total_cases:     Optional[int]  = None
    active_cases:    Optional[int]  = None
    total_deaths:    Optional[int]  = None
    recovered:       Optional[int]  = None
    today_cases:     Optional[int]  = None
    today_deaths:    Optional[int]  = None

    # Derived
    cfr_percent:     Optional[float] = None
    cases_per_million: Optional[float] = None

    # Geographic
    region:          Optional[str]  = None    # global / country / continent
    country_code:    Optional[str]  = None
    region_breakdown: dict          = field(default_factory=dict)

    # Temporal
    data_year:       Optional[int]  = None
    fetched_at:      str            = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    data_freshness:  str            = ""

    # Flags
    is_estimate:     bool           = False   # True for annual WHO estimates
    is_live:         bool           = False   # True for disease.sh / ProMED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["data_quality"] = self.data_quality.value
        return d


@dataclass
class FusedDiseaseRecord:
    """
    Result after multi-source fusion.
    Contains fused values + provenance of each field.
    """
    disease:             str
    icd10:               Optional[str]

    # Fused values (weighted average or priority override)
    total_cases:         Optional[int]
    active_cases:        Optional[int]
    total_deaths:        Optional[int]
    cfr_percent:         Optional[float]
    today_cases:         Optional[int]
    cases_per_million:   Optional[float]
    region_breakdown:    dict

    # Provenance — which source each value came from
    provenance:          dict          = field(default_factory=dict)
    sources_used:        list          = field(default_factory=list)
    source_count:        int           = 0
    fusion_method:       str           = ""   # e.g. "weighted_average", "priority_override"
    data_freshness:      str           = ""
    fetched_at:          str           = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ComputedMetrics:
    """
    All epidemiological metrics computed from fused data + timeline.
    Every value has a formula comment and WHY explanation.
    """
    disease:              str

    # Trend (computed from 7-day rolling average comparison)
    pct_change_7d:        Optional[float]   # formula: (avg_recent - avg_prior) / avg_prior * 100
    trend_direction:      TrendDirection
    trend_explanation:    str               # human-readable WHY

    # R0 / Rt (computed from exponential growth rate)
    r0_estimate:          float             # formula: exp(growth_rate * serial_interval)
    rt_effective:         float             # formula: ratio of consecutive generation intervals
    r0_explanation:       str

    # Doubling time (from exponential growth)
    doubling_time_days:   Optional[float]   # formula: ln(2) / growth_rate
    doubling_explanation: str

    # Risk score (SIR-derived composite)
    risk_score:           float             # 0–100 weighted composite
    risk_label:           str              # LOW / MODERATE / HIGH / CRITICAL
    risk_explanation:     str              # WHY is risk this level

    # CFR context
    cfr_percent:          Optional[float]
    cfr_vs_baseline:      Optional[str]    # "above baseline", "at baseline"

    # Anomaly flags
    anomaly_detected:     bool
    anomaly_dates:        list
    anomaly_explanation:  str

    # Forecast
    forecast_14d:         list             # predicted case counts
    forecast_dates:       list
    forecast_model:       str
    forecast_explanation: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trend_direction"] = self.trend_direction.value
        return d
