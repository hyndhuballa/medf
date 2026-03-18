"""
ml/forecast.py — XGBoost Forecaster
Outperforms Prophet on disease time-series (lowest MAE/RMSE per 2024 research)
Uses lag-feature supervised learning instead of seasonal decomposition
"""

import numpy as np
from datetime import datetime, timedelta

def _lag_features(series: list, lags: int = 7):
    arr = np.array(series, dtype=float)
    X, y = [], []
    for i in range(lags, len(arr)):
        X.append(arr[i - lags:i])
        y.append(arr[i])
    return np.array(X), np.array(y)


def forecast_xgboost(timeline: list, key: str = "cases", periods: int = 14) -> dict:
    """
    XGBoost lag-feature forecaster.
    Research basis: Outperforms Prophet on SFTS, Dengue, COVID datasets (2024).
    """
    try:
        from xgboost import XGBRegressor
        values = [float(pt.get(key) or 0) for pt in timeline]
        dates  = [pt.get("date", "") for pt in timeline]

        if len(values) < 16:
            return _fallback_linear(values, dates, periods, key)

        LAGS = 7
        X, y = _lag_features(values, LAGS)
        model = XGBRegressor(
            n_estimators=200, learning_rate=0.05,
            max_depth=4, subsample=0.8,
            colsample_bytree=0.8, random_state=42, verbosity=0
        )
        model.fit(X, y)

        window = list(values[-LAGS:])
        forecast, upper, lower = [], [], []
        last_date = dates[-1] if dates else ""

        for i in range(periods):
            x_in = np.array(window[-LAGS:]).reshape(1, -1)
            pred = float(model.predict(x_in)[0])
            pred = max(0, pred)
            forecast.append(round(pred))
            upper.append(round(pred * 1.12))
            lower.append(round(pred * 0.88))
            window.append(pred)

        # Generate future dates
        future_dates = []
        try:
            base = datetime.strptime(last_date, "%m/%d/%y")
            future_dates = [(base + timedelta(days=i+1)).strftime("%-m/%-d/%y") for i in range(periods)]
        except Exception:
            future_dates = [f"Day+{i+1}" for i in range(periods)]

        return {
            "status": "ok", "model": "XGBoost",
            "periods": periods, "key": key,
            "forecast": forecast, "upper": upper, "lower": lower,
            "future_dates": future_dates,
            "note": "XGBoost lag-7 supervised — outperforms Prophet on epidemic data",
        }

    except ImportError:
        values = [float(pt.get(key) or 0) for pt in timeline]
        dates  = [pt.get("date", "") for pt in timeline]
        return _fallback_linear(values, dates, periods, key)
    except Exception as e:
        return {"status": "error", "error": str(e), "model": "XGBoost"}


def _fallback_linear(values, dates, periods, key):
    """Linear regression fallback — zero extra dependencies"""
    if len(values) < 4:
        return {"status": "insufficient_data", "forecast": []}
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    m, b = np.polyfit(x, y, 1)
    forecast = [max(0, round(m * (len(values) + i) + b)) for i in range(periods)]
    upper = [round(v * 1.12) for v in forecast]
    lower = [round(max(0, v * 0.88)) for v in forecast]
    future_dates = [f"Day+{i+1}" for i in range(periods)]
    return {
        "status": "ok", "model": "LinearRegression (fallback)",
        "periods": periods, "key": key,
        "forecast": forecast, "upper": upper, "lower": lower,
        "future_dates": future_dates,
    }
