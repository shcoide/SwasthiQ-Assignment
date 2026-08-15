from app.analytics import (
    revenue_by_hour,
    top_medicines_by_quantity,
    top_medicines_by_revenue,
)
from tests.factories import make_row


def test_zero_visit_day_has_no_peak_hour():
    result = revenue_by_hour([])

    assert result["peak_hour"] is None
    assert len(result["buckets"]) == 24
    assert all(bucket["revenue_paise"] == 0 for bucket in result["buckets"])


def test_revenue_by_hour_buckets_and_finds_peak():
    rows = [
        make_row(visit_id="v1", hour=9, amount_paid_paise=1000),
        make_row(visit_id="v2", hour=9, amount_paid_paise=500),
        make_row(visit_id="v3", hour=14, amount_paid_paise=5000),
    ]

    result = revenue_by_hour(rows)

    by_hour = {b["hour"]: b["revenue_paise"] for b in result["buckets"]}
    assert by_hour[9] == 1500
    assert by_hour[14] == 5000
    assert result["peak_hour"] == 14


def test_revenue_by_hour_includes_refund_as_negative_adjustment():
    rows = [
        make_row(visit_id="v1", hour=10, amount_paid_paise=4000),
        make_row(visit_id="v1-refund", hour=11, amount_paid_paise=-4000, is_refund=True),
    ]

    result = revenue_by_hour(rows)
    by_hour = {b["hour"]: b["revenue_paise"] for b in result["buckets"]}

    assert by_hour[10] == 4000
    assert by_hour[11] == -4000


def test_top_medicines_by_quantity_and_revenue_are_separate_rankings():
    rows = [
        make_row(
            visit_id="v1",
            line_items=[
                {"drug_name": "Paracetamol", "qty": 10, "unit_price_paise": 100},
                {"drug_name": "Vitamin C", "qty": 1, "unit_price_paise": 50000},
            ],
            amount_paid_paise=51000,
        ),
    ]

    by_qty = top_medicines_by_quantity(rows)
    by_rev = top_medicines_by_revenue(rows)

    # Paracetamol wins on quantity (10 units) despite lower total revenue.
    assert by_qty[0]["drug_name"] == "Paracetamol"
    assert by_qty[0]["total_qty"] == 10

    # Vitamin C wins on revenue (50000 paise) despite lower quantity.
    assert by_rev[0]["drug_name"] == "Vitamin C"
    assert by_rev[0]["total_revenue_paise"] == 50000


def test_refunded_visit_line_items_excluded_from_medicine_rankings():
    sale = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "Ibuprofen", "qty": 5, "unit_price_paise": 1000}],
        amount_paid_paise=5000,
    )
    refund = make_row(
        visit_id="v1-refund",
        line_items=[{"drug_name": "Ibuprofen", "qty": 5, "unit_price_paise": 1000}],
        amount_paid_paise=-5000,
        is_refund=True,
    )

    by_qty = top_medicines_by_quantity([sale, refund])

    assert len(by_qty) == 1
    assert by_qty[0]["total_qty"] == 5  # only the sale counted, not the refund row


def test_zero_visit_day_has_empty_medicine_rankings():
    assert top_medicines_by_quantity([]) == []
    assert top_medicines_by_revenue([]) == []
