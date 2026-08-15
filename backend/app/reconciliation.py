"""Deterministic EOD reconciliation. Pure functions only — no I/O, no LLM calls.

This is the ground-truth layer: analytics and the narrative are checked
against the numbers computed here, never the other way around.

Definitions (all amounts in integer paise):
  - billed:      sum of (qty * unit_price_paise) - discount_paise, for
                 non-refund visits. Refund rows contribute 0 to billed —
                 they are not a new billing event.
  - collected:   sum of amount_paid_paise across all rows. Refund rows carry
                 a negative amount_paid_paise, so a refund reduces collected.
  - outstanding: billed - collected, per payment mode. A refund therefore
                 shows up as increased outstanding for that mode, since money
                 that was collected has since gone back out.
  - refunds:     sum of the absolute value of amount_paid_paise for rows
                 where is_refund is true.
"""

from app.models import BillingRow, PaymentMode

PAYMENT_MODES = [PaymentMode.CASH, PaymentMode.CARD, PaymentMode.UPI]


def _visit_billed_paise(row: BillingRow) -> int:
    gross = sum(item.qty * item.unit_price_paise for item in row.line_items)
    return gross - row.discount_paise


def compute_reconciliation(rows: list[BillingRow]) -> dict:
    """Compute the EOD reconciliation report for one clinic-day."""
    by_mode = {
        mode.value: {"billed_paise": 0, "collected_paise": 0, "refunds_paise": 0}
        for mode in PAYMENT_MODES
    }

    for row in rows:
        bucket = by_mode[row.payment_mode.value]
        if row.is_refund:
            bucket["refunds_paise"] += abs(row.amount_paid_paise)
        else:
            bucket["billed_paise"] += _visit_billed_paise(row)
        bucket["collected_paise"] += row.amount_paid_paise

    for bucket in by_mode.values():
        bucket["outstanding_paise"] = bucket["billed_paise"] - bucket["collected_paise"]

    total_billed_paise = sum(b["billed_paise"] for b in by_mode.values())
    total_collected_paise = sum(b["collected_paise"] for b in by_mode.values())
    total_outstanding_paise = sum(b["outstanding_paise"] for b in by_mode.values())
    total_refunds_paise = sum(b["refunds_paise"] for b in by_mode.values())

    return {
        "total_billed_paise": total_billed_paise,
        "total_collected_paise": total_collected_paise,
        "total_outstanding_paise": total_outstanding_paise,
        "total_refunds_paise": total_refunds_paise,
        "visit_count": len(rows),
        "by_payment_mode": by_mode,
    }
