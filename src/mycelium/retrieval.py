# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Candidate generation and fusion (spec 04 §3, D-009, ADR-0017).

One entry point — :func:`search` — shared by the CLI, the MCP server, and the
evaluation harness, so the three cannot drift into answering the same question
differently. Before this module the query path *was* ``store.search_chunks``;
now the store offers candidate generators and this decides how they combine.

**Fusion is by rank, never by score.** BM25 returns unbounded relevance scores;
cosine similarity returns [-1, 1]. Adding them means inventing an exchange rate
between two units, and the exchange rate silently becomes a tuning parameter
nobody measured. Reciprocal Rank Fusion (spec 04 §3, k=60) reads only *positions*:
each list contributes ``1 / (k + rank)``, so a passage both legs rank highly wins,
and a passage only one leg knows about still places. Nothing needs normalising,
and adding the symbol and graph legs (3.4, 5.2) is one more rank list.

**Every result says how it got there.** A hit carries the legs that produced it
and its rank in each, which is what makes `--explain` an audit rather than a
story (spec 04 §2) and what let gate G2 be argued from data.

The v1 planner is deliberately absent: spec 04 §2's routing rules (identifier
queries to lexical, questions to hybrid) arrive with the symbol leg they route
to, at 3.4. Until then both legs run for every query, which is the honest
behaviour to measure hybrid against.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Final

from mycelium.config import RetrievalConfig
from mycelium.embedding import Embedder
from mycelium.store import SearchFilters, SearchHit, SqliteStore

__all__ = [
    "DEFAULT_LIMIT",
    "FusedHit",
    "SearchOutcome",
    "reciprocal_rank_fusion",
    "search",
]

DEFAULT_LIMIT: Final = 10
RRF_K: Final = 60
"""Fusion constant (spec 04 §3): each list contributes ``1 / (RRF_K + rank)``."""
VECTOR_CANDIDATES: Final = 50
"""Depth of the vector leg before fusion (spec 04 §3: "k=50 default")."""

_LEXICAL: Final = "lexical"
_VECTOR: Final = "vector"


@dataclass(frozen=True, slots=True)
class FusedHit:
    """One ranked chunk, and the evidence for its rank."""

    hit: SearchHit
    score: float
    """Fused RRF score. Comparable within one result set, meaningless across sets."""
    legs: tuple[str, ...]
    """Which candidate generators produced it, in fusion order."""
    ranks: dict[str, int]
    """1-based rank within each leg that produced it."""

    def explain(self) -> dict[str, object]:
        return {
            "score": round(self.score, 6),
            "legs": list(self.legs),
            "ranks": dict(sorted(self.ranks.items())),
        }


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    """The results, plus what the query path actually did to produce them."""

    hits: tuple[FusedHit, ...]
    legs: tuple[str, ...]
    """Generators that ran — a single-element tuple is a lexical-only search."""
    degraded: tuple[str, ...] = ()
    """Legs that were configured but could not run, with the reason attached."""
    notes: tuple[str, ...] = field(default=())
    timings_ms: dict[str, int] = field(default_factory=dict)
    """Per-stage wall time. `mycelium_explain` promises it (spec 05 §3.4), and a
    leg that has quietly become the slow one should be visible without a profiler."""

    def explain(self) -> dict[str, object]:
        return {
            "legs": list(self.legs),
            "degraded": list(self.degraded),
            "notes": list(self.notes),
            "timings_ms": dict(self.timings_ms),
        }


