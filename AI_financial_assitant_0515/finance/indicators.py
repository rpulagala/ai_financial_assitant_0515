"""Deterministic financial indicator calculations — no LLM involved here."""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from database.models import BudgetLine, Commitment, Mandate, Supplier


def get_budget_summary(session: Session, la_id: int, fy_id: int) -> dict:
    lines = session.query(BudgetLine).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()

    if not lines:
        return {}

    total_voted = sum(l.voted_amount for l in lines)
    total_opened = sum(l.opened_credits for l in lines)
    total_committed = sum(l.committed_amount for l in lines)
    total_mandated = sum(l.mandated_amount for l in lines)
    total_paid = sum(l.paid_amount for l in lines)
    total_available = sum(l.available_amount for l in lines)

    execution_rate = (total_mandated / total_opened * 100) if total_opened > 0 else 0
    committed_rate = (total_committed / total_opened * 100) if total_opened > 0 else 0

    return {
        "total_voted": total_voted,
        "total_opened_credits": total_opened,
        "total_committed": total_committed,
        "total_mandated": total_mandated,
        "total_paid": total_paid,
        "total_available": total_available,
        "execution_rate": round(execution_rate, 1),
        "committed_rate": round(committed_rate, 1),
        "line_count": len(lines),
        "source": "budget_lines table",
    }


def get_chapter_breakdown(session: Session, la_id: int, fy_id: int) -> list[dict]:
    lines = session.query(BudgetLine).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()

    chapters: dict[str, dict] = {}
    for l in lines:
        key = f"{l.section}-{l.chapter}"
        if key not in chapters:
            chapters[key] = {
                "section": l.section,
                "chapter": l.chapter,
                "opened_credits": 0,
                "mandated_amount": 0,
                "committed_amount": 0,
                "available_amount": 0,
            }
        chapters[key]["opened_credits"] += l.opened_credits
        chapters[key]["mandated_amount"] += l.mandated_amount
        chapters[key]["committed_amount"] += l.committed_amount
        chapters[key]["available_amount"] += l.available_amount

    result = []
    for ch in chapters.values():
        rate = (ch["mandated_amount"] / ch["opened_credits"] * 100) if ch["opened_credits"] > 0 else 0
        ch["execution_rate"] = round(rate, 1)
        result.append(ch)

    return sorted(result, key=lambda x: x["opened_credits"], reverse=True)


def get_commitment_stats(session: Session, la_id: int, fy_id: int) -> dict:
    comms = session.query(Commitment).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()

    if not comms:
        return {}

    six_months_ago = date.today() - timedelta(days=180)
    old_open = [c for c in comms if c.status == "open" and c.date and c.date < six_months_ago and c.remaining_amount > 0]
    no_contract = [c for c in comms if not c.contract_reference and c.committed_amount > 10000]
    total_remaining = sum(c.remaining_amount for c in comms if c.status == "open")

    return {
        "total_commitments": len(comms),
        "open_commitments": len([c for c in comms if c.status == "open"]),
        "total_remaining_amount": total_remaining,
        "old_open_commitments": len(old_open),
        "old_open_amount": sum(c.remaining_amount for c in old_open),
        "no_contract_count": len(no_contract),
        "source": "commitments table",
    }


def get_mandate_stats(session: Session, la_id: int, fy_id: int) -> dict:
    mandates = session.query(Mandate).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()

    if not mandates:
        return {}

    rejected = [m for m in mandates if m.status == "rejected"]
    total_amount = sum(m.amount for m in mandates if m.status == "validated")
    rejected_amount = sum(m.amount for m in rejected)
    rejection_rate = (len(rejected) / len(mandates) * 100) if mandates else 0

    reasons: dict[str, int] = {}
    for m in rejected:
        reason = m.rejection_reason or "Unknown"
        reasons[reason] = reasons.get(reason, 0) + 1

    return {
        "total_mandates": len(mandates),
        "validated_mandates": len([m for m in mandates if m.status == "validated"]),
        "rejected_mandates": len(rejected),
        "rejection_rate": round(rejection_rate, 1),
        "total_validated_amount": total_amount,
        "rejected_amount": rejected_amount,
        "top_rejection_reasons": sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5],
        "source": "mandates table",
    }


def get_supplier_stats(session: Session, la_id: int, fy_id: int) -> dict:
    mandates = session.query(Mandate).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id, status="validated"
    ).all()

    if not mandates:
        return {}

    totals: dict[str, float] = {}
    for m in mandates:
        name = m.supplier_name or "Unknown"
        totals[name] = totals.get(name, 0) + m.amount

    grand_total = sum(totals.values())
    top = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:10]
    top_share = (top[0][1] / grand_total * 100) if grand_total > 0 and top else 0

    return {
        "unique_suppliers": len(totals),
        "total_amount": grand_total,
        "top_suppliers": [{"name": n, "amount": a, "share": round(a / grand_total * 100, 1)} for n, a in top],
        "top_supplier_share": round(top_share, 1),
        "source": "mandates table aggregated by supplier",
    }
