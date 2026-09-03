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

DERIVED_SETS = {
    "eval/corpora/uv-docs-ingested/eval/release.jsonl": "eval/corpora/uv-docs/eval/release.jsonl",
    "eval/corpora/uv-docs-ingested/eval/dev.jsonl": "eval/corpora/uv-docs/eval/dev.jsonl",
}
"""Derived set → the judged set it is carried from (`tools/build_ingested_cases.py`).

Nothing in a derived set is judged: every query, grade, slice and note is copied
verbatim from the source, and only the *anchor* is computed (ADR-0039). So the
conjunction rule below does not apply to it, and applying it was a category error
that only became visible at roadmap 4.15 — the first chunking change after both
guards existed.

The bind is that a derived set is a function of the chunker. A chunking change
*must* move it (the `ingest / lanes` job fails otherwise, [BUG-0018]) and the
conjunction rule *forbade* moving it, so the two guards could not both be
satisfied and no ordering of two PRs helped: the set only changes once the
chunker does. Nothing weaker replaces the rule — what replaces it is stronger.
A derived set may not move in the same change as **its source**, and its contents
are byte-checked against the generator on every CI run, which is a better
guarantee than "nobody edited this file" (roadmap 4.15, ADR-0047)."""

TUNING_PATHS = (
    "src/mycelium/retrieval.py",
    "src/mycelium/chunking.py",
    "src/mycelium/config.py",
    "src/mycelium/store/",
    "src/mycelium/embedding/",
    "src/mycelium/eval/retrievers.py",
    "src/mycelium/eval/metrics.py",
)
"""Everything that can change what a query returns or how it is scored.

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
