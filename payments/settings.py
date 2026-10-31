"""Service settings.

``PAYMENTS_ENV`` picks ``config/<env>.yaml``. Without a config file (local
development and tests) the defaults below apply: an in-memory database and the
acquirer's sandbox.
"""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class ProcessorSettings(BaseModel):
    base_url: str = "https://sandbox.acquirer.example/v2"
    timeout_seconds: float = 10.0


class NotificationSettings(BaseModel):
    refund_webhook_url: str = "https://customer-comms.internal.example/hooks/refunds"


class Settings(BaseModel):
    env: str = "dev"
    database_path: str = ":memory:"
    processor: ProcessorSettings = Field(default_factory=ProcessorSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


def load_settings(env: str | None = None) -> Settings:
    env = env or os.environ.get("PAYMENTS_ENV", "dev")
    path = CONFIG_DIR / f"{env}.yaml"
    data = yaml.safe_load(path.read_text()) if path.exists() else None
    return Settings(env=env, **(data or {}))
