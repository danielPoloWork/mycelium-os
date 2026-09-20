#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What the agent-task verdict is worth, across the two constants that set it.

    python tools/measure_agent_task_band.py [ROOT] [--tasks PATH] [--manifest PATH]

The comparison spec 04 §7.4 asks for has a model of the incumbent inside it, and
that model has exactly two numbers: **how much one read costs** and **how many
files the loop opens** before it gives up. Roadmap 6.4 found out the expensive way
what happens when nobody measures them — the loop read the first matching file
whole whatever its size, so on this corpus it read one document on 22 of 22 tasks
and 93 % of its measured cost was `ROADMAP.md`.

Roadmap 6.22 bounded the read. This tool is the other half of that: it runs the
suite across a band of both constants, so the choice is auditable rather than
asserted, and so the shape of the comparison is visible instead of one row of it.

Two readings come out of the band, and they are the honest pair:

- **at equal cost** — the incumbent's first read costs about what a search does,
  and brings back far less;
- **at equal evidence** — the incumbent reaches a comparable evidence rate only
  by opening every file the model allows, and pays several times the context to
  get there.

Neither is quotable on its own, which is why this prints both. `--manifest`
writes the run in the benchmark schema (spec 04 §7.5) so a report can cite it.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

# The manifest's schema tag and the machine block are the reference profile's, read
# rather than restated: spec 04 §7.5 says what a manifest must record, and two
# copies of that list are two lists (the discipline `verify.py` and CI hold).
from benchmark_reference_profile import SCHEMA, hardware  # noqa: E402

from mycelium.__about__ import __version__  # noqa: E402
from mycelium.eval.tasks import (  # noqa: E402
    DEFAULT_BUDGET_TOKENS,
    MAX_GREP_FILES,
    MAX_SEARCH_K,
    TaskSuiteReport,
    load_tasks,
    run_task_suite,
)
from mycelium.store import SqliteStore  # noqa: E402

DEFAULT_BUDGETS: Final = (1_000, 2_000, 4_000, 8_000, 16_000)
DEFAULT_FILES: Final = (1, 2, 3, 5)
DEFAULT_KS: Final = (8, 10, 20, 50)
"""The `k` a caller might ask for: the tool's default, the literal this suite
used to carry, a middle, and the cap the contract states (roadmap 6.28)."""


def _stats(report: TaskSuiteReport, strategy: str) -> dict[str, Any]:
    rows = [row for row in report.by_strategy(strategy) if row.scorable]
    tokens = sorted(row.tokens for row in rows)
    return {
        "strategy": strategy,
        "found": sum(1 for row in rows if row.found),
        "scorable": len(rows),
        "mean": round(statistics.mean(tokens), 1),
        "p50": float(statistics.median(tokens)),
        "p95": float(tokens[max(0, int(0.95 * (len(tokens) - 1)))]),
        "max": float(tokens[-1]),
        "total": float(sum(tokens)),
        "mean_documents": round(statistics.mean(row.documents_read for row in rows), 2),
        "unit": "tokens",
    }


def _corpus(root: Path) -> dict[str, Any]:
    """The corpus the comparison ran over — a verdict without it is a verdict about
    nothing, and one of the two it can be is a self-hosting corpus that grows with
    every merge (roadmap 6.23)."""
    with SqliteStore.open(root, read_only=True) as store:
        counts = store.counts()
    return {"documents": counts["documents"], "chunks": counts["chunks"]}


def _commit() -> str:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover - a tarball, not a clone
        return ""


def recorded(path: Path, root: Path) -> str:
    """How a manifest names a path: repo-relative where it is, never a local one.

    A measurement of *this* corpus at a committed tree is taken in a clean
    checkout somewhere else — the working tree holds the change being written up,
    and a self-hosting corpus would otherwise include the report measuring it
    (roadmap 6.23). What belongs in the manifest is the commit, which it already
    records, and the shape of the tree — not the temporary directory it happened
    to sit in.
    """
    for base in (ROOT, root):
        try:
            relative = path.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
        return relative or "."
    return path.name


def kind_of(suite: Path) -> str:
    """Which corpus a comparison ran on, read from the suite it ran."""
    return (
        "vendored, compiled - documentation this project did not write"
        if "corpora" in suite.resolve().parts
        else "this repository's own, compiled"
    )


def suite_of(root: Path) -> Path:
    """Where a corpus keeps its agent-task suite.

    A parameter rather than this repository's own path, because since roadmap
    6.23 there is more than one suite: `eval/corpora/uv-docs` carries tasks
    judged against documentation nobody here wrote, and the verdict spec 04 §7.4
    arms at 1.0 is meant to be read on that one (ADR-0053). The convention is the
    CLI's — `<root>/eval/tasks.jsonl` — so a band and `mycelium eval --tasks`
    cannot end up measuring two different files.
    """
    return root / "eval" / "tasks.jsonl"


