#!/usr/bin/env python3
"""Query JSON-lines logs.

Examples:
  logq.py logs.jsonl --count-by event
  logq.py logs.jsonl --where event=processor.timeout --fields ts,customer_id,idempotency_key
  logq.py logs.jsonl --where event=http.response --where status=504 --per-minute
  logq.py logs.jsonl --where event=charge.created --group-by customer_id --having-count-gt 1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter


def parse_where(clauses: list[str]) -> list[tuple[str, str]]:
    conditions = []
    for clause in clauses:
        key, sep, value = clause.partition("=")
        if not sep:
            raise SystemExit(f"--where expects KEY=VALUE, got {clause!r}")
        conditions.append((key, value))
    return conditions


def render(record: dict, fields: str | None) -> str:
    if fields:
        return "  ".join(f"{name}={record.get(name)}" for name in fields.split(","))
    return json.dumps(record, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file")
    parser.add_argument(
        "--where", action="append", default=[], metavar="KEY=VALUE",
        help="keep records where KEY equals VALUE (repeatable)",
    )
    parser.add_argument("--fields", help="comma-separated fields to print")
    parser.add_argument("--count-by", metavar="FIELD", help="count records per value of FIELD")
    parser.add_argument("--per-minute", action="store_true", help="count records per minute")
    parser.add_argument("--group-by", metavar="FIELD", help="print records grouped by FIELD")
    parser.add_argument(
        "--having-count-gt", type=int, default=0, metavar="N",
        help="with --group-by, only groups with more than N records",
    )
    parser.add_argument("--limit", type=int, default=0, help="print at most N records")
    args = parser.parse_args(argv)

    conditions = parse_where(args.where)
    with open(args.file) as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    records = [r for r in records if all(str(r.get(k)) == v for k, v in conditions)]

    if args.count_by:
        counts = Counter(str(r.get(args.count_by)) for r in records)
        for value, count in counts.most_common():
            print(f"{count:6d}  {value}")
    elif args.per_minute:
        counts = Counter(str(r.get("ts", ""))[:16] for r in records)
        for minute, count in sorted(counts.items()):
            print(f"{minute}  {count:4d}  {'#' * count}")
    elif args.group_by:
        groups: dict[str, list[dict]] = {}
        for record in records:
            groups.setdefault(str(record.get(args.group_by)), []).append(record)
        for value, group in groups.items():
            if len(group) > args.having_count_gt:
                print(f"== {args.group_by}={value} ({len(group)} records)")
                for record in group:
                    print("   " + render(record, args.fields))
    else:
        for record in records[: args.limit or None]:
            print(render(record, args.fields))
    print(f"({len(records)} matching records)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
