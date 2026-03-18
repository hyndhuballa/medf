"""
ml/risk.py — Epidemiological Risk Scoring
Replaces arbitrary KMeans with SIR-model-derived features:
  - R0 (basic reproduction number)
  - Doubling time
  - CFR-weighted burden
  - WHO risk matrix framework
Far more interpretable and clinically meaningful than cluster labels.
"""

import numpy as np
import math


def estimate_r0(values: list, serial_interval: float = 5.0) -> float:
    """
    Estimate R0 from growth rate using exponential growth approximation:
    R0 = exp(r * serial_interval) where r = daily growth rate
    Serial interval = 5 days (COVID-19/Dengue baseline)
    """
    if len(values) < 14:
        return 1.0
    recent = [v for v in values[-7:] if v > 0]
    prior  = [v for v in values[-14:-7] if v > 0]
    if not recent or not prior:
        return 1.0
    r_avg = sum(recent) / len(recent)
    p_avg = sum(prior)  / len(prior)
    if p_avg <= 0:
        return 1.0
    daily_growth = (r_avg - p_avg) / (p_avg * 7 + 1e-9)
    r0 = math.exp(max(-2, min(2, daily_growth * serial_interval)))
    return round(r0, 3)


def estimate_doubling_time(values: list, window: int = 7) -> float | None:
    """
    Estimate epidemic doubling time (days) from recent growth.
    T_double = ln(2) / r  where r = growth rate
    """
    if len(values) < window * 2:
        return None
    recent = sum(values[-window:]) / window
    prior  = sum(values[-window*2:-window]) / window
    if prior <= 0 or recent <= prior:
        return None
    r = (recent - prior) / (prior * window)
    if r <= 0:
        return None
    return round(0.693 / r, 1)


def effective_reproduction_number(values: list, serial_interval: float = 5.0) -> float:
    """
    Rt — effective reproduction number (accounts for immunity/interventions).
    Uses ratio of consecutive generation intervals.
    """
    if len(values) < serial_interval * 2 + 1:
        return estimate_r0(values, serial_interval)
    window = max(1, int(serial_interval))
    recent = sum(values[-window:]) + 1e-9
    prior  = sum(values[-window*2:-window]) + 1e-9
    rt = (recent / prior)
    return round(rt, 3)


def compute_risk_score(
    timeline: list,
    active: int,
    population: int,
    cfr: float,
    today_cases: int = 0,
) -> dict:
    """
    Composite epidemiological risk score (0–100) using:
    - R0 / Rt (40% weight)
    - CFR (25% weight)
    - Active burden per million (25% weight)
    - Doubling time (10% weight)
    Research basis: WHO risk matrix + SIR model features
    """
    values = [float(pt.get("cases") or 0) for pt in timeline] if timeline else []

    r0 = estimate_r0(values)
    rt = effective_reproduction_number(values)
    dt = estimate_doubling_time(values)
    active_per_million = (active / max(population, 1)) * 1_000_000

    # Normalized component scores (0–100)
    r0_score     = min(100, max(0, (r0 - 1.0) * 33))     # R0=1→0, R0=4→99
    cfr_score    = min(100, cfr * 200)                     # CFR 50%→100pts
    burden_score = min(100, active_per_million / 50)       # 5k/million→100pts
    dt_score     = 0
    if dt and dt < 60:
        dt_score = min(100, max(0, (60 - dt) * 1.8))      # faster doubling=higher risk

    # Weighted composite
    composite = (
        r0_score     * 0.40 +
        cfr_score    * 0.25 +
        burden_score * 0.25 +
        dt_score     * 0.10
    )
    composite = round(composite, 1)

    label = (
        "CRITICAL" if composite >= 75 else
        "HIGH"     if composite >= 50 else
        "MODERATE" if composite >= 25 else
        "LOW"
    )

    return {
        "composite_score": composite,
        "label": label,
        "method": "SIR-derived epidemiological risk matrix",
        "epidemiology": {
            "r0_estimate": r0,
            "rt_effective": rt,
            "doubling_time_days": dt,
            "active_per_million": round(active_per_million, 1),
            "cfr_percent": round(cfr * 100, 3),
        },
        "component_scores": {
            "r0_score": round(r0_score, 1),
            "cfr_score": round(cfr_score, 1),
            "burden_score": round(burden_score, 1),
            "doubling_time_score": round(dt_score, 1),
        },
        "interpretation": (
            f"R0={r0} ({'spreading' if r0 > 1 else 'contained'}), "
            f"Rt={rt}, "
            f"doubling every {dt or 'N/A'} days"
        ),
        "is_epidemic": r0 > 1.0,
    }
