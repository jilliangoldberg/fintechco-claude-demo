"""Identifier generation."""

import secrets
from collections import defaultdict
from typing import Protocol

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


class Ids(Protocol):
    def new(self, prefix: str) -> str: ...


class RandomIds:
    """Prefixed random identifiers, e.g. ``ch_3k9v0q2m8x1d7f4a``."""

    def new(self, prefix: str) -> str:
        return f"{prefix}_" + "".join(secrets.choice(ALPHABET) for _ in range(16))


class SequentialIds:
    """Predictable identifiers for tests, e.g. ``ch_0001``."""

    def __init__(self) -> None:
        self._counters: defaultdict[str, int] = defaultdict(int)

    def new(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}_{self._counters[prefix]:04d}"
