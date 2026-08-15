from app.narrative import extract_numbers, validate_traceability

SAMPLE_REPORT = {
    "reconciliation": {
        "total_billed_paise": 150000,
        "total_collected_paise": 120000,
        "total_outstanding_paise": 30000,
        "total_refunds_paise": 5000,
        "visit_count": 12,
        "by_payment_mode": {
            "cash": {"billed_paise": 50000, "collected_paise": 50000, "refunds_paise": 0, "outstanding_paise": 0},
            "card": {"billed_paise": 60000, "collected_paise": 40000, "refunds_paise": 0, "outstanding_paise": 20000},
            "upi": {"billed_paise": 40000, "collected_paise": 30000, "refunds_paise": 5000, "outstanding_paise": 10000},
        },
    },
    "analytics": {
        "revenue_by_hour": {
            "buckets": [{"hour": h, "revenue_paise": 0} for h in range(24)],
            "peak_hour": 11,
        },
        "top_medicines_by_quantity": [{"drug_name": "Paracetamol", "total_qty": 40}],
        "top_medicines_by_revenue": [{"drug_name": "Vitamin C", "total_revenue_paise": 25000}],
    },
}


def test_narrative_grounded_entirely_in_report_is_fully_traced():
    text = (
        "Today the clinic billed ₹1500.00 and collected ₹1200.00, leaving ₹300.00 outstanding. "
        "There were 12 visits and ₹50.00 in refunds. Paracetamol was the top seller by quantity (40 units)."
    )

    traced, untraced = validate_traceability(text, SAMPLE_REPORT)

    assert untraced == []
    assert len(traced) > 0


def test_untraceable_number_is_rejected():
    text = "Today the clinic billed ₹1500.00 but profit margin was 42%, a record high."

    traced, untraced = validate_traceability(text, SAMPLE_REPORT)

    # 42 (from "42%") cannot trace to anything in the report and must be flagged.
    assert any("42" in item for item in untraced)


def test_fabricated_money_amount_is_rejected():
    text = "The clinic collected ₹9,999.00 today, a new record."

    traced, untraced = validate_traceability(text, SAMPLE_REPORT)

    assert "₹9,999.00" in untraced or "9,999.00" in untraced
    assert not traced  # nothing in this sentence should trace


def test_percentages_are_always_untraceable_even_if_numerically_plausible():
    # 20% happens to be numerically close to some report values, but the report
    # has no percentage field at all — any percentage is a computed/invented figure.
    text = "Outstanding balance is roughly 20% of billed revenue."

    traced, untraced = validate_traceability(text, SAMPLE_REPORT)

    assert "20%" in untraced


def test_ordinal_list_markers_are_not_treated_as_claimed_figures():
    text = "1. Billed ₹1500.00\n2. Collected ₹1200.00"

    traced, untraced = validate_traceability(text, SAMPLE_REPORT)

    assert "1." not in "".join(untraced)
    assert untraced == []


def test_zero_visit_report_rejects_any_invented_activity_number():
    empty_report = {
        "reconciliation": {
            "total_billed_paise": 0,
            "total_collected_paise": 0,
            "total_outstanding_paise": 0,
            "total_refunds_paise": 0,
            "visit_count": 0,
            "by_payment_mode": {},
        },
        "analytics": {
            "revenue_by_hour": {"buckets": [], "peak_hour": None},
            "top_medicines_by_quantity": [],
            "top_medicines_by_revenue": [],
        },
    }
    text = "The clinic had 8 visits today and billed ₹450.00."

    traced, untraced = validate_traceability(text, empty_report)

    assert "8" in untraced
    assert "₹450.00" in untraced or "450.00" in untraced


def test_extract_numbers_finds_currency_and_plain_figures():
    numbers = extract_numbers("Billed ₹1,500.00, 12 visits, refunds ₹50.")

    assert "₹1,500.00" in numbers
    assert "12" in numbers
