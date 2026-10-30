# Subcent (`subcent-si`) — Agent Instructions

When working in this repository, the following guardrails MUST be followed.

## 1. Unit tests are mandatory (highest priority)

- Whenever you add or change functionality (public functions, classes, CLI subcommands, etc.), you MUST implement corresponding unit tests under `tests/`. Never propose implementation code without tests.
- If a proposed change cannot be covered by tests, explain why and obtain approval first.
- After any code change, always run the test suite and confirm everything passes before considering the work done:

  ```bash
  python -m unittest discover -s tests -v
  ```

- Completing work or committing while tests are failing is forbidden.

## 2. Git workflow (feature branch + PR)

- NEVER commit or push directly to `main`.
- For new features or bug fixes, always create a new feature branch from the remote `main`:

  ```bash
  git fetch origin
  git checkout -b feature/<short-description> origin/main
  ```

  (Use appropriate prefixes: `fix/<name>` for bug fixes, `docs/<name>` for documentation)
- After committing and pushing, open a **Pull Request targeting `origin/main`**. Merging happens only after human review.
- PR description must include: purpose of the change, results of the added tests, and whether there are any breaking changes.

## 3. Project principles

- **Keep zero dependencies:** use only the Python standard library (`sqlite3`, `functools`, `inspect`, `argparse`, etc.). Do not add external packages to `dependencies` lightly; if one is truly needed, present the rationale and obtain approval first.
- Maintain compatibility with Python 3.9+ (`pyproject.toml`: `requires-python = ">=3.9"`).
- Write type annotations in code (existing project style: `from __future__ import annotations`).
- Fail-closed principle: if an error or uncertainty occurs during a guardrail decision, always choose the "block" side.

## 4. References

- Running tests: `python -m unittest discover -s tests -v` (do not use pytest)
- Package layout: `subcent/` (`core.py` holds the policy engine, `cli.py` holds the CLI)
- See the Roadmap section in README for the roadmap
