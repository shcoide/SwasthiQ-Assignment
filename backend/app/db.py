"""SQLite storage for ingested billing rows.

This is the only module that touches persistence. Reconciliation and
analytics never import it — they operate on plain BillingRow lists that the
API layer fetches from here.
"""

import json
import sqlite3
from datetime import date
from pathlib import Path

from app.models import BillingRow

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "clinic_billing.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id TEXT NOT NULL,
    log_date TEXT NOT NULL,
    visit_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    line_items TEXT NOT NULL,
    payment_mode TEXT NOT NULL,
    amount_paid_paise INTEGER NOT NULL,
    discount_paise INTEGER NOT NULL,
    is_refund INTEGER NOT NULL,
    UNIQUE(clinic_id, visit_id)
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(_SCHEMA)
    return conn


_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn


def save_billing_log(clinic_id: str, log_date: date, rows: list[BillingRow]) -> int:
    """Replace any existing rows for this clinic-day with the given rows."""
    conn = _connection()
    with conn:
        conn.execute(
            "DELETE FROM billing_rows WHERE clinic_id = ? AND log_date = ?",
            (clinic_id, log_date.isoformat()),
        )
        conn.executemany(
            """
            INSERT INTO billing_rows (
                clinic_id, log_date, visit_id, timestamp, doctor_id,
                line_items, payment_mode, amount_paid_paise, discount_paise, is_refund
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.clinic_id,
                    log_date.isoformat(),
                    row.visit_id,
                    row.timestamp.isoformat(),
                    row.doctor_id,
                    json.dumps([item.model_dump() for item in row.line_items]),
                    row.payment_mode.value,
                    row.amount_paid_paise,
                    row.discount_paise,
                    int(row.is_refund),
                )
                for row in rows
            ],
        )
    return len(rows)


def load_billing_log(clinic_id: str, log_date: date) -> list[BillingRow]:
    conn = _connection()
    cursor = conn.execute(
        """
        SELECT visit_id, timestamp, doctor_id, line_items, payment_mode,
               amount_paid_paise, discount_paise, is_refund
        FROM billing_rows
        WHERE clinic_id = ? AND log_date = ?
        ORDER BY timestamp ASC
        """,
        (clinic_id, log_date.isoformat()),
    )
    rows = []
    for record in cursor.fetchall():
        (
            visit_id,
            timestamp,
            doctor_id,
            line_items_json,
            payment_mode,
            amount_paid_paise,
            discount_paise,
            is_refund,
        ) = record
        rows.append(
            BillingRow.model_validate(
                {
                    "clinic_id": clinic_id,
                    "visit_id": visit_id,
                    "timestamp": timestamp,
                    "doctor_id": doctor_id,
                    "line_items": json.loads(line_items_json),
                    "payment_mode": payment_mode,
                    "amount_paid_paise": amount_paid_paise,
                    "discount_paise": discount_paise,
                    "is_refund": bool(is_refund),
                }
            )
        )
    return rows
