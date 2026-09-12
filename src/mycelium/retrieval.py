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
and the graph leg (roadmap 5.3) and the symbol leg (5.9) are each one more rank
list.

**The graph leg proposes documents; BM25 disposes of chunks.** Expansion walks
one hop from the fused seeds over the typed edges and returns *nodes* — sections,
documents, symbols — which are not candidates, because a candidate is a chunk and
chunk boundaries are a packing decision the graph refuses to key on (ADR-0018).
So the node set is resolved back to its chunks and those are ranked against the
query by the same BM25 the lexical leg uses. A proposed node whose chunks contain
none of the query's words contributes nothing (ADR-0075).

**The symbol leg looks a name up and offers where it is defined.** Spec 04 §3
asks for an *exact* lookup in the `symbols` table for the query's
identifier-like tokens, and the chunks behind a symbol are its `doc_refs` — the
places that define it (ADR-0073). Since roadmap 5.23 a command-shaped query —
`uv tool install`, `uv lock --check` — is looked up the same way in the `cli`
language, whose symbols are the commands the corpus demonstrates at a prompt
and names in prose (ADR-0094). Like the graph leg it may add and may not
promote, and like the graph leg it is off by default, because its ablation lost
too: on these three corpora it cannot fire on one judged `symbol` case, and
where it does fire the definition site is a *naming* site rather than a
documenting one (ADR-0080).

**Every result says how it got there.** A hit carries the legs that produced it
and its rank in each, which is what makes `--explain` an audit rather than a
story (spec 04 §2) and what let gate G2 be argued from data.

**The plan decides whether a query needs a leg; the configuration decides
whether it may have one.** :mod:`mycelium.planner` classifies the query against
spec 04 §2's table and asks for generators; this module runs a derived leg only
when the configuration enables it *and* the plan asks for it. The plan can only
narrow — a regex must not be able to overturn a verdict three gates decided
(ADR-0083). The graph and symbol legs are routed; the vector leg is not, because
withholding it from identifier queries was measured and is worse.
"""

import re
import time
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field, replace
from typing import Final

from mycelium.config import RetrievalConfig
from mycelium.embedding import Embedder
from mycelium.graph import nodes_of_anchor, split_section_ref
from mycelium.planner import (
    GRAPH,
    LEXICAL,
    RELATIONSHIP_PHRASES,
    STOPWORDS,
    SYMBOL,
    VECTOR,
    Plan,
    plan_query,
)
from mycelium.sdk.identity import digest_json
from mycelium.sdk.types import Sha256Digest
from mycelium.store import (
    STEM_WEIGHT,
    SearchFilters,
    SearchHit,
    SqliteStore,
    TermHits,
    field_weights,
    fts_schema,
)
from mycelium.symbols import (
    CLI_LANGUAGE,
    DOC_LANGUAGE,
    GRAMMARS,
    MAX_COMMAND_WORDS,
    command_phrase,
    identifier_like,
)

__all__ = [
    "DEFAULT_LIMIT",
    "GRAPH_DISCOUNT",
    "GRAPH_NODES",
    "GRAPH_SEEDS",
    "RRF_K",
    "STOPWORDS",
    "SYMBOL_CANDIDATES",
    "SYMBOL_DISCOUNT",
    "SYMBOL_LANGUAGES",
    "SYMBOL_PROMOTE",
    "SYMBOL_PROMOTE_LANGUAGES",
    "VECTOR_CANDIDATES",
    "FusedHit",
    "Plan",
    "SearchOutcome",
    "query_terms",
    "reciprocal_rank_fusion",
    "retrieval_identity",
    "search",
    "symbol_lookup_ids",
]

DEFAULT_LIMIT: Final = 10
RRF_K: Final = 60
"""Fusion constant (spec 04 §3): each list contributes ``1 / (RRF_K + rank)``."""
VECTOR_CANDIDATES: Final = 50
"""Depth of the vector leg before fusion (spec 04 §3: "k=50 default")."""

GRAPH_SEEDS: Final = 10
"""How many fused candidates open a door. Spec 04 §5 says "top-k fused
candidates" without fixing k; 10 is the served window, and the measurement that
sized it found rescuing seeds at ranks 1, 2, 3, 4, 5, 7 and 8 — a smaller budget
would have thrown four of nine rescues away (ADR-0075)."""

GRAPH_NODES: Final = 10
"""Spec 04 §5's node budget, applied twice: at most this many neighbour nodes are
carried past the walk, and at most this many chunks leave the leg."""

GRAPH_DISCOUNT: Final = 0.9
"""What a graph-proposed candidate contributes, against 1.0 for a directly
retrieved one — spec 04 §5's discount.

