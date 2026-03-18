"""Unified Disease Intelligence Schema"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone

@dataclass
class EpidemiologyData:
    disease: str
    icd10: Optional[str]
    total_cases: Optional[int]
    active_cases: Optional[int]
    total_deaths: Optional[int]
    today_cases: Optional[int]
    cfr_percent: Optional[float]
    trend_direction: Optional[str]
    pct_change_7d: Optional[float]
    r0_estimate: Optional[float]
    rt_effective: Optional[float]
    doubling_time_days: Optional[float]
    data_source: str
    data_freshness: str
    year: Optional[int] = None
    region_breakdown: dict = field(default_factory=dict)

@dataclass
class GenomicData:
    disease: str
    top_genes: list = field(default_factory=list)
    total_associations: int = 0
    efo_id: Optional[str] = None
    data_source: str = "Open Targets Platform"
    note: Optional[str] = None

@dataclass
class TherapeuticData:
    disease: str
    drugs: list = field(default_factory=list)
    who_essential_count: int = 0
    treatment_note: Optional[str] = None
    data_source: str = "PubChem PUG-REST"

@dataclass
class AlertData:
    total_alerts: int
    high_severity: int
    recent_alerts: list = field(default_factory=list)
    diseases_mentioned: list = field(default_factory=list)
    sources: list = field(default_factory=list)

@dataclass
class UnifiedDiseaseIntelligence:
    query: str
    disease_name: str
    risk_level: str
    risk_score: float
    epidemiology: EpidemiologyData
    genomics: GenomicData
    therapeutics: TherapeuticData
    alerts: AlertData
    insights: list = field(default_factory=list)
    cross_domain_links: list = field(default_factory=list)
    india_context: Optional[dict] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    def to_dict(self): return asdict(self)
