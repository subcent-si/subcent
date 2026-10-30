# Subcent (`subcent-si`)

**Programmable Spend Guardrails & Semantic Audit Logging for Autonomous AI Agents.**

Autonomous AI agents equipped with payment tools—such as the Stripe Agent Toolkit, Coinbase x402 micropayments, or Web3 wallets—can execute financial transactions at machine speed. Without deterministic boundaries, a single prompt injection, hallucinated parameter, or infinite retry loop can drain an operational budget in seconds.

**Subcent** wraps your agent's payment functions with a fail-closed, deterministic policy engine and records every approved and blocked attempt—along with the agent's semantic rationale—into a local SQLite audit trail.

## Features

- **Zero-Dependency:** Built exclusively on the Python standard library (`sqlite3`, `functools`, `inspect`, `argparse`). No heavyweight runtime dependencies or external sidecars required.
- **Sync / Async Support:** Transparently protect both standard synchronous functions (`def`) and asynchronous coroutines (`async def`) used across modern AI agent frameworks with a single `@guard.protect` decorator.
- **Deterministic Spend Caps:** Enforce per-transaction ceilings (`max_per_tx`), rolling UTC daily budgets (`daily_budget`), and merchant whitelists (`allowed_merchants`) before any payment API call executes.
- **Semantic Audit Trail:** Require agents to supply a non-empty natural-language `rationale` for every transaction and inspect full historical logs (`APPROVED` and `BLOCKED`) via the built-in `subcent audit` CLI.

## Installation

```bash
pip install subcent-si
```

## Quickstart

### Synchronous Payment Tool

```python
from subcent import Subcent, SpendLimitExceeded

guard = Subcent(
    max_per_tx=5.00,
    daily_budget=25.00,
    allowed_merchants=["stripe.com", "api.perplexity.ai"],
    require_rationale=True,
)

@guard.protect
def execute_payment(amount: float, recipient: str, rationale: str) -> dict:
    # Call Stripe Agent Toolkit or payment gateway here
    return {"status": "paid", "amount": amount, "recipient": recipient}

# 1. Approved transaction
res = execute_payment(
    1.50,
    "api.perplexity.ai",
    "Fetch real-time market research for Q4 synthesis",
)
print(res)

# 2. Blocked transaction (exceeds max_per_tx)
try:
    execute_payment(
        12.00,
        "stripe.com",
        "Upgrade compute tier without human approval",
    )
except SpendLimitExceeded as err:
    print(f"Blocked by Subcent: {err}")
```

### Asynchronous Payment Tool (`async def`)

```python
import asyncio
from subcent import Subcent

guard = Subcent(
    max_per_tx=2.00,
    daily_budget=10.00,
    allowed_merchants=["x402.coinbase.com"],
)

@guard.protect
async def x402_micropayment(amount: float, recipient: str, rationale: str) -> str:
    await asyncio.sleep(0.01)
    return f"Settled ${amount:.2f} to {recipient}"

async def main() -> None:
    receipt = await x402_micropayment(
        amount=0.75,
        recipient="x402.coinbase.com",
        rationale="Unlock paywalled financial filing dataset",
    )
    print(receipt)

asyncio.run(main())
```

## CLI Audit Log

Inspect recent transaction attempts directly from your terminal using `subcent audit`:

```bash
$ subcent audit --db .subcent_audit.db -n 20
+----------------------------+----------+--------+-------------------+---------------------------------------------------------+
| TIMESTAMP                  | STATUS   | AMOUNT | RECIPIENT         | RATIONALE / REASON                                      |
+----------------------------+----------+--------+-------------------+---------------------------------------------------------+
| 2026-10-30T06:21:10.412109 | BLOCKED  | $12.00 | stripe.com        | Amount 12.00 exceeds max_per_tx limit of 5.00 (ratio... |
| 2026-10-30T06:21:10.409812 | BLOCKED  |  $3.00 | shady-wallet.xyz  | Recipient 'shady-wallet.xyz' is not in allowed_merch... |
| 2026-10-30T06:21:10.405301 | APPROVED |  $0.75 | x402.coinbase.com | Unlock paywalled financial filing dataset               |
| 2026-10-30T06:21:10.401004 | APPROVED |  $1.50 | api.perplexity.ai | Fetch real-time market research for Q4 synthesis        |
+----------------------------+----------+--------+-------------------+---------------------------------------------------------+
```

## Roadmap

1. **v0.1 — Local SQLite Guardrails (Current):** Zero-dependency decorator (`@guard.protect`), deterministic per-tx and daily UTC budgets, merchant whitelisting, mandatory semantic rationale, and local CLI audit table viewer.
2. **v0.2 — MCP & Agent Framework Integrations:** Drop-in middleware and tool wrappers for Model Context Protocol (MCP) servers, LangChain / LangGraph, OpenAI Agents SDK, and Coinbase x402 / Stripe Agent Toolkit.
3. **v0.3 — Subcent Cloud Dashboard & Human-in-the-Loop Webhooks:** Centralized multi-agent budget telemetry, real-time Slack / Discord / webhook approval flows when transactions exceed soft thresholds, and cryptographic policy signing.

## License

MIT License. See [LICENSE](LICENSE) for details.
