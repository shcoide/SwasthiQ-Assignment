# EOD Billing & Analytics Agent

A clinic billing reconciliation system: ingest a day's billing transactions,
compute a deterministic end-of-day reconciliation and analytics, then generate
an LLM narrative summary that is verified against those deterministic numbers
before it's ever shown to a user.

## Deployment status

There is no live-hosted link yet — given the time constraint on this
assignment, deployment wasn't completed in time. It's in progress and this
README will be updated with the live URL once it's up. Until then, the
project is fully runnable and testable locally — see [Run & test it
locally](#run--test-it-locally) below.

## Architecture

```
backend/app/
  models.py         Pydantic schema for the billing log
  validation.py      parse + validate a day's log, row-indexed errors
  reconciliation.py  PURE — billed / collected / outstanding / refunds
  analytics.py        PURE — revenue by hour, top medicines (qty & revenue)
  narrative.py        the only module that calls the LLM, plus grounding validation
  db.py               SQLite storage (the only module that touches persistence)
  api.py               FastAPI routes
frontend/src/
  components/          Sidebar, ReconciliationDashboard, Analytics, NarrativePanel
  api/client.js        fetch wrappers for the backend
```

### REST API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/billing-log` | Ingest and validate one clinic-day's billing log (JSON array of rows) |
| `GET` | `/api/reconciliation/{clinic_id}/{date}` | Deterministic EOD reconciliation |
| `GET` | `/api/analytics/{clinic_id}/{date}` | Deterministic analytics |
| `GET` | `/api/narrative/{clinic_id}/{date}` | LLM narrative + `traced_figures`, grounded in the above |

`POST /api/billing-log` accepts the raw JSON array described in the input
schema below. All rows in one request must share a `clinic_id` and calendar
date (derived from `timestamp`, in UTC) — re-ingesting the same clinic-day
replaces the previous rows for that day, so ingestion is idempotent per day.

A malformed row never produces a generic 500. `validation.py` validates every
row independently, collects every failure, and the API returns `422` with:

```json
{
  "detail": {
    "errors": [
      { "row_index": 2, "message": "amount_paid_paise: Input should be a valid integer" }
    ]
  }
}
```

### Input schema (one row per visit)

```json
{
  "clinic_id": "string",
  "visit_id": "string",
  "timestamp": "2026-08-15T09:15:00Z",
  "doctor_id": "string",
  "line_items": [{ "drug_name": "string", "qty": 1, "unit_price_paise": 5000 }],
  "payment_mode": "cash | card | upi",
  "amount_paid_paise": 10000,
  "discount_paise": 0,
  "is_refund": false
}
```

Money is an integer number of paise everywhere — `unit_price_paise`,
`amount_paid_paise`, and `discount_paise` are all `StrictInt` in
`models.py`, so a stray float in the input JSON (e.g. `12.5`) is rejected at
validation, not silently rounded.

## How the deterministic layer guarantees consistency

`reconciliation.py` and `analytics.py` are pure functions: they take a list
of validated `BillingRow` objects and return a plain dict, with **no
database access and no LLM call**. That means:

- The same input always produces the same output — reconciliation numbers
  are reproducible and auditable, not something an LLM could quietly drift.
- `api.py` is the only place these functions are ever called, always with
  rows freshly loaded from SQLite — there's no code path where the frontend,
  the narrative, or a cached value could diverge from what these functions
  compute.
- `narrative.py` never touches billing rows directly. It only ever receives
  the dict these two modules already produced — the **report** — as its
  single source of truth. This is what "grounded" means concretely: the LLM
  has no way to see a number that didn't come from here.

Reconciliation definitions (all amounts in paise):

- `billed` = `sum(qty * unit_price_paise) - discount_paise` for non-refund
  visits. A refund row contributes 0 to billed — it isn't a new sale.
- `collected` = `sum(amount_paid_paise)` across all rows. Refund rows carry a
  negative `amount_paid_paise`, so a refund reduces collected.
- `outstanding` = `billed - collected`, per payment mode. A refund therefore
  increases outstanding for that mode, since money that was collected has
  since gone back out.
- `refunds` = sum of `abs(amount_paid_paise)` where `is_refund` is true.

Analytics rankings (`top_medicines_by_quantity` / `top_medicines_by_revenue`)
only count line items from non-refund rows, and are two separate ranked
lists — a medicine that wins on quantity does not necessarily win on revenue,
and the code never merges them into one table.

## How narrative grounding & validation works

`narrative.py` is the only module in the app allowed to call the Anthropic
API (model `claude-sonnet-4-6`). The flow:

1. `api.py` builds a `report` dict from `reconciliation.py` +
   `analytics.py` — nothing else is passed to the LLM.
2. The system prompt instructs the model: never invent, estimate, or
   round-trip a number that isn't in the report; never compute a derived
   statistic (percentage, average, ratio) that isn't already there; and if a
   metric would be useful but can't be computed from the available data
   (e.g. profit — there's no cost data anywhere in this system), say so
   plainly instead of approximating it.
3. After the model responds, `validate_traceability()` extracts every
   number-looking token from the narrative text and checks each one against
   every numeric leaf value in the report — including its rupee conversion
   (paise ÷ 100, both exact and rounded), since the narrative is expected to
   present money in rupees. **Percentages are always rejected** — the report
   never contains a percentage field, so any percentage in the text is
   necessarily something the model computed on its own, which rule #2 above
   forbids.
4. If every number traces back to a report field, the narrative is returned
   along with `traced_figures` — a map from each number in the text to the
   report field it came from. This is what the "Traced Figures" panel in the
   UI renders directly.
5. If even one number is untraceable, or the LLM call fails, returns a
   refusal, or comes back empty/malformed, `narrative.py` never lets that
   content through. It returns a structured error instead — the API still
   responds `200` with `narrative: null` and an `error` message, so a bad
   LLM response can never silently corrupt what the user sees. The
   deterministic reconciliation and analytics numbers remain available and
   correct regardless of whether the narrative succeeded.

`validate_traceability()` and `extract_numbers()` are pure and unit-tested
without any network access (see `tests/test_narrative.py`) — including a test
that a fabricated/untraceable number is rejected.

## Run & test it locally

Requires Python 3.11+, Node 18+, and `ANTHROPIC_API_KEY` in the environment
for the narrative endpoint (reconciliation and analytics work without it).

### 1. Start the backend

```sh
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

Storage is SQLite, created automatically at `backend/data/clinic_billing.db`
on first write. Leave this running in its own terminal.

**Verify it's up**, in a second terminal:

```sh
curl -s http://localhost:8000/docs -o /dev/null -w "%{http_code}\n"   # should print 200
```

Interactive API docs (Swagger UI) are at `http://localhost:8000/docs` — you
can POST a billing log and hit the `GET` endpoints directly from there
without touching the frontend.

### 2. Start the frontend

In a separate terminal (backend keeps running):

```sh
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, talking to the backend at
`http://localhost:8000` by default (override with `VITE_API_BASE_URL`).

Use the "Upload billing log (JSON)" button in the top bar to POST a day's
billing log (a JSON array matching the input schema above) straight from the
browser — it also sets the clinic/date selectors to whatever was ingested.
From there, click through Reconciliation → Analytics → AI Narrative in the
sidebar to see each screen populate.

### 3. Run the backend test suite

```sh
cd backend
source .venv/bin/activate   # if not already active
pytest tests/ -v
```

Covers: reconciliation and analytics on non-happy-path days (malformed row,
refund, partial payment, zero-visit day), row-indexed validation errors, and
the narrative traceability validator — including that it rejects an
untraceable number. These run fully offline; no `ANTHROPIC_API_KEY` needed.

### 4. (Optional) Smoke-test the API end to end with curl

With the backend running from step 1:

```sh
curl -X POST http://localhost:8000/api/billing-log \
  -H "Content-Type: application/json" \
  -d '[{"clinic_id":"clinic-1","visit_id":"v1","timestamp":"2026-08-15T09:00:00Z",
       "doctor_id":"d1","line_items":[{"drug_name":"Paracetamol","qty":2,"unit_price_paise":5000}],
       "payment_mode":"cash","amount_paid_paise":10000,"discount_paise":0,"is_refund":false}]'

curl http://localhost:8000/api/reconciliation/clinic-1/2026-08-15
curl http://localhost:8000/api/analytics/clinic-1/2026-08-15
curl http://localhost:8000/api/narrative/clinic-1/2026-08-15   # needs ANTHROPIC_API_KEY
```