**The admissible range is derived; the value inside it is a choice, and the
difference is stated rather than blurred.** RRF at k=60 is deliberately flat: a
list's rank 1 contributes ``1/61`` and its rank 50 ``1/110``, less than a factor
of two across the whole leg. Two bounds follow, for a served window of ten:

- a passage with *only* graph evidence must not outrank one the lexical leg
  ranked first, so ``d/61 < 1/61`` — that is, ``d < 1``;
- and it must be able to displace the weakest passage in the window, or the leg
  cannot change an answer at all and the ablation would be measuring nothing:
  ``d/61 > 1/70``, that is ``d > 0.871``.

So the mechanism spec 04 §5 prescribes has an operating window of roughly
``0.87 < d < 1`` and no more. Anything at or below the coarse "half as good"
reading of *discount* is arithmetically inert — ``0.5/61 < 1/110`` puts the
leg's best candidate below the lexical leg's worst — which is a fact about RRF
worth knowing before choosing a number. **0.9** is a round value inside the
derived window; it lets the leg's first two or three proposals reach a ten-deep
result and no more. It is not the product of a sweep, and ADR-0075 records the
one ablation run at it rather than the best of several."""

SYMBOL_CANDIDATES: Final = 10
"""How many definition sites leave the symbol leg.

The same budget the graph leg spends on nodes, for the same reason: a leg deeper
than the served window can only rearrange the window's tail. In practice the
lookup returns one or two chunks — a symbol's `doc_refs` holds the chunks that
define it, and a name is normally defined once."""

SYMBOL_DISCOUNT: Final = 0.9
"""What a symbol-proposed candidate contributes, against 1.0 for a directly
retrieved one.

Not re-derived here: ADR-0075 worked out that RRF at k=60 leaves any added leg
an operating window of roughly ``0.87 < d < 1`` for a served window of ten —
below it the leg's best candidate cannot displace the window's weakest and
results are byte-identical, at 1.0 it ties the lexical leg's own first choice.
0.9 is the same round value inside that window the graph leg uses, and using a
*different* number for this leg would be a second unmeasured constant with no
argument behind it."""

SYMBOL_PROMOTE: Final = False
"""Whether the leg may re-rank a passage another leg already returned.

``False`` is ADR-0075's load-bearing rule — *a leg adds; it never promotes* —
and it is the rule that keeps RRF from paying a passage twice for one piece of
evidence. It is a named constant rather than a hard-coded `if` because spec 04
§2's own words are *"symbol lookup **first**"*, which reads as a licence to
promote, and the two readings needed measuring rather than arguing about: the
runner flips this to score the other arm. Both readings lose, for different
reasons, and ADR-0080 reports each."""

SYMBOL_PROMOTE_LANGUAGES: Final[tuple[str, ...]] = ("cli",)
"""Languages whose definition sites the leg offers *whether or not* another leg
already returned them — promotion by language, where :data:`SYMBOL_PROMOTE` is
promotion for all.

`cli` and only `cli` (roadmap 5.23, ADR-0094). A command's sites are the
sections that run it at a prompt or name it as code — the documentation of the
command — where a filename's sites are the headings that spell it (ADR-0091),
which is why promoting `doc` terms cost 1.1 % overall at ADR-0080 and promoting
commands cost nothing: measured on all six sets, add-only is byte-identical to
the lexical ranking, promotion for `cli` clears the slice bar on both dev sets
(+7.7 % and +16.2 %, overall +1.3 % and +2.5 %) and is identical on both
release sets and on this repository's own. That is *proposable*, not *earned*
— a default needs a held-out gain — so the leg still ships off, and an operator
who turns it on gets this reading rather than the inert one. Part of
:func:`retrieval_identity` because it decides a ranking whenever the flag is
on."""

_LEXICAL: Final = LEXICAL
_VECTOR: Final = VECTOR
_GRAPH: Final = GRAPH
_SYMBOL: Final = SYMBOL
"""The leg names, imported from the planner rather than restated.

