#!/usr/bin/env python3
"""PreToolUse hook: block writing card numbers or secrets into files.

Owned by Platform Eng. Checks the text about to be written (Write content,
Edit new_string, NotebookEdit new_source) for:

- card numbers: 13-19 digits, spaces or dashes allowed, passing the Luhn check
- live API keys, AWS access keys and private keys

Also works as a scanner: ``python3 scan_sensitive.py --scan FILE...``.
Standard library only; runs on Python 3.9+.
"""

from __future__ import annotations

import json
import re
import sys

# Digit runs glued to letters (hashes, ids) aren't card numbers.
CARD_CANDIDATE = re.compile(r"(?<![0-9A-Za-z_])(?:\d[ -]?){12,18}\d(?![0-9A-Za-z_])")
SECRETS = {
    "live API key": re.compile(r"\b[rs]k_live_[0-9A-Za-z]{10,}"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def luhn_valid(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def findings(text: str) -> list[str]:
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in CARD_CANDIDATE.finditer(line):
            digits = re.sub(r"[ -]", "", match.group())
            if 13 <= len(digits) <= 19 and luhn_valid(digits):
                found.append(f"line {lineno}: card number {digits[:4]} **** {digits[-4:]}")
        for label, pattern in SECRETS.items():
            if pattern.search(line):
                found.append(f"line {lineno}: {label}")
    return found


def written_text(tool_input: dict) -> str:
    parts = [tool_input.get(key) for key in ("content", "new_string", "new_source")]
    parts += [edit.get("new_string") for edit in tool_input.get("edits") or []]
    return "\n".join(part for part in parts if isinstance(part, str))


def hook() -> None:
    event = json.load(sys.stdin)
    problems = findings(written_text(event.get("tool_input") or {}))
    if not problems:
        return
    reason = (
        "Blocked by FinTechCo policy SEC-2 (PCI DSS / secrets): "
        + "; ".join(problems[:5])
        + ". Use acquirer tokens (tok_...) and card_last4 only. Secrets belong in the vault, "
        "never in files."
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def scan(paths: list[str]) -> int:
    status = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        for problem in findings(text):
            print(f"{path}: {problem}")
            status = 1
    return status


if __name__ == "__main__":
    if sys.argv[1:2] == ["--scan"]:
        sys.exit(scan(sys.argv[2:]))
    hook()
