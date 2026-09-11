#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Run the gates this change actually needs, and say which ones those are.

    python tools/verify.py [--base <ref>] [--mode <mode>] [--list] [--json]

Every item in this repository was verified the same way: run everything, twice,
and wait. Measured on 2026-09-04, that is where the time goes — and where it does
*not*:

| where                                    | the whole suite |
|------------------------------------------|----------------:|
| CI, `ubuntu-24.04`                        |            110 s |
| CI, `windows-2022`                        |            279 s |
| this machine (Windows, 20 cores, serial)  |            721 s |

Two things follow. The local loop is slow because it is Windows, not because it
is under-parallelised — `pytest-xdist` was measured and **refused**: `--dist
loadfile` saved 22 % (562 s) because the cost sits in a handful of expensive
files, and `--dist load` was *worse than serial* (1389 s) because per-test
distribution destroys the fixture reuse this suite depends on. And running
everything locally duplicates, slowly, what CI already does quickly and in
parallel.

So the loop changes shape rather than speed: **run the gates the diff implicates
locally, and let CI be the authority on the rest.** That is only safe if the
scope cannot be quietly narrowed, which is the whole design of this tool.

**The mode is derived, and may only be widened.** It comes from the diff, not
from a person: a change touching `src/mycelium/retrieval.py` is `retrieval`
whatever anyone would prefer. `--mode` exists to ask for *more* — a wider mode is
always allowed, a narrower one is refused by name. A declaration that could
narrow would be a way to land unverified code, which is boundary **B13** in the
threat model, and the refusal below is its control.

The mode is *declared* in the sense that matters: every run prints the mode it
used and why, `--json` emits it for CI to key its matrix on, and the PR body
carries it. What ran is on the record rather than inferred from a green tick.

**And the plan is checked against CI, not merely believed.** The workflow says of
the mode "one implementation, two callers", which is true — both ask this file.
It was never true of *what a mode runs*: that lived here as `plan()` and again in
the workflow as job conditions and shell steps, and the two drifted. At
`retrieval` CI gated three corpora and this tool gated one, so a contributor
could pass the local loop and be told something new by CI, which is the one thing
a scoped loop must not do. `tests/test_verify_ladder.py` now reads both and fails
when they disagree (roadmap 4.35, ADR-0059).

The rungs, and what each adds:

| mode | adds |
|---|---|
| `docs` | the congruence lint |
| `code` | format, lint, types, the suite, the two ingestion reproductions |
| `retrieval` | the frozen-set rule, the corpora built and gated, G2, the two ablations |
| `full` | the benchmarks, alone rather than beside four hundred other tests |
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from check_frozen_release_sets import TUNING_PATHS  # noqa: E402

MODES: tuple[str, ...] = ("docs", "code", "retrieval", "full")
"""Narrowest to widest. Each mode runs everything the mode before it runs."""

DOC_SUFFIXES = frozenset({".md", ".txt", ".png", ".svg", ".jpg"})
"""Extensions that cannot change behaviour. Deliberately short: anything not
named here widens the mode, so a new file type is over-verified rather than
skipped — the safe direction for a list nobody remembers to update."""

CODE_PREFIXES = (
    "src/",
    "tests/",
    "tools/",
    "contrib/",
    "pyproject.toml",
    "uv.lock",
)
"""Paths whose change is a code change.

`contrib/` joined at roadmap 5.5 with the first module. It is a second
distribution rather than part of `src/`, and it is held to the same gates for
the reason spec 05 §4.3 keeps contrib in-repo before the freeze: a core change
that breaks a module must fail the *core's* suite, or the plugin-API validation
is a promise nobody checks."""

EVAL_DATA_PREFIXES = ("eval/",)
"""The judged sets, the baselines and the corpora. A change here moves what the
gates *measure*, which is as much a retrieval change as touching the ranker.

The vendored corpora used to need a rule of their own — `eval/corpora/` derived
`full`, because only `full` built and gated them, so a change to one of *them*
would otherwise have skipped its own gate (roadmap 4.26). `retrieval` gates them
now, and the exception has nothing left to except: one rule covers the judged
sets, the baselines and the corpora alike (roadmap 4.35, ADR-0059)."""

CI_PREFIXES = (".github/",)

CORPORA = ("eval/corpora/uv-docs", "eval/corpora/uv-docs-ingested")
"""The vendored corpora, built and gated from `retrieval` upward.

Named here rather than inline because `tests/test_verify_ladder.py` reads this
list and the CI workflow's `eval` job and asserts they agree. The mode has always
been one implementation with two callers; the *plan* was two implementations
with one name, which is how they came to disagree (roadmap 4.35, ADR-0059)."""


CHECKED_PATHS: Final = ("src", "tests", "tools", "contrib")
"""What the formatter and the linter read.

`tools/` joined at roadmap 4.43, and the reason it had not is that nobody priced
it: the eighteen files that build the ingested corpus, carry the judgements,
measure the ranking and decide gate G2's currency were reviewed and nothing else.
Measured before adding them — `ruff check` and `ruff format --check` are under a
second either way, and the difference between the two target lists is smaller than
the run-to-run spread of either one."""