A plan asks for generators by name and this module runs them by name; two
spellings of one vocabulary is how a router comes to route to a leg that does not
exist (ADR-0083)."""

_TERM: Final = re.compile(r"\w+", re.UNICODE)

_QUERY_TOKEN: Final = re.compile(r"[A-Za-z0-9_./:+-]+")
"""How the symbol leg cuts a query into candidate names.

Deliberately *not* :data:`_TERM`, which is the lexical leg's word boundary and
splits `uv.lock` into `uv` and `lock` — the two halves of a name are not the
name, and a leg asked for exact matches must see the token an author wrote."""

SYMBOL_LANGUAGES: Final = tuple(sorted({grammar.language for grammar in GRAMMARS} | {DOC_LANGUAGE}))
"""The `<language>` segments a bare query token might name (spec 03 §2).

A query says `RetryPolicy`, not `sym:python:RetryPolicy`, so the lookup composes
one candidate id per language and asks for all of them at once. Derived from the
grammar registry rather than listed, so a grammar added to
:mod:`mycelium.symbols.code` is searchable without a second edit here."""


def retrieval_identity() -> Sha256Digest:
    """Digest everything that decides a ranking, so a measurement can date itself.

    Gate G2 is a *comparison* of the vector-fused ranking against the lexical one,
    and its verdict is only about the product for as long as both arms are the
    ones that ship. They were not: the verdict recorded at ADR-0017 was carried as
    prose for three milestones while the lexical leg moved four times underneath
    it — chunk packing (roadmap 4.15), stemming (4.19), function-word stripping
    (4.28) and the heading split (4.36) — and nothing anywhere could notice,
    because nothing recorded what the verdict had been measured *under*
    (ADR-0064, roadmap 4.40).

    This is that record. Every field is read from the module that owns it, at call
    time, so the digest cannot agree with a configuration that has changed:

    - the BM25 field weights and the stem weight — the ranking's own arithmetic;
    - the stopword *membership*, not its size: swapping one word for another
      changes what the lexical leg searches on and leaves a count identical;
    - the fusion constants, which decide what the vector leg contributes;
    - the `chunks_fts` statement itself, because a change to the indexed
      columns, their order, the tokenizer or the prefix settings is a change to
      what BM25 can see. The *statement*, not the store's schema version: that
      version moves for every table, so adding one no query reads used to stale
      a retrieval verdict and hand someone a re-record only the embedding model
      could complete (roadmap 5.12, ADR-0084);
    - the graph leg's and the symbol leg's constants, which decide a ranking
      whenever their flags are on;
    - the planner's relationship phrasings, which decide *whether* the graph leg
      runs on a given query and are therefore part of the ranking exactly as the
      leg's own constants are (roadmap 5.11). The membership, again, rather than
      the count.

    Each of the four changes above moves at least one of them, which is the check
    that this fingerprint is a fingerprint rather than a decoration. What it
    cannot see is a knob nobody added here — no digest can — so a new ranking
    parameter belongs in this dict in the same commit that introduces it.

    Deliberately *not* included: the shipped `[retrieval] profile`,
    `[retrieval] graph_expansion` and `[retrieval] symbol_lookup`. A default flip
    and a stale measurement are different mistakes with different remedies, so
    they are reported separately rather than folded into one digest. The two
    derived legs' *constants* are here, because they decide a ranking whenever
    their flag is on and a verdict measured under one set of them is not about
    another.
    """
    return digest_json(
        {
            "fts_schema": fts_schema(),
            "field_weights": field_weights(),
            "fusion": {"rrf_k": RRF_K, "vector_candidates": VECTOR_CANDIDATES},
            "graph": {
                "seeds": GRAPH_SEEDS,
                "nodes": GRAPH_NODES,
                "discount": GRAPH_DISCOUNT,
            },
            "symbol": {
                "candidates": SYMBOL_CANDIDATES,
                "discount": SYMBOL_DISCOUNT,
                "promote": SYMBOL_PROMOTE,
                "promote_languages": list(SYMBOL_PROMOTE_LANGUAGES),
                "languages": list(SYMBOL_LANGUAGES),
                "command_words": MAX_COMMAND_WORDS,
            },
            "routing": {"relationship_phrases": sorted(RELATIONSHIP_PHRASES)},
            "stem_weight": STEM_WEIGHT,
            "stopwords": sorted(STOPWORDS),
        }
    )


def query_terms(query: str) -> list[str]:
    """The words the lexical leg searches on, in the order they were written.

    A query made *entirely* of function words keeps them all: "what is it" has
    no content words to fall back on, and searching for nothing would abstain on
    a question the corpus may well answer. Removing every term is never an
    improvement over searching badly.
    """
    found = [term.lower() for term in _TERM.findall(query)]
    kept = [term for term in found if term not in STOPWORDS]
    return kept or found


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
    via_edge: str = ""
    """How graph expansion reached this passage, when it did (spec 04 §5).

    ``"<edge type> from <seed anchor>"`` — the label spec 04 §5 requires, and the
    only part of a result whose provenance is a *derivation* rather than a match.
    Empty for everything the lexical or vector legs found directly."""

    via_symbol: str = ""
    """Which symbol's definition site this passage is, when the symbol leg
    offered it (roadmap 5.9).

    ``"defines <symbol id>"``. The counterpart of `via_edge` for the other
    derived leg: a passage here was chosen because it *defines a name the query
    used*, not because it matched the query's words, and a reader deciding
    whether to trust a result should be able to see the difference."""

    def explain(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "score": round(self.score, 6),
            "legs": list(self.legs),
            "ranks": dict(sorted(self.ranks.items())),
        }
        if self.via_edge:
            detail["via_edge"] = self.via_edge
        if self.via_symbol:
            detail["via_symbol"] = self.via_symbol
        return detail


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    """The results, plus what the query path actually did to produce them."""

    hits: tuple[FusedHit, ...]
    legs: tuple[str, ...]
    """Generators that ran — a single-element tuple is a lexical-only search."""
    plan: Plan = field(default_factory=lambda: plan_query(""))
    """What spec 04 §2's rule set made of the query, and which rules matched.

    Reported rather than inferred: `legs` says what ran, and the difference
    between what the plan asked for and what ran is a configuration decision the
    reader is entitled to see (ADR-0083)."""
    degraded: tuple[str, ...] = ()
    """Legs that were configured but could not run, with the reason attached."""
    notes: tuple[str, ...] = field(default=())
    timings_ms: dict[str, int] = field(default_factory=dict)
    """Per-stage wall time. `mycelium_explain` promises it (spec 05 §3.4), and a
    leg that has quietly become the slow one should be visible without a profiler."""
    terms: tuple[TermHits, ...] = ()
    """What each query word reached in the lexical index — empty unless asked for.

    Ranking is silent about what it did *not* find, so a query carried by one of
    its five words looks exactly like a query carried by all five (roadmap 4.21,
    ADR-0044). This is that silence, ended. Populated only when `search` is
    called with `explain=True`, because it costs two index queries per term."""

    def explain(self) -> dict[str, object]:
        return {
            "plan": self.plan.as_dict(),
            "legs": list(self.legs),
            "degraded": list(self.degraded),
            "notes": list(self.notes),
            "timings_ms": dict(self.timings_ms),
            "terms": [item.as_dict() for item in self.terms],
        }

    @property
    def dead_terms(self) -> tuple[TermHits, ...]:
        """Query words this corpus contains in no form at all."""
        return tuple(item for item in self.terms if item.unmatched)


def reciprocal_rank_fusion(
    lists: Sequence[tuple[str, Sequence[SearchHit]]],
    *,
    k: int = 60,
    limit: int = DEFAULT_LIMIT,
    weights: Mapping[str, float] | None = None,
) -> tuple[FusedHit, ...]:
    """Fuse ranked lists by Reciprocal Rank Fusion (Cormack et al., spec 04 §3).

    `lists` is ``(leg name, hits best-first)``. Ties break on anchor so the same
    inputs always produce the same order — fusion must not become a source of
    non-determinism just because two passages scored alike.

    `weights` scales a named leg's contribution; an unnamed leg contributes 1.0.
    It exists for the discount spec 04 §5 asks of the graph leg, and
    :data:`GRAPH_DISCOUNT` records what this build passes and why.
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    hits: dict[str, SearchHit] = {}
    legs_of: dict[str, list[str]] = {}
    scale = weights or {}

    for leg, results in lists:
        weight = scale.get(leg, 1.0)
        for position, hit in enumerate(results, start=1):
            anchor = hit.chunk.anchor
            scores[anchor] = scores.get(anchor, 0.0) + weight / (k + position)
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


