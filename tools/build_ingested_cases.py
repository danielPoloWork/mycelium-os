#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Carry the second corpus's frozen judgements across to its ingested twin.

    python tools/build_ingested_cases.py

Writes `eval/corpora/uv-docs-ingested/eval/{dev,release}.jsonl`.

**Nothing here is judged.** Every query, every grade and every slice is copied
verbatim from `eval/corpora/uv-docs/eval/*.jsonl`, which were frozen before this
corpus existed and cannot have been fitted to it. What this tool computes is the
*anchor*: where, in the document projected from a rendered copy of the same file,
the passage the judgement already picked ended up.

That matters more than it sounds. Re-judging the ingested corpus by hand would
answer a different question — "can I find passages in these documents" — and it
would be answered by the same agent that wrote the parsers, which is the trap
ADR-0027 exists to name. Deriving the anchor mechanically keeps the judgement
fixed and lets the *retrieval* be the only thing that varies.

## How an anchor is carried across

1. `provenance.json` says which evidence document a source document became.
2. The judged anchor's text is read out of the Markdown corpus's own store — a
   chunk, or the concatenation of a section's chunks.
3. Every chunk of the twin document is scored by **coverage**: what fraction of
   the judged text's word tokens the candidate contains. The best-covered chunk
   wins.
4. Below `MIN_COVERAGE` nothing wins. The anchor is dropped, the case is reported,
   and if a case loses every anchor it is dropped whole — because a case whose
   answer is not in the corpus is not a hard case, it is a broken one.

Coverage rather than F1 on purpose: an ingested chunk is often *larger* than the
Markdown chunk it corresponds to (a PDF page holds several sections), and
penalising it for that would measure the chunker, not the projection.

Every dropped anchor is printed. A silent drop would quietly make the ingested
corpus easier than its twin, which is the one way this comparison could lie.
"""

import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import load_cases, validate_judged_set, write_cases  # noqa: E402
from mycelium.sdk.types import Chunk, EvalCase, RelevantAnchor  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

MARKDOWN_CORPUS = ROOT / "eval" / "corpora" / "uv-docs"
INGESTED_CORPUS = ROOT / "eval" / "corpora" / "uv-docs-ingested"

MIN_COVERAGE = 0.5
"""Half the judged passage's words have to be in the candidate chunk.

Not a tuned constant — a floor below which "the same passage" stops being a
defensible claim. Every mapping's actual coverage is printed, so a reviewer can
see how far above it the real ones sit rather than trusting the number.
"""

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def coverage(judged: Sequence[str], candidate: Sequence[str]) -> float:
    """The fraction of the judged passage's distinct words present in `candidate`."""
    wanted = set(judged)
    if not wanted:
        return 0.0
    return len(wanted & set(candidate)) / len(wanted)


def chunks_of_path(store: SqliteStore, doc_path: str) -> tuple[Chunk, ...]:
    """Every chunk of the document at `doc_path`, in document order."""
    document = store.get_document_by_path(doc_path)
    return () if document is None else store.chunks_of(document.doc_id)


def judged_text(store: SqliteStore, anchor: str) -> str:
    """The text a judgement points at: one chunk, or a whole section."""
    if not anchor.endswith("/"):
        chunk = store.get_chunk(anchor)
        return chunk.text if chunk is not None else ""
    doc_path, _, prefix = anchor.partition("#")
    return "\n".join(
        chunk.text
        for chunk in chunks_of_path(store, doc_path)
        if chunk.anchor.partition("#")[2].startswith(prefix)
    )


def main() -> int:  # noqa: C901 - a report is a sequence of stated steps
    manifest_path = INGESTED_CORPUS / "provenance.json"
    if not manifest_path.is_file():
        print(f"missing {manifest_path}; run tools/build_ingested_corpus.py first")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    build(MARKDOWN_CORPUS)
    build(INGESTED_CORPUS)

    dropped_anchors: list[str] = []
    dropped_cases: list[str] = []
    mapped: list[tuple[str, str, float]] = []

    with (
        SqliteStore.open(MARKDOWN_CORPUS, read_only=True) as source_store,
        SqliteStore.open(INGESTED_CORPUS, read_only=True) as twin_store,
    ):
        written: dict[str, tuple[EvalCase, ...]] = {}
        for name in ("dev", "release"):
            carried: list[EvalCase] = []
            for case in load_cases(MARKDOWN_CORPUS / "eval" / f"{name}.jsonl"):
                anchors: list[RelevantAnchor] = []
                for relevant in case.relevant:
                    doc_path = relevant.anchor.partition("#")[0]
                    entry = manifest.get(doc_path)
                    if entry is None:
                        dropped_anchors.append(f"{case.case_id}: {relevant.anchor} — no twin")
                        continue
                    wanted = tokens(judged_text(source_store, relevant.anchor))
                    best, score = None, 0.0
                    for chunk in chunks_of_path(twin_store, entry["evidence"]):
                        found = coverage(wanted, tokens(chunk.text))
                        if found > score:
                            best, score = chunk.anchor, found
                    if best is None or score < MIN_COVERAGE:
                        dropped_anchors.append(
                            f"{case.case_id}: {relevant.anchor} — best coverage {score:.2f}"
                        )
                        continue
                    mapped.append((relevant.anchor, best, score))
                    anchors.append(RelevantAnchor(anchor=best, grade=relevant.grade))

                if case.answerable and not anchors:
                    dropped_cases.append(case.case_id)
                    continue
                carried.append(case.model_copy(update={"relevant": tuple(anchors)}))
            written[name] = tuple(carried)

        errors, warnings = validate_judged_set(written["dev"] + written["release"], twin_store)

    for anchor, best, score in mapped:
        print(f"  {score:.2f}  {anchor}  ->  {best}")
    for line in dropped_anchors:
        print(f"  dropped anchor  {line}")
    for case_id in dropped_cases:
        print(f"  dropped case    {case_id} — no anchor survived")
    for warning in warnings:
        print(f"  warning: {warning}")
    if errors:
        print("The carried set does not hold against the ingested corpus:")
        for error in errors:
            print(f"  {error}")
        return 1

    destination = INGESTED_CORPUS / "eval"
    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", written["dev"])
    write_cases(destination / "release.jsonl", written["release"])
    print(
        f"carried {len(written['dev'])} dev and {len(written['release'])} release cases; "
        f"{len(mapped)} anchors mapped, {len(dropped_anchors)} dropped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
