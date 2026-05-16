import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from database.connection import get_session
from database.models import Alert
from finance.indicators import get_budget_summary, get_chapter_breakdown
from finance.rules import run_all_rules


def fmt_eur(v: float) -> str:
    return f"€{v:,.0f}".replace(",", " ")


def render(la_id: int, fy_id: int, la_name: str, year: int):
    session = get_session()

    st.title(f"Dashboard — {la_name} — {year}")

    summary = get_budget_summary(session, la_id, fy_id)
    if not summary:
        st.warning("No budget data found. Import sample data from the sidebar to get started.")
        session.close()
        return

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Opened Credits", fmt_eur(summary["total_opened_credits"]))
    col2.metric("Mandated", fmt_eur(summary["total_mandated"]), f"{summary['execution_rate']}% executed")
    col3.metric("Available", fmt_eur(summary["total_available"]))
    col4.metric("Committed Rate", f"{summary['committed_rate']}%")

    st.divider()

    # Gauge — execution rate
    col_gauge, col_donut = st.columns(2)
    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=summary["execution_rate"],
            title={"text": "Overall Execution Rate (%)"},
            gauge={
                "axis": {"range": [0, 100]},
                "steps": [
                    {"range": [0, 40], "color": "#fce4d6"},
                    {"range": [40, 70], "color": "#fff2cc"},
                    {"range": [70, 100], "color": "#e2efda"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "value": summary["execution_rate"]},
            },
        ))
        fig_gauge.update_layout(height=280, margin=dict(t=40, b=10))
        st.plotly_chart(fig_gauge, width="stretch")

    with col_donut:
        labels = ["Mandated", "Committed (not mandated)", "Available"]
        values = [
            summary["total_mandated"],
            max(0, summary["total_committed"] - summary["total_mandated"]),
            summary["total_available"],
        ]
        fig_donut = px.pie(
            names=labels, values=values,
            title="Credit Utilisation",
            color_discrete_sequence=["#4472c4", "#ed7d31", "#a9d18e"],
            hole=0.4,
        )
        fig_donut.update_layout(height=280, margin=dict(t=40, b=10))
        st.plotly_chart(fig_donut, width="stretch")

    # Chapter breakdown bar chart
    chapters = get_chapter_breakdown(session, la_id, fy_id)
    if chapters:
        df_ch = pd.DataFrame(chapters)
        df_ch["label"] = df_ch["section"].str[:4] + " Ch." + df_ch["chapter"]
        fig_bar = px.bar(
            df_ch.head(12),
            x="label", y=["opened_credits", "committed_amount", "mandated_amount"],
            barmode="group",
            title="Budget by Chapter — Opened vs Committed vs Mandated",
            labels={"value": "Amount (€)", "label": "Chapter", "variable": ""},
            color_discrete_map={
                "opened_credits": "#4472c4",
                "committed_amount": "#ed7d31",
                "mandated_amount": "#a9d18e",
            },
        )
        fig_bar.update_layout(height=360, margin=dict(t=40, b=20))
        st.plotly_chart(fig_bar, width="stretch")

    st.divider()

    # Alerts summary
    st.subheader("Active Alerts")
    col_run, _ = st.columns([1, 3])
    with col_run:
        if st.button("Run Rules Engine", type="primary"):
            with st.spinner("Analysing data..."):
                n = run_all_rules(la_id, fy_id)
            st.success(f"{n} alert(s) generated.")
            st.rerun()

    _sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts = session.query(Alert).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id, status="open"
    ).all()
    alerts.sort(key=lambda a: _sev_order.get(a.severity, 99))

    severity_colors = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    if alerts:
        for a in alerts[:10]:
            icon = severity_colors.get(a.severity, "⚪")
            with st.expander(f"{icon} [{a.severity.upper()}] {a.title}"):
                st.write(f"**Type:** {a.alert_type}")
                st.write(f"**Explanation:** {a.explanation}")
                st.write(f"**Calculation:** `{a.calculation_details}`")
                st.write(f"**Recommendation:** {a.recommendation}")
        if len(alerts) > 10:
            st.info(f"...and {len(alerts) - 10} more alerts. See the Alerts page.")
    else:
        st.info("No alerts. Click 'Run Rules Engine' to analyse the imported data.")

    session.close()
