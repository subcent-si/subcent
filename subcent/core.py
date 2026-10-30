"""Core spend guardrail engine and SQLite semantic audit logger for Subcent."""

from __future__ import annotations

import functools
import inspect
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple


class SpendLimitExceeded(Exception):
    """Raised when a payment tool call violates Subcent guardrail policies."""


class Subcent:
    """Programmable spend guardrails and semantic audit trail for AI agent payment tools."""

    def __init__(
        self,
        max_per_tx: float,
        daily_budget: float,
        allowed_merchants: Optional[List[str]] = None,
        require_rationale: bool = True,
        db_path: str = ".Subcent_audit.db",
    ) -> None:
        self.max_per_tx = float(max_per_tx)
        self.daily_budget = float(daily_budget)
        self.allowed_merchants = list(allowed_merchants) if allowed_merchants is not None else None
        self.require_rationale = bool(require_rationale)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite audit_logs table if it does not already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    amount REAL NOT NULL,
                    recipient TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _log_event(
        self,
        timestamp: str,
        amount: float,
        recipient: str,
        rationale: str,
        status: str,
        reason: str,
    ) -> None:
        """Record an APPROVED or BLOCKED transaction attempt in the SQLite audit log."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (timestamp, amount, recipient, rationale, status, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, amount, recipient, rationale, status, reason),
            )
            conn.commit()

    def _get_daily_approved_spend(self, utc_date_prefix: str) -> float:
        """Return the cumulative APPROVED spend for the given UTC date prefix (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0.0)
                FROM audit_logs
                WHERE status = 'APPROVED' AND timestamp LIKE ?
                """,
                (f"{utc_date_prefix}%",),
            )
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0

    def _extract_and_validate(
        self,
        sig: inspect.Signature,
        args: Tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Tuple[str, float, str, str]:
        """Bind arguments, validate against all guardrail policies, or raise an exception."""
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        arguments = bound.arguments

        raw_amount = arguments.get("amount", None)
        if (
            raw_amount is None
            or isinstance(raw_amount, bool)
            or not isinstance(raw_amount, (int, float))
            or float(raw_amount) <= 0
        ):
            raise ValueError(
                f"Invalid 'amount': expected a positive number, got {raw_amount!r}."
            )

        amount = float(raw_amount)
        recipient = str(arguments.get("recipient", "unknown") or "unknown")
        raw_rationale = arguments.get("rationale", "")
        rationale = "" if raw_rationale is None else str(raw_rationale)

        now_utc = datetime.now(timezone.utc).isoformat()
        utc_date_prefix = now_utc[:10]

        # 1. Rationale requirement check
        if self.require_rationale and not rationale.strip():
            reason = "Missing or empty payment rationale (require_rationale=True)"
            self._log_event(now_utc, amount, recipient, rationale, "BLOCKED", reason)
            raise SpendLimitExceeded(reason)

        # 2. Allowed merchants check
        if self.allowed_merchants is not None and recipient not in self.allowed_merchants:
            reason = f"Recipient '{recipient}' is not in allowed_merchants"
            self._log_event(now_utc, amount, recipient, rationale, "BLOCKED", reason)
            raise SpendLimitExceeded(reason)

        # 3. Single transaction limit check
        if amount > self.max_per_tx:
            reason = f"Amount {amount:.2f} exceeds max_per_tx limit of {self.max_per_tx:.2f}"
            self._log_event(now_utc, amount, recipient, rationale, "BLOCKED", reason)
            raise SpendLimitExceeded(reason)

        # 4. Daily cumulative budget check (UTC date prefix match)
        spent_today = self._get_daily_approved_spend(utc_date_prefix)
        if spent_today + amount > self.daily_budget:
            reason = (
                f"Daily budget exceeded: spent {spent_today:.2f} + requested {amount:.2f} "
                f"> daily_budget {self.daily_budget:.2f}"
            )
            self._log_event(now_utc, amount, recipient, rationale, "BLOCKED", reason)
            raise SpendLimitExceeded(reason)

        return now_utc, amount, recipient, rationale

    def protect(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator that enforces spend guardrails on both sync and async functions."""
        sig = inspect.signature(func)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                now_utc, amount, recipient, rationale = self._extract_and_validate(
                    sig, args, kwargs
                )
                result = await func(*args, **kwargs)
                self._log_event(now_utc, amount, recipient, rationale, "APPROVED", "OK")
                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            now_utc, amount, recipient, rationale = self._extract_and_validate(
                sig, args, kwargs
            )
            result = func(*args, **kwargs)
            self._log_event(now_utc, amount, recipient, rationale, "APPROVED", "OK")
            return result

        return sync_wrapper
