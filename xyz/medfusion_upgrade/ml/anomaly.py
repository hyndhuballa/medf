"""
ml/anomaly.py — Z-Score + CUSUM Anomaly Detection
WHO/CDC surveillance standard — more interpretable than IsolationForest
Z-Score catches spikes; CUSUM catches sustained shifts (slow-building outbreaks)
"""

import numpy as np


def detect_anomalies(values: list, z_threshold: float = 2.5, cusum_k: float = 0.5) -> dict:
    """
    Combined Z-Score + CUSUM detector.
    - Z-Score: flags single-point spikes above threshold
    - CUSUM: cumulative sum detects sustained upward/downward shifts
    Research basis: Actual CDC/WHO EWARN surveillance methodology
    """
    arr = np.array(values, dtype=float)
    n = len(arr)

    if n < 7:
        return {"method": "Z-Score+CUSUM", "anomalies": [], "z_scores": [], "status": "insufficient_data"}

    mean = np.mean(arr)
    std  = np.std(arr) + 1e-9

    # Z-Score
    z_scores = (arr - mean) / std
    z_flags  = np.abs(z_scores) > z_threshold

    # CUSUM
    k = cusum_k * std
    h = 5.0 * std          # decision threshold
    cp = np.zeros(n)
    cn = np.zeros(n)
    for i in range(1, n):
        cp[i] = max(0.0, cp[i-1] + arr[i] - mean - k)
        cn[i] = max(0.0, cn[i-1] + mean - arr[i] - k)
    cusum_flags = (cp > h) | (cn > h)

    combined   = z_flags | cusum_flags
    indices    = [int(i) for i in np.where(combined)[0]]
    severity   = []
    for i in range(n):
        if z_scores[i] > 3 or cp[i] > h * 2:
            severity.append("critical")
        elif combined[i]:
            severity.append("warning")
        else:
            severity.append("normal")

    return {
        "method": "Z-Score + CUSUM (WHO standard)",
        "total_points": n,
        "anomaly_count": len(indices),
        "anomaly_indices": indices,
        "severity_per_point": severity,
        "z_scores": [round(float(z), 3) for z in z_scores],
        "cusum_pos": [round(float(v), 1) for v in cp],
        "thresholds": {"z": z_threshold, "cusum_h": round(float(h), 1)},
        "interpretation": "Z-Score catches spikes; CUSUM catches slow-building outbreaks",
    }
