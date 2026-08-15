"""Shared test data builders."""

from app.models import BillingRow

DEFAULT_CLINIC = "clinic-1"
DEFAULT_DAY = "2026-08-15"


def make_row(
    *,
    visit_id: str,
    hour: int = 10,
    line_items: list[dict] | None = None,
    payment_mode: str = "cash",
    amount_paid_paise: int = 0,
    discount_paise: int = 0,
    is_refund: bool = False,
    clinic_id: str = DEFAULT_CLINIC,
    doctor_id: str = "doc-1",
) -> BillingRow:
    return BillingRow.model_validate(
        {
            "clinic_id": clinic_id,
            "visit_id": visit_id,
            "timestamp": f"{DEFAULT_DAY}T{hour:02d}:00:00Z",
            "doctor_id": doctor_id,
            "line_items": line_items or [],
            "payment_mode": payment_mode,
            "amount_paid_paise": amount_paid_paise,
            "discount_paise": discount_paise,
            "is_refund": is_refund,
        }
    )
