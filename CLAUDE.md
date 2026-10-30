# payments-api

Card payments service for the FinTechCo mobile app: charges, refunds and the
double-entry ledger behind them. FastAPI + SQLite on Python 3.12, managed with
uv. README.md covers the architecture and the mobile client contract.

## Commands

- Tests: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Run locally: `uv run uvicorn payments.main:create_app --factory`

## Rules

- Money is integer minor units (`amount_minor`). Never use float for amounts.
- Every mutating endpoint requires an `Idempotency-Key`. A customer is charged at most once per key.
- Ledger postings must balance: debits equal credits per currency.
- Never log card data, full tokens or customer emails; `card_last4` only. Log through `EventLogger`.
- Changes under `payments/services/` need tests.
- Fixes start with a failing regression test that reproduces the problem.
- Keep PRs small and reference the ticket or incident ID (e.g. `SUP-1182`, `INC-2041`).

## Pilot notes

- This repo is part of the Claude Code pilot. Policy hooks in `.claude/hooks/` are owned by Platform Eng.
- Incident exports live in `ops/incidents/<id>/`; triage them with `/incident-triage <folder>`.
