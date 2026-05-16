"""Business rules engine — deterministic anomaly detection."""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from database.models import BudgetLine, Commitment, Mandate, Alert, Supplier
from database.connection import get_session


def _clear_alerts(session: Session, la_id: int, fy_id: int):
    session.query(Alert).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).delete()


def rule_insufficient_credits(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    lines = session.query(BudgetLine).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()
    for line in lines:
        if line.opened_credits > 0:
            avail_pct = line.available_amount / line.opened_credits * 100
            if avail_pct < 5:
                alerts.append(Alert(
                    local_authority_id=la_id,
                    fiscal_year_id=fy_id,
                    alert_type="Insufficient Credits",
                    severity="high",
                    rule_id="INSUF_CREDITS",
                    entity_type="budget_line",
                    entity_id=line.id,
                    title=f"Chapter {line.chapter} — Article {line.article}: only {avail_pct:.1f}% credits remaining",
                    explanation=(
                        f"Article {line.article} ({line.label}) has opened credits of "
                        f"€{line.opened_credits:,.0f} but only €{line.available_amount:,.0f} "
                        f"({avail_pct:.1f}%) remain available after commitments."
                    ),
                    calculation_details=(
                        f"opened_credits={line.opened_credits:,.0f} | "
                        f"committed={line.committed_amount:,.0f} | "
                        f"available={line.available_amount:,.0f} | "
                        f"available_rate={avail_pct:.1f}%"
                    ),
                    recommendation="Review whether commitments can be reduced or a budget amendment is required.",
                ))
    return alerts


def rule_old_commitments(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    cutoff = date.today() - timedelta(days=180)
    comms = session.query(Commitment).filter(
        Commitment.local_authority_id == la_id,
        Commitment.fiscal_year_id == fy_id,
        Commitment.status == "open",
        Commitment.remaining_amount > 0,
    ).all()
    for c in comms:
        if c.date and c.date < cutoff:
            age_days = (date.today() - c.date).days
            alerts.append(Alert(
                local_authority_id=la_id,
                fiscal_year_id=fy_id,
                alert_type="Old Outstanding Commitment",
                severity="medium" if c.remaining_amount < 50000 else "high",
                rule_id="OLD_COMMITMENT",
                entity_type="commitment",
                entity_id=c.id,
                title=f"Commitment {c.commitment_number} — open for {age_days} days — €{c.remaining_amount:,.0f} remaining",
                explanation=(
                    f"Commitment {c.commitment_number} ({c.object}) placed with {c.supplier_name} "
                    f"on {c.date} remains open after {age_days} days with €{c.remaining_amount:,.0f} not yet mandated."
                ),
                calculation_details=(
                    f"commitment_date={c.date} | committed={c.committed_amount:,.0f} | "
                    f"mandated={c.mandated_amount:,.0f} | remaining={c.remaining_amount:,.0f}"
                ),
                recommendation=(
                    "Verify whether goods/services have been received. If yes, generate mandate. "
                    "If no, consider closing the commitment."
                ),
            ))
    return alerts


def rule_no_contract_reference(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    comms = session.query(Commitment).filter(
        Commitment.local_authority_id == la_id,
        Commitment.fiscal_year_id == fy_id,
        Commitment.committed_amount >= 40000,
    ).all()
    for c in comms:
        if not c.contract_reference:
            alerts.append(Alert(
                local_authority_id=la_id,
                fiscal_year_id=fy_id,
                alert_type="Commitment Without Contract",
                severity="medium",
                rule_id="NO_CONTRACT",
                entity_type="commitment",
                entity_id=c.id,
                title=f"Commitment {c.commitment_number} (€{c.committed_amount:,.0f}) has no contract reference",
                explanation=(
                    f"Commitment {c.commitment_number} for {c.supplier_name} totalling "
                    f"€{c.committed_amount:,.0f} exceeds the threshold but has no public contract reference."
                ),
                calculation_details=f"committed_amount={c.committed_amount:,.0f} | threshold=€40,000",
                recommendation="Attach the relevant public contract reference or verify procurement compliance.",
            ))
    return alerts


def rule_rejected_mandates(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    mandates = session.query(Mandate).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id, status="rejected"
    ).all()

    suppliers: dict[str, list] = {}
    for m in mandates:
        suppliers.setdefault(m.supplier_name, []).append(m)

    for supplier, mlist in suppliers.items():
        total_rejected = sum(m.amount for m in mlist)
        alerts.append(Alert(
            local_authority_id=la_id,
            fiscal_year_id=fy_id,
            alert_type="Rejected Mandates",
            severity="medium" if len(mlist) < 3 else "high",
            rule_id="REJECTED_MANDATES",
            entity_type="supplier",
            title=f"{supplier}: {len(mlist)} rejected mandate(s) — €{total_rejected:,.0f}",
            explanation=(
                f"Supplier {supplier} has {len(mlist)} rejected mandate(s) totalling €{total_rejected:,.0f}. "
                f"Rejection reasons: {', '.join(set(m.rejection_reason for m in mlist if m.rejection_reason))}."
            ),
            calculation_details=f"rejected_count={len(mlist)} | rejected_amount={total_rejected:,.0f}",
            recommendation="Review rejection reasons with the accounting service and resubmit corrected mandates.",
        ))
    return alerts


def rule_supplier_concentration(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    mandates = session.query(Mandate).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id, status="validated"
    ).all()
    if not mandates:
        return []

    totals: dict[str, float] = {}
    for m in mandates:
        totals[m.supplier_name] = totals.get(m.supplier_name, 0) + m.amount

    grand_total = sum(totals.values())
    for supplier, amount in totals.items():
        share = amount / grand_total * 100 if grand_total > 0 else 0
        if share > 25:
            alerts.append(Alert(
                local_authority_id=la_id,
                fiscal_year_id=fy_id,
                alert_type="Supplier Concentration",
                severity="medium" if share < 40 else "high",
                rule_id="SUPPLIER_CONCENTRATION",
                entity_type="supplier",
                title=f"{supplier} represents {share:.1f}% of total expenditure",
                explanation=(
                    f"Supplier {supplier} received €{amount:,.0f} out of a total expenditure of "
                    f"€{grand_total:,.0f}, representing {share:.1f}% of all validated mandates."
                ),
                calculation_details=f"supplier_amount={amount:,.0f} | grand_total={grand_total:,.0f} | share={share:.1f}%",
                recommendation=(
                    "Assess dependency risk. Consider competitive procurement if contracts are expiring."
                ),
            ))
    return alerts


def rule_abnormal_consumption(session: Session, la_id: int, fy_id: int) -> list[Alert]:
    alerts = []
    lines = session.query(BudgetLine).filter_by(
        local_authority_id=la_id, fiscal_year_id=fy_id
    ).all()
    for line in lines:
        if line.opened_credits > 0:
            rate = line.mandated_amount / line.opened_credits * 100
            if rate > 98 and line.opened_credits > 50000:
                alerts.append(Alert(
                    local_authority_id=la_id,
                    fiscal_year_id=fy_id,
                    alert_type="Abnormal Consumption",
                    severity="high",
                    rule_id="ABNORMAL_CONSUMPTION",
                    entity_type="budget_line",
                    entity_id=line.id,
                    title=f"Chapter {line.chapter} — Article {line.article}: {rate:.1f}% consumed — nearly exhausted",
                    explanation=(
                        f"Article {line.article} ({line.label}) has consumed {rate:.1f}% of opened credits. "
                        f"Only €{line.available_amount:,.0f} remains available."
                    ),
                    calculation_details=(
                        f"mandated={line.mandated_amount:,.0f} | opened={line.opened_credits:,.0f} | rate={rate:.1f}%"
                    ),
                    recommendation="Alert service manager. Budget amendment may be required before year-end.",
                ))
    return alerts


def run_all_rules(la_id: int, fy_id: int):
    """Run all rules, clear old alerts, and store new ones."""
    session = get_session()
    try:
        _clear_alerts(session, la_id, fy_id)

        all_alerts = []
        all_alerts += rule_insufficient_credits(session, la_id, fy_id)
        all_alerts += rule_old_commitments(session, la_id, fy_id)
        all_alerts += rule_no_contract_reference(session, la_id, fy_id)
        all_alerts += rule_rejected_mandates(session, la_id, fy_id)
        all_alerts += rule_supplier_concentration(session, la_id, fy_id)
        all_alerts += rule_abnormal_consumption(session, la_id, fy_id)

        for alert in all_alerts:
            session.add(alert)
        session.commit()
        return len(all_alerts)
    finally:
        session.close()
