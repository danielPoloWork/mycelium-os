#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Measure what a repeated query word is worth, on both halves of the expression.

    python tools/measure_query_repetition.py [--corpus PATH]... [--json]

`expanded_query` builds one MATCH expression out of two halves (ADR-0048): the
surface terms against the surface columns, their stems against the stem columns.
The two halves disagree about repetition, and always have:

- the **stem** half is deduplicated — `dict.fromkeys(stem_text(terms))`, with a
  comment saying why;
- the **surface** half is a plain comprehension over every match, so a question
  contributes one `OR` arm per **occurrence** of a word rather than per word.

Roadmap 6.17 bounded the query at 64 terms, which made the *cost* of that moot.
What it left is a question about **ranking**, and roadmap 6.26 is where it was
measured rather than argued: a duplicated arm is not free in FTS5. Doubling
`"link" OR "link"` doubles that term's BM25 contribution exactly, and it changes
the order — which is the whole of the question.

## The three arms

| arm | surface | stems |
|---|---|---|
| **A** incumbent | one arm per occurrence | deduplicated |
| **B** dedup both | deduplicated | deduplicated |
| **C** repeat both | one arm per occurrence | one arm per occurrence |

A and C weight a repeated word by how often the question says it. B does not.
Symmetry is available in both directions, which is why both are measured: *"the
asymmetry is wrong"* has two possible repairs and they do not agree.

## What it found (roadmap 6.26, ADR-0141)

Every set regressed or held under **B**, and **C** gained on two sets and
regressed on the third — so neither symmetric arm clears the standing bar for a
ranking change (a release-set gain with no overall regression on any set,
ADR-0070/ADR-0080, applied again at ADR-0137). The incumbent stays, and the
asymmetry is now a measured decision rather than an unexamined one.

Run by hand, not in the gate ladder: nothing here is a shippable flag, so there
is no default for a `--check` to hold. The numbers belong to a decision already
taken, and this script is how a reader re-takes it.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import mycelium.store.sqlite as sq  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.harness import _score  # noqa: E402
from mycelium.eval.retrievers import (  # noqa: E402
    anchor_facts,
    build_retriever,
    resolvable_anchors,
)
from mycelium.eval.tasks import load_tasks, run_task_suite  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402
from mycelium.store.stemming import stem_text  # noqa: E402

CORPORA: Final[tuple[str, ...]] = (
    ".",
    "eval/corpora/uv-docs",
    "eval/corpora/uv-docs-ingested",
)

SETS: Final[tuple[str, ...]] = ("eval/dev.jsonl", "eval/release.jsonl")

_SHIPPED_FTS = sq.fts_query
_SHIPPED_EXPANDED = sq.expanded_query


def _dedup_surface(text: str, *, prefix: bool = False, match_all: bool = False) -> str:
    """Arm B's surface half: one arm per distinct word.

    `dict.fromkeys` rather than a set, for the reason the stem half already gives:
    the expression must stay deterministic for the same query.
    """
    terms = list(dict.fromkeys(sq._FTS_TERM.findall(text)))
    if not terms:
        return ""
    suffix = "*" if prefix else ""
    return (" " if match_all else " OR ").join(f'"{term}"{suffix}' for term in terms)


def _repeating_stems(text: str, *, prefix: bool = False, match_all: bool = False) -> str:
    """Arm C's expression: the stem half weights by occurrence too."""
    surface = sq.fts_query(text, prefix=prefix, match_all=match_all)
    if not surface or prefix:
        return surface
    stems = stem_text(sq._FTS_TERM.findall(text))
    joiner = " " if match_all else " OR "
    stemmed = joiner.join(f'"{stem}"' for stem in stems)
    return f"{sq._SURFACE_FIELDS} : ({surface}) OR {sq._STEM_FIELDS} : ({stemmed})"


@dataclass(frozen=True)
class Arm:
    """One way of treating a repeated word, and how to install it."""

    key: str
    title: str
    install: Callable[[], None]


def _shipped() -> None:
    sq.fts_query = _SHIPPED_FTS
    sq.expanded_query = _SHIPPED_EXPANDED


def _arm_b() -> None:
    _shipped()
    sq.fts_query = _dedup_surface


def _arm_c() -> None:
    _shipped()
    sq.expanded_query = _repeating_stems


ARMS: Final[tuple[Arm, ...]] = (
    Arm("A", "incumbent: surface repeats, stems deduplicated", _shipped),
    Arm("B", "deduplicate both halves", _arm_b),
    Arm("C", "repeat in both halves", _arm_c),
)


def repeated_terms(query: str) -> list[str]:
    """The words this query says more than once, in first-seen order."""
    terms = sq._FTS_TERM.findall(query)
    seen = dict.fromkeys(terms)
    return [term for term in seen if terms.count(term) > 1]


