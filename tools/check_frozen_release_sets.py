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
    "eval/corpora/uv-docs-ingested/eval/release.jsonl",
)
"""Every frozen release set. The third one is *derived* — its judgements are carried
from the second, not written — so an ingestion change may legitimately move it, and
ingestion is deliberately not in `TUNING_PATHS`. What stays refused is the thing the
rule is about: moving the retriever and the judgements in one change."""

TUNING_PATHS = (
    "src/mycelium/retrieval.py",
    "src/mycelium/chunking.py",
    "src/mycelium/store/",
    "src/mycelium/embedding/",
    "src/mycelium/eval/retrievers.py",
    "src/mycelium/eval/metrics.py",
)
"""Everything that can change what a query returns or how it is scored."""


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

    if judged:
        print(f"release set(s) changed, no retrieval change alongside: {', '.join(judged)}")
    else:
        print("release sets untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
