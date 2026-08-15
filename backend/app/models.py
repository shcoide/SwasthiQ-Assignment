"""Pydantic models for the clinic billing log schema.

Money is always an integer number of paise. Fields that represent money use
`strict=True` so a stray float (e.g. `12.5`) in the input JSON is rejected at
the validation boundary instead of being silently coerced.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, StrictInt, field_validator


class PaymentMode(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"


class LineItem(BaseModel):
    drug_name: str
    qty: StrictInt = Field(gt=0)
    unit_price_paise: StrictInt = Field(ge=0)


class BillingRow(BaseModel):
    clinic_id: str
    visit_id: str
    timestamp: datetime
    doctor_id: str
    line_items: list[LineItem]
    payment_mode: PaymentMode
    amount_paid_paise: StrictInt
    discount_paise: StrictInt = Field(default=0, ge=0)
    is_refund: bool = False

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware ISO 8601 (e.g. include 'Z' or '+00:00')"
            )
        return value

    @field_validator("clinic_id", "visit_id", "doctor_id")
    @classmethod
    def not_blank(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"{info.field_name} must not be blank")
        return value
