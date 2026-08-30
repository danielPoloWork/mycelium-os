# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The retrievers an evaluation run compares (spec 04 §7.4, D-010).

Two of them, and the second one is the point.

**`mycelium`** is the product: field-weighted BM25 over the compiled snapshot.

**`grep`** is the incumbent. D-010 is blunt about this — the real competitor is not
another retriever, it is the agent's own ``grep``/``glob``/``read`` loop, and "if
Mycelium OS does not visibly beat grep on these tasks, the correct response is to
fix the product, not the benchmark." A baseline that exists only to lose proves
nothing, so this one is built to be fair: it sees the same corpus, extracts terms
the same way, returns the same anchor space, and ranks by the same signal a person
scanning matches would use — how many query terms a passage contains, then how
many times.

What it deliberately lacks is everything the compiler adds: field weighting, term
saturation, length normalisation, and the structure that makes an anchor mean
something. That gap is the product's claim, and this is where it gets measured.
"""

import re
from dataclasses import dataclass
from typing import Final, Protocol

from mycelium.config import RetrievalConfig
from mycelium.embedding import Embedder
from mycelium.retrieval import RRF_K, VECTOR_CANDIDATES
from mycelium.retrieval import search as run_search
from mycelium.store import SqliteStore

__all__ = [
    "GrepRetriever",
    "HybridRetriever",
    "MyceliumRetriever",
    "Retriever",
    "build_retriever",
    "resolvable_anchors",
    "terms_of",
]

_TERM: Final = re.compile(r"\w+", re.UNICODE)
_STOPWORDS: Final = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
    }
)
"""Words a grep user would not bother typing; removed for both retrievers alike."""


class Retriever(Protocol):
    """Anything an evaluation run can score."""

    @property
    def name(self) -> str:
        """How the run manifest identifies this retriever."""
        ...

    @property
    def config(self) -> dict[str, str | int | float | bool]:
        """What a run manifest must record to be reproducible."""
        ...

    def search(self, query: str, limit: int) -> list[str]:
        """Return anchors, best first."""
        ...


def terms_of(query: str) -> list[str]:
    """Extract query terms — shared, so neither retriever gets an easier question."""
    found = [term.lower() for term in _TERM.findall(query)]
    kept = [term for term in found if term not in _STOPWORDS]
    return kept or found


@dataclass(frozen=True, slots=True)
class MyceliumRetriever:
    """The product: field-weighted BM25 over the published snapshot."""

    store: SqliteStore
    name: str = "mycelium"

    @property
    def config(self) -> dict[str, str | int | float | bool]:
        return {
            "engine": "fts5-bm25",
            "weights": "title=3.0,heading_path=2.0,body=1.0",
            "hybrid": False,
        }

    def search(self, query: str, limit: int) -> list[str]:
        hits = self.store.search_chunks(" ".join(terms_of(query)), limit=limit)
        return [hit.chunk.anchor for hit in hits]


@dataclass(frozen=True, slots=True)
class GrepRetriever:
    """The incumbent: scan the corpus for query terms and read what matches."""

    store: SqliteStore
    name: str = "grep"

    @property
    def config(self) -> dict[str, str | int | float | bool]:
        return {
            "engine": "substring-scan",
            "ranking": "distinct-terms-then-occurrences",
            "case_sensitive": False,
        }

    def search(self, query: str, limit: int) -> list[str]:
        terms = terms_of(query)
        if not terms:
            return []
        patterns = [re.compile(rf"\b{re.escape(term)}", re.IGNORECASE) for term in terms]

        scored: list[tuple[int, int, str]] = []
        for anchor, text in self._corpus():
            counts = [len(pattern.findall(text)) for pattern in patterns]
            distinct = sum(1 for count in counts if count)
            if not distinct:
                continue
            # A person scanning grep output prefers passages mentioning more of
            # what they asked for, then passages mentioning it more often.
            scored.append((distinct, sum(counts), anchor))

        scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
        return [anchor for _, _, anchor in scored[:limit]]

    def _corpus(self) -> list[tuple[str, str]]:
        return [
            (chunk.anchor, chunk.text)
            for doc_id in self.store.document_ids()
            for chunk in self.store.chunks_of(doc_id)
        ]


@dataclass(frozen=True, slots=True)
class HybridRetriever:
    """The product with its vector leg on: BM25 ∥ vector, fused by RRF (D-009).

    Scored against :class:`MyceliumRetriever` rather than against grep, because
    that is the comparison gate G2 asks for: hybrid must beat *lexical* by ≥ 5 %
    nDCG@10 with no slice worse than −2 %, or the shipped default stays lexical
    and the README says so (spec 04 §7.3).
    """

    store: SqliteStore
    embedder: Embedder
    name: str = "hybrid"

    @property
    def config(self) -> dict[str, str | int | float | bool]:
        return {
            "engine": "fts5-bm25 + vector",
            "weights": "title=3.0,heading_path=2.0,body=1.0",
            "hybrid": True,
            "fusion": "rrf",
            "rrf_k": RRF_K,
            "vector_candidates": VECTOR_CANDIDATES,
            "model_id": self.embedder.model_id,
            "provider": self.embedder.provider,
        }

    def search(self, query: str, limit: int) -> list[str]:
        # The raw query, not `terms_of`: an embedder is asked a question in the
        # words it was trained on, and stripping stopwords from "what does the
        # project use for X" throws away the grammar the model reads. The lexical
        # leg inside `search` still tokenises as it always did.
        outcome = run_search(
            self.store,
            query,
            limit=limit,
            config=RetrievalConfig(profile="hybrid"),
            embedder=self.embedder,
        )
        return [fused.hit.chunk.anchor for fused in outcome.hits]


def build_retriever(name: str, store: SqliteStore, embedder: Embedder | None = None) -> Retriever:
    """Resolve a retriever by name, refusing anything unknown."""
    if name == "mycelium":
        return MyceliumRetriever(store=store)
    if name == "grep":
        return GrepRetriever(store=store)
    if name == "hybrid":
        if embedder is None:
            msg = (
                "the 'hybrid' retriever needs an embedder: install "
                "`mycelium-os[embeddings]`, make the model available, and build the "
                "snapshot with vectors"
            )
            raise ValueError(msg)
        return HybridRetriever(store=store, embedder=embedder)
    msg = f"unknown retriever {name!r}; expected 'mycelium', 'grep', or 'hybrid'"
    raise ValueError(msg)


def resolvable_anchors(store: SqliteStore) -> set[str]:
    """Every anchor the snapshot can serve — the denominator of gate G1."""
    return {chunk.anchor for doc_id in store.document_ids() for chunk in store.chunks_of(doc_id)}
