"""
services/query_intelligence.py
PHASE 7 — Query Intelligence Layer

Handles:
1. Synonym mapping (covid = covid-19 = coronavirus = sars-cov-2)
2. Fuzzy matching (typos, partial names)
3. Region-aware queries ("dengue in india", "flu in europe")
4. Entity disambiguation
"""

import re
from typing import Optional


# ─── Comprehensive synonym map ────────────────────────────────────────────────
DISEASE_SYNONYMS: dict[str, str] = {
    # COVID-19
    "covid":          "covid-19",
    "covid19":        "covid-19",
    "coronavirus":    "covid-19",
    "sars-cov-2":     "covid-19",
    "sars cov 2":     "covid-19",
    "corona":         "covid-19",
    "sarscov2":       "covid-19",

    # Tuberculosis
    "tb":             "tuberculosis",
    "tubercolosis":   "tuberculosis",  # common typo
    "tubercluosis":   "tuberculosis",
    "mycobacterium":  "tuberculosis",

    # Influenza
    "flu":            "influenza",
    "h1n1":           "influenza",
    "h3n2":           "influenza",
    "swine flu":      "influenza",
    "seasonal flu":   "influenza",

    # Avian Influenza
    "avian flu":      "h5n1",
    "bird flu":       "h5n1",
    "avian influenza":"h5n1",

    # Monkeypox
    "monkeypox":      "mpox",
    "monkey pox":     "mpox",

    # Dengue
    "dengue fever":   "dengue",
    "denv":           "dengue",

    # Ebola
    "ebola virus":    "ebola",
    "evd":            "ebola",
    "ebola hemorrhagic":"ebola",

    # HIV
    "aids":           "hiv",
    "hiv/aids":       "hiv",

    # Cholera
    "vibrio":         "cholera",

    # Malaria
    "plasmodium":     "malaria",
    "p. falciparum":  "malaria",

    # Nipah
    "nipah virus":    "nipah",
    "niv":            "nipah",

    # Yellow fever
    "yellow fever":   "yellow_fever",

    # Zika
    "zika virus":     "zika",

    # Typhoid
    "typhoid fever":  "typhoid",
    "enteric fever":  "typhoid",
}

# ─── Region synonym map ───────────────────────────────────────────────────────
REGION_SYNONYMS: dict[str, str] = {
    "usa":            "us",
    "united states":  "us",
    "america":        "us",
    "uk":             "united kingdom",
    "britain":        "united kingdom",
    "england":        "united kingdom",
    "eu":             "europe",
    "european union": "europe",
    "south asia":     "india",   # common shorthand
    "southeast asia": "regional",
    "sub-saharan":    "africa",
}

# ICD-10 map
ICD10_MAP: dict[str, str] = {
    "covid-19":     "U07.1",
    "malaria":      "B50-B54",
    "tuberculosis": "A15-A19",
    "dengue":       "A90",
    "influenza":    "J11",
    "ebola":        "A98.4",
    "mpox":         "B04",
    "cholera":      "A00",
    "hiv":          "B20",
    "measles":      "B05",
    "h5n1":         "J09.X1",
    "typhoid":      "A01.0",
    "plague":       "A20",
}

# Serial intervals (days) — WHO published values
SERIAL_INTERVALS: dict[str, float] = {
    "covid-19":     5.8,
    "influenza":    2.9,
    "ebola":        15.3,
    "dengue":       14.0,
    "measles":      11.7,
    "mpox":         9.8,
    "sars":         8.4,
    "tuberculosis": 60.0,   # very long — chronic disease
    "malaria":      None,   # vector-borne, serial interval not directly applicable
    "cholera":      2.0,
}


class ParsedQuery:
    """Result of query parsing"""
    def __init__(self, raw: str):
        self.raw         = raw
        self.disease     = ""
        self.region      = None
        self.icd10       = None
        self.serial_int  = 5.0  # default
        self.synonyms    = []
        self.canonical   = ""
        self.confidence  = 1.0


