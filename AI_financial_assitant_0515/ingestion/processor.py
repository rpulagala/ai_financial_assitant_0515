"""File ingestion pipeline: load → map → validate → store."""
import io
from datetime import datetime, date
import pandas as pd
from sqlalchemy.orm import Session
from database.models import ImportBatch, BudgetLine, Commitment, Mandate, Supplier
from ingestion.mapper import auto_map_columns, detect_data_type, get_aliases_for_type


def load_file(file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, str]:
    """Load CSV or Excel into a DataFrame. Returns (df, file_type)."""
    if file_name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, encoding="utf-8-sig")
        return df, "csv"
    else:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        return df, "excel"


def validate_and_clean(df: pd.DataFrame, mapping: dict[str, str | None], data_type: str) -> tuple[pd.DataFrame, list[str]]:
    """Apply mapping, clean types, return cleaned df and list of warnings."""
    warnings = []
    cleaned = pd.DataFrame()

    for internal_field, source_col in mapping.items():
        if source_col and source_col in df.columns:
            cleaned[internal_field] = df[source_col]
        else:
            cleaned[internal_field] = None
            if source_col is None:
                warnings.append(f"Field '{internal_field}' not mapped — column not found.")

    # Type coercions
    numeric_fields = [
        "voted_amount", "opened_credits", "committed_amount", "mandated_amount",
        "paid_amount", "available_amount", "amount", "committed_amount",
        "mandated_amount", "remaining_amount", "total_mandated",
    ]
    for f in numeric_fields:
        if f in cleaned.columns:
            cleaned[f] = (
                cleaned[f]
                .astype(str)
                .str.replace(r"[€\s,]", "", regex=True)
                .str.replace(",", ".", regex=False)
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0)
            )

    date_fields = ["date"]
    for f in date_fields:
        if f in cleaned.columns:
            cleaned[f] = pd.to_datetime(cleaned[f], errors="coerce", dayfirst=False)

    return cleaned, warnings


def compute_quality_score(df: pd.DataFrame, warnings: list[str]) -> float:
    """Simple quality score 0–100."""
    total_cells = df.size
    null_cells = df.isnull().sum().sum()
    completeness = max(0, 1 - null_cells / total_cells) if total_cells > 0 else 0
    warning_penalty = min(0.3, len(warnings) * 0.05)
    return round((completeness - warning_penalty) * 100, 1)


def _safe_date(val) -> date | None:
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


def store_budget_lines(session: Session, df: pd.DataFrame, la_id: int, fy_id: int, batch_id: int):
    for _, row in df.iterrows():
        opened = float(row.get("opened_credits") or 0)
        committed = float(row.get("committed_amount") or 0)
        mandated = float(row.get("mandated_amount") or 0)
        paid = float(row.get("paid_amount") or 0)
        avail = float(row.get("available_amount") or 0) or (opened - committed)
        session.add(BudgetLine(
            local_authority_id=la_id,
            fiscal_year_id=fy_id,
            import_batch_id=batch_id,
            section=str(row.get("section") or "").strip().upper() or "FONCTIONNEMENT",
            chapter=str(row.get("chapter") or "").strip(),
            article=str(row.get("article") or "").strip(),
            service=str(row.get("service") or "").strip(),
            label=str(row.get("label") or "").strip(),
            voted_amount=float(row.get("voted_amount") or 0),
            opened_credits=opened,
            committed_amount=committed,
            mandated_amount=mandated,
            paid_amount=paid,
            available_amount=avail,
        ))


def store_commitments(session: Session, df: pd.DataFrame, la_id: int, fy_id: int, batch_id: int):
    for _, row in df.iterrows():
        committed = float(row.get("committed_amount") or 0)
        mandated = float(row.get("mandated_amount") or 0)
        remaining = float(row.get("remaining_amount") or 0) or (committed - mandated)
        session.add(Commitment(
            local_authority_id=la_id,
            fiscal_year_id=fy_id,
            import_batch_id=batch_id,
            commitment_number=str(row.get("commitment_number") or ""),
            date=_safe_date(row.get("date")),
            supplier_name=str(row.get("supplier_name") or ""),
            service=str(row.get("service") or ""),
            chapter=str(row.get("chapter") or ""),
            article=str(row.get("article") or ""),
            object=str(row.get("object") or ""),
            committed_amount=committed,
            mandated_amount=mandated,
            remaining_amount=remaining,
            contract_reference=str(row.get("contract_reference") or "").strip() or None,
            status=str(row.get("status") or "open").lower(),
        ))


def store_mandates(session: Session, df: pd.DataFrame, la_id: int, fy_id: int, batch_id: int):
    for _, row in df.iterrows():
        session.add(Mandate(
            local_authority_id=la_id,
            fiscal_year_id=fy_id,
            import_batch_id=batch_id,
            mandate_number=str(row.get("mandate_number") or ""),
            date=_safe_date(row.get("date")),
            supplier_name=str(row.get("supplier_name") or ""),
            amount=float(row.get("amount") or 0),
            chapter=str(row.get("chapter") or ""),
            article=str(row.get("article") or ""),
            service=str(row.get("service") or ""),
            status=str(row.get("status") or "validated").lower(),
            rejection_reason=str(row.get("rejection_reason") or "") or None,
        ))


def store_suppliers(session: Session, df: pd.DataFrame, la_id: int, fy_id: int, batch_id: int):
    for _, row in df.iterrows():
        name = str(row.get("name") or "")
        session.add(Supplier(
            local_authority_id=la_id,
            import_batch_id=batch_id,
            name=name,
            siret=str(row.get("siret") or "") or None,
            internal_reference=str(row.get("internal_reference") or "") or None,
            normalized_name=name.upper().strip(),
        ))


STORE_FNS = {
    "budget_lines": store_budget_lines,
    "commitments": store_commitments,
    "mandates": store_mandates,
    "suppliers": store_suppliers,
}


def run_import(
    session: Session,
    file_bytes: bytes,
    file_name: str,
    la_id: int,
    fy_id: int,
    data_type: str | None = None,
    column_mapping: dict | None = None,
) -> ImportBatch:
    df, file_type = load_file(file_bytes, file_name)
    detected_type = data_type or detect_data_type(list(df.columns))
    aliases = get_aliases_for_type(detected_type)
    mapping = column_mapping or auto_map_columns(list(df.columns), aliases)

    cleaned, warnings = validate_and_clean(df, mapping, detected_type)
    quality = compute_quality_score(cleaned, warnings)

    batch = ImportBatch(
        local_authority_id=la_id,
        file_name=file_name,
        file_type=file_type,
        data_type=detected_type,
        row_count=len(df),
        quality_score=quality,
        status="completed",
        warnings="\n".join(warnings) if warnings else None,
    )
    session.add(batch)
    session.flush()

    store_fn = STORE_FNS.get(detected_type)
    if store_fn:
        store_fn(session, cleaned, la_id, fy_id, batch.id)

    session.commit()
    return batch
