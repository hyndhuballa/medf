"""
connector_healthmap.py
HealthMap — Real-time automated disease outbreak monitoring
Source: https://healthmap.org/en/
Uses HealthMap public JSON feed — no key required for basic access
Falls back to RSS if JSON unavailable
"""

import requests
import feedparser
from datetime import datetime, timezone

SOURCE_NAME = "HealthMap"
JSON_URL    = "https://healthmap.org/en/feed.json"
RSS_URL     = "https://healthmap.org/en/feed/"

SEVERITY_KEYWORDS = {
    "high":   ["outbreak","epidemic","emergency","death","fatality","surge","alert","crisis"],
    "medium": ["cases","spread","confirmed","infection","reported","detected"],
    "low":    ["monitoring","update","surveillance","warning"],
}

def _tag_severity(text: str) -> str:
    t = text.lower()
    for level, kws in SEVERITY_KEYWORDS.items():
        if any(k in t for k in kws):
            return level
    return "low"

def _extract_country(text: str) -> str | None:
    """Simple heuristic — HealthMap titles often end with country in parens"""
    import re
    m = re.search(r'\(([A-Za-z\s]+)\)\s*$', text)
    return m.group(1).strip() if m else None


def fetch(max_items: int = 20) -> dict:
    """Fetch HealthMap outbreak alerts"""
    # Try JSON feed first
    try:
        r = requests.get(JSON_URL, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            alerts = []
            for item in (data if isinstance(data, list) else data.get("items", []))[:max_items]:
                title   = item.get("title", "") or item.get("summary", "")
                country = item.get("country") or _extract_country(title)
                alerts.append({
                    "title":       title,
                    "disease":     item.get("disease") or item.get("category"),
                    "country":     country,
                    "lat":         item.get("lat") or item.get("latitude"),
                    "lon":         item.get("lon") or item.get("longitude"),
                    "published_at":item.get("pubDate") or item.get("date"),
                    "url":         item.get("link") or item.get("url"),
                    "severity":    _tag_severity(title),
                    "source":      "HealthMap",
                })
            return {
                "source": SOURCE_NAME, "source_url": JSON_URL,
                "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
                "status": "ok",
                "data": {"alerts": alerts, "total": len(alerts), "method": "json"},
            }
    except Exception:
        pass

    # Fallback: RSS feed
    try:
        import requests as _req
        _resp = _req.get(RSS_URL, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        _resp.raise_for_status()
        feed = feedparser.parse(_resp.text)
        alerts = []
        for entry in feed.entries[:max_items]:
            title   = entry.get("title", "")
            summary = entry.get("summary", "")
            country = _extract_country(title)
            alerts.append({
                "title":       title,
                "disease":     None,
                "country":     country,
                "lat":         None, "lon": None,
                "published_at":entry.get("published"),
                "url":         entry.get("link"),
                "severity":    _tag_severity(title + " " + summary),
                "source":      "HealthMap",
            })
        return {
            "source": SOURCE_NAME, "source_url": RSS_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok" if alerts else "empty",
            "data": {"alerts": alerts, "total": len(alerts), "method": "rss"},
        }
    except Exception as e:
        return {
            "source": SOURCE_NAME, "source_url": RSS_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error", "error": str(e), "data": None,
        }
