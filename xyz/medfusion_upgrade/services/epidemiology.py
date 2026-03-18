"""
services/epidemiology.py
PHASE 5+6 — Real Epidemiological Computations + Time-Series Pipeline

All formulas explicitly documented.
No hardcoding. Every value is computed from real data.
"""

import math
import numpy as np
from typing import Optional
from schemas.models import ComputedMetrics, TrendDirection


# ─── PHASE 6: Time-series smoothing ──────────────────────────────────────────

def moving_average(values: list[float], window: int = 7) -> list[float]:
    """
    7-day simple moving average to smooth case counts.
    Formula: MA[i] = mean(values[i-window+1 : i+1])
    Used to reduce noise before trend detection.
    """
    if len(values) < window:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        result.append(sum(values[start:i+1]) / (i - start + 1))
    return result


def compute_pct_change_7d(timeline: list[dict]) -> tuple[Optional[float], str]:
    """
    7-day percentage change in case counts.
    Formula: pct_change = (avg_recent_7d - avg_prior_7d) / avg_prior_7d * 100
    where:
      avg_recent_7d = mean of last 7 days
      avg_prior_7d  = mean of days 8-14 ago
    Requires at least 14 data points.
    Returns (pct_change, explanation)
    """
    values = [float(pt.get("cases") or 0) for pt in timeline]
    smoothed = moving_average(values, window=3)  # smooth first

    if len(smoothed) < 14:
        return None, "Insufficient data for 7-day comparison (need ≥14 points)"

    recent_avg = sum(smoothed[-7:]) / 7
    prior_avg  = sum(smoothed[-14:-7]) / 7

    if prior_avg == 0:
        return None, "Prior 7-day average is zero — cannot compute percentage change"

    pct = round((recent_avg - prior_avg) / prior_avg * 100, 2)
    explanation = (
        f"7-day avg: {recent_avg:,.0f} cases/day vs prior 7-day avg: {prior_avg:,.0f} cases/day "
        f"→ change of {pct:+.1f}%"
    )
    return pct, explanation


def detect_trend(pct_change: Optional[float],
                 threshold_pct: float = 5.0) -> tuple[TrendDirection, str]:
    """
    Classify trend direction.
    Thresholds:
      > +5%  = rising
      < -5%  = declining
      -5% to +5% = stable
    Threshold of 5% chosen to filter noise from day-to-day fluctuations.
    Returns (direction, explanation)
    """
    if pct_change is None:
        return TrendDirection.UNKNOWN, "Trend unknown — insufficient historical data"
    if pct_change > threshold_pct:
        return TrendDirection.RISING, f"Cases trending upward ({pct_change:+.1f}% over 7 days)"
    elif pct_change < -threshold_pct:
        return TrendDirection.DECLINING, f"Cases trending downward ({pct_change:+.1f}% over 7 days)"
    else:
        return TrendDirection.STABLE, f"Cases stable ({pct_change:+.1f}% over 7 days, within ±5% threshold)"


def compute_cfr(total_cases: Optional[int], total_deaths: Optional[int]) -> tuple[Optional[float], str]:
    """
    Case Fatality Rate.
    Formula: CFR = (total_deaths / total_cases) * 100
    Note: CFR underestimates true infection fatality rate (IFR) due to
    undercounting of asymptomatic/mild cases.
    Returns (cfr_percent, explanation)
    """
    if not total_cases or not total_deaths or total_cases == 0:
        return None, "CFR unavailable — missing case or death count"
    cfr = round(total_deaths / total_cases * 100, 4)
    return cfr, f"CFR = {total_deaths:,} deaths / {total_cases:,} cases = {cfr:.3f}%"


# ─── PHASE 5: R0 and Rt computation ──────────────────────────────────────────

def estimate_r0(timeline: list[dict], serial_interval: float = 5.0) -> tuple[float, str]:
    """
    Basic Reproduction Number (R0) from exponential growth approximation.
    Formula: R0 = exp(r * T_serial)
    where:
      r = daily growth rate
      T_serial = serial interval in days (5.0 for COVID default)
    
    Growth rate computed from 7-day vs prior 7-day comparison.
    Returns (r0, explanation)
    """
    values = [float(pt.get("cases") or 0) for pt in timeline]
    if len(values) < 14:
        return 1.0, "R0 = 1.0 (default — insufficient data for estimation)"

    recent_avg = sum(values[-7:]) / 7
    prior_avg  = sum(values[-14:-7]) / 7

    if prior_avg <= 0:
        return 1.0, "R0 = 1.0 — prior period has zero cases"

    daily_growth = (recent_avg - prior_avg) / (prior_avg * 7)
    r0 = math.exp(max(-2, min(2, daily_growth * serial_interval)))
    r0 = round(r0, 3)

    explanation = (
        f"R0 = exp({daily_growth:.4f} × {serial_interval}) = {r0} "
        f"({'spreading' if r0 > 1 else 'contained'}). "
        f"Serial interval assumed {serial_interval} days."
    )
    return r0, explanation


