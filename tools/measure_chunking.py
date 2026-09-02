#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Measure what packing atomic blocks costs and buys (roadmap 4.11, ADR-0042).

    python tools/measure_chunking.py [repository-root]

Roadmap 4.8 refused ten re-rankings and left one hypothesis standing: the unit
BM25 scores is wrong before ranking ever sees it. This measures the change to
that unit — letting a table or code block share a chunk with the prose around it
instead of standing alone — on three axes, because a chunking change is only
partly a retrieval question:

**Shape.** The size distribution before and after. The diagnosis in ADR-0031 was
"chunks of wildly different sizes", so the first thing to check is whether the
change makes them comparable.

**Retrieval.** nDCG@10 / MRR / R@10 on the **dev** sets, which is what tuning may
read (spec 04 §7.1). The release view is printed too, because gate G3 decides
whether this ships — but see the third axis before believing it.

**Judged-anchor survival.** This is the axis a re-ranking never had. Chunk
boundaries carry ordinals, so merging two chunks *deletes an anchor*: a judgment
naming `#section/2` in a section that now has one chunk scores zero however good
the retrieval is. Those cases are not measuring the change, and a number that
mixes them with the ones that are is worse than no number. So they are counted
and named, and re-judging them is a separate change by construction
(`tools/check_frozen_release_sets.py` enforces it).
"""

import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.chunking import ChunkingPolicy, chunk_document  # noqa: E402
from mycelium.config import load_config  # noqa: E402
from mycelium.corpus import CorpusScope, discover  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import (  # noqa: E402
    credit_judgments,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mycelium.eval.retrievers import terms_of  # noqa: E402
from mycelium.markdown.adapter import parse_markdown  # noqa: E402
from mycelium.sdk.types import Chunk  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

K = 10
DEPTH = 50


@dataclass(frozen=True, slots=True)
class Corpus:
    label: str
    root: Path


def corpora(ours: Path) -> list[Corpus]:
    return [
        Corpus("ours", ours),
        Corpus("uv", ROOT / "eval" / "corpora" / "uv-docs"),
    ]


# ---------------------------------------------------------------------------
# Re-chunk a corpus from source, without building a store
# ---------------------------------------------------------------------------


def rechunk(root: Path, *, pack_atomic: bool) -> dict[str, tuple[Chunk, ...]]:
    """Every document's chunks under `pack_atomic`, keyed by repository path.

    Read from the Markdown rather than from the store on purpose: the question is
    what the chunker *would* produce, and a store holds what it did produce.
    """
    config = load_config(root)
    policy = ChunkingPolicy(
        target_tokens=config.chunking.target_tokens or config.chunking.max_tokens,
        max_tokens=config.chunking.max_tokens,
        pack_atomic=pack_atomic,
    )
    scope = CorpusScope.of(config.project)
    out: dict[str, tuple[Chunk, ...]] = {}
    for path in discover(root, scope):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            document = parse_markdown(text)
        except Exception as error:  # noqa: BLE001 - a corpus may carry a quarantined file
            print(f"  ! {relative}: {error}", file=sys.stderr)
            continue
        out[relative] = chunk_document(document.kir, doc_path=relative, policy=policy)
    return out


def shape(chunked: dict[str, tuple[Chunk, ...]]) -> dict[str, float]:
    sizes = sorted(chunk.tokens for chunks in chunked.values() for chunk in chunks)
    if not sizes:  # pragma: no cover - a corpus always has chunks
        return {}
    return {
        "chunks": len(sizes),
        "median": statistics.median(sizes),
        "p10": sizes[len(sizes) // 10],
        "p90": sizes[int(len(sizes) * 0.9)],
        "under25": sum(1 for size in sizes if size < 25) / len(sizes),
        "spread": sizes[int(len(sizes) * 0.9)] / max(1, sizes[len(sizes) // 10]),
    }


# ---------------------------------------------------------------------------
# Judged-anchor survival — the axis a re-ranking never had
# ---------------------------------------------------------------------------


def anchors_of(chunked: dict[str, tuple[Chunk, ...]]) -> set[str]:
    return {chunk.anchor for chunks in chunked.values() for chunk in chunks}


def survival(root: Path, set_name: str, after: set[str]) -> tuple[int, int, list[str]]:
    """How many of a set's judged anchors still name a chunk after the change.

    A section-scoped judgment (`doc#sec/`, ADR-0029) survives any boundary change
    — that is the durability argument, now load-bearing. A chunk-exact one
    survives only if its ordinal still exists.
    """
    cases = [case for case in load_cases(root / "eval" / f"{set_name}.jsonl") if case.answerable]
    total = 0
    kept = 0
    broken: list[str] = []
    for case in cases:
        case_broken = False
        for relevant in case.relevant:
            total += 1
            anchor = str(relevant.anchor)
            if _is_section(anchor) or anchor in after:
                kept += 1
            else:
                case_broken = True
        if case_broken:
            broken.append(case.case_id)
    return kept, total, broken


def _is_section(anchor: str) -> bool:
    return anchor.endswith("/")


# ---------------------------------------------------------------------------
# Retrieval, over a store the change has been applied to
# ---------------------------------------------------------------------------


def retrieval(root: Path, set_name: str, *, only: Sequence[str] | None = None) -> dict[str, float]:
    """Score a published store's lexical leg, optionally over named cases only."""
    cases = [case for case in load_cases(root / "eval" / f"{set_name}.jsonl") if case.answerable]
    if only is not None:
        allowed = set(only)
        cases = [case for case in cases if case.case_id in allowed]
    if not cases:
        return {}
    totals = [0.0, 0.0, 0.0]
    with SqliteStore.open(root, read_only=True) as store:
        for case in cases:
            judged = {str(relevant.anchor): relevant.grade for relevant in case.relevant}
            hits = store.search_chunks(" ".join(terms_of(case.query)), limit=DEPTH)
            credited = credit_judgments([hit.chunk.anchor for hit in hits], judged)
            totals[0] += ndcg_at_k(credited, judged, K)
            totals[1] += reciprocal_rank(credited, judged)
            totals[2] += recall_at_k(credited, judged, K)
    count = len(cases)
    return {
        "cases": count,
        "ndcg": totals[0] / count,
        "mrr": totals[1] / count,
        "r10": totals[2] / count,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    ours = Path(args[0]) if args else ROOT

    print("=== shape: what the unit looks like before and after ===\n")
    print(
        f"{'corpus':<8} {'packing':<10} {'chunks':>7} {'median':>7} {'p10':>5} {'p90':>6} "
        f"{'<25t':>6} {'p90/p10':>8}"
    )
    changed: dict[str, tuple[set[str], set[str]]] = {}
    for corpus in corpora(ours):
        before = rechunk(corpus.root, pack_atomic=False)
        after = rechunk(corpus.root, pack_atomic=True)
        changed[corpus.label] = (anchors_of(before), anchors_of(after))
        for name, chunked in (("atomic", before), ("packed", after)):
            row = shape(chunked)
            print(
                f"{corpus.label:<8} {name:<10} {row['chunks']:7.0f} {row['median']:7.0f} "
                f"{row['p10']:5.0f} {row['p90']:6.0f} {row['under25']:6.1%} {row['spread']:8.1f}"
            )

    print("\n=== judged-anchor survival: which cases still measure the change ===\n")
    print(f"{'set':<14} {'anchors kept':>13} {'broken cases'}")
    comparable: dict[tuple[str, str], list[str]] = {}
    for corpus in corpora(ours):
        after = changed[corpus.label][1]
        for set_name in ("dev", "release"):
            kept, total, broken = survival(corpus.root, set_name, after)
            cases = [
                case.case_id
                for case in load_cases(corpus.root / "eval" / f"{set_name}.jsonl")
                if case.answerable and case.case_id not in broken
            ]
            comparable[(corpus.label, set_name)] = cases
            label = f"{corpus.label}/{set_name}"
            print(
                f"{label:<14} {kept:>6}/{total:<6} "
                f"{', '.join(broken) if broken else '(none - every judgment survives)'}"
            )

    print(
        "\nA broken case scores zero on retrieval quality it may not deserve, so the"
        "\nretrieval table below is printed twice: over every case, and over the"
        "\ncomparable ones only. Re-judging them is a separate change by construction."
    )
    print(
        "\n=== retrieval: run this after `mycelium build` on each corpus, once per"
        "\n    setting, because it reads the published store ===\n"
    )
    print(f"{'set':<14} {'cases':>6} {'nDCG@10':>8} {'MRR':>7} {'R@10':>7}")
    for corpus in corpora(ours):
        for set_name in ("dev", "release"):
            for scope, only in (
                ("all", None),
                ("comparable", comparable[(corpus.label, set_name)]),
            ):
                row = retrieval(corpus.root, set_name, only=only)
                if not row:
                    continue
                label = f"{corpus.label}/{set_name}"
                print(
                    f"{label:<14} {row['cases']:6.0f} {row['ndcg']:8.3f} {row['mrr']:7.3f} "
                    f"{row['r10']:7.3f}  {scope}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
