# AI Financial Assistant — Local Governments
### Phase 1 Proof-of-Concept

---

## What Was Built

A working proof-of-concept for a **sovereign, vertical AI financial intelligence platform** targeting local governments (municipalities, inter-municipal bodies, public authorities). The system acts as an intelligence layer above existing financial data — not a replacement for finance software.

Built in a single session from `Requirement.txt`. The stack is Python + Streamlit + SQLite + Claude API, designed to be upgraded to FastAPI + PostgreSQL + React for the web MVP.

---

## The Problem Being Solved

Local government finance teams have a lot of data but it is scattered, hard to consolidate, and slow to turn into decisions. Specifically:

- Exporting Excel files manually and reconciling tables takes time
- No early warning system for budget risks (credits running out, old commitments, rejected mandates)
- Non-financial users (elected officials, service managers) cannot read raw data
- Producing executive notes is slow and manual
- Heterogeneous software makes cross-system views impossible

This product imports CSV/Excel files, normalises them into a financial data model, runs deterministic anomaly detection rules, and lets users ask questions in plain language — with all answers sourced and traceable back to imported data.

---

## Architecture — Key Design Decisions

### The LLM is an explanation layer, not the brain

The most important architectural principle from `Requirement.txt` is:

> *"The developer should prioritize correctness, traceability, and security over advanced AI sophistication."*

Claude is given **pre-computed, structured data** and asked to explain it in plain language. It never queries the database directly and never invents figures. Every number in an AI answer is traceable to an import batch and a source row.

```
User question
  → Intent classifier (keyword matching)
  → Permission check (tenant filter applied)
  → Deterministic data retrieval (SQLAlchemy queries)
  → Deterministic indicator calculations (finance/indicators.py)
  → Context builder (structured JSON summary)
  → Claude API (explanation + formatting only)
  → Response with citations and confidence level
  → Logged to conversation_logs table
```

### Tenant isolation is enforced at every query

Every database query filters by `local_authority_id`. This is the foundation for future multi-tenant SaaS deployment. The demo runs a single tenant (`tenant_id="demo-01"`).

### Rules engine is deterministic — no LLM involved

Anomaly detection (insufficient credits, old commitments, rejected mandates, supplier concentration) runs as explicit Python rules. The output is stored in the `alerts` table with full calculation details. Claude can then be asked to explain alerts, but the detection itself is rule-based and auditable.

---

## Project Structure

```
AI_financial_assitant_0515/
│
├── app.py                      # Streamlit entry point, st.navigation() setup
├── config.py                   # API key, DB path, model name
├── requirements.txt
├── .env.example                # Copy to .env and set ANTHROPIC_API_KEY
├── Requirement.txt             # Original product requirements document
│
├── database/
│   ├── models.py               # SQLAlchemy ORM — all entities
│   └── connection.py           # SQLite engine + session factory
│
├── ingestion/
│   ├── processor.py            # Full pipeline: load → map → validate → store
│   └── mapper.py               # Auto column-mapping (alias matching)
│
├── finance/
│   ├── indicators.py           # Deterministic KPI calculations (no LLM)
│   └── rules.py                # Business rules engine → Alert records
│
├── ai/
│   └── orchestrator.py         # Intent classify → retrieve → Claude → log
│
├── ui/                         # Streamlit page modules (not standalone scripts)
│   ├── dashboard.py            # KPI cards, gauge, charts, alert preview
│   ├── import_page.py          # File upload, column mapping UI, import history
│   ├── chat_page.py            # AI chat with suggested questions + source citations
│   └── alerts_page.py          # Rules engine output with filters and charts
│
└── sample_data/                # Realistic French municipality demo data
    ├── budget_lines.csv        # 33 lines, €14.4M budget, M57 chapter structure
    ├── commitments.csv         # 30 commitments, intentional anomalies built in
    ├── mandates.csv            # 50 mandates, 7 rejected (14% rejection rate)
    └── suppliers.csv           # 25 suppliers, potential duplicate included
```

---

## Data Model

Core entities (SQLite for PoC, designed to migrate to PostgreSQL):

| Entity | Purpose |
|--------|---------|
| `LocalAuthority` | Tenant root — every query filters by this |
| `FiscalYear` | Year scoping for all financial data |
| `ImportBatch` | Tracks every file upload with quality score and warnings |
| `BudgetLine` | voted → opened → committed → mandated → paid → available |
| `Commitment` | Engagement tracking with supplier, chapter, contract reference |
| `Mandate` | Payment orders with rejection tracking |
| `Supplier` | Normalised supplier registry |
| `Alert` | Rules engine output — severity, explanation, calculation, recommendation |
| `ConversationLog` | Full AI interaction log — question, intent, answer, confidence |

### Critical budget concept distinction

The model enforces the M57 public finance chain. These five amounts must never be confused:

```
voted_amount        → approved by council
opened_credits      → available after amendments
committed_amount    → legally engaged (engagements)
mandated_amount     → payment orders issued (mandats)
paid_amount         → actually paid by treasury
available_amount    = opened_credits - committed_amount
```

