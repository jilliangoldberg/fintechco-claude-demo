# Runbook: issuing refunds

## Charges that exist in payments-api

Use the API:

```
POST /v1/charges/{charge_id}/refunds
Idempotency-Key: <ticket id, e.g. SUP-1234>

{"reason": "..."}            # omit amount_minor for a full refund
```

## Unmatched captures

An unmatched capture is a payment the acquirer captured that has no charge in
payments-api, so there is no `charge_id` to refund through the API.

1. Refund the capture in the acquirer portal using its `processor_charge_id`.
2. Ask Finance Ops (#fin-ops) to record a ledger adjustment that references the incident or ticket ID.
3. Reply on the customer's ticket with the acquirer refund reference.

Refunds over $500 need a second approver.