def census(corpora: Sequence[str]) -> dict[str, int]:
    """How many judged queries repeat a word at all.

    The number roadmap 6.26 was filed against was *two of 155*, taken at 6.17 —
    before roadmap 6.8 authored the release sets from 19 and 25 cases to 286 and
    404. The item's premise was a measurement of a corpus that no longer exists,
    which is why this census runs before the arms do.
    """
    queries = repeating = 0
    for corpus in corpora:
        root = ROOT / corpus
        for name in (*SETS, "eval/tasks.jsonl"):
            path = root / name
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                query = str(row.get("query") or row.get("prompt") or "")
                queries += 1
                if repeated_terms(query):
                    repeating += 1
    return {"queries": queries, "repeating": repeating}


def score_arms(corpus: str, case_set: str) -> dict[str, Any]:
    """Score every arm over one set, on one store opened once."""
    root = ROOT / corpus
    cases = load_cases(root / case_set)
    scores: dict[str, float] = {}
    per_case: dict[str, dict[str, float]] = {}
    with SqliteStore.open(root, read_only=True) as store:
        resolvable = resolvable_anchors(store)
        facts = anchor_facts(store)
        for arm in ARMS:
            arm.install()
            results, overall, _ = _score(
                cases, build_retriever("mycelium", store), resolvable, facts
            )
            scores[arm.key] = overall.ndcg_at_10
            per_case[arm.key] = {item.case_id: item.ndcg_at_10 for item in results}
        _shipped()
    moved = {
        key: sorted(
            case_id
            for case_id, value in per_case[key].items()
            if abs(value - per_case["A"][case_id]) > 1e-9
        )
        for key in ("B", "C")
    }
    return {"corpus": corpus, "set": case_set, "cases": len(cases), "ndcg": scores, "moved": moved}


def score_tasks(corpus: str) -> dict[str, Any]:
    """The agent-task suite, which the filing item asked for by name."""
    root = ROOT / corpus
    path = root / "eval/tasks.jsonl"
    if not path.is_file():
        return {}
    tasks = load_tasks(path)
    found: dict[str, float] = {}
    tokens: dict[str, float] = {}
    for arm in ARMS:
        arm.install()
        report = run_task_suite(root, tasks)
        summary = report.summary("mycelium")
        found[arm.key] = float(summary.get("success_rate", 0.0))
        tokens[arm.key] = float(summary.get("mean_tokens", 0.0))
    _shipped()
    return {"corpus": corpus, "evidence_found": found, "mean_tokens": tokens}


def render(
    counted: dict[str, int], rows: Sequence[dict[str, Any]], tasks: Sequence[dict[str, Any]]
) -> None:
    print(
        f"{counted['repeating']} of {counted['queries']} judged queries repeat a word "
        f"(the item was filed against 2 of 155, before roadmap 6.8 grew the release sets)\n"
    )
    for arm in ARMS:
        print(f"  {arm.key}  {arm.title}")
    print()
    print(f"  {'set':38} {'A':>8} {'B':>17} {'C':>17}")
    for row in rows:
        base = row["ndcg"]["A"]
        label = f"{row['corpus']}/{Path(row['set']).stem}"

        def against(key: str, base: float = base, row: dict[str, Any] = row) -> str:
            value = row["ndcg"][key]
            pct = (value - base) / base * 100 if base else 0.0
            return f"{value:.4f} ({pct:+.2f}%)"

        print(f"  {label:38} {base:8.4f} {against('B'):>17} {against('C'):>17}")
        for key in ("B", "C"):
            if row["moved"][key]:
                print(
                    f"       {key} moved {len(row['moved'][key])}: {', '.join(row['moved'][key])}"
                )
    if tasks:
        print(f"\n  {'agent tasks (evidence found)':38} {'A':>8} {'B':>17} {'C':>17}")
        for row in tasks:
            found = row["evidence_found"]
            print(f"  {row['corpus']:38} {found['A']:8.3f} {found['B']:>17.3f} {found['C']:>17.3f}")
    print(
        "\nA ranking change earns its default with a release-set gain and no overall "
        "regression on any set (ADR-0070, ADR-0080, ADR-0137). Read the rows above "
        "against that bar."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="append", help="repeatable; defaults to all three")
    parser.add_argument("--json", action="store_true", help="emit the measurement as JSON")
    parser.add_argument("--no-tasks", action="store_true", help="skip the agent-task suite")
    arguments = parser.parse_args(argv)

    corpora = tuple(arguments.corpus) if arguments.corpus else CORPORA
    counted = census(corpora)
    rows = [
        score_arms(corpus, case_set)
        for corpus in corpora
        for case_set in SETS
        if (ROOT / corpus / case_set).is_file()
    ]
    tasks = [] if arguments.no_tasks else [row for row in (score_tasks(c) for c in corpora) if row]

    if arguments.json:
        print(
            json.dumps({"census": counted, "sets": rows, "tasks": tasks}, indent=2, sort_keys=True)
        )
    else:
        render(counted, rows, tasks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
