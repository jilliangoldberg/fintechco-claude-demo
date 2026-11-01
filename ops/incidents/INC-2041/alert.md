# [P2] Unmatched acquirer captures: payments-api

| | |
|---|---|
| Fired | 2026-11-01 14:10 UTC |
| Source | recon-monitor (acquirer captures vs. payments ledger, 5 min lag) |
| Service | payments-api, production |
| Routed to | payments on-call |

5 acquirer captures between 13:40 and 14:10 UTC have no matching charge in the
payments ledger (threshold: 0).

## Context

- Acquirer status page: "Elevated API latency", 13:58 to 14:06 UTC (p99 11.8 s). Resolved.
- payments-api returned 7 `504`s on `POST /v1/charges` in the same window.

## Attached by on-call

- `logs.jsonl`: payments-api logs, 13:40 to 14:10 UTC
- `processor_transactions.csv`: acquirer dashboard export (captures), same window
