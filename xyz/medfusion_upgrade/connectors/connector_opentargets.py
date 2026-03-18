"""
connector_opentargets.py
Open Targets Platform — Gene-disease associations
Explicitly required by hackathon PDF:
  "Disease-associated genes ranked by evidence strength;
   gene-disease scores from Open Targets or NCBI OMIM"
GraphQL API — no key required
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "Open Targets Platform"
GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# EFO (Experimental Factor Ontology) IDs for diseases
# EFO/MONDO IDs — verified against Open Targets Platform search
# Verify at: https://platform.opentargets.org/disease/<efo_id>
DISEASE_EFO = {
    "covid-19":      "MONDO_0100096",   # COVID-19 ✓
    "malaria":       "EFO_0001068",     # malaria ✓
    "tuberculosis":  "EFO_0000222",     # tuberculosis ✓
    "tb":            "EFO_0000222",
    "dengue":        "MONDO_0005502",   # dengue disease ✓ (NOT EFO_0000400 which is diabetes)
    "influenza":     "EFO_0004252",     # influenza ✓
    "flu":           "EFO_0004252",
    "ebola":         "EFO_0007149",     # Ebola hemorrhagic fever ✓
    "hiv":           "EFO_0000764",     # HIV infection ✓
    "cholera":       "EFO_0000694",     # cholera ✓
    "measles":       "EFO_0006792",     # measles ✓
    "mpox":          "MONDO_0005765",   # monkeypox ✓
    "h5n1":          "EFO_0007342",     # influenza A (H5N1) ✓
    "zika":          "EFO_0007243",     # Zika virus ✓
    "hepatitis b":   "EFO_0004197",     # hepatitis B ✓
    "typhoid":       "EFO_0000712",     # typhoid fever ✓
    "yellow fever":  "EFO_0007141",     # yellow fever ✓
}

QUERY = """
query DiseaseAssociations($efoId: String!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    description
    associatedTargets(page: {index: 0, size: $size}) {
      count
      rows {
        target {
          id
          approvedSymbol
          approvedName
          biotype
        }
        score
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""


def fetch_gene_associations(disease: str, top_n: int = 10) -> dict:
    """Fetch top gene-disease associations from Open Targets"""
    dl = disease.lower().strip()
    efo_id = DISEASE_EFO.get(dl)

    # Try partial match
    if not efo_id:
        for key, eid in DISEASE_EFO.items():
            if dl in key or key in dl:
                efo_id = eid
                break

    if not efo_id:
        return {
            "source": SOURCE_NAME, "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "no_efo_mapping",
            "disease": disease,
            "note": f"No EFO ID mapping for '{disease}'. Known diseases: {', '.join(DISEASE_EFO.keys())}",
            "data": [],
        }

    try:
        r = requests.post(
            GRAPHQL_URL,
            json={"query": QUERY, "variables": {"efoId": efo_id, "size": top_n}},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()

        disease_data = (result.get("data") or {}).get("disease") or {}
        if not disease_data:
            return {
                "source": SOURCE_NAME, "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
                "status": "no_data", "disease": disease, "efo_id": efo_id, "data": [],
            }

        assoc_data   = disease_data.get("associatedTargets", {})
        total        = assoc_data.get("count", 0)
        rows         = assoc_data.get("rows", [])

        genes = []
        for row in rows:
            target = row.get("target", {})
            score  = row.get("score", 0)
            dtype_scores = {d["id"]: round(d["score"], 4) for d in row.get("datatypeScores", [])}
            genes.append({
                "gene_symbol":     target.get("approvedSymbol"),
                "gene_name":       target.get("approvedName"),
                "ensembl_id":      target.get("id"),
                "biotype":         target.get("biotype"),
                "association_score": round(score, 4),
                "evidence_types":  dtype_scores,
                "opentargets_url": f"https://platform.opentargets.org/target/{target.get('id')}",
            })

        return {
            "source":     SOURCE_NAME,
            "source_url": GRAPHQL_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status":     "ok",
            "disease":    disease_data.get("name", disease),
            "efo_id":     efo_id,
            "data": {
                "total_gene_associations": total,
                "top_genes":               genes,
                "disease_description":     disease_data.get("description"),
            },
        }

    except Exception as e:
        return {
            "source": SOURCE_NAME, "source_url": GRAPHQL_URL,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "error", "error": str(e), "data": [],
        }