---

## Business Rules Implemented

| Rule ID | Detects | Severity |
|---------|---------|---------|
| `INSUF_CREDITS` | Budget line with < 5% credits remaining | High |
| `OLD_COMMITMENT` | Open commitment > 6 months with remaining amount | Medium / High |
| `NO_CONTRACT` | Commitment ≥ €40K without contract reference | Medium |
| `REJECTED_MANDATES` | Suppliers with rejected payment orders | Medium / High |
| `SUPPLIER_CONCENTRATION` | Single supplier > 25% of total spend | Medium / High |
| `ABNORMAL_CONSUMPTION` | Budget line > 98% consumed | High |

Each alert stores: title, explanation, calculation formula, source reference, recommendation, severity, status.

---

## Running the App

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key (needed for AI Chat only)
copy .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
streamlit run app.py
```

App opens at **http://localhost:8501**

**First-time setup in the UI:**
1. Sidebar → **Load Sample Data** (imports all 4 CSV files)
2. Dashboard → **Run Rules Engine** (generates 49 alerts from sample data)
3. Enter your Anthropic API key in the sidebar for AI Chat

---

## AI Chat — How It Works

Intent is classified by keyword matching (no LLM for classification):

| Intent | Triggered by |
|--------|-------------|
| `budget_execution` | execution, rate, credits, chapter, consumed |
| `commitments` | commitment, engaged, remaining, contract |
| `mandates` | mandate, rejected, mandated |
| `suppliers` | supplier, concentration, vendor |
| `alerts` | alert, anomaly, risk |
| `general` | fallback — retrieves all data types |

The AI system prompt enforces hard rules:
- No figure without a source
- No invented data — refuse and state what's missing
- Structure: Summary → Key Figures → Analysis → Limits → Recommendation
- Confidence level: HIGH / MEDIUM / LOW / NONE

Suggested questions are pre-built for common finance director queries.

---

## Navigation

Uses Streamlit's `st.navigation()` / `st.Page()` API (not the legacy `pages/` folder convention). The `ui/` folder holds page modules with `render()` functions — they are not standalone Streamlit scripts. Context (`la_id`, `fy_id`, `la_name`, `year`) is passed via `st.session_state`.

---

## Current State (Phase 1 PoC — complete)

**Working:**
- CSV/Excel import with auto column mapping and quality scoring
- Full financial data model in SQLite
- 6 deterministic business rules generating typed alerts
- AI chat with intent routing, data retrieval, Claude explanation, and logging
- Dashboard with KPI cards, execution gauge, chapter bar chart, alert preview
- Import page with column mapping UI and import history
- Alerts page with severity/type filters and charts
- Sample data for a fictional French municipality (Commune de Saint-Exupéry-les-Bains)

**Not yet built (Phase 2+ scope):**
- Authentication and RBAC (roles: finance director, elected official, service manager, etc.)
- Multi-tenant UI (currently hardcoded to one demo tenant)
- PostgreSQL migration
- RAG module (document indexing and retrieval)
- Word/PDF/Excel report export
- Real-time connector or automated file deposit
- Forecasting and financial ratios
- Proper service-level permissions

---

## Next Steps (Phase 2 priorities per Requirement.txt)

1. **Authentication** — OAuth2/SSO, role-based access, tenant selection at login
2. **PostgreSQL** — swap SQLite engine in `database/connection.py`, add Alembic migrations
3. **Report generation** — budget execution note, old commitments report, supplier concentration report (Word/PDF via `python-docx` + `reportlab`)
4. **RAG module** — document upload → text extraction → chunking → embeddings → pgvector retrieval → citations in AI answers
5. **Multi-tenant UI** — local authority selector, service-level data scoping
6. **FastAPI backend** — separate the data/AI layer from the UI for web MVP

---

## Tech Stack

| Layer | PoC | Target (Phase 2+) |
|-------|-----|--------------------|
| UI | Streamlit | React + Next.js |
| Backend | Streamlit (monolith) | Python FastAPI |
| Database | SQLite | PostgreSQL |
| Vector DB | — | pgvector or Qdrant |
| AI | Claude API (Anthropic) | Abstracted model interface |
| Auth | None | OAuth2 + OpenID Connect |
| Storage | Local filesystem | S3-compatible |

The AI provider is abstracted in `ai/orchestrator.py` (model name via `config.AI_MODEL`). Swapping to Mistral or another provider requires only changing the client and model string.

---

## Sample Data Details

The demo dataset represents **Commune de Saint-Exupéry-les-Bains**, a fictional French municipality, fiscal year 2025.

Intentional anomalies built into the data for rules engine demonstration:
- Several commitments from 2024 still open (old commitment rule triggers)
- ENGIE has 3 rejected mandates (rejected mandates rule)
- Some budget lines at 0% available (insufficient credits rule)
- Articles at 99-100% consumption (abnormal consumption rule)
- Chapters 66 and 012 fully consumed (fixed charges by design)
- One supplier entry with a slight name variation (potential duplicate)

Budget structure follows M57 nomenclature (French local government accounting standard).
