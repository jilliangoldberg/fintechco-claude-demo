#!/usr/bin/env python3
"""PreToolUse hook: block changes to change-managed files.

Owned by Platform Eng. Reads the hook event (JSON) on stdin and denies Edit,
Write and NotebookEdit calls, and shell commands, that would modify a
protected path. Standard library only; runs on Python 3.9+.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

PROTECTED = {
    "config/production.yaml": (
        "Blocked by FinTechCo policy PLAT-7: config/production.yaml is change-managed. "
        "Production config changes need an approved change request (CR) and are applied "
        "by the release pipeline, not by editing this file. Do not retry or work around "
        "this block. Tell the user, and offer to draft the CR (change, risk, rollback)."
    ),
    ".claude/hooks/*": (
        "Blocked by FinTechCo policy PLAT-3: policy hooks are owned by Platform Eng and "
        "can't be changed from a coding session."
    ),
    ".claude/settings.json": (
        "Blocked by FinTechCo policy PLAT-3: project Claude Code settings are owned by "
        "Platform Eng and can't be changed from a coding session."
    ),
}

# Commands that only read files. Anything with redirection, pipes or chaining
# is treated as a possible write.
READ_ONLY = re.compile(
    r"^\s*(cat|head|tail|less|wc|grep|rg|ls|stat|diff|git\s+(diff|log|show|blame|status))\b"
)
SHELL_OPERATORS = re.compile(r"[>|;&`]|\$\(")


def deny(reason: str) -> None:
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
    sys.exit(0)


def check_bash(command: str) -> None:
    if READ_ONLY.match(command) and not SHELL_OPERATORS.search(command):
        return
    for pattern, reason in PROTECTED.items():
        if pattern.rstrip("*") in command:
            deny(reason)


def check_path(path: str, project: str) -> None:
    relative = os.path.relpath(os.path.realpath(path), project)
    for pattern, reason in PROTECTED.items():
        if fnmatch.fnmatch(relative, pattern):
            deny(reason)


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    project = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")

    if event.get("tool_name") == "Bash":
        check_bash(tool_input.get("command", ""))
        return
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if path:
        check_path(path, project)


if __name__ == "__main__":
    main()
