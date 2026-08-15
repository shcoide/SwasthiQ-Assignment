import pytest

from app.validation import BillingLogValidationError, parse_billing_log
from tests.factories import DEFAULT_CLINIC, DEFAULT_DAY


def _valid_row(visit_id="v1"):
    return {
        "clinic_id": DEFAULT_CLINIC,
        "visit_id": visit_id,
        "timestamp": f"{DEFAULT_DAY}T10:00:00Z",
        "doctor_id": "doc-1",
        "line_items": [{"drug_name": "Paracetamol", "qty": 1, "unit_price_paise": 1000}],
        "payment_mode": "cash",
        "amount_paid_paise": 1000,
        "discount_paise": 0,
        "is_refund": False,
    }


def test_valid_day_parses_cleanly():
    rows = parse_billing_log([_valid_row("v1"), _valid_row("v2")])
    assert len(rows) == 2


def test_zero_visit_day_parses_to_empty_list():
    assert parse_billing_log([]) == []


def test_malformed_row_reports_row_index_and_reason():
    bad_row = _valid_row("v1")
    bad_row["line_items"][0]["unit_price_paise"] = 12.5  # float money — not allowed

    with pytest.raises(BillingLogValidationError) as excinfo:
        parse_billing_log([_valid_row("v0"), bad_row])

    errors = excinfo.value.to_dict()["errors"]
    assert len(errors) == 1
    assert errors[0]["row_index"] == 1
    assert "unit_price_paise" in errors[0]["message"]


def test_missing_required_field_is_reported_with_index():
    bad_row = _valid_row("v1")
    del bad_row["payment_mode"]

    with pytest.raises(BillingLogValidationError) as excinfo:
        parse_billing_log([bad_row])

    errors = excinfo.value.to_dict()["errors"]
    assert errors[0]["row_index"] == 0
    assert "payment_mode" in errors[0]["message"]


def test_timestamp_without_timezone_is_rejected():
    bad_row = _valid_row("v1")
    bad_row["timestamp"] = "2026-08-15T10:00:00"  # no UTC offset

    with pytest.raises(BillingLogValidationError) as excinfo:
        parse_billing_log([bad_row])

    assert "timestamp" in excinfo.value.to_dict()["errors"][0]["message"]


def test_invalid_payment_mode_is_rejected():
    bad_row = _valid_row("v1")
    bad_row["payment_mode"] = "bitcoin"

    with pytest.raises(BillingLogValidationError):
        parse_billing_log([bad_row])


def test_mixed_clinics_in_one_payload_is_rejected():
    row_a = _valid_row("v1")
    row_b = _valid_row("v2")
    row_b["clinic_id"] = "clinic-2"

    with pytest.raises(BillingLogValidationError) as excinfo:
        parse_billing_log([row_a, row_b])

    assert "one clinic" in excinfo.value.to_dict()["errors"][0]["message"]
