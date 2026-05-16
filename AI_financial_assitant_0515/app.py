"""AI Financial Assistant — Local Governments (PoC)."""
import os
import streamlit as st
from datetime import date

import config
from database.connection import get_engine, get_session
from database.models import LocalAuthority, FiscalYear, Base
from ingestion.processor import run_import

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure DB schema exists
get_engine()


# ─── Demo data loader ────────────────────────────────────────────────────────

SAMPLE_FILES = [
    ("sample_data/budget_lines.csv", "budget_lines"),
    ("sample_data/commitments.csv", "commitments"),
    ("sample_data/mandates.csv", "mandates"),
    ("sample_data/suppliers.csv", "suppliers"),
]


def load_demo_data(la_id: int, fy_id: int):
    session = get_session()
    for path, data_type in SAMPLE_FILES:
        if not os.path.exists(path):
            st.warning(f"Sample file not found: {path}")
            continue
        with open(path, "rb") as f:
            run_import(
                session=session,
                file_bytes=f.read(),
                file_name=os.path.basename(path),
                la_id=la_id,
                fy_id=fy_id,
                data_type=data_type,
            )
    session.close()


def ensure_demo_tenant() -> tuple[int, int]:
    """Create the demo local authority and fiscal year if they don't exist."""
    session = get_session()
    la = session.query(LocalAuthority).filter_by(tenant_id="demo-01").first()
    if not la:
        la = LocalAuthority(
            name="Commune de Saint-Exupéry-les-Bains",
            siret="21340561200019",
            type="municipality",
            tenant_id="demo-01",
        )
        session.add(la)
        session.flush()

    fy = session.query(FiscalYear).filter_by(local_authority_id=la.id, year=2025).first()
    if not fy:
        fy = FiscalYear(
            local_authority_id=la.id,
            year=2025,
            status="open",
        )
        session.add(fy)
        session.flush()

    la_id, fy_id = la.id, fy.id
    session.commit()
    session.close()
    return la_id, fy_id


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.title("🏛️ AI Financial\nAssistant")
        st.caption(config.APP_VERSION)
        st.divider()

        la_id, fy_id = ensure_demo_tenant()

        session = get_session()
        authorities = session.query(LocalAuthority).all()
        years_available = session.query(FiscalYear).filter_by(local_authority_id=la_id).all()
        session.close()

        la_names = {a.id: a.name for a in authorities}
        selected_la_id = st.selectbox(
            "Local Authority",
            options=[a.id for a in authorities],
            format_func=lambda i: la_names[i],
        )

        year_options = {fy.id: fy.year for fy in years_available}
        selected_fy_id = st.selectbox(
            "Fiscal Year",
            options=list(year_options.keys()),
            format_func=lambda i: year_options[i],
        )
        selected_year = year_options.get(selected_fy_id, 2025)

        st.divider()
        st.subheader("Demo Data")
        if st.button("Load Sample Data", use_container_width=True):
            with st.spinner("Loading 4 sample datasets..."):
                load_demo_data(selected_la_id, selected_fy_id)
            st.success("Sample data loaded.")
            st.rerun()

        st.divider()
        api_key = st.text_input(
            "Anthropic API Key",
            value=config.ANTHROPIC_API_KEY,
            type="password",
            help="Required for AI chat. Set ANTHROPIC_API_KEY env var or enter here.",
        )
        if api_key:
            config.ANTHROPIC_API_KEY = api_key

        st.divider()
        nav = st.radio(
            "Navigation",
            options=["Dashboard", "Import", "AI Chat", "Alerts"],
            label_visibility="collapsed",
        )

    la_name = la_names.get(selected_la_id, "Unknown")
    return selected_la_id, selected_fy_id, la_name, selected_year, nav


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    la_id, fy_id, la_name, year, nav = render_sidebar()

    if nav == "Dashboard":
        from pages.dashboard import render
        render(la_id, fy_id, la_name, year)

    elif nav == "Import":
        from pages.import_page import render
        render(la_id, fy_id, la_name, year)

    elif nav == "AI Chat":
        from pages.chat_page import render
        render(la_id, fy_id, la_name, year)

    elif nav == "Alerts":
        from pages.alerts_page import render
        render(la_id, fy_id, la_name, year)


if __name__ == "__main__":
    main()
