import streamlit as st
import pandas as pd
from database.connection import get_session
from database.models import ImportBatch
from ingestion.processor import load_file, run_import
from ingestion.mapper import auto_map_columns, detect_data_type, get_aliases_for_type


DATA_TYPE_LABELS = {
    "budget_lines": "Budget Lines",
    "commitments": "Commitments",
    "mandates": "Mandates",
    "suppliers": "Suppliers",
    "unknown": "Unknown",
}


def render(la_id: int, fy_id: int, la_name: str, year: int):
    st.title(f"File Import — {la_name} — {year}")

    uploaded = st.file_uploader(
        "Upload Excel (.xlsx) or CSV file",
        type=["csv", "xlsx", "xls"],
    )

    if not uploaded:
        st.info("Upload a CSV or Excel file to begin. Sample files are available in the `sample_data/` folder.")
        _show_import_history(la_id, fy_id)
        return

    file_bytes = uploaded.read()
    file_name = uploaded.name

    df, file_type = load_file(file_bytes, file_name)
    st.success(f"File loaded: {len(df)} rows, {len(df.columns)} columns ({file_type.upper()})")

    # Detect data type
    detected = detect_data_type(list(df.columns))
    data_type = st.selectbox(
        "Data type",
        options=list(DATA_TYPE_LABELS.keys()),
        index=list(DATA_TYPE_LABELS.keys()).index(detected) if detected in DATA_TYPE_LABELS else 0,
        format_func=lambda k: DATA_TYPE_LABELS[k],
    )

    # Preview
    with st.expander("Preview (first 5 rows)"):
        st.dataframe(df.head(5))

    # Column mapping
    st.subheader("Column Mapping")
    aliases = get_aliases_for_type(data_type)
    auto_mapping = auto_map_columns(list(df.columns), aliases)

    cols = [None] + list(df.columns)
    user_mapping: dict[str, str | None] = {}
    n_cols = 3
    fields = list(aliases.keys())
    rows = [fields[i:i+n_cols] for i in range(0, len(fields), n_cols)]

    for row in rows:
        grid = st.columns(n_cols)
        for i, field in enumerate(row):
            default = auto_mapping.get(field)
            default_idx = cols.index(default) if default in cols else 0
            chosen = grid[i].selectbox(
                f"`{field}`",
                options=cols,
                index=default_idx,
                key=f"map_{field}",
            )
            user_mapping[field] = chosen

    mapped = sum(1 for v in user_mapping.values() if v)
    st.write(f"**{mapped}/{len(user_mapping)}** fields mapped.")

    if st.button("Import Data", type="primary"):
        session = get_session()
        with st.spinner("Importing..."):
            batch = run_import(
                session=session,
                file_bytes=file_bytes,
                file_name=file_name,
                la_id=la_id,
                fy_id=fy_id,
                data_type=data_type,
                column_mapping=user_mapping,
            )
        _show_import_report(batch)
        session.close()

    _show_import_history(la_id, fy_id)


def _show_import_report(batch: ImportBatch):
    st.subheader("Import Report")
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows Imported", batch.row_count)
    col2.metric("Quality Score", f"{batch.quality_score:.0f}/100")
    col3.metric("Status", batch.status.upper())
    st.write(f"**File:** {batch.file_name}")
    st.write(f"**Data Type:** {batch.data_type}")
    st.write(f"**Imported at:** {batch.imported_at}")
    if batch.warnings:
        with st.expander("Warnings"):
            st.text(batch.warnings)
    else:
        st.success("No warnings.")


def _show_import_history(la_id: int, fy_id: int):
    st.subheader("Import History")
    session = get_session()
    batches = (
        session.query(ImportBatch)
        .filter_by(local_authority_id=la_id)
        .order_by(ImportBatch.imported_at.desc())
        .limit(20)
        .all()
    )
    session.close()

    if not batches:
        st.info("No imports yet.")
        return

    rows = [
        {
            "Date": str(b.imported_at)[:19],
            "File": b.file_name,
            "Type": b.data_type,
            "Rows": b.row_count,
            "Quality": f"{b.quality_score:.0f}%",
            "Status": b.status,
        }
        for b in batches
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
