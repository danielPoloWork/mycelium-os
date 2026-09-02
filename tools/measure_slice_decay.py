#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Did the retriever get worse, or did the corpus get bigger? (ADR-0044)

    python tools/measure_slice_decay.py <git-ref> [--set release] [corpus-root]
    python tools/measure_slice_decay.py 9adad70 --set release

Gate G3 refuses to enforce across a corpus change, by design and correctly
([BUG-0014]): on a self-hosting corpus every PR moves the numbers, and a gate
that fired on that would train everyone to re-bless. The cost of that decision is
that a **slow decay can cross several milestones unremarked**, which is what
roadmap 4.17 found — `relationship` on our own release set halved between two
blesses and no gate could have said so.

This is the instrument G3 cannot be. It holds the judgments and the code fixed and
varies only the corpus: it checks the named ref out into a throwaway worktree,
copies **today's** judged sets in, compiles it with **today's** compiler, and
scores both. A slice that moves here moved because documents arrived; a slice that
does not is telling you to look at the code instead.

Heavy on purpose — two full builds — so it is a tool a human runs while asking a
question, not a gate. What it prints is per-slice deltas and, for the slices that
moved, the per-case ranks behind them, because a two-case slice's mean says
nothing on its own (ADR-0044).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.config import load_config  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k, section_of  # noqa: E402
from mycelium.eval.retrievers import terms_of  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

DEPTH, K = 50, 10
JUDGED_SETS = ("dev.jsonl", "release.jsonl")


def _worktree(ref: str, into: Path) -> None:
    """Check `ref` out into a detached throwaway worktree."""
    subprocess.run(
        ["git", "worktree", "add", "-q", "--detach", str(into), ref],
        cwd=ROOT,
        check=True,
    )


def _discard(into: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(into)], cwd=ROOT, check=False)


def _score(
    root: Path, set_name: str
) -> tuple[dict[str, float], dict[str, tuple[float, int | None]]]:
    """Per-slice nDCG@10, and per case (nDCG@10, rank of the first judged hit)."""
    cases = [c for c in load_cases(root / "eval" / f"{set_name}.jsonl") if c.answerable]
    per_slice: dict[str, list[float]] = {}
    per_case: dict[str, tuple[float, int | None]] = {}
    with SqliteStore.open(root, read_only=True) as store:
        for case in cases:
            judged = {relevant.anchor: relevant.grade for relevant in case.relevant}
            ranked = [
                hit.chunk.anchor
                for hit in store.search_chunks(" ".join(terms_of(case.query)), limit=200)
            ]
            value = ndcg_at_k(credit_judgments(ranked[:DEPTH], judged), judged, K)
            where = next(
                (
                    rank
                    for rank, anchor in enumerate(ranked, start=1)
                    if anchor in judged or section_of(anchor) in judged
                ),
                None,
            )
            per_case[case.case_id] = (value, where)
            for member in case.slices or ():
                per_slice.setdefault(member.value, []).append(value)
    return {n: sum(v) / len(v) for n, v in sorted(per_slice.items())}, per_case


def _corpus_size(root: Path) -> str:
    with SqliteStore.open(root, read_only=True) as store:
        counts = store.counts()
    return f"{counts['documents']} docs, {counts['chunks']} chunks"


def main() -> int:
    argv = sys.argv[1:]
    set_name = "release"
    positional: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--set" and index + 1 < len(argv):
            set_name = argv[index + 1].removesuffix(".jsonl")
            index += 2
            continue
        if token.startswith("--set="):
            set_name = token.split("=", 1)[1].removesuffix(".jsonl")
        elif not token.startswith("--"):
            positional.append(token)
        index += 1
    if not positional:
        print(__doc__)
        return 2
    ref = positional[0]
    here = Path(positional[1]) if len(positional) > 1 else ROOT

    staging = Path(tempfile.mkdtemp(prefix="mycelium-decay-"))
    before = staging / "before"
    try:
        _worktree(ref, before)
        # Today's judgments, so the *only* free variable is the corpus. Copying
        # them in is the whole method: a set that changed between the two refs
        # would make the comparison meaningless in exactly the way this tool
        # exists to avoid.
        for name in JUDGED_SETS:
            source = here / "eval" / name
            if source.exists():
                shutil.copy2(source, before / "eval" / name)

        print(f"compiling {ref} with today's compiler ...")
        build(before, config=load_config(before))
        print(f"compiling {here} ...")
        build(here, config=load_config(here))

        print(f"\nbefore  {ref}: {_corpus_size(before)}")
        print(f"after   {here.name or here}: {_corpus_size(here)}")

        old_slices, old_cases = _score(before, set_name)
        new_slices, new_cases = _score(here, set_name)

        print(f"\n{set_name}.jsonl, per slice — same judgments, same code, corpus varied\n")
        print(f"  {'slice':<16}{'before':>9}{'after':>9}{'delta':>10}")
        moved = []
        for name in sorted(set(old_slices) | set(new_slices)):
            was, now = old_slices.get(name, 0.0), new_slices.get(name, 0.0)
            delta = (now - was) / was if was else float("nan")
            print(f"  {name:<16}{was:9.4f}{now:9.4f}{delta:9.1%}")
            if was and delta < -0.02:
                moved.append(name)

        if not moved:
            print("\nNo slice regressed beyond -2 % on corpus growth alone.")
            return 0

        print(f"\nSlices that moved: {', '.join(moved)}. The cases behind them:\n")
        cases = load_cases(here / "eval" / f"{set_name}.jsonl")
        for case in cases:
            if not (moved_here := [s.value for s in case.slices or () if s.value in moved]):
                continue
            was, was_rank = old_cases.get(case.case_id, (0.0, None))
            now, now_rank = new_cases.get(case.case_id, (0.0, None))
            flag = "  <<< this one" if abs(now - was) > 1e-9 else ""
            print(f"  {case.case_id} [{','.join(moved_here)}] {case.query!r}")
            print(
                f"      nDCG@10 {was:.4f} -> {now:.4f}   first judged hit at "
                f"{was_rank} -> {now_rank}{flag}"
            )
        print(
            "\nA case whose score did not move is not the cause. A slice of one or two\n"
            "cases cannot distinguish a regression from a single case's luck — which is\n"
            "the finding ADR-0044 records, not a caveat about this tool."
        )
        return 0
    finally:
        _discard(before)
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
