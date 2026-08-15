"""Parsing and validation of a raw billing-log payload into BillingRow objects.

Malformed input never raises a generic exception. Every failure is collected
into a `RowError` carrying the offending row index and a human-readable
reason, then surfaced together via `BillingLogValidationError`.
"""

from datetime import date

from pydantic import ValidationError

from app.models import BillingRow


class RowError:
    def __init__(self, row_index: int, message: str):
        self.row_index = row_index
        self.message = message

    def to_dict(self) -> dict:
        return {"row_index": self.row_index, "message": self.message}


class BillingLogValidationError(Exception):
    """Raised when one or more rows in a billing log payload are invalid."""

    def __init__(self, errors: list[RowError]):
        self.errors = errors
        summary = "; ".join(f"row {e.row_index}: {e.message}" for e in errors)
        super().__init__(f"Billing log validation failed — {summary}")

    def to_dict(self) -> dict:
        return {"errors": [e.to_dict() for e in self.errors]}


def _describe_pydantic_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def parse_billing_log(raw_rows: list[dict]) -> list[BillingRow]:
    """Validate a day's worth of raw billing rows.

    Raises BillingLogValidationError (never a generic exception) listing
    every malformed row by index, plus cross-row consistency errors
    (mixed clinics or dates in a single day-log submission).
    """
    if not isinstance(raw_rows, list):
        raise BillingLogValidationError(
            [RowError(0, "payload must be a JSON array of billing rows")]
        )

    errors: list[RowError] = []
    rows: list[BillingRow] = []

    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            errors.append(RowError(index, "row must be a JSON object"))
            continue
        try:
            rows.append(BillingRow.model_validate(raw_row))
        except ValidationError as exc:
            errors.append(RowError(index, _describe_pydantic_error(exc)))

    if errors:
        raise BillingLogValidationError(errors)

    if not rows:
        return rows

    clinic_ids = {row.clinic_id for row in rows}
    if len(clinic_ids) > 1:
        raise BillingLogValidationError(
            [
                RowError(
                    -1,
                    f"all rows must belong to one clinic; found {sorted(clinic_ids)}",
                )
            ]
        )

    dates = {_row_date(row) for row in rows}
    if len(dates) > 1:
        raise BillingLogValidationError(
            [
                RowError(
                    -1,
                    f"all rows must belong to one clinic-day; found dates {sorted(str(d) for d in dates)}",
                )
            ]
        )

    return rows


def _row_date(row: BillingRow) -> date:
    return row.timestamp.date()
