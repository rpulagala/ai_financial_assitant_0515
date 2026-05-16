"""AI Financial Assistant — Local Governments (PoC)."""
import os
import streamlit as st

import config
from database.connection import get_engine, get_session
from database.models import LocalAuthority, FiscalYear

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

get_engine()

st.markdown("""
<style>
[data-testid="stSidebarNavLink"] p {
    font-size: 1.15rem !important;
    font-weight: 500 !important;
}
[data-testid="stSidebarNavLink"] svg {
    width: 1.2rem !important;
    height: 1.2rem !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

SAMPLE_FILES = [
    ("sample_data/budget_lines.csv", "budget_lines"),
    ("sample_data/commitments.csv",  "commitments"),
    ("sample_data/mandates.csv",     "mandates"),
    ("sample_data/suppliers.csv",    "suppliers"),
]


def load_demo_data(la_id: int, fy_id: int):
    from ingestion.processor import run_import
    session = get_session()
    for path, data_type in SAMPLE_FILES:
        if not os.path.exists(path):
            st.warning(f"Sample file not found: {path}")
            continue
        with open(path, "rb") as f:
            run_import(session=session, file_bytes=f.read(),
                       file_name=os.path.basename(path),
                       la_id=la_id, fy_id=fy_id, data_type=data_type)
    session.close()


def ensure_demo_tenant() -> tuple[int, int, str, int]:
    session = get_session()
    la = session.query(LocalAuthority).filter_by(tenant_id="demo-01").first()
    if not la:
        la = LocalAuthority(name="Commune de Saint-Exupéry-les-Bains",
                            siret="21340561200019", type="municipality",
                            tenant_id="demo-01")
        session.add(la); session.flush()
    fy = session.query(FiscalYear).filter_by(local_authority_id=la.id, year=2025).first()
    if not fy:
        fy = FiscalYear(local_authority_id=la.id, year=2025, status="open")
        session.add(fy); session.flush()
    la_id, fy_id, la_name, year = la.id, fy.id, la.name, fy.year
    session.commit()
    session.close()
    return la_id, fy_id, la_name, year


# ─── Bootstrap session state ─────────────────────────────────────────────────

la_id, fy_id, la_name, year = ensure_demo_tenant()
st.session_state.setdefault("la_id",   la_id)
st.session_state.setdefault("fy_id",   fy_id)
st.session_state.setdefault("la_name", la_name)
st.session_state.setdefault("year",    year)


# ─── Page callables ──────────────────────────────────────────────────────────

def page_dashboard():
    from ui.dashboard import render
    render(st.session_state.la_id, st.session_state.fy_id,
           st.session_state.la_name, st.session_state.year)


def page_import():
    from ui.import_page import render
    render(st.session_state.la_id, st.session_state.fy_id,
           st.session_state.la_name, st.session_state.year)


def page_chat():
    from ui.chat_page import render
    render(st.session_state.la_id, st.session_state.fy_id,
           st.session_state.la_name, st.session_state.year)


def page_alerts():
    from ui.alerts_page import render
    render(st.session_state.la_id, st.session_state.fy_id,
           st.session_state.la_name, st.session_state.year)


# ─── Navigation (top-left sidebar) ───────────────────────────────────────────

pg = st.navigation([
    st.Page(page_dashboard, title="Dashboard", icon="📊", default=True),
    st.Page(page_import,    title="Import",    icon="📂"),
    st.Page(page_chat,      title="AI Chat",   icon="🤖"),
    st.Page(page_alerts,    title="Alerts",    icon="🚨"),
])

# ─── Sidebar extras (rendered below the nav links) ───────────────────────────

with st.sidebar:
    st.divider()
    st.caption(f"**{la_name}** · {year}")

    if st.button("Load Sample Data", use_container_width=True):
        with st.spinner("Loading 4 sample datasets..."):
            load_demo_data(st.session_state.la_id, st.session_state.fy_id)
        st.success("Sample data loaded.")
        st.rerun()

    st.divider()
    api_key = st.text_input(
        "Anthropic API Key",
        value=config.ANTHROPIC_API_KEY,
        type="password",
        help="Required for AI Chat. Set ANTHROPIC_API_KEY env var or enter here.",
    )
    if api_key:
        config.ANTHROPIC_API_KEY = api_key

    st.divider()
    st.caption(config.APP_VERSION)

pg.run()
