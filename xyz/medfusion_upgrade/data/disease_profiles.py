"""
data/disease_profiles.py
Covers missing PS requirements:
  - Classification data (ICD-10 codes, WHO disease family)
  - Genomic data (known variants, pathogen type, genome size)
  - Therapeutic data (approved drugs, vaccines, treatment protocols)
  - Epidemiological parameters (serial interval, incubation, R0 range)
All data sourced from WHO/CDC/NIH public references.
"""

DISEASE_PROFILES = {
    "covid-19": {
        "display_name": "COVID-19",
        "aliases": ["covid", "sars-cov-2", "coronavirus"],
        "classification": {
            "icd10": "U07.1",
            "icd11": "RA01.0",
            "who_family": "Coronaviridae",
            "pathogen_type": "RNA virus",
            "transmission": ["airborne", "droplet", "contact"],
        },
        "genomic": {
            "pathogen": "SARS-CoV-2",
            "genome_type": "Single-stranded positive-sense RNA",
            "genome_size_kb": 29.9,
            "key_variants": ["Alpha (B.1.1.7)", "Delta (B.1.617.2)", "Omicron (B.1.1.529)", "XBB.1.5"],
            "key_genes": ["Spike (S)", "Nucleocapsid (N)", "Envelope (E)", "Membrane (M)"],
            "mutation_rate": "~1-2 mutations/month",
        },
        "therapeutic": {
            "approved_antivirals": ["Paxlovid (nirmatrelvir/ritonavir)", "Remdesivir", "Molnupiravir"],
            "vaccines": ["Pfizer-BioNTech (mRNA)", "Moderna (mRNA)", "J&J (vector)", "AstraZeneca (vector)"],
            "treatment_protocol": "Supportive care + antivirals for high-risk patients",
            "who_essential_medicines": True,
        },
        "epidemiology": {
            "serial_interval_days": 5.8,
            "incubation_days": "2-14 (avg 5)",
            "r0_range": "2.5 - 5.7 (original), 8-15 (Omicron)",
            "cfr_range": "0.5% - 3%",
            "high_risk_groups": ["elderly", "immunocompromised", "cardiovascular disease"],
        },
    },
    "dengue": {
        "display_name": "Dengue Fever",
        "aliases": ["dengue fever", "denv"],
        "classification": {
            "icd10": "A90",
            "icd11": "1D2Z",
            "who_family": "Flaviviridae",
            "pathogen_type": "RNA virus",
            "transmission": ["Aedes aegypti mosquito", "Aedes albopictus mosquito"],
        },
        "genomic": {
            "pathogen": "Dengue virus (DENV)",
            "genome_type": "Single-stranded positive-sense RNA",
            "genome_size_kb": 10.7,
            "key_variants": ["DENV-1", "DENV-2", "DENV-3", "DENV-4"],
            "key_genes": ["Envelope (E)", "NS1", "NS3 (helicase)", "NS5 (polymerase)"],
            "mutation_rate": "High — 4 serotypes provide no cross-immunity",
        },
        "therapeutic": {
            "approved_antivirals": ["None approved — supportive care only"],
            "vaccines": ["Dengvaxia (CYD-TDV) — seropositive individuals only"],
            "treatment_protocol": "Fluid management, paracetamol (NO NSAIDs/aspirin)",
            "who_essential_medicines": False,
        },
        "epidemiology": {
            "serial_interval_days": 14,
            "incubation_days": "4-10",
            "r0_range": "2.0 - 6.0",
            "cfr_range": "0.5% - 5% (severe dengue)",
            "high_risk_groups": ["children", "re-infection (different serotype)", "tropics residents"],
        },
    },
    "influenza": {
        "display_name": "Influenza",
        "aliases": ["flu", "influenza a", "influenza b", "h1n1", "h3n2"],
        "classification": {
            "icd10": "J11",
            "icd11": "1E30",
            "who_family": "Orthomyxoviridae",
            "pathogen_type": "RNA virus (segmented)",
            "transmission": ["droplet", "contact", "airborne (close proximity)"],
        },
        "genomic": {
            "pathogen": "Influenza A/B virus",
            "genome_type": "Negative-sense single-stranded segmented RNA",
            "genome_size_kb": 13.5,
            "key_variants": ["H1N1", "H3N2", "H5N1 (avian)", "H7N9"],
            "key_genes": ["Hemagglutinin (HA)", "Neuraminidase (NA)", "PB1", "PB2"],
            "mutation_rate": "High — antigenic drift/shift annually",
        },
        "therapeutic": {
            "approved_antivirals": ["Oseltamivir (Tamiflu)", "Zanamivir (Relenza)", "Baloxavir (Xofluza)"],
            "vaccines": ["Annual flu vaccine (trivalent/quadrivalent)"],
            "treatment_protocol": "Antivirals within 48h of symptom onset for high-risk",
            "who_essential_medicines": True,
        },
        "epidemiology": {
            "serial_interval_days": 2.9,
            "incubation_days": "1-4",
            "r0_range": "1.2 - 1.4 (seasonal), 2.0-3.0 (pandemic)",
            "cfr_range": "0.01% - 0.1% (seasonal)",
            "high_risk_groups": ["elderly 65+", "children <5", "pregnant women", "immunocompromised"],
        },
    },
    "ebola": {
        "display_name": "Ebola Virus Disease",
        "aliases": ["ebola", "evd", "ebola hemorrhagic fever"],
        "classification": {
            "icd10": "A98.4",
            "icd11": "1D60",
            "who_family": "Filoviridae",
            "pathogen_type": "RNA virus",
            "transmission": ["direct contact (blood/fluids)", "contact with infected animals"],
        },
        "genomic": {
            "pathogen": "Ebola virus (EBOV)",
            "genome_type": "Negative-sense single-stranded RNA",
            "genome_size_kb": 18.9,
            "key_variants": ["Zaire (most lethal)", "Sudan", "Bundibugyo", "Taï Forest"],
            "key_genes": ["Glycoprotein (GP)", "Nucleoprotein (NP)", "VP35", "VP40"],
            "mutation_rate": "Moderate — GP mutations affect transmissibility",
        },
        "therapeutic": {
            "approved_antivirals": ["Inmazeb (atoltivimab/maftivimab/odesivimab)", "Ebanga (ansuvimab)"],
            "vaccines": ["Ervebo (rVSV-ZEBOV) — FDA approved 2019"],
            "treatment_protocol": "Supportive care + monoclonal antibodies",
            "who_essential_medicines": False,
        },
        "epidemiology": {
            "serial_interval_days": 15.3,
            "incubation_days": "2-21",
            "r0_range": "1.5 - 2.5",
            "cfr_range": "25% - 90% (strain dependent)",
            "high_risk_groups": ["healthcare workers", "family caregivers", "funeral attendees"],
        },
    },
    "malaria": {
        "display_name": "Malaria",
        "aliases": ["plasmodium", "p. falciparum"],
        "classification": {
            "icd10": "B50-B54",
            "icd11": "1F40",
            "who_family": "Plasmodiidae (parasite, not virus)",
            "pathogen_type": "Protozoan parasite",
            "transmission": ["Anopheles mosquito bite"],
        },
        "genomic": {
            "pathogen": "Plasmodium falciparum (most lethal)",
            "genome_type": "Eukaryotic nuclear DNA (23Mb)",
            "genome_size_kb": 23000,
            "key_variants": ["P. falciparum", "P. vivax", "P. malariae", "P. ovale"],
            "key_genes": ["PfCRT (chloroquine resistance)", "PfKelch13 (artemisinin resistance)"],
            "mutation_rate": "Drug resistance a major concern — kelch13 mutations",
        },
        "therapeutic": {
            "approved_antivirals": ["Artemisinin-based combination therapies (ACTs)", "Chloroquine (where susceptible)"],
            "vaccines": ["RTS,S/AS01 (Mosquirix) — WHO recommended 2021", "R21/Matrix-M — 2023"],
            "treatment_protocol": "ACT first-line; severe malaria = IV artesunate",
            "who_essential_medicines": True,
        },
        "epidemiology": {
            "serial_interval_days": "N/A (vector-borne)",
            "incubation_days": "7-30 (P. falciparum: 9-14)",
            "r0_range": "5.0 - 100 (highly variable by region/vector density)",
            "cfr_range": "0.1% - 0.5% (treated), up to 20% (severe untreated)",
            "high_risk_groups": ["children <5 in sub-Saharan Africa", "pregnant women", "travellers"],
        },
    },
    "tuberculosis": {
        "display_name": "Tuberculosis",
        "aliases": ["tb", "mycobacterium tuberculosis"],
        "classification": {
            "icd10": "A15-A19",
            "icd11": "1B10",
            "who_family": "Mycobacteriaceae (bacteria)",
            "pathogen_type": "Bacterium",
            "transmission": ["airborne (respiratory droplets)"],
        },
        "genomic": {
            "pathogen": "Mycobacterium tuberculosis",
            "genome_type": "Circular double-stranded DNA (4.4Mb)",
            "genome_size_kb": 4400,
            "key_variants": ["Drug-susceptible TB", "MDR-TB", "XDR-TB", "TDR-TB"],
            "key_genes": ["rpoB (rifampicin resistance)", "katG (isoniazid resistance)", "gyrA (fluoroquinolone resistance)"],
            "mutation_rate": "Slow — but drug resistance accumulation critical",
        },
        "therapeutic": {
            "approved_antivirals": ["Isoniazid", "Rifampicin", "Pyrazinamide", "Ethambutol (HRZE 6-month regimen)"],
            "vaccines": ["BCG vaccine — prevents severe TB in children"],
            "treatment_protocol": "HRZE 6-month DOT (Directly Observed Therapy)",
            "who_essential_medicines": True,
        },
        "epidemiology": {
            "serial_interval_days": 60,
            "incubation_days": "2-12 weeks (latent: years)",
            "r0_range": "2.0 - 3.0",
            "cfr_range": "10% - 50% (untreated), <5% (treated)",
            "high_risk_groups": ["HIV-positive", "malnourished", "crowded housing", "healthcare workers"],
        },
    },
    "cholera": {
        "display_name": "Cholera",
        "aliases": ["vibrio cholerae"],
        "classification": {
            "icd10": "A00",
            "icd11": "1A00",
            "who_family": "Vibrionaceae (bacteria)",
            "pathogen_type": "Bacterium",
            "transmission": ["contaminated water", "contaminated food"],
        },
        "genomic": {
            "pathogen": "Vibrio cholerae O1/O139",
            "genome_type": "Two circular chromosomes (2.9Mb + 1.1Mb)",
            "genome_size_kb": 4000,
            "key_variants": ["El Tor (classical)", "O1 Ogawa", "O1 Inaba", "O139 Bengal"],
            "key_genes": ["ctxAB (cholera toxin)", "tcpA (colonization)", "VPI-1 (pathogenicity island)"],
            "mutation_rate": "Moderate — El Tor variants gaining toxigenicity",
        },
        "therapeutic": {
            "approved_antivirals": ["ORS (primary)", "Azithromycin", "Doxycycline", "Ciprofloxacin"],
            "vaccines": ["Dukoral (oral)", "Shanchol (oral)", "Euvichol-Plus (oral)"],
            "treatment_protocol": "Rapid ORS rehydration — IV fluids for severe cases",
            "who_essential_medicines": True,
        },
        "epidemiology": {
            "serial_interval_days": 2,
            "incubation_days": "2 hours - 5 days",
            "r0_range": "2.0 - 6.0",
            "cfr_range": "<1% (treated), 25-50% (untreated)",
            "high_risk_groups": ["disaster-affected populations", "no clean water access", "children"],
        },
    },
    "mpox": {
        "display_name": "Mpox (Monkeypox)",
        "aliases": ["monkeypox", "mpox"],
        "classification": {
            "icd10": "B04",
            "icd11": "1E71",
            "who_family": "Poxviridae",
            "pathogen_type": "DNA virus",
            "transmission": ["direct contact (skin lesions)", "respiratory droplets", "animal contact"],
        },
        "genomic": {
            "pathogen": "Monkeypox virus (MPXV)",
            "genome_type": "Double-stranded DNA",
            "genome_size_kb": 197,
            "key_variants": ["Clade I (Central Africa — more severe)", "Clade IIb (2022 outbreak)"],
            "key_genes": ["B7R (host range)", "F3L (virulence)", "D9R (immunoevasion)"],
            "mutation_rate": "DNA virus — relatively stable, but Clade IIb shows APOBEC3 mutations",
        },
        "therapeutic": {
            "approved_antivirals": ["Tecovirimat (TPOXX)", "Brincidofovir", "Cidofovir"],
            "vaccines": ["JYNNEOS (MVA-BN) — FDA approved", "ACAM2000 (smallpox vaccine)"],
            "treatment_protocol": "Supportive care; tecovirimat for severe/high-risk cases",
            "who_essential_medicines": False,
        },
        "epidemiology": {
            "serial_interval_days": 9.8,
            "incubation_days": "5-21",
            "r0_range": "0.6 - 2.4 (Clade IIb 2022: ~1.0)",
            "cfr_range": "0-11% (Clade IIb: <0.1%)",
            "high_risk_groups": ["MSM (2022 outbreak)", "immunocompromised", "healthcare workers"],
        },
    },
    "h5n1": {
        "display_name": "H5N1 Avian Influenza",
        "aliases": ["avian flu", "bird flu", "h5n1"],
        "classification": {
            "icd10": "J09.X1",
            "icd11": "1E30.1",
            "who_family": "Orthomyxoviridae",
            "pathogen_type": "RNA virus",
            "transmission": ["infected bird contact", "contaminated environments", "rare human-to-human"],
        },
        "genomic": {
            "pathogen": "Influenza A (H5N1)",
            "genome_type": "Negative-sense segmented RNA",
            "genome_size_kb": 13.5,
            "key_variants": ["Clade 2.3.4.4b (dominant 2022+)", "Clade 2.2", "Clade 1"],
            "key_genes": ["PB2 (E627K mutation — mammalian adaptation)", "HA", "NA"],
            "mutation_rate": "High pandemic risk if PB2 E627K + human-to-human transmission established",
        },
        "therapeutic": {
            "approved_antivirals": ["Oseltamivir (Tamiflu)", "Zanamivir", "Baloxavir"],
            "vaccines": ["Pre-pandemic H5N1 vaccines stockpiled (US strategic reserve)"],
            "treatment_protocol": "Oseltamivir ASAP; ICU support; isolation",
            "who_essential_medicines": False,
        },
        "epidemiology": {
            "serial_interval_days": "N/A (no sustained human-to-human)",
            "incubation_days": "2-8",
            "r0_range": "<1.0 (current), pandemic potential if mutates",
            "cfr_range": "52% (human cases reported to WHO)",
            "high_risk_groups": ["poultry workers", "veterinarians", "live bird market workers", "dairy farm workers (2024)"],
        },
    },
}


def get_profile(query: str) -> dict | None:
    """Return disease profile by name or alias"""
    q = query.lower().strip()
    for key, profile in DISEASE_PROFILES.items():
        if q == key or q in profile.get("aliases", []):
            return {**profile, "query_key": key}
    # Fuzzy partial match
    for key, profile in DISEASE_PROFILES.items():
        if q in key or any(q in alias for alias in profile.get("aliases", [])):
            return {**profile, "query_key": key}
    return None


def list_diseases() -> list:
    return [
        {"key": k, "display_name": v["display_name"], "icd10": v["classification"]["icd10"]}
        for k, v in DISEASE_PROFILES.items()
    ]
