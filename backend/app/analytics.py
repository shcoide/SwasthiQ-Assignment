"""Deterministic analytics. Pure functions only — no I/O, no LLM calls.

Rankings are computed only from non-refund line items: a refund removes a
sale, it isn't a new sale of its own, so counting it would double-count
quantity/revenue that was already reversed in reconciliation.
"""

from app.models import BillingRow


def revenue_by_hour(rows: list[BillingRow]) -> dict:
    """Net revenue (collected amount, including refund adjustments) bucketed
    by UTC hour-of-day (0-23), plus the peak hour."""
    buckets = {hour: 0 for hour in range(24)}
    for row in rows:
        buckets[row.timestamp.hour] += row.amount_paid_paise

    peak_hour = max(buckets, key=lambda h: buckets[h]) if rows else None

    return {
        "buckets": [
            {"hour": hour, "revenue_paise": buckets[hour]} for hour in range(24)
        ],
        "peak_hour": peak_hour,
    }


def _sale_line_items(rows: list[BillingRow]):
    for row in rows:
        if row.is_refund:
            continue
        yield from row.line_items


def top_medicines_by_quantity(rows: list[BillingRow], limit: int = 10) -> list[dict]:
    """Ranking of medicines by total quantity sold. Separate ranking from
    top_medicines_by_revenue — deliberately not merged into one table."""
    totals: dict[str, int] = {}
    for item in _sale_line_items(rows):
        totals[item.drug_name] = totals.get(item.drug_name, 0) + item.qty

    ranked = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    return [{"drug_name": name, "total_qty": qty} for name, qty in ranked[:limit]]


def top_medicines_by_revenue(rows: list[BillingRow], limit: int = 10) -> list[dict]:
    """Ranking of medicines by total revenue (qty * unit_price_paise, before
    visit-level discount — discount is not allocated per line item)."""
    totals: dict[str, int] = {}
    for item in _sale_line_items(rows):
        totals[item.drug_name] = (
            totals.get(item.drug_name, 0) + item.qty * item.unit_price_paise
        )

    ranked = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    return [
        {"drug_name": name, "total_revenue_paise": revenue}
        for name, revenue in ranked[:limit]
    ]


def compute_analytics(rows: list[BillingRow]) -> dict:
    return {
        "revenue_by_hour": revenue_by_hour(rows),
        "top_medicines_by_quantity": top_medicines_by_quantity(rows),
        "top_medicines_by_revenue": top_medicines_by_revenue(rows),
    }
