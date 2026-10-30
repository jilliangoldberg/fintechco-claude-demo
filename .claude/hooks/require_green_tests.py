#!/usr/bin/env python3
"""Stop hook: don't let a session finish with failing tests.

Owned by Platform Eng. If the working tree has Python changes, run the test
suite. If it fails, block the stop and hand Claude the failure summary so it
keeps working. Gives up after a few consecutive blocks so a session can never
loop forever. Standard library only; runs on Python 3.9+.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

MAX_CONSECUTIVE_BLOCKS = 3


def changed_python_files(project: str) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line[3:] for line in result.stdout.splitlines() if line.rstrip('"').endswith(".py")]


def pytest_command(project: str) -> list[str]:
    args = ["-q", "-x", "--no-header", "-p", "no:cacheprovider"]
    if shutil.which("uv"):
        return ["uv", "run", "--frozen", "pytest", *args]
    return [os.path.join(project, ".venv", "bin", "python"), "-m", "pytest", *args]


def block_count_file(session_id: str) -> str:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "default"
    return os.path.join(tempfile.gettempdir(), f"fintechco-stop-hook-{safe}")


def read_count(path: str) -> int:
    try:
        with open(path) as handle:
            return int(handle.read() or 0)
    except (OSError, ValueError):
        return 0


def main() -> None:
    event = json.load(sys.stdin)
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or "."
    counter = block_count_file(str(event.get("session_id", "")))
    if not event.get("stop_hook_active") and os.path.exists(counter):
        os.remove(counter)

    if not changed_python_files(project):
        return
    try:
        result = subprocess.run(
            pytest_command(project),
            cwd=project,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        summary = "the test run timed out after 90 s"
    else:
        if result.returncode == 0:
            return
        summary = "\n".join((result.stdout + result.stderr).strip().splitlines()[-25:])

    blocks = read_count(counter) + 1
    if blocks > MAX_CONSECUTIVE_BLOCKS:
        return
    with open(counter, "w") as handle:
        handle.write(str(blocks))
    reason = "FinTechCo policy: tests must pass before you finish. `uv run pytest` fails:\n"
    json.dump({"decision": "block", "reason": reason + summary}, sys.stdout)


if __name__ == "__main__":
    main()
