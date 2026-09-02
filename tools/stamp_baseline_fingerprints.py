#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Add the content fingerprint to baselines blessed before gate G3 had one.

    python tools/stamp_baseline_fingerprints.py [--check] [--force]

Roadmap 4.13 split one corpus fingerprint into two: `content_digest`, which
decides whether G3 enforces, and `corpus_digest`, which records how the corpus
was cut and is reported rather than gated on (ADR-0045). Baselines blessed before
the split carry only the second, so G3 falls back to comparing boundaries and
says so — which is safe, and is exactly the abstention roadmap 4.15 needs to not
happen.

This is the one-shot that arms the new comparison **without re-blessing**. It
adds a field and changes no number: the per-slice scores stay whatever they were,
so 4.15's flip is measured against the line that was already drawn rather than
against one moved in the same change.

What makes that honest rather than merely convenient is the check it refuses on.
Before writing anything, the tool rebuilds each corpus and compares the *chunk*
fold against what the baseline already recorded. They must match. If they do
not, the corpus or the chunker has moved since the bless, the numbers in that
file describe something else, and a content fingerprint taken now would attach
today's corpus to yesterday's scores. In that case the tool refuses and tells you
to re-bless deliberately, which is a decision, not a stamp.

**A refusal is expected on a corpus under active authorship**, and this
repository's own is one: its documentation grows with every PR, so its baseline
has been stale — and G3 correctly abstaining on it — since the bless. Stamping
cannot fix that, and pretending otherwise is the failure this check exists to
prevent. The vendored corpora do not move, so theirs stamp cleanly.

Refusal is per corpus: the ones that check out are written, the one that does not
is left exactly as it was. `--check` reports without writing; `--force`
overwrites a content fingerprint already present, which only makes sense
immediately after a deliberate re-bless.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from build_eval_cases import stage_corpus  # noqa: E402

from mycelium.build import build  # noqa: E402
from mycelium.eval.harness import corpus_fingerprint_of  # noqa: E402

CORPORA: tuple[tuple[str, str], ...] = (
    ("this repository", "."),
    ("uv-docs", "eval/corpora/uv-docs"),
    ("uv-docs-ingested", "eval/corpora/uv-docs-ingested"),
)
"""Every corpus with a committed baseline, and the label used in the report."""

BASELINE = "eval/baselines/release.json"
"""The release set is the one CI gates, so it is the one that must be blessed."""

SKIP = frozenset({".git", ".mycelium", ".venv", "export", ".hypothesis", ".ruff_cache"})


def staged(relative: str, destination: Path) -> None:
    """Copy one corpus into `destination`; the committed tree is never built.

    A build pins a `mycelium_id` into any document that lacks one (ADR-0009), and
    a tool that measures should not edit the tree it measures — the complaint
    roadmap 4.14 exists to fix. Neither fingerprint can see frontmatter, so a
    staged copy and an in-place build give the same two digests.
    """
    if relative == ".":
        stage_corpus(destination)
        return
    source = ROOT / relative
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(*SKIP))


def stamp(label: str, relative: str, *, check: bool, force: bool) -> bool:
    """Stamp (or verify) one corpus's baseline. Returns False on a refusal."""
    path = ROOT / relative / BASELINE
    if not path.is_file():
        print(f"  {label}: no committed baseline at {relative}/{BASELINE} - nothing to do")
        return True

    data = json.loads(path.read_text(encoding="utf-8"))
    pending = [
        name
        for name, entry in data.items()
        if isinstance(entry, dict) and (force or not entry.get("content_digest"))
    ]
    if not pending:
        print(f"  {label}: already carries a content fingerprint for every retriever")
        return True

    with tempfile.TemporaryDirectory(prefix="stamp-") as tmp:
        root = Path(tmp) / "corpus"
        staged(relative, root)
        build(root)
        fingerprint = corpus_fingerprint_of(root)

    if not fingerprint:
        print(f"  {label}: the build produced no readable store - refusing")
        return False

    for name in sorted(pending):
        recorded = data[name].get("corpus_digest")
        if recorded and recorded != fingerprint.chunks:
            print(
                f"  {label} / {name}: REFUSED - the chunk fold has moved since this "
                f"baseline was blessed, so its numbers describe a different corpus.\n"
                f"    baseline {recorded}\n    now      {fingerprint.chunks}\n"
                f"    Re-bless deliberately (`mycelium eval <root> --bless`) instead of "
                f"stamping today's corpus onto yesterday's scores."
            )
            return False
        data[name]["content_digest"] = fingerprint.content
        print(f"  {label} / {name}: content_digest = {fingerprint.content}")

    if check:
        print(f"  {label}: --check, nothing written")
        return True
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  {label}: wrote {path.relative_to(ROOT).as_posix()}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report without writing")
    parser.add_argument(
        "--force", action="store_true", help="overwrite a content fingerprint already present"
    )
    args = parser.parse_args()

    print("Stamping the content fingerprint gate G3 enforces on (roadmap 4.13):")
    ok = True
    for label, relative in CORPORA:
        ok = stamp(label, relative, check=args.check, force=args.force) and ok
    if not ok:
        print(
            "\nAt least one corpus refused; the rest were stamped, and the refusing one was "
            "left exactly as it was. A corpus under active authorship is expected here - its "
            "baseline is stale, G3 is correctly abstaining on it, and only a deliberate "
            "re-bless fixes that."
        )
        return 1
    print("\nDone. Per-slice scores are untouched - `git diff` should show added lines only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
