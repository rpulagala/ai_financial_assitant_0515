"""AI orchestration layer — Claude is given structured data, never raw SQL access."""
import json
import uuid
from datetime import datetime
import anthropic
from sqlalchemy.orm import Session
from database.models import Alert, ConversationLog
from finance.indicators import (
    get_budget_summary,
    get_chapter_breakdown,
    get_commitment_stats,
    get_mandate_stats,
    get_supplier_stats,
)
import config

SYSTEM_PROMPT = """You are a specialized financial assistant for local governments (municipalities).

Your role is to analyze financial data and answer questions clearly and accurately.

ABSOLUTE RULES:
1. Never invent figures. Use ONLY the data provided in the context block.
2. Always cite the source of each figure (table name or calculation).
3. If data is missing or insufficient, say so explicitly — do not guess.
4. Distinguish clearly between: FACT (from data), ANALYSIS (your interpretation), RECOMMENDATION.
5. Include a confidence level: HIGH (full data available), MEDIUM (partial data), LOW (limited data).
6. Structure every answer as:
   - **Summary** (1-2 sentences)
   - **Key Figures** (bullet points with sources)
   - **Analysis** (what the numbers mean)
   - **Limits** (what data is missing or uncertain)
   - **Recommendation** (cautious, clearly labelled)
7. If a question is outside the available data scope, refuse politely and explain why.
8. Write in clear, professional language suitable for finance directors and elected officials.
"""

INTENT_KEYWORDS = {
    "budget_execution": [
        "execution", "taux", "rate", "budget", "crédits", "credits", "consommé",
        "consumed", "ouvert", "opened", "voté", "voted", "disponible", "available",
        "chapitre", "chapter", "section",
    ],
    "commitments": [
        "engagement", "commitment", "engagé", "committed", "restant", "remaining",
        "ancien", "old", "marché", "contract", "fournisseur commitment",
    ],
    "mandates": [
        "mandat", "mandate", "rejeté", "rejected", "rejet", "rejection",
        "mandaté", "mandated",
    ],
    "suppliers": [
        "fournisseur", "supplier", "prestataire", "concentration", "tiers",
        "prestataires", "vendors",
    ],
    "alerts": [
        "alerte", "alert", "anomalie", "anomaly", "risque", "risk", "problème",
        "issue", "warning",
    ],
}


def classify_intent(question: str) -> str:
    q_lower = question.lower()
    scores = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q_lower:
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def build_context(data: dict) -> str:
    parts = []
    for key, value in data.items():
        parts.append(f"=== {key.upper().replace('_', ' ')} ===")
        parts.append(json.dumps(value, indent=2, ensure_ascii=False, default=str))
    return "\n".join(parts)


def answer_question(
    question: str,
    la_id: int,
    fy_id: int,
    session: Session,
    session_id: str | None = None,
) -> dict:
    if not config.ANTHROPIC_API_KEY:
        return {
            "answer": "No ANTHROPIC_API_KEY configured. Please set it in your .env file.",
            "intent": "error",
            "confidence": "none",
            "sources": [],
        }

    intent = classify_intent(question)
    data: dict = {}
    sources: list[str] = []

    # Retrieve structured data based on intent — no LLM involved here
    if intent in ("budget_execution", "general"):
        summary = get_budget_summary(session, la_id, fy_id)
        if summary:
            data["budget_summary"] = summary
            data["chapter_breakdown"] = get_chapter_breakdown(session, la_id, fy_id)
            sources.append("budget_lines table")

    if intent in ("commitments", "general"):
        comm = get_commitment_stats(session, la_id, fy_id)
        if comm:
            data["commitment_statistics"] = comm
            sources.append("commitments table")

    if intent in ("mandates", "general"):
        mand = get_mandate_stats(session, la_id, fy_id)
        if mand:
            data["mandate_statistics"] = mand
            sources.append("mandates table")

    if intent in ("suppliers", "general"):
        supp = get_supplier_stats(session, la_id, fy_id)
        if supp:
            data["supplier_statistics"] = supp
            sources.append("mandates table (aggregated by supplier)")

    if intent in ("alerts", "general"):
        alerts = session.query(Alert).filter_by(
            local_authority_id=la_id, fiscal_year_id=fy_id, status="open"
        ).order_by(Alert.severity.desc()).limit(20).all()
        if alerts:
            data["active_alerts"] = [
                {"type": a.alert_type, "severity": a.severity, "title": a.title, "recommendation": a.recommendation}
                for a in alerts
            ]
            sources.append("alerts table")

    if not data:
        answer_text = (
            "I do not have sufficient financial data to answer this question. "
            "Please import budget lines, commitments, mandates, or suppliers first."
        )
        confidence = "none"
    else:
        context = build_context(data)
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.AI_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Available financial data (use ONLY these figures):\n\n{context}"
                ),
            }],
        )
        answer_text = response.content[0].text
        confidence = "high" if len(data) >= 2 else "medium"

    # Log conversation
    log = ConversationLog(
        local_authority_id=la_id,
        session_id=session_id or str(uuid.uuid4()),
        question=question,
        intent=intent,
        answer=answer_text,
        confidence_level=confidence,
    )
    session.add(log)
    session.commit()

    return {
        "answer": answer_text,
        "intent": intent,
        "confidence": confidence,
        "sources": sources,
    }
