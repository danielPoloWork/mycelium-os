# Local Build & Test

How to build, test, and check `mycelium-os` on your machine. CI runs the same commands
on Linux / Windows / macOS on CPython 3.12+; reproducing them locally avoids a red round-trip.

## Prerequisites

- **Python 3.12+** toolchain.
- **Build system:** Hatch (PEP 517/518, pyproject.toml).
- **Package manager:** uv (or pip-tools) with a locked pyproject.toml.
- **Formatter / linter:** ruff format (Black-compatible), ruff check + mypy --strict.
- **Docs:** mkdocs-material (or Sphinx for API-heavy libs) (for the API docs build).

## Commands

```bash
# Build
hatch build

# Test
pytest -q

# Format check
ruff format --check .

# Lint
ruff check . && mypy --strict src

# Benchmark
pytest tests/bench --benchmark-only

# Cross-artifact congruence (run before drafting any PR)
python tools/consistency_lint.py
```

## Before you open a PR

1. `ruff format --check .` and `ruff check . && mypy --strict src` are clean.
2. `pytest -q` passes; new/changed behavior is covered (≥ 80% line).
3. mypy --strict (type soundness), pytest -p no:cacheprovider under faulthandler, tracemalloc leak checks are green where applicable.
4. `python tools/consistency_lint.py` passes.
5. The relevant docs (README, ROADMAP, ADRs, patterns, changelog) are updated in the same
   PR — see [`../workflow/documentation.md`](../workflow/documentation.md).