def measure(
    root: Path,
    budgets: Sequence[int],
    files: Sequence[int],
    ks: Sequence[int] = DEFAULT_KS,
    suite: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """The three bands, and the shipped point they all pass through.

    Three, since roadmap 6.28: the incumbent's two constants and **ours**. Our
    side had one too and it was a literal, which is how it went unnoticed that
    the arm could not spend a budget larger than about 3 100 tokens (ADR-0143).
    """
    tasks = load_tasks(suite if suite is not None else suite_of(root))

    by_files: list[dict[str, Any]] = []
    for count in files:
        report = run_task_suite(
            root, tasks, budget_tokens=DEFAULT_BUDGET_TOKENS, max_grep_files=count
        )
        row = _stats(report, "grep")
        row["name"] = f"grep, {count} file(s) opened, {DEFAULT_BUDGET_TOKENS}-token read"
        row["max_grep_files"] = count
        row["budget"] = DEFAULT_BUDGET_TOKENS
        by_files.append(row)

    by_budget: list[dict[str, Any]] = []
    shipped: dict[str, Any] = {}
    for budget in budgets:
        report = run_task_suite(root, tasks, budget_tokens=budget)
        for strategy in ("mycelium", "grep"):
            row = _stats(report, strategy)
            row["name"] = f"{strategy}, {budget}-token budget"
            row["budget"] = budget
            row["max_grep_files"] = MAX_GREP_FILES if strategy == "grep" else None
            by_budget.append(row)
            if budget == DEFAULT_BUDGET_TOKENS:
                shipped[strategy] = row

    # Our own constant, swept at the largest budget in the band: `k` binds before
    # the budget does, so a caller that leaves it at the tool's default cannot
    # spend a large budget either. That is the honest spread to publish beside
    # the number the suite reports (roadmap 6.28).
    widest = max(budgets)
    by_k: list[dict[str, Any]] = []
    for k in ks:
        report = run_task_suite(root, tasks, budget_tokens=widest, search_k=k)
        row = _stats(report, "mycelium")
        row["name"] = f"mycelium, k={k}, {widest}-token budget"
        row["budget"] = widest
        row["search_k"] = k
        by_k.append(row)

    return by_files, by_budget, by_k, shipped


def _table(rows: Sequence[dict[str, Any]], key: str, label: str) -> str:
    width = max(len(label), *(len(str(row[key])) for row in rows))
    lines = [
        f"{label:>{width}} | {'evidence':>9} | {'mean':>8} {'p50':>8} {'p95':>8} | {'docs':>5}"
    ]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(
            f"{str(row[key]):>{width}} | {row['found']:4d}/{row['scorable']:<4d} | "
            f"{row['mean']:8.0f} {row['p50']:8.0f} {row['p95']:8.0f} | "
            f"{row['mean_documents']:5.2f}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path, help="A built repository.")
    parser.add_argument(
        "--budgets",
        default=",".join(str(size) for size in DEFAULT_BUDGETS),
        help="Comma-separated context budgets; each is also the read window.",
    )
    parser.add_argument(
        "--files",
        default=",".join(str(size) for size in DEFAULT_FILES),
        help="Comma-separated counts of files the grep loop opens.",
    )
    parser.add_argument(
        "--ks",
        default=",".join(str(size) for size in DEFAULT_KS),
        help="Comma-separated `k` values our arm asks search for, at the widest budget.",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        help="The suite to run; defaults to <root>/eval/tasks.jsonl, as the CLI reads it.",
    )
    parser.add_argument("--manifest", type=Path, help="Write the run manifest here.")
    parser.add_argument("--json", action="store_true", help="Print the run as JSON.")
    args = parser.parse_args(argv)

    budgets = [int(item) for item in str(args.budgets).split(",") if item.strip()]
    files = [int(item) for item in str(args.files).split(",") if item.strip()]
    ks = [int(item) for item in str(args.ks).split(",") if item.strip()]
    suite = args.tasks if args.tasks is not None else suite_of(args.root)
    by_files, by_budget, by_k, shipped = measure(args.root, budgets, files, ks, suite)

    mine, theirs = shipped["mycelium"], shipped["grep"]
    print(
        f"At the shipped budget ({DEFAULT_BUDGET_TOKENS} tokens) and "
        f"{MAX_GREP_FILES} files:\n"
        f"  mycelium {mine['found']}/{mine['scorable']} at {mine['p50']:.0f} tokens (median)\n"
        f"  grep     {theirs['found']}/{theirs['scorable']} at {theirs['p50']:.0f} tokens "
        f"({theirs['p50'] / mine['p50']:.2f}x), lead "
        f"{mine['found'] - theirs['found']:+d} tasks"
    )
    print("\nThe incumbent as a band - how many files the loop opens:")
    print(_table(by_files, "max_grep_files", "files opened"))
    print("\nBoth strategies as the caller's budget moves (it is also the read window):")
    print(_table(by_budget, "name", "arm"))
    print(
        f"\nOur own constant, at the widest budget ({max(budgets)} tokens) - `k` binds "
        "before the budget does:"
    )
    print(_table(by_k, "search_k", "k"))

    document = {
        "schema": SCHEMA,
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "commit": _commit(),
        "toolchain": {"mycelium": __version__, "python": platform.python_version()},
        "hardware": hardware(),
        "corpus": {
            # Which corpus a comparison ran on *is* the comparison since roadmap
            # 6.23, so the manifest says which of the two it was rather than
            # restating a constant that used to be true.
            "kind": kind_of(suite),
            "root": recorded(args.root, args.root),
            "tasks": recorded(suite, args.root),
            "generator": "tools/measure_agent_task_band.py",
            **_corpus(args.root),
        },
        "budgets": {
            "read_window_tokens": DEFAULT_BUDGET_TOKENS,
            "max_grep_files": MAX_GREP_FILES,
            "search_k": MAX_SEARCH_K,
        },
        "task_profile": {
            "kind": "context each strategy puts in front of a model (spec 04 section 7.4)",
            "measurements": by_files + by_budget + by_k,
        },
    }
    if args.json:
        print(json.dumps(document, indent=2, sort_keys=True))
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nmanifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