@dataclass(frozen=True, slots=True)
class _Proposal:
    """One node the walk reached, and the evidence that reached it."""

    node: str
    seed_rank: int
    """Fused rank of the candidate whose door this node was behind — the
    strength of the evidence for looking here at all."""
    via: str
    """`"<edge type> from <seed anchor>"`, for the `via_edge` label."""


def _walk(store: SqliteStore, seeds: Sequence[FusedHit]) -> tuple[_Proposal, ...]:
    """One hop out from every seed, round by round, bounded to the node budget.

    **Round-robin across seeds, not depth-first through the best one.** The first
    implementation took the budget in seed order and a measurement threw it out:
    on `r-0018` the top hit is an ADR that links to a dozen others, so it filled
    all ten places by itself and the seeds at ranks 3 and 4 — the two that
    actually reach the answer — never proposed anything. Ten seeds each
    contributing their first neighbour is the same principle `neighbours` already
    applies across depth (ADR-0018): spend a bounded budget on breadth, because
    the cheapest thing to lose is a densely linked document's twelfth link.

    Deterministic by construction: seeds are visited in fused order, each seed's
    nodes in the order :func:`~mycelium.graph.nodes_of_anchor` returns them, and
    the store orders the edges of a node. The first proposal of a node wins, so a
    node reachable from two seeds is attributed to the better-ranked one.
    """
    queues: list[tuple[int, str, list[tuple[str, str]]]] = []
    for rank, seed in enumerate(seeds, start=1):
        anchor = seed.hit.chunk.anchor
        own = set(nodes_of_anchor(anchor))
        reached: list[tuple[str, str]] = []
        for node in nodes_of_anchor(anchor):
            for edge, direction in store.edges_of(node):
                other = edge.to if direction == "out" else edge.from_
                if other in own:
                    # A node the seed already stands on is not a neighbour, and
                    # the containment edge back to the seed's own document is
                    # the commonest way to reach one (`part_of`, ADR-0074).
                    continue
                reached.append((other, str(edge.type)))
        queues.append((rank, anchor, reached))

    found: dict[str, _Proposal] = {}
    for round_ in range(max((len(q[2]) for q in queues), default=0)):
        for rank, anchor, reached in queues:
            if round_ >= len(reached):
                continue
            node, edge_type = reached[round_]
            if node in found:
                continue
            found[node] = _Proposal(node, rank, f"{edge_type} from {anchor}")
            if len(found) >= GRAPH_NODES:
                return tuple(found.values())
    return tuple(found.values())