def reciprocal_rank_fusion(
    lists: Sequence[tuple[str, Sequence[SearchHit]]], *, k: int = 60, limit: int = DEFAULT_LIMIT
) -> tuple[FusedHit, ...]:
    """Fuse ranked lists by Reciprocal Rank Fusion (Cormack et al., spec 04 §3).

    `lists` is ``(leg name, hits best-first)``. Ties break on anchor so the same
    inputs always produce the same order — fusion must not become a source of
    non-determinism just because two passages scored alike.
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    hits: dict[str, SearchHit] = {}
    legs_of: dict[str, list[str]] = {}

    for leg, results in lists:
        for position, hit in enumerate(results, start=1):
            anchor = hit.chunk.anchor
            scores[anchor] = scores.get(anchor, 0.0) + 1.0 / (k + position)
            ranks.setdefault(anchor, {})[leg] = position
            legs_of.setdefault(anchor, []).append(leg)
            hits.setdefault(anchor, hit)

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        FusedHit(
            hit=hits[anchor],
            score=score,
            legs=tuple(legs_of[anchor]),
            ranks=ranks[anchor],
        )
        for anchor, score in ordered[:limit]
    )


def _serve_only(
    filters: SearchFilters | None, settings: RetrievalConfig
) -> tuple[SearchFilters | None, str | None]:
    """Narrow a caller's filters to what the configuration is willing to serve.

    The policy is applied *here*, at the one seam the CLI, the MCP server and the
    evaluation harness all pass through, rather than at each of them: a serving
    rule enforced by three callers is a rule enforced by whichever of them was
    updated last. It narrows and never widens, so a query that already asked for
    `verified` keeps asking for exactly that.

    Returns ``(None, note)`` when the caller asked for precisely what the policy
    refuses. That is not an error — the question is well formed and the answer is
    "nothing, and here is why" — so the note travels with an empty result rather
    than becoming an exception the CLI and the MCP server would each render
    differently (ADR-0024).
    """
    allowed = settings.served_statuses
    if allowed is None:
        return filters, None

    note = "candidate documents are not served (`[retrieval] include_candidate = false`)"
    asked = (filters.verification_statuses if filters else None) or allowed
    admissible = frozenset(asked) & allowed
    if not admissible:
        return None, note
    return replace(filters or SearchFilters(), verification_statuses=admissible), note


def search(
    store: SqliteStore,
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    filters: SearchFilters | None = None,
    config: RetrievalConfig | None = None,
    embedder: Embedder | None = None,
    prefix: bool = False,
) -> SearchOutcome:
    """Run the configured candidate generators and fuse them.

    Lexical always runs: it needs no model, no optional dependency, and no
    network, so it is the floor below which retrieval cannot fall. The vector
    leg joins when `config.hybrid` is on, an `embedder` is supplied, the store
    actually holds vectors for that model — and the lexical leg found at least
    one hit, because lexical evidence is the vector leg's precondition
    (ADR-0025): hybrid abstains wherever lexical abstains, instead of serving
    the nearest neighbours of a question the corpus cannot answer. When the
    embedder or the vectors are missing, the search *degrades to lexical and
    says so* rather than failing. A snapshot built before the embedder existed
    must still be searchable.

    Both legs are generated `vector_candidates` deep regardless of `limit`,
    because fusion needs depth to work with: fusing two top-10 lists throws away
    precisely the agreement that makes RRF worth doing.
    """
    settings = config or RetrievalConfig()
    filters, policy_note = _serve_only(filters, settings)
    if filters is None and policy_note is not None:
        return SearchOutcome(
            hits=(), legs=(), degraded=(), notes=(policy_note,), timings_ms={"total": 0}
        )

    depth = max(limit, VECTOR_CANDIDATES)
    timings: dict[str, int] = {}

    started = time.perf_counter()
    lexical = store.search_chunks(query, limit=depth, filters=filters, prefix=prefix)
    timings[_LEXICAL] = _elapsed_ms(started)
    lists: list[tuple[str, Sequence[SearchHit]]] = [(_LEXICAL, lexical)]
    degraded: list[str] = []
    notes: list[str] = [policy_note] if policy_note else []

    if settings.hybrid:
        if not lexical:
            # Lexical evidence is the vector leg's precondition (ADR-0025). A
            # vector leg asked for 50 candidates returns 50 for *any* query —
            # cosine similarity always produces a ranking — so without this,
            # hybrid answers questions the corpus cannot answer (ADR-0017 measured
            # 4 of 4). When not one query term occurs in the corpus, hybrid
            # abstains exactly where lexical abstains, by construction rather
            # than by a calibrated constant; the leg is *withheld*, so no
            # embedding latency is paid for a query that gets no answer.
            notes.append(
                "vector leg withheld: no lexical evidence for this query in the "
                "corpus, so hybrid abstains rather than serving nearest "
                "neighbours (ADR-0025)"
            )
        elif embedder is None:
            degraded.append(f"{_VECTOR}: no embedder configured")
        elif not store.vector_counts().get(embedder.model_id):
            degraded.append(
                f"{_VECTOR}: this snapshot holds no vectors for {embedder.model_id}; "
                "run `mycelium build` to embed it"
            )
        else:
            started = time.perf_counter()
            vector = embedder.embed_query(query)
            timings["embed_query"] = _elapsed_ms(started)

            started = time.perf_counter()
            lists.append(
                (
                    _VECTOR,
                    store.search_vectors(
                        vector, embedder.model_id, limit=VECTOR_CANDIDATES, filters=filters
                    ),
                )
            )
            timings[_VECTOR] = _elapsed_ms(started)
            notes.append(f"vector leg: {embedder.model_id} via {embedder.provider}")
    else:
        notes.append("hybrid disabled by configuration")

    started = time.perf_counter()
    fused = reciprocal_rank_fusion(lists, k=RRF_K, limit=limit)
    timings["fusion"] = _elapsed_ms(started)
    timings["total"] = sum(timings.values())

    return SearchOutcome(
        hits=fused,
        legs=tuple(leg for leg, _ in lists),
        degraded=tuple(degraded),
        notes=tuple(notes),
        timings_ms=timings,
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