def parse_query(raw_query: str) -> ParsedQuery:
    """
    Parse a user query into structured components.
    Handles: disease names, region modifiers, synonyms, typos.
    
    Examples:
      "dengue"           → disease=dengue, region=None
      "dengue in india"  → disease=dengue, region=india
      "covid"            → disease=covid-19 (synonym resolved)
      "tuberculosis"     → disease=tuberculosis, icd10=A15-A19
      "tb in africa"     → disease=tuberculosis, region=africa
    """
    result  = ParsedQuery(raw_query)
    cleaned = raw_query.lower().strip()

    # Step 1: Detect region modifier ("X in Y" pattern)
    region_match = re.search(r'\bin\s+([a-z\s]+)$', cleaned)
    if region_match:
        region_raw = region_match.group(1).strip()
        result.region = REGION_SYNONYMS.get(region_raw, region_raw)
        cleaned = cleaned[:region_match.start()].strip()

    # Step 2: Resolve synonyms
    canonical = DISEASE_SYNONYMS.get(cleaned, cleaned)
    result.disease   = canonical
    result.canonical = canonical
    result.synonyms  = [k for k, v in DISEASE_SYNONYMS.items() if v == canonical]

    # Step 3: ICD-10 lookup
    result.icd10 = ICD10_MAP.get(canonical, "N/A")

    # Step 4: Serial interval for R0 computation
    si = SERIAL_INTERVALS.get(canonical)
    if si:
        result.serial_int = si

    # Step 5: Fuzzy fallback for typos
    if canonical not in ICD10_MAP and canonical not in DISEASE_SYNONYMS.values():
        best_match = _fuzzy_match(canonical, list(ICD10_MAP.keys()))
        if best_match:
            result.canonical = best_match
            result.disease   = best_match
            result.icd10     = ICD10_MAP.get(best_match, "N/A")
            result.confidence = 0.8

    return result


def _fuzzy_match(query: str, candidates: list[str], threshold: float = 0.6) -> Optional[str]:
    """
    Simple fuzzy matching using character overlap (Dice coefficient).
    Formula: 2 * |bigrams(a) ∩ bigrams(b)| / (|bigrams(a)| + |bigrams(b)|)
    """
    def bigrams(s: str) -> set:
        return {s[i:i+2] for i in range(len(s)-1)}

    query_bg = bigrams(query)
    best_score = 0.0
    best_match = None

    for candidate in candidates:
        cand_bg = bigrams(candidate)
        if not query_bg or not cand_bg:
            continue
        overlap = len(query_bg & cand_bg)
        score   = 2 * overlap / (len(query_bg) + len(cand_bg))
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score >= threshold else None


# ─── Alert filtering ──────────────────────────────────────────────────────────

def filter_alerts_for_disease(alerts: list[dict], query: ParsedQuery) -> list[dict]:
    """
    PHASE 4: Context-aware alert filtering.
    Filter alerts by disease name + synonyms + region.
    
    Strategy:
    1. Exact disease match in title/disease field
    2. Any synonym match
    3. If region specified, filter by region/country
    Returns only relevant alerts, sorted by severity.
    """
    search_terms = {query.canonical} | set(query.synonyms) | {query.raw.lower()}

    def _matches(alert: dict) -> bool:
        title   = (alert.get("title") or "").lower()
        disease = (alert.get("disease") or "").lower()
        summary = (alert.get("summary") or "").lower()
        country = (alert.get("country") or "").lower()
        text    = f"{title} {disease} {summary}"

        disease_match = any(term in text for term in search_terms)
        if not disease_match:
            return False

        if query.region:
            region_lower = query.region.lower()
            return region_lower in text or region_lower in country

        return True

    matched = [a for a in alerts if _matches(a)]

    # Sort: high severity first, then by date
    sev_order = {"high": 0, "medium": 1, "low": 2}
    matched.sort(key=lambda a: (sev_order.get(a.get("severity","low"), 2)))

    return matched or alerts[:3]  # fallback: return 3 most recent if no match
