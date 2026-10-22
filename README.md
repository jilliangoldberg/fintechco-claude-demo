# payments-api

Card payments service for the FinTechCo mobile app: charges, refunds and the
double-entry ledger behind them. Cards are charged through our acquirer. The
app never sends card numbers, only acquirer tokens (`tok_…`) and the last four
digits for display.

## Architecture

```
mobile app ──HTTPS──▶ payments-api ──▶ acquirer API (authorize + capture)
                          │
                          └──▶ SQLite: charges, refunds, ledger_entries, idempotency_keys
```

| Module | Responsibility |
|---|---|
| `payments/api/` | HTTP routes, error mapping, request logging |
| `payments/services/charges.py` | Charge flow: idempotency, acquirer call, ledger posting |
| `payments/services/refunds.py` | Full and partial refunds |
| `payments/services/idempotency.py` | `Idempotency-Key` storage and replay |
| `payments/services/ledger.py` | Balanced double-entry postings |
| `payments/processor/` | Acquirer client, plus an in-memory mock for tests |
| `payments/log.py` | Structured JSON event logging |

## Running locally

```
uv sync
uv run pytest
uv run uvicorn payments.main:create_app --factory --reload
```

`PAYMENTS_ENV` selects `config/<env>.yaml`. Without it you get an in-memory
database and the acquirer sandbox.

## API

| Method | Path | Notes |
|---|---|---|
| `POST` | `/v1/charges` | Requires `Idempotency-Key` |
| `GET` | `/v1/charges/{id}` | Includes `refunded_minor` |
| `POST` | `/v1/charges/{id}/refunds` | Requires `Idempotency-Key`; omit `amount_minor` for a full refund |
| `GET` | `/healthz` | Load balancer check |

Amounts are integers in minor units: `"amount_minor": 4250` is $42.50.

### Idempotency

Every mutating request carries an `Idempotency-Key` header, scoped to the
customer. A retry with the same key and body returns the original response;
the same key with a different body is rejected with `422`. A customer is
charged at most once per key.

## Mobile client contract

How the FinTechCo app calls `POST /v1/charges`:

- The app creates one `Idempotency-Key` per checkout and reuses it for every retry of that checkout.
- Request timeout: **15 s**.
- On `504`, or a client-side timeout, the app retries **once**, about **2 s** later, with the same key.
- On `409 request_in_progress` the app shows "Payment processing" and refreshes the order later.
- On `402` the app shows the decline reason. "Try again" retries with the same key.

## Configuration

`config/staging.yaml` and `config/production.yaml` set the database path, the
acquirer base URL and the acquirer timeout (`processor.timeout_seconds`).
`PROCESSOR_API_KEY` comes from the environment (see `.env.example`).

## Operations

- Logs are JSON lines, one event per line (`charge.received`,
  `processor.request`, `processor.timeout`, ...). See `payments/log.py`.
- Runbooks live in `ops/runbooks/`.
