# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Retrieval metrics (spec 04 §7.2).

Recall@10, Recall@50, nDCG@10, MRR, and citation coverage. Standard definitions,
written out rather than imported, because a metric whose implementation nobody can
read is a number nobody should trust — and because the graded-relevance detail
(gain ``2^grade - 1``) is exactly where evaluation harnesses quietly differ.

**Two of these are not about ranking, and the second one is new.** Every metric
above ranks *chunks* — did the right passage come back, and how high. Citation
*coverage* asks instead whether the anchor resolves at all (gate G1), and citation
*precision* asks whether it names a place a reader can find (roadmap 6.7,
ADR-0122). A run can rank well and cite badly: an ingested PDF whose headings were
never recovered returns the right passage under the anchor ``#/7``, which is a
correct answer and a citation nobody can check without this tool.
"""

import math
from collections.abc import Mapping, Sequence, Set
from typing import Final

__all__ = [
    "SECTION_MARKER",
    "citation_coverage",
    "citation_precision",
    "cited_tokens",
    "credit_judgments",
    "dcg",
    "ndcg_at_k",
    "recall_at_k",
    "reciprocal_rank",
]


SECTION_MARKER: Final = "/"
"""A judged anchor ending here names a section, not a chunk (ADR-0029)."""


def section_of(anchor: str) -> str:
    """The section a chunk anchor belongs to, in judged-anchor form."""
    document, _, path = anchor.partition("#")
    return f"{document}#{path.rsplit('/', 1)[0]}/"


def credit_judgments(retrieved: Sequence[str], judged: Mapping[str, int]) -> list[str]:
    """Rewrite a retrieved list into the judgments it satisfies, each **once**.

    A judgment may name a chunk or a section (:data:`mycelium.sdk.types.JudgedAnchor`).
    A chunk judgment is satisfied by that chunk; a section judgment by any chunk
    under it. Everything else is passed through unchanged, so it scores zero the
    way an unjudged anchor always has.

    **Once** is the load-bearing word. A section split into twelve chunks would
    otherwise let a retriever fill the top ten with that one section and score a
    perfect run for finding a single thing. After the first match the rest of the
    section is neither rewarded nor punished — it lands in the ranking as any
    unjudged passage does, which is what it is.

    Chunk judgments are matched before section judgments, so a set that names both
    means what it wrote: the exact chunk, and its section as a weaker fallback.
    """
    seen: set[str] = set()
    credited: list[str] = []
    for anchor in retrieved:
        if anchor in judged and anchor not in seen:
            seen.add(anchor)
            credited.append(anchor)
            continue
        section = section_of(anchor)
        if section in judged and section not in seen:
            seen.add(section)
            credited.append(section)
            continue
        credited.append(anchor)
    return credited


def dcg(gains: Sequence[float]) -> float:
    """Discounted cumulative gain of an ordered gain list."""
    return sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))


def ndcg_at_k(retrieved: Sequence[str], judged: dict[str, int], k: int) -> float:
    """Normalised DCG at `k` with exponential gain, the IR default.

    Returns 0.0 when nothing is judged relevant: a case with no ground truth
    cannot be scored, and pretending otherwise (1.0 for "nothing to miss")
    would inflate every average that contains one.
    """
    if not judged:
        return 0.0
    gains = [(2 ** judged.get(anchor, 0)) - 1 for anchor in retrieved[:k]]
    ideal = sorted(judged.values(), reverse=True)[:k]
    best = dcg([(2**grade) - 1 for grade in ideal])
    return 0.0 if best == 0 else dcg(gains) / best


def recall_at_k(retrieved: Sequence[str], judged: dict[str, int], k: int) -> float:
    """Fraction of judged-relevant anchors present in the top `k`."""
    if not judged:
        return 0.0
    found = sum(1 for anchor in retrieved[:k] if anchor in judged)
    return found / len(judged)


def reciprocal_rank(retrieved: Sequence[str], judged: dict[str, int]) -> float:
    """1 / rank of the first relevant result, or 0.0 if none was returned."""
    for rank, anchor in enumerate(retrieved, start=1):
        if anchor in judged:
            return 1.0 / rank
    return 0.0


def citation_coverage(retrieved: Sequence[str], resolvable: set[str]) -> float:
    """Fraction of returned anchors that resolve in the snapshot (gate G1).

    Must be 1.00 every release, no exceptions: a citation that does not resolve is
    the one failure this product cannot tolerate. An empty result set is vacuously
    covered — abstention is measured separately.
    """
    if not retrieved:
        return 1.0
    return sum(1 for anchor in retrieved if anchor in resolvable) / len(retrieved)


def citation_precision(retrieved: Sequence[str], located: Set[str], k: int) -> float:
    """Fraction of the top-`k` citations that name where in the document they point.

    The companion to :func:`citation_coverage`, and the gap roadmap 6.7 was filed
    to close. Coverage asks whether an anchor *resolves* — gate G1, NFR-5 — and
    every other metric here ranks *chunks*. None of them asks whether the anchor a
    reader is handed **names the right thing**, which is the property an agent
    actually depends on when it cites evidence to a human who will check it.

    That gap decided roadmap 4.9 in the negative: docling's ML pipeline turns
    ``#/0`` into ``#platform-support/0`` for an ingested PDF — a real improvement
    to a citation, and invisible to every number this project could produce
    (ADR-0040). This is the number it was missing.

    **`located` comes from the snapshot, and must not be computed from the anchor
    string.** An anchor's two coordinates are different kinds of thing: a heading
    path is *semantic* — a reader finds `#platform-support` by searching the
    document for that heading — and an ordinal is *positional*, resolvable only by
    the tool that minted it and moved by any edit above it. But an anchor omits
    the document's single level-1 heading (ADR-0007), so a passage that sits under
    a real title and before the first `##` is spelled `docs/a.md#/0`, exactly like
    chunk 0 of a document with no headings whatsoever. The two are only
    distinguishable from the chunk record, which is why
    :func:`~mycelium.eval.retrievers.anchor_facts` supplies this set — and why
    the first draft of this metric, which parsed the anchor, called 193 of this
    repository's 1 461 chunks unstructured when one is (ADR-0122).

    **Computed over every returned anchor, not only the ones that answered.** The
    alternative — score the citations that satisfied a judgement — sounds more
    targeted and is worse in two ways. It couples a citation-quality number to
    ranking quality, so a retriever that ranks badly is measured on a handful of
    anchors and a retriever that ranks well on many; and comparing two arms then
    compares two different sample sizes. A reader is handed all `k`, so all `k`
    are scored (ADR-0122).

    **No judged input, and that is a finding rather than an omission.** Roadmap 6.7
    predicted this metric would need "a judged notion of the correct anchor
    granularity per case". It does not. Whether an anchor names a heading path is a
    fact about the anchor, readable without an opinion about the query — and
    ADR-0029's rule already answers the one question a judgement could add here: a
    judgement that names a *section* has declared that any chunk under it is an
    acceptable answer, so citing one chunk of a judged section is not a citation
    failure by the judge's own standard. Adding a subjective input to a decidable
    question would have made the measurement weaker, not stronger (ADR-0122).

    An empty result set is vacuously precise, the same convention
    :func:`citation_coverage` uses and for the same reason: abstention is measured
    separately, and a run that returned nothing has no citation to fault.
    """
    head = retrieved[:k]
    if not head:
        return 1.0
    return sum(1 for anchor in head if anchor in located) / len(head)


def cited_tokens(retrieved: Sequence[str], tokens: Mapping[str, int], k: int) -> int:
    """Mean size, in tokens, of the passages the top-`k` citations point at.

    The diagnostic that makes :func:`citation_precision` readable, because the two
    move independently and a citation is imprecise in both directions. A located
    anchor pointing at 700 tokens still asks a reader to scan a page to check one
    sentence; an unlocated anchor pointing at 60 asks them to find it first.

    ADR-0039 and ADR-0040 already found this quantity deciding results and treated
    it as a confound: a text-layer PDF arm's page-sized chunks scored *well* on
    rank because a large chunk catches the answer more often, while its citations
    were the worst in the corpus. Reported beside the precision, the confound
    becomes a reading.

    A mean rather than a median because every other summary here is a mean and
    means compose across cases; the outlier it is sensitive to is exactly the
    oversized chunk worth seeing. Anchors the map does not know are skipped — with
    coverage gated at 1.00 there are none, and a run that has lost that has a
    louder failure to report.
    """
    sizes = [tokens[anchor] for anchor in retrieved[:k] if anchor in tokens]
    return round(sum(sizes) / len(sizes)) if sizes else 0
