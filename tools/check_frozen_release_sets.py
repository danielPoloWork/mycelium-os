#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Refuse a change that tunes retrieval and re-judges the release set at once.

    python tools/check_frozen_release_sets.py <base-ref>

Spec 04 §7.1: "the release set is frozen before any tuning of the change under
test." A set nobody can edit is not what that means — sets have to grow — so what
is enforced is the *conjunction*: one change may move the retriever, or move the
judgments, and not both.

That is the only form of the rule a machine can check, and it catches the failure
that actually happens: a run comes back worse, the judgment looks wrong in
hindsight, and the set quietly becomes the thing that fits (ADR-0027).

One rule that used to live here has been retired: a *derived* set may now move
with the set it is carried from, because a byte-exact regeneration check says
more than a rule about which commit two files arrived in. See `DERIVED_SETS`
below, which is kept empty rather than deleted (roadmap 4.26, ADR-0056).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RELEASE_SETS = (
    "eval/release.jsonl",
    "eval/corpora/uv-docs/eval/release.jsonl",
)
"""Every *judged* frozen release set — the ones a human wrote and could re-fit."""

DERIVED_SETS: dict[str, str] = {}
"""Empty, and the emptiness is the decision (roadmap 4.26, ADR-0056).

A derived set — `eval/corpora/uv-docs-ingested/eval/*.jsonl` — used to be
forbidden from moving in the same change as the judged set it is carried from.
Nothing in it is judged: every query, grade, slice and note is copied verbatim
and only the *anchor* is computed (ADR-0039), so the rule was never about
re-fitting. It was a proxy for "this file was not hand-edited".

The proxy is retired because the direct check exists and is stronger.
`tools/build_ingested_cases.py --check` regenerates the carry from the source set
and the corpus and byte-compares it, in CI, on every run (roadmap 4.16,
[BUG-0018]). A hand-edited derived set fails that check whichever commit it
arrived in; a rule about *when* two files changed cannot say anything a
regeneration cannot say better.

What the proxy did do was deadlock growth. A derived set is a function of its
source and the chunker, so it *must* move when either does — and the rule forbade
exactly that, from the chunking side at roadmap 4.15 and from the judgement side
at 4.20, where eight drafted cases could not land because the carry could not
follow them. No ordering of two PRs helped: the set only changes once its source
does.

The mapping is kept rather than deleted so the shape of the rule stays visible,
and so re-arming it is a one-line change if the reproduction check ever stops
running in CI."""

TUNING_PATHS = (
    "src/mycelium/retrieval.py",
    "src/mycelium/chunking.py",
    "src/mycelium/config.py",
    "src/mycelium/store/",
    "src/mycelium/embedding/",
    "src/mycelium/eval/",
)
"""Everything that can change what a query returns or how it is scored.

`src/mycelium/eval/` is the whole package rather than the two files it used to
name (`retrievers.py`, `metrics.py`). `harness.py` was outside it, and it is the
module that drives the retriever over the cases, averages the results and decides
every gate — so a change there classified as ordinary code and ran no gate at
all. That is not hypothetical: PR #81 changed it and CI reported `eval / gates
G1-G6` as *skipping* (roadmap 4.35, ADR-0059). A directory is the right unit here
for the same reason `store/` and `embedding/` are: the question is not which file
holds the ranking today.

`config.py` is here because a shipped *default* changes the retriever as surely as
the algorithm does: `[chunking] pack_atomic` moves every chunk boundary, and its
default lives in `ChunkingConfig` rather than in the chunker (roadmap 4.11,
ADR-0042). Without this line a single change could flip that default and re-judge
a release set unrefused, which is precisely the conjunction this script exists to
catch."""


def changed_files(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"cannot diff against {base}: {result.stderr.strip()}")
        raise SystemExit(2)
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    changed = changed_files(base)

    judged = [path for path in changed if path in RELEASE_SETS]
    tuned = [path for path in changed if path.startswith(TUNING_PATHS)]
    derived = [path for path in changed if path in DERIVED_SETS]

    refitted = [(path, DERIVED_SETS[path]) for path in derived if DERIVED_SETS[path] in changed]
    if refitted:
        print("This change moves a derived set *and* the judgements it is carried from:")
        for path, source in refitted:
            print(f"  derived: {path}")
            print(f"  source:  {source}")
        print(
            "\nA derived set may move with the machinery — it is regenerated, not written. "
            "It may not move in the same change as the judgements it copies, because then "
            "nothing distinguishes a carry from a re-fit (ADR-0039, ADR-0047)."
        )
        return 1

    if judged and tuned:
        print("This change re-judges a frozen release set *and* tunes retrieval:")
        for path in judged:
            print(f"  judged:  {path}")
        for path in tuned:
            print(f"  tuning:  {path}")
        print(
            "\nSplit it in two. A release set may grow, and a retriever may change, but a "
            "change that does both cannot be told apart from fitting the set to the result "
            "(spec 04 §7.1, ADR-0027)."
        )
        return 1

    if derived:
        print(f"derived set(s) regenerated, source judgements untouched: {', '.join(derived)}")
    if judged:
        print(f"release set(s) changed, no retrieval change alongside: {', '.join(judged)}")
    elif not derived:
        print("release sets untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
