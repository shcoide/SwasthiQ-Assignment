from app.reconciliation import compute_reconciliation
from tests.factories import make_row


def test_zero_visit_day_is_all_zero():
    report = compute_reconciliation([])

    assert report["visit_count"] == 0
    assert report["total_billed_paise"] == 0
    assert report["total_collected_paise"] == 0
    assert report["total_outstanding_paise"] == 0
    assert report["total_refunds_paise"] == 0
    for mode in ("cash", "card", "upi"):
        assert report["by_payment_mode"][mode]["billed_paise"] == 0


def test_fully_paid_visit_has_no_outstanding():
    row = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "Paracetamol", "qty": 2, "unit_price_paise": 5000}],
        payment_mode="card",
        amount_paid_paise=10000,
    )

    report = compute_reconciliation([row])

    assert report["total_billed_paise"] == 10000
    assert report["total_collected_paise"] == 10000
    assert report["total_outstanding_paise"] == 0
    assert report["by_payment_mode"]["card"]["billed_paise"] == 10000


def test_partial_payment_leaves_outstanding_balance():
    row = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "Amoxicillin", "qty": 1, "unit_price_paise": 20000}],
        payment_mode="upi",
        amount_paid_paise=12000,
    )

    report = compute_reconciliation([row])

    assert report["total_billed_paise"] == 20000
    assert report["total_collected_paise"] == 12000
    assert report["total_outstanding_paise"] == 8000
    assert report["by_payment_mode"]["upi"]["outstanding_paise"] == 8000


def test_discount_reduces_billed_amount():
    row = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "Cetirizine", "qty": 3, "unit_price_paise": 1000}],
        payment_mode="cash",
        amount_paid_paise=2500,
        discount_paise=500,
    )

    report = compute_reconciliation([row])

    assert report["total_billed_paise"] == 2500  # (3*1000) - 500
    assert report["total_outstanding_paise"] == 0


def test_refund_reduces_collected_and_is_tracked_separately():
    visit = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "Ibuprofen", "qty": 2, "unit_price_paise": 3000}],
        payment_mode="cash",
        amount_paid_paise=6000,
    )
    refund = make_row(
        visit_id="v1-refund",
        payment_mode="cash",
        amount_paid_paise=-6000,
        is_refund=True,
    )

    report = compute_reconciliation([visit, refund])

    assert report["total_billed_paise"] == 6000
    assert report["total_collected_paise"] == 0  # 6000 collected, then 6000 refunded
    assert report["total_refunds_paise"] == 6000
    assert report["total_outstanding_paise"] == 6000  # money billed no longer held
    assert report["by_payment_mode"]["cash"]["refunds_paise"] == 6000


def test_payment_modes_are_isolated_from_each_other():
    cash = make_row(
        visit_id="v1",
        line_items=[{"drug_name": "A", "qty": 1, "unit_price_paise": 1000}],
        payment_mode="cash",
        amount_paid_paise=1000,
    )
    card = make_row(
        visit_id="v2",
        line_items=[{"drug_name": "B", "qty": 1, "unit_price_paise": 2000}],
        payment_mode="card",
        amount_paid_paise=500,
    )

    report = compute_reconciliation([cash, card])

    assert report["by_payment_mode"]["cash"]["outstanding_paise"] == 0
    assert report["by_payment_mode"]["card"]["outstanding_paise"] == 1500
    assert report["by_payment_mode"]["upi"]["billed_paise"] == 0
    assert report["total_billed_paise"] == 3000
