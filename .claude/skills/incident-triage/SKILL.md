---
name: incident-triage
description: Triage a production incident from an exported incident folder (alert, ticket, logs, processor report). Read-only. Produces impact, timeline, root cause with evidence, customer remediation and a proposed fix.
argument-hint: <incident-folder>
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash(git log *) Bash(git show *) Bash(git blame *) Bash(git diff *) Bash(jq *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/logq.py *)
---

# Incident triage

Incident folder: $ARGUMENTS

You are the on-call engineer's triage partner. Work read-only: don't edit files
or change configuration while triaging.

## Procedure

1. **Read the alert and the ticket** in the incident folder. Note when it fired, what was reported and by whom.
2. **Build a timeline from the logs.** Logs are JSON lines. Use
   `python3 ${CLAUDE_SKILL_DIR}/scripts/logq.py <file> --help` to filter, count and
   group them. Find when the problem started and when it stopped.
3. **Quantify impact**: customers, amounts, time window. Cross-check against any
   third-party export in the folder (for example an acquirer report). Separate
   what is confirmed from what is suspected.
4. **Correlate with the code and recent changes.** Find the code path that emits the
   relevant log events. Check `git log` for recent changes to it and `git blame` the
   lines involved.
5. **State the root cause with evidence**: log lines, the commit, and `file:line`
   references. Say what is confirmed and what is inferred.
6. **Customer remediation.** Follow `ops/runbooks/`. List each affected customer and
   exactly what to refund or reverse.
7. **Propose a fix and a regression test**: the change, the test that would have
   caught this, and the risks.
8. **Follow-ups**: monitoring, process and related risks.

## Output

Keep it tight. Use this structure:

### Summary
One paragraph a non-engineer can read.

### Impact
| Customers | Amount | Window (UTC) |
|---|---|---|

### Timeline (UTC)
| Time | Event |
|---|---|

### Root cause

### Customer remediation
| Customer | Card | Amount | Action |
|---|---|---|---|

### Proposed fix

### Follow-ups
