"""
Connector 6 — ProMED RSS Feed (Disease Outbreak Alerts)
Source: https://promedmail.org/feed/
Returns: Latest infectious disease outbreak alerts from ProMED-mail
         Parsed via feedparser — no API key required
"""

import feedparser
from datetime import datetime, timezone
import re

SOURCE_NAME = "ProMED-mail"
SOURCE_URL = "https://promedmail.org/feed/"
SOURCE_TYPE = "outbreak_alerts"

# Keyword-based severity tagging
HIGH_KEYWORDS = ["outbreak", "emergency", "fatalities", "deaths", "epidemic", "pandemic", "alert"]
MEDIUM_KEYWORDS = ["cases", "spread", "confirmed", "infection", "surge"]


def _tag_severity(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(k in text for k in HIGH_KEYWORDS):
        return "high"
    if any(k in text for k in MEDIUM_KEYWORDS):
        return "medium"
    return "low"


def _extract_disease(title: str) -> str | None:
    """Simple regex to extract disease name from ProMED title format"""
    # ProMED titles like: "CHOLERA, DIARRHEA & DYSENTERY UPDATE (42): ..."
    match = re.match(r"^([A-Z\s,&]+?)(?:\s+UPDATE|\s+-|\s+\()|\s*$", title.strip())
    if match:
        raw = match.group(1).strip(" ,&")
        return raw.title() if len(raw) > 2 else None
    return None


def fetch(max_items: int = 20) -> dict:
    """Fetch and parse ProMED RSS feed for disease outbreak alerts"""
    try:
        # Fetch with explicit timeout (feedparser.parse has no timeout)
        import requests as _req
        _resp = _req.get(SOURCE_URL, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        _resp.raise_for_status()
        feed = feedparser.parse(_resp.text)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed parse error: {feed.bozo_exception}")

        alerts = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")
            link = entry.get("link", "")

            # Parse date
            pub_struct = entry.get("published_parsed")
            if pub_struct:
                pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc).isoformat()
            else:
                pub_dt = published

            alerts.append({
                "title": title,
                "disease": _extract_disease(title),
                "summary": summary[:300] if summary else None,
                "published_at": pub_dt,
                "link": link,
                "severity": _tag_severity(title, summary),
            })

        high_alerts = [a for a in alerts if a["severity"] == "high"]
        diseases_mentioned = list({a["disease"] for a in alerts if a["disease"]})

        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "ok",
            "data": {
                "total_alerts": len(alerts),
                "high_severity_count": len(high_alerts),
                "diseases_mentioned": diseases_mentioned,
                "alerts": alerts,
                "feed_title": feed.feed.get("title", "ProMED"),
                "feed_updated": feed.feed.get("updated", None),
            },
        }

    except Exception as e:
        return {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error",
            "error": str(e),
            "data": None,
        }