def _candidate_anchors(
    store: SqliteStore, proposals: Sequence[_Proposal]
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Resolve proposed nodes to the chunks behind them.

    Returns ``(anchor -> the via label that proposed it, every anchor)``. A
    document node stands for all of its chunks, a section node for the chunks
    under that heading, and a symbol node for the chunks that define it — which
    is what `doc_refs` is (ADR-0073). One store round-trip for every document
    involved, because ten inside a 30 ms budget is a cost with no reason.
    """
    documents: list[str] = []
    sections: list[tuple[str, str, _Proposal]] = []
    symbols: list[_Proposal] = []
    for proposal in proposals:
        section = split_section_ref(proposal.node)
        if section is not None:
            document, slug = section
            path = document.removeprefix("doc:")
            sections.append((path, slug, proposal))
            documents.append(path)
        elif proposal.node.startswith("doc:"):
            documents.append(proposal.node.removeprefix("doc:"))
        elif proposal.node.startswith("sym:"):
            symbols.append(proposal)

    by_path = store.anchors_of_paths(sorted(set(documents)))
    symbol_refs = (
        {symbol.symbol: symbol.doc_refs for symbol in store.all_symbols()} if symbols else {}
    )

    via: dict[str, str] = {}
    for proposal in proposals:
        section = split_section_ref(proposal.node)
        if section is not None:
            document, slug = section
            anchors = [
                anchor
                for anchor in by_path.get(document.removeprefix("doc:"), ())
                if anchor.partition("#")[2].rsplit("/", 1)[0] == slug
            ]
        elif proposal.node.startswith("doc:"):
            anchors = list(by_path.get(proposal.node.removeprefix("doc:"), ()))
        else:
            anchors = list(symbol_refs.get(proposal.node, ()))
        for anchor in anchors:
            via.setdefault(anchor, proposal.via)
    return via, tuple(via)


def _expand(
    store: SqliteStore,
    seeds: Sequence[FusedHit],
    searched: str,
    filters: SearchFilters | None,
    retrieved: Set[str],
) -> tuple[tuple[SearchHit, ...], dict[str, str]]:
    """The graph leg: one hop from the seeds, ranked by BM25, one chunk per document.

    **The leg carries only passages the other legs did not return, and that is
    the difference between an expansion and a second vote.** The first
    implementation let a passage the lexical leg had already ranked appear in
    this list too, and RRF then summed both contributions: a passage at lexical
    rank 40 that happened to be adjacent to a seed scored
    ``1/100 + 0.9/61`` and leapfrogged the passage at lexical rank 1, which
    scored ``1/61``. Measured on six case sets, it cost between 5 % and 56 %
    overall — cases that had been perfect fell to a third — because *being
    adjacent* was worth nearly as much as *being the best match* (ADR-0075).

    So expansion may **add** and may not **promote**. What the ranking already
    found keeps the rank the ranking gave it.

    The one-per-document rule is the diversity guard spec 04 §4 asks of the
    result set, applied where it is cheapest: without it a single adjacent
    document with thirty chunks could fill the whole leg, which is the opposite
    of what an expansion is for.
    """
    if not seeds:
        return (), {}
    proposals = _walk(store, seeds)
    if not proposals:
        return (), {}
    via, anchors = _candidate_anchors(store, proposals)
    candidates = tuple(anchor for anchor in anchors if anchor not in retrieved)
    if not candidates:
        return (), {}

    ranked = store.rank_anchors(searched, candidates, limit=len(candidates))
    chosen: list[SearchHit] = []
    seen_documents: set[str] = set()
    for hit in ranked:
        if hit.path in seen_documents:
            continue
        if filters is not None and not _admits(filters, hit):
            continue
        seen_documents.add(hit.path)
        chosen.append(hit)
        if len(chosen) >= GRAPH_NODES:
            break
    return tuple(chosen), {hit.chunk.anchor: via[hit.chunk.anchor] for hit in chosen}


def symbol_lookup_ids(query: str) -> tuple[str, ...]:
    """The symbol ids an *exact* lookup for `query` should ask the store about.

    Spec 04 §3's condition — identifier-like tokens — applied to the query's own
    tokens, then crossed with :data:`SYMBOL_LANGUAGES` to turn a bare name into
    the ids spec 03 §2 keys the table on. A query with no identifier-like token
    asks nothing, which is the common case and costs one regex.

    **Exact, and only exact.** A tail match — letting `venv` find `.venv`, or
    `lock` find `uv.lock` — was measured on both uv corpora and rejected: it is
    what makes three of the four firings on those sets, and every one of them
    matches a *different* thing from the one the query asked about (ADR-0080).
    Resolving a use by its last segment is right for an edge, where ambiguity can
    be refused and the claim is only "these two names are related" (ADR-0074),
    and wrong for a ranking, where the claim is "read this passage".
    """
    names = [token for token in _QUERY_TOKEN.findall(query) if identifier_like(token)]
    ids = [
        f"sym:{language}:{name}" for name in dict.fromkeys(names) for language in SYMBOL_LANGUAGES
    ]
    # A command is an identifier whose separator is a space (roadmap 5.23): a
    # command-shaped or quoted query is looked up whole, in the `cli` language
    # alone, and never by a prefix of itself. The shape test is the planner's
    # `command` rule, shared here for the reason `identifier_like` is shared
    # (ADR-0080, ADR-0094).
    phrase = command_phrase(query, stopwords=STOPWORDS)
    if phrase is not None:
        ids.append(f"sym:{CLI_LANGUAGE}:{phrase}")
    return tuple(dict.fromkeys(ids))


def _symbol_candidates(
    store: SqliteStore,
    query: str,
    searched: str,
    filters: SearchFilters | None,
    retrieved: Set[str],
) -> tuple[tuple[SearchHit, ...], dict[str, str]]:
    """The symbol leg: where the query's names are defined, ranked by BM25.

    The same two-step shape as the graph leg, and for the same reason: the table
    answers *which passages define this name*, which is a membership question,
    and the order within that set is a relevance question BM25 already answers
    (`rank_anchors`). A symbol whose defining chunks hold none of the query's
    words contributes nothing.

    `SYMBOL_PROMOTE` decides whether a passage another leg already returned may
    appear here as well. Off, this leg can only surface a definition site the
    ranking placed beyond its fifty candidates — which on a corpus of a few
    hundred chunks is almost never, and that near-emptiness *is* ADR-0080's
    finding rather than a bug in this function.
    """
    ids = symbol_lookup_ids(query)
    if not ids:
        return (), {}
    symbols = store.symbols_by_id(ids)
    if not symbols:
        return (), {}

    # One chunk often defines the same name twice over — `## RetryPolicy` above
    # the fence that declares `class RetryPolicy` is a `doc` term *and* a
    # `python` class — so the label names every symbol that put the passage here
    # rather than whichever sorted first, which would have been an arbitrary
    # tie-break presented as a fact.
    defines: dict[str, list[str]] = {}
    for symbol in symbols:
        for anchor in symbol.doc_refs:
            defines.setdefault(anchor, []).append(symbol.symbol)
    via = {anchor: "defines " + ", ".join(ids) for anchor, ids in defines.items()}
    candidates = tuple(
        anchor
        for anchor, ids in defines.items()
        if SYMBOL_PROMOTE
        or anchor not in retrieved
        or any(identity.split(":")[1] in SYMBOL_PROMOTE_LANGUAGES for identity in ids)
    )
    if not candidates:
        return (), {}

    ranked = store.rank_anchors(searched, candidates, limit=len(candidates))
    chosen = [hit for hit in ranked if filters is None or _admits(filters, hit)]
    chosen = chosen[:SYMBOL_CANDIDATES]
    return tuple(chosen), {hit.chunk.anchor: via[hit.chunk.anchor] for hit in chosen}


def _admits(filters: SearchFilters, hit: SearchHit) -> bool:
    """Whether the serving policy admits an expanded hit (ADR-0024).

    The other legs are filtered in SQL; this one is filtered here, because its
    candidate set is a list of anchors rather than a query. The rule is the same
    rule, applied at the same seam — an expanded passage may not reach a caller
    that the configuration would not have served it to.
    """
    if filters.namespace is not None and hit.chunk.namespace != filters.namespace:
        return False
    if filters.trust_classes is not None and hit.trust_class not in filters.trust_classes:
        return False
    if (
        filters.verification_statuses is not None
        and hit.verification_status not in filters.verification_statuses
    ):
        return False
    return filters.path_prefix is None or hit.path.startswith(filters.path_prefix)


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
    related: bool = False,
    explain: bool = False,
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

    The two derived legs need *both* permissions: the configuration's, and the
    plan's. The graph leg joins when `config.graph_expansion` is on — off by
    default, because the ablation spec 04 §5 gates it on did not clear the bar
    (ADR-0075) — **and** when the plan's relationship rule matched, which is
    spec 04 §2's routing and roadmap 5.11's measurement: expansion pays its cost
    on every query and offers its benefit on few, and routing recovers the
    difference. It runs *after* the first fusion, because its seeds are fused
    candidates, and it never runs without them: a query the corpus cannot answer
    has no door to walk through.

    The symbol leg joins when `config.symbol_lookup` is on — also off by
    default, and also because it was measured off (ADR-0080) — and when the
    plan's identifier rule matched. That rule is the test the leg used to apply
    to itself, moved to where a plan can report it, so the behaviour is
    unchanged.

    `related` is the caller's own routing signal (spec 04 §2's `--related`). It
    does not *enable* the graph leg: the plan narrows and never widens, so a
    caller who wants the leg on for one query turns it on the way `--hybrid`
    turns the vector leg on, and `--related` then says this query is the kind
    that wants it.

    `explain=True` additionally counts what each query word reaches, which is the
    one question ranking cannot answer about itself (roadmap 4.21). It is off by
    default because it costs two index queries per term and the harness that
    measures p95 latency runs thousands of queries.
    """
    settings = config or RetrievalConfig()
    plan = plan_query(query, related=related)
    filters, policy_note = _serve_only(filters, settings)
    if filters is None and policy_note is not None:
        return SearchOutcome(
            hits=(),
            legs=(),
            degraded=(),
            notes=(policy_note,),
            timings_ms={"total": 0},
            plan=plan,
        )

    depth = max(limit, VECTOR_CANDIDATES)
    timings: dict[str, int] = {}

    # The lexical leg searches on content words; the vector leg below is given
    # `query` whole, because an embedder reads the grammar (ADR-0057).
    searched = " ".join(query_terms(query))
    dropped = [term for term in _TERM.findall(query.lower()) if term not in searched.split()]

    started = time.perf_counter()
    lexical = store.search_chunks(searched, limit=depth, filters=filters, prefix=prefix)
    timings[_LEXICAL] = _elapsed_ms(started)
    lists: list[tuple[str, Sequence[SearchHit]]] = [(_LEXICAL, lexical)]
    degraded: list[str] = []
    notes: list[str] = [policy_note] if policy_note else []
    if dropped:
        notes.append(
            f"lexical leg searched on {searched!r}: {len(dropped)} function word(s) "
            f"dropped ({', '.join(dict.fromkeys(dropped))})"
        )

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

    retrieved = {hit.chunk.anchor for _, results in lists for hit in results}
    via_symbol: dict[str, str] = {}
    if settings.symbol_lookup and plan.asks_for(_SYMBOL):
        started = time.perf_counter()
        proposed, via_symbol = _symbol_candidates(store, query, searched, filters, retrieved)
        timings[_SYMBOL] = _elapsed_ms(started)
        if proposed:
            lists.append((_SYMBOL, proposed))
            started = time.perf_counter()
            fused = reciprocal_rank_fusion(
                lists, k=RRF_K, limit=limit, weights={_SYMBOL: SYMBOL_DISCOUNT}
            )
            timings["fusion"] += _elapsed_ms(started)
            named = {
                identity
                for label in via_symbol.values()
                for identity in label.removeprefix("defines ").split(", ")
            }
            notes.append(
                f"symbol leg: {len(proposed)} definition site(s) for "
                f"{len(named)} symbol(s) the query names"
            )
        else:
            notes.append(
                "symbol leg: no identifier-like token in this query names a symbol this "
                "snapshot defines, outside what the other legs already returned"
            )
    elif settings.symbol_lookup:
        notes.append(
            "symbol leg not planned: no identifier-like token, quoted phrase or "
            "command-shaped query (spec 04 §2, ADR-0094)"
        )

    via: dict[str, str] = {}
    if settings.graph_expansion and plan.asks_for(_GRAPH):
        # Expansion runs on the *fused* candidates, not on the lexical list:
        # spec 04 §5 says "from top-k fused candidates", and a seed the vector
        # leg promoted is as good a door as one BM25 found.
        started = time.perf_counter()
        seeds = reciprocal_rank_fusion(lists, k=RRF_K, limit=GRAPH_SEEDS)
        expanded, via = _expand(
            store,
            seeds,
            searched,
            filters,
            {hit.chunk.anchor for _, results in lists for hit in results},
        )
        timings[_GRAPH] = _elapsed_ms(started)
        if expanded:
            lists.append((_GRAPH, expanded))
            started = time.perf_counter()
            fused = reciprocal_rank_fusion(
                lists,
                k=RRF_K,
                limit=limit,
                weights={_GRAPH: GRAPH_DISCOUNT, _SYMBOL: SYMBOL_DISCOUNT},
            )
            timings["fusion"] += _elapsed_ms(started)
            notes.append(
                f"graph leg: {len(expanded)} passage(s) proposed by one hop from "
                f"{len(seeds)} seed(s) and ranked against the query"
            )
        else:
            notes.append("graph leg: one hop from the seeds proposed nothing this query matched")
    elif settings.graph_expansion:
        notes.append(
            "graph leg not planned: no relationship phrasing in this query and --related "
            "was not asked for (spec 04 §2); pass --related to expand anyway"
        )

    if via or via_symbol:
        fused = tuple(
            replace(
                hit,
                via_edge=via.get(hit.hit.chunk.anchor, ""),
                via_symbol=via_symbol.get(hit.hit.chunk.anchor, ""),
            )
            for hit in fused
        )

    terms: tuple[TermHits, ...] = ()
    if explain:
        started = time.perf_counter()
        # The terms that *ran*, not the words that were typed: a report crediting
        # a word the search never used explains someone else's query (ADR-0050).
        terms = store.term_hits(searched, filters=filters)
        timings["terms"] = _elapsed_ms(started)
        dead = [item.term for item in terms if item.unmatched]
        if dead:
            notes.append(
                f"{len(dead)} query term(s) match nothing in this corpus, in any "
                f"inflection: {', '.join(dead)}"
            )
    timings["total"] = sum(timings.values())

    return SearchOutcome(
        hits=fused,
        legs=tuple(leg for leg, _ in lists),
        degraded=tuple(degraded),
        notes=tuple(notes),
        timings_ms=timings,
        terms=terms,
        plan=plan,
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
