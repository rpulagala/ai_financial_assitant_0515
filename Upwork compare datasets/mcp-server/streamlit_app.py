import os
import httpx
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from datetime import date, timedelta
import pandas as pd

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AAPL – Apple Inc.",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1200px; }
  [data-testid="metric-container"] {
    background: #f8f9fa; border: 1px solid #e0e0e0;
    border-radius: 8px; padding: 14px 18px;
  }
  [data-testid="stMetricLabel"]  { font-size: 11px !important; color: #80868b !important; text-transform: uppercase; letter-spacing: 0.5px; }
  [data-testid="stMetricValue"]  { font-size: 22px !important; color: #202124 !important; }
  h3 { font-size: 12px !important; text-transform: uppercase !important;
       color: #80868b !important; letter-spacing: 0.5px !important; }
  a  { color: #1a73e8 !important; }
</style>
""", unsafe_allow_html=True)

# ── API key ───────────────────────────────────────────────────────────────────

load_dotenv()

def _api_key() -> str:
    # Prefer Streamlit Cloud secrets, fall back to .env / env var
    try:
        return st.secrets["FINANCIAL_DATASETS_API_KEY"]
    except Exception:
        return os.environ.get("FINANCIAL_DATASETS_API_KEY", "")

TICKER   = "AAPL"
API_BASE = "https://api.financialdatasets.ai"

# ── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch(path: str) -> dict:
    key = _api_key()
    headers = {"X-API-KEY": key} if key else {}
    try:
        with httpx.Client() as c:
            r = c.get(f"{API_BASE}{path}", headers=headers, timeout=30)
            return r.json() if r.is_success else {}
    except Exception as e:
        return {"error": str(e)}

# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_money(v):
    if v is None: return "—"
    abs_v, sign = abs(v), "-" if v < 0 else ""
    if abs_v >= 1e12: return f"{sign}${abs_v/1e12:.2f}T"
    if abs_v >= 1e9:  return f"{sign}${abs_v/1e9:.2f}B"
    if abs_v >= 1e6:  return f"{sign}${abs_v/1e6:.2f}M"
    return f"{sign}${abs_v:.2f}"

def fmt_pct(num, den):
    if not num or not den: return "—"
    return f"{num / den * 100:.1f}%"

def fmt_date(s):
    if not s: return "—"
    try:
        return pd.to_datetime(s).strftime("%b %d, %Y")
    except Exception:
        return s

def q_label(s: dict) -> str:
    raw = s.get("calendar_date") or s.get("report_date") or s.get("date") or ""
    try:
        d = pd.to_datetime(raw)
        return f"Q{(d.month - 1) // 3 + 1} '{d.year % 100:02d}"
    except Exception:
        return raw

# ── Load all data ─────────────────────────────────────────────────────────────

today  = date.today()
start  = (today - timedelta(days=1826)).isoformat()  # 5 years back

with st.spinner("Loading AAPL data…"):
    snap    = fetch(f"/prices/snapshot/?ticker={TICKER}")
    prices  = fetch(f"/prices/?ticker={TICKER}&interval=day&interval_multiplier=1&start_date={start}&end_date={today.isoformat()}")
    income  = fetch(f"/financials/income-statements/?ticker={TICKER}&period=quarterly&limit=4")
    balance = fetch(f"/financials/balance-sheets/?ticker={TICKER}&period=quarterly&limit=1")
    cash    = fetch(f"/financials/cash-flow-statements/?ticker={TICKER}&period=quarterly&limit=4")
    news    = fetch(f"/news/?ticker={TICKER}")
    filings = fetch(f"/filings/?ticker={TICKER}&limit=8")

if not _api_key():
    st.warning("No API key found. Set `FINANCIAL_DATASETS_API_KEY` in `.env` or Streamlit Cloud secrets.", icon="⚠️")

# ── Header ────────────────────────────────────────────────────────────────────

s      = snap.get("snapshot", {})
price  = s.get("price") or s.get("close") or 0
open_p = s.get("open") or price
change = price - open_p
pct    = (change / open_p * 100) if open_p else 0
sign   = "+" if change >= 0 else ""
color  = "#137333" if change >= 0 else "#c5221f"
ts     = fmt_date(s.get("time") or s.get("date"))

st.markdown("<div style='font-size:16px;color:#3c4043;margin-bottom:4px'>Apple Inc. (AAPL)</div>", unsafe_allow_html=True)
st.markdown(
    f"<div style='display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px'>"
    f"<span style='font-size:40px;font-weight:400;color:#202124;letter-spacing:-1px'>${price:.2f}</span>"
    f"<span style='font-size:20px;color:{color}'>{sign}${change:.2f} ({sign}{pct:.2f}%)</span>"
    f"</div>",
    unsafe_allow_html=True,
)
st.markdown(f"<div style='font-size:12px;color:#80868b;margin-bottom:18px'>As of {ts}</div>", unsafe_allow_html=True)
st.divider()

# ── Price chart ───────────────────────────────────────────────────────────────

price_rows = sorted(prices.get("prices", []), key=lambda x: x["time"])

if price_rows:
    df = pd.DataFrame(price_rows)
    df["time"] = pd.to_datetime(df["time"])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=df["time"], y=df["close"],
            name="Close",
            line=dict(color="#0b8043", width=1.8),
            fill="tozeroy", fillcolor="rgba(11,128,67,0.07)",
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>$%{y:.2f}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=df["time"], y=df["volume"],
            name="Volume",
            marker_color="rgba(11,128,67,0.15)",
            hovertemplate="Vol: %{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )

    six_months_ago = (today - timedelta(days=182)).isoformat()

    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=7,  label="1D",  step="day",   stepmode="backward"),
                    dict(count=14, label="5D",  step="day",   stepmode="backward"),
                    dict(count=1,  label="1M",  step="month", stepmode="backward"),
                    dict(count=6,  label="6M",  step="month", stepmode="backward"),
                    dict(count=1,  label="YTD", step="year",  stepmode="todate"),
                    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                    dict(count=5,  label="5Y",  step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="white", bordercolor="#e0e0e0",
                activecolor="#e8f0fe",
                font=dict(color="#3c4043", size=12),
                x=0, xanchor="left", y=1.08,
            ),
            range=[six_months_ago, today.isoformat()],
            showgrid=True, gridcolor="rgba(0,0,0,0.04)",
            tickfont=dict(color="#80868b", size=11),
            showline=False, zeroline=False,
        ),
        yaxis=dict(
            side="right", showgrid=True, gridcolor="rgba(0,0,0,0.04)",
            tickprefix="$", tickfont=dict(color="#80868b", size=11),
            showline=False, zeroline=False,
        ),
        yaxis2=dict(
            showgrid=False, showticklabels=False, zeroline=False,
            range=[0, df["volume"].max() * 6],
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.warning("No price history available.")

st.divider()

# ── KPI metrics ───────────────────────────────────────────────────────────────

stmts = income.get("income_statements", [])
flows = cash.get("cash_flow_statements", [])

ttm_rev = sum(s.get("revenue") or 0 for s in stmts) or None
ttm_ni  = sum(s.get("net_income") or 0 for s in stmts) or None
eps     = (stmts[0].get("eps_diluted") or stmts[0].get("eps")) if stmts else None
fcf     = flows[0].get("free_cash_flow") if flows else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue (TTM)",    fmt_money(ttm_rev), help="Trailing 12 months")
c2.metric("Net Income (TTM)", fmt_money(ttm_ni),  help="Trailing 12 months")
c3.metric("EPS Diluted",      f"${eps:.2f}" if eps is not None else "—", help="Latest quarter")
c4.metric("Free Cash Flow",   fmt_money(fcf), help="Latest quarter")

st.divider()

# ── Income statement ──────────────────────────────────────────────────────────

st.markdown("### Income Statement (Quarterly)")

if stmts:
    cols = [q_label(s) for s in stmts]
    data = {
        "Revenue":          [fmt_money(s.get("revenue"))          for s in stmts],
        "Gross Profit":     [fmt_money(s.get("gross_profit"))      for s in stmts],
        "Operating Income": [fmt_money(s.get("operating_income"))  for s in stmts],
        "Net Income":       [fmt_money(s.get("net_income"))        for s in stmts],
        "EPS Diluted":      [f"${s.get('eps_diluted') or s.get('eps') or 0:.2f}" for s in stmts],
        "Gross Margin":     [fmt_pct(s.get("gross_profit"),     s.get("revenue")) for s in stmts],
        "Operating Margin": [fmt_pct(s.get("operating_income"), s.get("revenue")) for s in stmts],
        "Net Margin":       [fmt_pct(s.get("net_income"),       s.get("revenue")) for s in stmts],
    }
    st.dataframe(
        pd.DataFrame(data, index=cols).T,
        use_container_width=True,
    )
else:
    st.info("No income statement data.")

# ── Balance sheet + Cash flow ─────────────────────────────────────────────────

left, right = st.columns(2)

with left:
    st.markdown("### Balance Sheet (Latest Quarter)")
    sheets = balance.get("balance_sheets", [])
    if sheets:
        sh  = sheets[0]
        col = fmt_date(sh.get("calendar_date") or sh.get("date"))
        items = {
            "Cash & Equivalents":   fmt_money(sh.get("cash_and_equivalents")),
            "Current Assets":       fmt_money(sh.get("current_assets")),
            "Total Assets":         fmt_money(sh.get("total_assets")),
            "Current Liabilities":  fmt_money(sh.get("current_liabilities")),
            "Total Liabilities":    fmt_money(sh.get("total_liabilities")),
            "Total Debt":           fmt_money(sh.get("total_debt")),
            "Stockholders' Equity": fmt_money(sh.get("stockholders_equity")),
            "Current Ratio": f"{sh['current_assets']/sh['current_liabilities']:.2f}" if sh.get("current_assets") and sh.get("current_liabilities") else "—",
            "Debt / Equity": f"{sh['total_debt']/sh['stockholders_equity']:.2f}" if sh.get("total_debt") and sh.get("stockholders_equity") else "—",
        }
        st.dataframe(
            pd.DataFrame({"Item": items.keys(), col: items.values()}).set_index("Item"),
            use_container_width=True,
        )
    else:
        st.info("No balance sheet data.")

with right:
    st.markdown("### Cash Flow (Quarterly)")
    if flows:
        cf_cols = [q_label(f) for f in flows]
        cf_data = {
            "Operating CF":         [fmt_money(f.get("operating_cash_flow"))   for f in flows],
            "Capital Expenditures": [fmt_money(f.get("capital_expenditures"))  for f in flows],
            "Free Cash Flow":       [fmt_money(f.get("free_cash_flow"))        for f in flows],
            "Investing CF":         [fmt_money(f.get("investing_cash_flow"))   for f in flows],
            "Financing CF":         [fmt_money(f.get("financing_cash_flow"))   for f in flows],
        }
        st.dataframe(
            pd.DataFrame(cf_data, index=cf_cols).T,
            use_container_width=True,
        )
    else:
        st.info("No cash flow data.")

st.divider()

# ── News ──────────────────────────────────────────────────────────────────────

st.markdown("### Latest News")
articles = news.get("news", [])[:6]
if articles:
    news_cols = st.columns(3)
    for i, a in enumerate(articles):
        src   = a.get("source", "News")
        title = a.get("title", "Untitled")
        url   = a.get("url", "#")
        dt    = fmt_date(a.get("published_at") or a.get("date"))
        with news_cols[i % 3]:
            st.markdown(
                f"<div style='border:1px solid #e0e0e0;border-radius:8px;padding:14px;margin-bottom:12px'>"
                f"<div style='font-size:10px;color:#80868b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px'>{src}</div>"
                f"<div style='font-size:13px;font-weight:500;line-height:1.4;margin-bottom:8px'>"
                f"<a href='{url}' target='_blank' style='color:#202124;text-decoration:none'>{title}</a></div>"
                f"<div style='font-size:11px;color:#80868b'>{dt}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
else:
    st.info("No news available.")

st.divider()

# ── SEC Filings ───────────────────────────────────────────────────────────────

st.markdown("### SEC Filings")
filing_list = filings.get("filings", [])
if filing_list:
    rows = [
        {
            "Type":   f.get("filing_type", "N/A"),
            "Filed":  fmt_date(f.get("filing_date") or f.get("date")),
            "Period": fmt_date(f.get("period_of_report") or f.get("period")),
            "Link":   f.get("report_url") or f.get("url") or "",
        }
        for f in filing_list
    ]
    st.dataframe(
        pd.DataFrame(rows),
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="View")},
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No filings available.")
