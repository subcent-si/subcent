"""Unit tests for Subcent spend guardrails and semantic audit logging."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from subcent import Subcent, SpendLimitExceeded


class TestSubcentCore(unittest.IsolatedAsyncioTestCase):
    """Test suite covering sync/async guardrails, argument resolution, and SQLite logging."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _fetch_logs(self) -> list[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT amount, recipient, rationale, status, reason FROM audit_logs ORDER BY id ASC"
            ).fetchall()

    def test_1_approved_transaction_recorded_in_sqlite(self) -> None:
        """1. Valid payment is approved, executes the function, and logs APPROVED in SQLite."""
        guard = Subcent(max_per_tx=10.0, daily_budget=50.0, db_path=self.db_path)
        calls: list[float] = []

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str) -> str:
            calls.append(amount)
            return f"paid:{amount}"

        result = pay(amount=4.5, recipient="stripe.com", rationale="Purchase market report API")
        self.assertEqual(result, "paid:4.5")
        self.assertEqual(calls, [4.5])

        logs = self._fetch_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(
            logs[0],
            (4.5, "stripe.com", "Purchase market report API", "APPROVED", "OK"),
        )

    def test_2_max_per_tx_exceeded_blocks_and_logs(self) -> None:
        """2. Exceeding max_per_tx raises SpendLimitExceeded without calling func and logs BLOCKED."""
        guard = Subcent(max_per_tx=5.0, daily_budget=50.0, db_path=self.db_path)
        executed = False

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str) -> str:
            nonlocal executed
            executed = True
            return "should_not_run"

        with self.assertRaises(SpendLimitExceeded):
            pay(amount=7.25, recipient="api.openai.com", rationale="Batch inference credits")

        self.assertFalse(executed)
        logs = self._fetch_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][0], 7.25)
        self.assertEqual(logs[0][3], "BLOCKED")
        self.assertIn("max_per_tx", logs[0][4])

    def test_3_daily_budget_exceeded_across_multiple_transactions(self) -> None:
        """3. Cumulative daily spend exceeding daily_budget raises SpendLimitExceeded."""
        guard = Subcent(max_per_tx=10.0, daily_budget=15.0, db_path=self.db_path)
        calls = 0

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str) -> str:
            nonlocal calls
            calls += 1
            return "ok"

        self.assertEqual(pay(amount=8.0, recipient="aws.amazon.com", rationale="GPU node hour 1"), "ok")
        self.assertEqual(pay(amount=6.0, recipient="aws.amazon.com", rationale="GPU node hour 2"), "ok")

        with self.assertRaises(SpendLimitExceeded):
            pay(amount=2.0, recipient="aws.amazon.com", rationale="GPU node hour 3")

        self.assertEqual(calls, 2)
        logs = self._fetch_logs()
        self.assertEqual(len(logs), 3)
        self.assertEqual([row[3] for row in logs], ["APPROVED", "APPROVED", "BLOCKED"])
        self.assertIn("daily_budget", logs[2][4])

    def test_4_unallowed_merchant_blocked(self) -> None:
        """4. Recipient outside allowed_merchants whitelist is blocked and logged."""
        guard = Subcent(
            max_per_tx=10.0,
            daily_budget=50.0,
            allowed_merchants=["stripe.com", "coinbase.com"],
            db_path=self.db_path,
        )
        executed = False

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str) -> str:
            nonlocal executed
            executed = True
            return "ok"

        with self.assertRaises(SpendLimitExceeded):
            pay(amount=2.0, recipient="shady-wallet.xyz", rationale="Transfer funds")

        self.assertFalse(executed)
        logs = self._fetch_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][3], "BLOCKED")
        self.assertIn("allowed_merchants", logs[0][4])

    def test_5_empty_rationale_blocked_when_required(self) -> None:
        """5. Empty or whitespace-only rationale is blocked when require_rationale=True."""
        guard = Subcent(
            max_per_tx=10.0,
            daily_budget=50.0,
            require_rationale=True,
            db_path=self.db_path,
        )
        executed = False

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str = "") -> str:
            nonlocal executed
            executed = True
            return "ok"

        with self.assertRaises(SpendLimitExceeded):
            pay(amount=3.0, recipient="stripe.com", rationale="   ")

        self.assertFalse(executed)
        logs = self._fetch_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][3], "BLOCKED")
        self.assertIn("rationale", logs[0][4])

    def test_6_positional_arguments_bound_via_inspect_signature(self) -> None:
        """6. Positional arguments e.g. pay(1.5, 'stripe.com', 'buying data') are bound and validated."""
        guard = Subcent(
            max_per_tx=5.0,
            daily_budget=20.0,
            allowed_merchants=["stripe.com"],
            db_path=self.db_path,
        )

        @guard.protect
        def pay(amount: float, recipient: str, rationale: str) -> str:
            return f"{recipient}:{amount}:{rationale}"

        res = pay(1.5, "stripe.com", "buying data")
        self.assertEqual(res, "stripe.com:1.5:buying data")

        logs = self._fetch_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0], (1.5, "stripe.com", "buying data", "APPROVED", "OK"))

        # Also check invalid amount raises ValueError
        with self.assertRaises(ValueError):
            pay(-1.0, "stripe.com", "invalid negative amount")

    async def test_7_async_function_protection_approves_and_blocks(self) -> None:
        """7. Async functions decorated with @guard.protect properly approve and block transactions."""
        guard = Subcent(
            max_per_tx=5.0,
            daily_budget=8.0,
            allowed_merchants=["x402.coinbase.com"],
            db_path=self.db_path,
        )
        executed_amounts: list[float] = []

        @guard.protect
        async def async_pay(amount: float, recipient: str, rationale: str) -> str:
            executed_amounts.append(amount)
            return f"async_paid:{amount}"

        res = await async_pay(4.0, "x402.coinbase.com", "Fetch paid API resource via x402")
        self.assertEqual(res, "async_paid:4.0")

        # Second call exceeds max_per_tx (6.0 > 5.0)
        with self.assertRaises(SpendLimitExceeded):
            await async_pay(6.0, "x402.coinbase.com", "Oversized x402 request")

        # Third call exceeds remaining daily budget (4.0 + 4.5 > 8.0)
        with self.assertRaises(SpendLimitExceeded):
            await async_pay(4.5, "x402.coinbase.com", "Second request over daily budget")

        self.assertEqual(executed_amounts, [4.0])
        logs = self._fetch_logs()
        self.assertEqual(len(logs), 3)
        self.assertEqual([row[3] for row in logs], ["APPROVED", "BLOCKED", "BLOCKED"])


if __name__ == "__main__":
    unittest.main()
