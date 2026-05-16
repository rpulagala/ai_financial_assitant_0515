import streamlit as st
import pandas as pd
import plotly.express as px
from database.connection import get_session
from database.models import Alert
from finance.rules import run_all_rules

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
SEVERITY_COLORS = {"critical": "#FF4B4B", "high": "#FFA500", "medium": "#FFD700", "low": "#90EE90"}


def render(la_id: int, fy_id: int, la_name: str, year: int):
    st.title(f"Alerts & Anomaly Detection — {la_name} — {year}")

    col_run, col_info = st.columns([1, 3])
    with col_run:
        if st.button("Run Rules Engine", type="primary"):
            with st.spinner("Running all rules..."):
                n = run_all_rules(la_id, fy_id)
            st.success(f"{n} alert(s) generated.")
            st.rerun()
    with col_info:
        st.caption(
            "The rules engine runs deterministic checks on imported data. "
            "Results are stored and displayed below."
        )

    session = get_session()
    alerts = (
        session.query(Alert)
        .filter_by(local_authority_id=la_id, fiscal_year_id=fy_id)
        .all()
    )
    session.close()

    if not alerts:
        st.info("No alerts yet. Import data and click 'Run Rules Engine'.")
        return

    # Summary charts
    df = pd.DataFrame([{
        "type": a.alert_type,
        "severity": a.severity,
        "status": a.status,
        "title": a.title,
    } for a in alerts])

    col1, col2 = st.columns(2)
    with col1:
        sev_counts = df["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        sev_counts["order"] = sev_counts["severity"].map(SEVERITY_ORDER)
        sev_counts = sev_counts.sort_values("order")
        fig = px.bar(
            sev_counts, x="severity", y="count",
            color="severity",
            color_discrete_map=SEVERITY_COLORS,
            title="Alerts by Severity",
        )
        fig.update_layout(showlegend=False, height=280)
        st.plotly_chart(fig, width="stretch")

    with col2:
        type_counts = df["type"].value_counts().reset_index()
        type_counts.columns = ["type", "count"]
        fig2 = px.pie(
            type_counts, names="type", values="count",
            title="Alerts by Type", hole=0.35,
        )
        fig2.update_layout(height=280)
        st.plotly_chart(fig2, width="stretch")

    st.divider()

    # Filters
    col_f1, col_f2 = st.columns(2)
    sev_filter = col_f1.multiselect(
        "Severity", options=["critical", "high", "medium", "low"], default=["critical", "high", "medium"]
    )
    type_filter = col_f2.multiselect(
        "Alert Type", options=df["type"].unique().tolist(), default=df["type"].unique().tolist()
    )

    filtered = [
        a for a in alerts
        if a.severity in sev_filter and a.alert_type in type_filter
    ]
    filtered.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 99))

    st.subheader(f"{len(filtered)} Alert(s)")

    for a in filtered:
        icon = SEVERITY_ICONS.get(a.severity, "⚪")
        with st.expander(f"{icon} [{a.severity.upper()}] {a.title}"):
            cols = st.columns([2, 1])
            with cols[0]:
                st.write(f"**Rule:** `{a.rule_id}`")
                st.write(f"**Type:** {a.alert_type}")
                st.write(f"**Explanation:**")
                st.write(a.explanation)
            with cols[1]:
                st.write(f"**Calculation:**")
                st.code(a.calculation_details or "N/A")
            st.write(f"**Recommendation:** {a.recommendation}")
            st.caption(f"Generated: {str(a.created_at)[:19]} | Status: {a.status}")