def estimate_rt(timeline: list[dict], serial_interval: float = 5.0) -> tuple[float, str]:
    """
    Effective Reproduction Number (Rt) — current transmission accounting for immunity.
    Formula: Rt = (sum of recent generation) / (sum of prior generation)
    where generation window = serial_interval days.
    
    Rt < 1: epidemic declining
    Rt = 1: stable endemic state
    Rt > 1: epidemic growing
    Returns (rt, explanation)
    """
    values = [float(pt.get("cases") or 0) for pt in timeline]
    window = max(1, int(serial_interval))

    if len(values) < window * 2 + 1:
        return 1.0, "Rt = 1.0 — insufficient data"

    recent = sum(values[-window:]) + 1e-9
    prior  = sum(values[-window*2:-window]) + 1e-9
    rt     = round(recent / prior, 3)

    interpretation = "declining" if rt < 0.9 else "growing" if rt > 1.1 else "stable"
    explanation = (
        f"Rt = {recent:.0f} (recent {window}d) / {prior:.0f} (prior {window}d) = {rt} "
        f"→ epidemic {interpretation}"
    )
    return rt, explanation


def estimate_doubling_time(timeline: list[dict], window: int = 7) -> tuple[Optional[float], str]:
    """
    Epidemic doubling time in days.
    Formula: T_double = ln(2) / r
    where r = daily growth rate
    
    Doubling time < 7 days: rapid exponential growth — CRITICAL
    Doubling time 7-30 days: moderate growth — HIGH
    Doubling time > 30 days: slow growth — manageable
    Returns (doubling_days, explanation)
    """
    values = [float(pt.get("cases") or 0) for pt in timeline]
    if len(values) < window * 2:
        return None, "Doubling time unavailable — insufficient data"

    recent_avg = sum(values[-window:]) / window
    prior_avg  = sum(values[-window*2:-window]) / window

    if prior_avg <= 0 or recent_avg <= prior_avg:
        return None, "Cases not growing — doubling time does not apply"

    growth_rate = (recent_avg - prior_avg) / (prior_avg * window)
    if growth_rate <= 0:
        return None, "Growth rate ≤ 0 — epidemic not doubling"

    doubling = round(math.log(2) / growth_rate, 1)

    context = (
        "CRITICAL — rapid spread" if doubling < 7 else
        "HIGH — fast spread" if doubling < 14 else
        "MODERATE — manageable growth" if doubling < 30 else
        "LOW — slow spread"
    )
    explanation = f"T_double = ln(2) / {growth_rate:.5f} = {doubling} days ({context})"
    return doubling, explanation


# ─── PHASE 3: SIR-derived risk score ─────────────────────────────────────────

def compute_risk_score(
    timeline:   list[dict],
    active:     int,
    population: int,
    cfr:        float,
    pct_change: Optional[float] = None,
    r0:         float = 1.0,
) -> tuple[dict, str]:
    """
    Composite epidemiological risk score (0–100).
    
    Components and weights:
      R0 score     (40%): R0=1→0pts, R0=4→100pts. Formula: min(100, (R0-1)*33)
      CFR score    (25%): CFR=0%→0pts, CFR=50%→100pts. Formula: min(100, CFR*200)
      Burden score (25%): active/million. Formula: min(100, active_per_million/50)
      Growth score (10%): 7-day pct_change. Formula: min(100, pct_change*3)
    
    Returns (score_dict, explanation_string)
    """
    active_per_million = (active / max(population, 1)) * 1_000_000

    r0_score     = min(100.0, max(0.0, (r0 - 1.0) * 33))
    cfr_score    = min(100.0, cfr * 200)
    burden_score = min(100.0, active_per_million / 50)
    growth_score = min(100.0, max(0.0, (pct_change or 0) * 3))

    composite = round(
        r0_score     * 0.40 +
        cfr_score    * 0.25 +
        burden_score * 0.25 +
        growth_score * 0.10, 1
    )

    label = (
        "CRITICAL" if composite >= 75 else
        "HIGH"     if composite >= 50 else
        "MODERATE" if composite >= 25 else
        "LOW"
    )

    explanation = (
        f"Risk {label} (score {composite}/100). "
        f"R0={r0} contributes {r0_score:.0f}pts (40% weight). "
        f"CFR={cfr:.2f}% contributes {cfr_score:.0f}pts (25% weight). "
        f"Active burden={active_per_million:.0f}/million contributes {burden_score:.0f}pts (25% weight). "
        f"7d growth={pct_change:+.1f}% contributes {growth_score:.0f}pts (10% weight)."
        if pct_change is not None else
        f"Risk {label} (score {composite}/100) — growth component unavailable."
    )

    return {
        "composite_score":    composite,
        "label":              label,
        "components": {
            "r0_score":       round(r0_score, 1),
            "cfr_score":      round(cfr_score, 1),
            "burden_score":   round(burden_score, 1),
            "growth_score":   round(growth_score, 1),
        },
        "epidemiology": {
            "r0_estimate":        r0,
            "active_per_million": round(active_per_million, 1),
            "cfr_percent":        round(cfr * 100, 3),
            "is_epidemic":        r0 > 1.0,
        },
    }, explanation


# ─── PHASE 2: Advanced trend classification ───────────────────────────────────

