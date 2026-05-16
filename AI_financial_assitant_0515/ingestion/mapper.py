"""Column mapping: auto-detect common column names and map to internal schema."""
import re

BUDGET_LINE_ALIASES = {
    "section": ["section", "type_budget", "budget_section", "fonct_invest"],
    "chapter": ["chapitre", "chapter", "chap"],
    "article": ["article", "art", "compte"],
    "service": ["service", "direction", "pole", "dept"],
    "label": ["libelle", "label", "intitule", "designation", "description"],
    "voted_amount": ["vote", "voted", "credit_vote", "montant_vote", "bp"],
    "opened_credits": ["ouvert", "opened", "credit_ouvert", "montant_ouvert", "ca"],
    "committed_amount": ["engage", "committed", "montant_engage", "engagement"],
    "mandated_amount": ["mandate", "mandated", "montant_mandate", "mandat", "realise"],
    "paid_amount": ["paye", "paid", "montant_paye", "paiement"],
    "available_amount": ["disponible", "available", "credit_dispo", "reste"],
}

COMMITMENT_ALIASES = {
    "commitment_number": ["numero", "number", "ref", "num_engagement", "engagement_num"],
    "date": ["date", "date_engagement", "created_at"],
    "supplier_name": ["fournisseur", "supplier", "tiers", "prestataire"],
    "service": ["service", "direction", "pole"],
    "chapter": ["chapitre", "chapter", "chap"],
    "article": ["article", "art"],
    "object": ["objet", "object", "libelle", "label", "designation"],
    "committed_amount": ["montant", "amount", "engage", "committed"],
    "mandated_amount": ["mandate", "mandated", "realise"],
    "remaining_amount": ["restant", "remaining", "solde"],
    "contract_reference": ["marche", "contract", "ref_marche", "num_marche"],
    "status": ["statut", "status", "etat"],
}

MANDATE_ALIASES = {
    "mandate_number": ["numero", "number", "ref", "num_mandat", "mandat_num"],
    "date": ["date", "date_mandat"],
    "supplier_name": ["fournisseur", "supplier", "tiers"],
    "amount": ["montant", "amount", "valeur"],
    "chapter": ["chapitre", "chapter", "chap"],
    "article": ["article", "art"],
    "service": ["service", "direction"],
    "status": ["statut", "status", "etat"],
    "rejection_reason": ["motif_rejet", "rejection_reason", "motif", "reason"],
}

SUPPLIER_ALIASES = {
    "name": ["nom", "name", "raison_sociale", "supplier"],
    "siret": ["siret", "siren", "num_siret"],
    "internal_reference": ["ref", "reference", "code_tiers", "internal_ref"],
}


def _normalize(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", col.lower().strip())


def auto_map_columns(columns: list[str], aliases: dict[str, list[str]]) -> dict[str, str | None]:
    """Returns {internal_field: source_column | None}."""
    norm_cols = {_normalize(c): c for c in columns}
    mapping: dict[str, str | None] = {}

    for field, candidates in aliases.items():
        # Always try the field name itself (both with and without underscores)
        all_candidates = [field, field.replace("_", "")] + candidates
        found = None
        for candidate in all_candidates:
            norm_candidate = _normalize(candidate)
            if norm_candidate in norm_cols:
                found = norm_cols[norm_candidate]
                break
        mapping[field] = found

    return mapping


def detect_data_type(columns: list[str]) -> str:
    norm = [_normalize(c) for c in columns]
    if any(k in norm for k in ["numengagement", "engagementnum", "montantengage"]):
        return "commitments"
    if any(k in norm for k in ["nummandat", "mandatnum", "motifirejet", "motifirejet"]):
        return "mandates"
    if any(k in norm for k in ["raisonsociale", "siret", "codetiers"]):
        return "suppliers"
    if any(k in norm for k in ["creditouvert", "montantvote", "creditvote", "creditdispo"]):
        return "budget_lines"
    # Fallback heuristic
    if "chapitre" in norm or "chapter" in " ".join(norm):
        if "montantengage" in norm or "engage" in " ".join(norm):
            return "commitments"
        return "budget_lines"
    return "unknown"


def get_aliases_for_type(data_type: str) -> dict:
    return {
        "budget_lines": BUDGET_LINE_ALIASES,
        "commitments": COMMITMENT_ALIASES,
        "mandates": MANDATE_ALIASES,
        "suppliers": SUPPLIER_ALIASES,
    }.get(data_type, {})
