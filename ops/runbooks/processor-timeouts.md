# Runbook: acquirer timeouts

**Service:** payments-api · **Owner:** payments on-call

## Symptoms

- `processor.timeout` events in payments-api logs, followed by `charge.failed` with `reason=processor_timeout`
- Elevated `504` rate on `POST /v1/charges`
- Acquirer status page reports elevated API latency

## Triage

1. Check the acquirer status page and #payments-alerts.
2. Size the impact from the logs: `processor.timeout` events per minute, and the customers and idempotency keys involved.
3. Check the recon monitor for unmatched captures in the same window.
4. If customers were affected, post a customer list in #support-escalations.

## Background

- The acquirer timeout is 10 s (`processor.timeout_seconds` in `config/<env>.yaml`). The mobile app gives up after 15 s (README, "Mobile client contract").
- A timeout means the outcome is unknown: the acquirer may or may not have charged the card.
- The mobile app retries a `504` once, with the same `Idempotency-Key`.

## Escalation

- Acquirer support: open a P2 or higher in the acquirer portal.
- Customer impact: Support lead and Finance Ops (#fin-ops).
