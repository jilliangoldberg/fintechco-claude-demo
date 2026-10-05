# payments-api

Card payments service for the FinTechCo mobile app.

## Running locally

```
uv sync
uv run pytest
uv run uvicorn payments.main:create_app --factory --reload
```
