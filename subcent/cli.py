"""Command-line interface for inspecting Subcent semantic audit logs."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import List, Optional, Sequence


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def _run_audit(db_path: str, limit: int) -> int:
    if not os.path.exists(db_path):
        print(
            f"No audit database found at '{db_path}'. "
            "Run an agent tool protected by @guard.protect first to generate audit logs."
        )
        return 0

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, status, amount, recipient, rationale, reason
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
    except sqlite3.Error as exc:
        print(f"Error reading audit database '{db_path}': {exc}", file=sys.stderr)
        return 1

    if not rows:
        print(f"Audit database '{db_path}' contains no recorded transactions yet.")
        return 0

    headers = ("TIMESTAMP", "STATUS", "AMOUNT", "RECIPIENT", "RATIONALE / REASON")
    formatted_rows: List[tuple[str, str, str, str, str]] = []
    for timestamp, status, amount, recipient, rationale, reason in rows:
        ts_str = _truncate(str(timestamp), 26)
        status_str = str(status)
        amount_str = f"${float(amount):.2f}"
        recipient_str = _truncate(str(recipient), 24)
        if status_str == "APPROVED":
            detail_str = str(rationale) if rationale else "OK"
        else:
            detail_str = f"{reason}" + (f" (rationale: {rationale})" if rationale else "")
        formatted_rows.append(
            (ts_str, status_str, amount_str, recipient_str, _truncate(detail_str, 55))
        )

    col_widths = [
        max(len(headers[i]), *(len(r[i]) for r in formatted_rows))
        for i in range(len(headers))
    ]

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = (
        "| "
        + " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
        + " |"
    )

    print(sep)
    print(header_line)
    print(sep)
    for r in formatted_rows:
        line = (
            "| "
            + " | ".join(
                r[i].rjust(col_widths[i]) if i == 2 else r[i].ljust(col_widths[i])
                for i in range(len(headers))
            )
            + " |"
        )
        print(line)
    print(sep)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subcent",
        description="Subcent CLI — Inspect AI Agent spend guardrail & semantic audit logs.",
    )
    subparsers = parser.add_subparsers(dest="command")

    audit_parser = subparsers.add_parser(
        "audit",
        help="Display recent payment audit log entries from SQLite.",
    )
    audit_parser.add_argument(
        "--db",
        default=".subcent_audit.db",
        help="Path to the SQLite audit database (default: .subcent_audit.db).",
    )
    audit_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Maximum number of recent log records to display (default: 20).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "audit":
        return _run_audit(db_path=args.db, limit=args.limit)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