TYPED_PATHS: Final = ("src", "tools", "contrib/chats/src")
"""What `mypy --strict` reads. No `tests/`, and that is a separate question.

`tools/` cost nothing measurable to add: three cold runs read 79.2 / 58.3 / 56.5 s
for `src` against 60.0 / 58.3 / 57.4 s for `src tools`, because the time goes into
the third-party graph — pydantic, numpy, typer — which `src` already imports and
`tools/` reuses. Eighteen more files, 87 checked to 105, no measurable cost
(roadmap 4.43).

`contrib/chats/src` joined at roadmap 5.5, named as a path rather than as
`contrib` because a distribution's *sources* are what `mypy --strict` reads and
its tests are the separate question `tests/` still is. Same reasoning, same
result: the third-party graph is already loaded, so 105 files checked becomes
110."""

MYCELIUM = [sys.executable, "-c", "from mycelium.cli import main; main()"]
"""How to invoke the CLI without depending on a console script being on PATH.

`python -m mycelium` does not work — the package has no `__main__` — and the
`mycelium` executable lives in a virtualenv's `Scripts/` or `bin/` depending on
the platform. Going through `sys.executable` is the one form that is true on a
contributor's machine and on every runner in the matrix."""


def changed_files(base: str) -> list[str]:
    """Every path this change touches: committed against `base`, and uncommitted.

    The working tree is included on purpose. Locally the gates run *before* the
    commit, so a tool that read only the committed diff would derive `docs` for a
    branch whose uncommitted work rewrites the ranker — the exact narrowing this
    tool exists to make impossible. In CI the tree is clean and this reduces to
    the committed diff.
    """
    result = subprocess.run(  # fixed argument vector, no shell
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"cannot diff against {base}: {result.stderr.strip()}")
        raise SystemExit(2)
    paths = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    status = subprocess.run(  # fixed argument vector, no shell
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    for line in status.stdout.splitlines():
        entry = line[3:].strip()
        if not entry:
            continue
        # A rename reads `old -> new`; the destination is what this change ships.
        paths.add(entry.split(" -> ")[-1].strip('"'))
    return sorted(path.replace("\\", "/") for path in paths if path)


def derive(paths: list[str]) -> tuple[str, str]:
    """The narrowest mode this diff may run under, and the path that decided it.

    Widest wins: one retrieval file in a hundred documentation files is a
    retrieval change. The reason is returned with the mode because "why am I
    running the evals" is the question a reader has at exactly this moment.
    """
    if not paths:
        return "full", "nothing changed against the base - running everything rather than nothing"

    for path in paths:
        if any(path.startswith(prefix) for prefix in TUNING_PATHS):
            return "retrieval", f"{path} can change what a query returns"
    for path in paths:
        if any(path.startswith(prefix) for prefix in EVAL_DATA_PREFIXES):
            return "retrieval", f"{path} changes what the gates measure"
    for path in paths:
        if any(path.startswith(prefix) for prefix in CI_PREFIXES):
            return "full", f"{path} changes the verification itself"
    for path in paths:
        if any(path.startswith(prefix) for prefix in CODE_PREFIXES):
            return "code", f"{path} can change behaviour"
    unknown = [path for path in paths if Path(path).suffix not in DOC_SUFFIXES]
    if unknown:
        return "full", f"{unknown[0]} is not a file type this tool can classify"
    return "docs", "every changed file is documentation"


def resolve(derived: str, asked: str | None) -> str:
    """Honour a request to widen; refuse one to narrow, by name."""
    if asked is None:
        return derived
    if MODES.index(asked) < MODES.index(derived):
        print(
            f"refusing --mode {asked}: this diff is a {derived} change, and a mode may only "
            f"widen. {asked} would skip gates the change can break, which is how unverified "
            "code lands (threat model B13)."
        )
        raise SystemExit(2)
    return asked


def plan(mode: str) -> list[tuple[str, list[str]]]:
    """The commands one mode runs, in order, cheapest first so failure is quick."""
    python = sys.executable
    steps: list[tuple[str, list[str]]] = [
        ("congruence", [python, "tools/consistency_lint.py"]),
    ]
    if mode == "docs":
        return steps
    steps += [
        ("format", [python, "-m", "ruff", "format", "--check", *CHECKED_PATHS]),
        ("lint", [python, "-m", "ruff", "check", *CHECKED_PATHS]),
        ("types", [python, "-m", "mypy", "--strict", *TYPED_PATHS]),
        ("tests", [python, "-m", "pytest", "-q"]),
        # The two derived-artifact reproductions CI's `ingest / lanes` job runs at
        # this mode. They were CI-only, which is ADR-0059's drift still live in
        # another job: a change to docling, pandoc, PDFium or the projector fails
        # them, and until now it failed them for the first time in CI. Measured at
        # 64 s and 15 s on this machine - real, and the safe direction is the one
        # this tool takes everywhere else (roadmap 4.40).
        ("ingested corpus", [python, "tools/build_ingested_corpus.py", "--check"]),
        ("carried cases", [python, "tools/build_ingested_cases.py", "--check"]),
    ]
    if mode == "code":
        return steps
    steps += [
        ("frozen sets", [python, "tools/check_frozen_release_sets.py", "origin/main"]),
        ("build", [*MYCELIUM, "build", ".", "--no-pin"]),
        ("gates", [*MYCELIUM, "eval", ".", "--gate", "--against", "grep"]),
    ]
    # Every corpus, at `retrieval` — because that is what CI's `eval` job does at
    # this mode, and because these two are the sets gate G3 actually *enforces*
    # on (ADR-0053). A retrieval change that ran only the corpus above skipped
    # the gate it was most likely to move, and the mode's name promised a gate it
    # did not run (roadmap 4.35, ADR-0059).
    for corpus in CORPORA:
        steps += [
            (f"build {corpus}", [*MYCELIUM, "build", corpus, "--no-pin"]),
            (
                f"gates {corpus}",
                [
                    *MYCELIUM,
                    "eval",
                    corpus,
                    "--set",
                    "eval/release.jsonl",
                    "--gate",
                    "--against",
                    "grep",
                ],
            ),
        ]
    # Gate G2, which until now had no runner at all (roadmap 4.40). It goes after
    # the corpora because it fingerprints them, and it does not need the embedding
    # model: what it checks is whether the *recorded* verdict still describes this
    # product. Where the model happens to be present it re-measures as well, and
    # says which of the two it did.
    steps.append(("gate G2", [python, "tools/measure_hybrid_gate.py", "--check"]))
    # Spec 04 §5's ablation, which decides whether graph expansion ships on
    # (roadmap 5.3). It joins here rather than at `full` for the same reason G2
    # did: it needs no model, it is deterministic, and what it guards is a
    # *default* that a retrieval change can invalidate without anyone noticing.
    # `--check` fails on the flag disagreeing with the measurement, never on the
    # ablation being lost — losing it is the recorded outcome (ADR-0075).
    steps.append(("graph ablation", [python, "tools/measure_graph_expansion.py", "--check"]))
    # Spec 04 §3's symbol leg, gated the same way and for the same reason
    # (roadmap 5.9, ADR-0080): deterministic, model-free, and what it guards is a
    # default that a change to extraction or to ranking could invalidate in
    # silence. `--check` fails on the flag disagreeing with the measurement.
    steps.append(("symbol ablation", [python, "tools/measure_symbol_leg.py", "--check"]))
    steps.append(("agent tasks", [*MYCELIUM, "eval", ".", "--tasks"]))
    if mode == "retrieval":
        return steps
    # The one thing `full` adds, and the one job CI gates on `full` alone. The
    # suite runs the benchmarks too, but it runs them beside four hundred other
    # tests on a loaded machine — which is the same numbers taken badly. A
    # performance claim needs a reproducible measurement (AGENTS.md §10), and
    # that means the benchmarks alone.
    steps.append(
        (
            "benchmarks",
            [
                python,
                "-m",
                "pytest",
                "tests/bench",
                # The module's own baselines travel with it (spec 05 §4.3), so
                # they are named here rather than found by a glob: a promoted
                # repository takes its benchmarks and this line goes with it.
                "contrib/chats/tests/bench",
                "--benchmark-only",
                "-q",
            ],
        )
    )
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="what to diff against")
    parser.add_argument("--mode", choices=MODES, help="widen the derived mode; never narrow it")
    parser.add_argument("--list", action="store_true", help="print the plan and run nothing")
    parser.add_argument("--json", action="store_true", help="emit the decision for CI to read")
    args = parser.parse_args()

    paths = changed_files(args.base)
    derived, reason = derive(paths)
    mode = resolve(derived, args.mode)
    steps = plan(mode)

    if args.json:
        print(
            json.dumps(
                {
                    "mode": mode,
                    "derived": derived,
                    "reason": reason,
                    "changed": len(paths),
                    "steps": [name for name, _ in steps],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    widened = f" (widened from {derived})" if mode != derived else ""
    print(f"mode: {mode}{widened} - {reason}")
    print(f"  {len(paths)} file(s) changed against {args.base}")
    print(f"  running: {', '.join(name for name, _ in steps)}\n")
    if args.list:
        for name, command in steps:
            print(f"  {name}: {' '.join(command[1:])}")
        return 0

    for name, command in steps:
        print(f"--- {name}")
        result = subprocess.run(command, cwd=ROOT, check=False)  # fixed argv, no shell
        if result.returncode != 0:
            print(f"\n{name} failed ({result.returncode}). Nothing after it ran.")
            return 1
    print(f"\nAll {mode} gates pass. CI runs the rest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
