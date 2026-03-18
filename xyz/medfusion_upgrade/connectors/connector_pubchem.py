"""
connector_pubchem.py
PubChem PUG-REST API — Drug/therapeutic information
Explicitly required by hackathon PDF: "Drug information via PubChem PUG-REST"
No API key required — fully open
"""

import requests
from datetime import datetime, timezone

SOURCE_NAME = "PubChem PUG-REST"
BASE_URL    = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Disease → known drug CIDs or names (used to seed the lookup)
DISEASE_DRUGS = {
    "covid-19":       ["Paxlovid", "Remdesivir", "Molnupiravir", "Dexamethasone"],
    "malaria":        ["Artemisinin", "Chloroquine", "Hydroxychloroquine", "Quinine"],
    "tuberculosis":   ["Isoniazid", "Rifampicin", "Pyrazinamide", "Ethambutol"],
    "dengue":         ["Paracetamol", "Acetaminophen"],
    "influenza":      ["Oseltamivir", "Zanamivir", "Baloxavir"],
    "ebola":          ["Remdesivir", "Atoltivimab"],
    "mpox":           ["Tecovirimat", "Brincidofovir"],
    "cholera":        ["Azithromycin", "Doxycycline", "Ciprofloxacin"],
    "h5n1":           ["Oseltamivir", "Zanamivir"],
    "hiv":            ["Tenofovir", "Emtricitabine", "Dolutegravir"],
    "measles":        ["Vitamin A"],
    "hepatitis b":    ["Entecavir", "Tenofovir"],
}

# WHO Essential Medicines List (21st edition, 2019) — cross-reference
WHO_ESSENTIAL = {
    "Artemisinin", "Chloroquine", "Quinine", "Isoniazid", "Rifampicin",
    "Pyrazinamide", "Ethambutol", "Dexamethasone", "Azithromycin",
    "Doxycycline", "Ciprofloxacin", "Paracetamol", "Acetaminophen",
    "Oseltamivir", "Remdesivir", "Tenofovir", "Emtricitabine",
}


def _fetch_drug(name: str) -> dict | None:
    """Fetch drug details from PubChem by name"""
    try:
        # Step 1: Get CID
        cid_url = f"{BASE_URL}/compound/name/{requests.utils.quote(name)}/cids/JSON"
        r = requests.get(cid_url, timeout=5)
        if r.status_code != 200:
            return {"name": name, "status": "not_found"}
        cids = r.json().get("IdentifierList", {}).get("CID", [])
        if not cids:
            return {"name": name, "status": "not_found"}
        cid = cids[0]

        # Step 2: Get properties
        props_url = f"{BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES/JSON"
        r2 = requests.get(props_url, timeout=5)
        props = {}
        if r2.status_code == 200:
            table = r2.json().get("PropertyTable", {}).get("Properties", [{}])
            if table:
                props = table[0]

        # Step 3: Get description
        desc_url = f"{BASE_URL}/compound/cid/{cid}/description/JSON"
        r3 = requests.get(desc_url, timeout=5)
        description = ""
        if r3.status_code == 200:
            sections = r3.json().get("InformationList", {}).get("Information", [])
            for s in sections:
                if s.get("Description"):
                    description = s["Description"][:300]
                    break

        return {
            "name":               name,
            "pubchem_cid":        cid,
            "pubchem_url":        f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            "molecular_formula":  props.get("MolecularFormula"),
            "molecular_weight":   props.get("MolecularWeight"),
            "iupac_name":         props.get("IUPACName"),
            "smiles":             props.get("IsomericSMILES"),
            "description":        description or None,
            "who_essential":      name in WHO_ESSENTIAL,
            "status":             "ok",
        }
    except Exception as e:
        return {"name": name, "status": "error", "error": str(e)}


def fetch_drugs_for_disease(disease: str, max_drugs: int = 3) -> dict:
    """Fetch PubChem drug data for a disease"""
    dl = disease.lower().strip()
    drug_names = DISEASE_DRUGS.get(dl, [])[:max_drugs]

    if not drug_names:
        # Try partial match
        for key, drugs in DISEASE_DRUGS.items():
            if dl in key or key in dl:
                drug_names = drugs[:max_drugs]
                break

    if not drug_names:
        return {
            "source": SOURCE_NAME,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "no_drugs_known",
            "disease": disease,
            "data": [],
        }

    drugs = []
    for name in drug_names:
        drug_data = _fetch_drug(name)
        if drug_data:
            drugs.append(drug_data)

    who_essential_count = sum(1 for d in drugs if d.get("who_essential"))

    return {
        "source":      SOURCE_NAME,
        "source_url":  BASE_URL,
        "fetched_at":  datetime.now(tz=timezone.utc).isoformat(),
        "status":      "ok",
        "disease":     disease,
        "data": {
            "drugs":                  drugs,
            "total_drugs_checked":    len(drugs),
            "who_essential_count":    who_essential_count,
            "treatment_note":         f"{who_essential_count}/{len(drugs)} drugs on WHO Essential Medicines List",
        },
    }