def classify_growth_type(values: list[float]) -> tuple[str, str]:
    """
    Detect whether growth is exponential, linear, plateau, or volatile.

    Method:
    - Fit linear model: cases = a*t + b
    - Fit log model:    log(cases) = a*t + b  (exponential if fits better)
    - Compare R² of both fits
    - Compute coefficient of variation for last 7 days to detect volatility

    Returns (growth_type, explanation)
    growth_type: "exponential" | "linear" | "plateau" | "volatile" | "declining"
    """
    import math
    if len(values) < 7:
        return "unknown", "Insufficient data for growth type classification"

    n      = len(values)
    xs     = list(range(n))

    # Linear fit (least squares)
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    ss_xy  = sum((x - x_mean)*(y - y_mean) for x, y in zip(xs, values))
    ss_xx  = sum((x - x_mean)**2 for x in xs)
    slope_lin = ss_xy / ss_xx if ss_xx > 0 else 0
    intercept_lin = y_mean - slope_lin * x_mean
    y_pred_lin = [slope_lin * x + intercept_lin for x in xs]
    ss_res_lin = sum((y - yp)**2 for y, yp in zip(values, y_pred_lin))
    ss_tot     = sum((y - y_mean)**2 for y in values)
    r2_lin     = 1 - ss_res_lin / ss_tot if ss_tot > 0 else 0

    # Log fit (exponential detection) — only if all values > 0
    r2_exp = 0.0
    if all(v > 0 for v in values):
        log_vals   = [math.log(v) for v in values]
        logy_mean  = sum(log_vals) / n
        ss_lxy     = sum((x - x_mean)*(ly - logy_mean) for x, ly in zip(xs, log_vals))
        slope_exp  = ss_lxy / ss_xx if ss_xx > 0 else 0
        int_exp    = logy_mean - slope_exp * x_mean
        yp_exp     = [math.exp(slope_exp * x + int_exp) for x in xs]
        ss_res_exp = sum((y - yp)**2 for y, yp in zip(values, yp_exp))
        r2_exp     = 1 - ss_res_exp / ss_tot if ss_tot > 0 else 0

    # Volatility: CV of last 7 days
    last7    = values[-7:]
    mean7    = sum(last7) / len(last7)
    std7     = math.sqrt(sum((v - mean7)**2 for v in last7) / len(last7)) if len(last7) > 1 else 0
    cv7      = std7 / mean7 if mean7 > 0 else 0
    volatile = cv7 > 0.25

    # Classify
    if volatile:
        return "volatile", f"High variability detected (CV={cv7:.2f} over last 7 days) — unstable transmission"
    if slope_lin < 0 and r2_lin > 0.6:
        return "declining", f"Linear decline detected (R²={r2_lin:.2f})"
    if r2_exp > 0.85 and r2_exp > r2_lin:
        return "exponential", f"Exponential growth detected (log-linear R²={r2_exp:.2f} > linear R²={r2_lin:.2f})"
    if r2_lin > 0.70:
        return "linear", f"Linear growth detected (R²={r2_lin:.2f})"
    if abs(slope_lin) / (y_mean + 1e-9) < 0.02:
        return "plateau", f"Plateau/stable phase (slope near zero, R²={r2_lin:.2f})"
    return "linear", f"Moderate linear trend (R²={r2_lin:.2f})"


def classify_trend_advanced(timeline: list[dict]) -> dict:
    """
    Full advanced trend classification combining:
    1. Percentage change (7-day comparison)
    2. Growth type (exponential/linear/plateau/volatile/declining)
    3. Velocity (rate of change acceleration)
    4. Smoothed values for visual layer

    Returns comprehensive trend dict used by pipeline.
    """
    values   = [float(pt.get("cases") or 0) for pt in timeline]
    smoothed = moving_average(values, window=7)

    pct_change, pct_expl = compute_pct_change_7d(timeline)
    direction, dir_expl  = detect_trend(pct_change)
    growth_type, gt_expl = classify_growth_type(smoothed) if len(smoothed) >= 7 else ("unknown","")

    # Velocity: is the rate of change itself accelerating?
    velocity = "stable"
    if len(smoothed) >= 14:
        recent_slope = (smoothed[-1] - smoothed[-7]) / 7
        prior_slope  = (smoothed[-7] - smoothed[-14]) / 7 if len(smoothed) >= 14 else 0
        if prior_slope != 0:
            accel = (recent_slope - prior_slope) / (abs(prior_slope) + 1e-9)
            if accel > 0.30:
                velocity = "accelerating"
            elif accel < -0.30:
                velocity = "decelerating"

    return {
        "direction":     direction.value,
        "pct_change_7d": pct_change,
        "growth_type":   growth_type,
        "velocity":      velocity,
        "smoothed_7d":   smoothed[-14:],
        "raw_last_7":    values[-7:],
        "explanation": (
            f"Trend: {direction.value} ({pct_change:+.1f}% 7d). "
            f"Growth pattern: {growth_type} ({gt_expl}). "
            f"Velocity: {velocity}."
        ) if pct_change is not None else f"Trend: {direction.value}. Growth: {growth_type}.",
    }
