#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Score candidate re-rankings of the lexical leg (ADR-0031, ADR-0041).

    python tools/measure_ranking.py [repository-root]      # the dev sets
    python tools/measure_ranking.py --release              # ...and the gate view
    python tools/measure_ranking.py --oracle               # the family's ceiling
    python tools/measure_ranking.py --stems                # the IDF-floor refusal

Roadmap 4.8 was open because the grep incumbent beat the product on the second
corpus. **It no longer does** (ADR-0049): measured after packing (4.15) and
stemming (4.19), uv/release reads 0.548 against the incumbent's 0.519, and the
product leads on all four sets. Nothing in this file is what closed it — every
re-ranking below is still refused — which is the finding worth keeping.

This is still where a candidate fix is measured before it is proposed, and it
reads the **dev** sets by default on purpose: the release sets are what gate G3
judges the outcome with, and a change developed against them cannot be told apart
from a change fitted to them (spec 04 §7.1).

Ten *re-ranking* candidates live here and **all ten are refused** — four rows by
ADR-0031 (a length prior at two floors, coverage-first, section aggregation) and
six more by ADR-0041, the section-level indexing hypothesis in every form it has,
plus the incumbent's own ranking function. `--release` prints the per-slice deltas
gate G3 reads, and `--oracle` prints the ceiling of the whole section family: the
per-case best of every strategy in it, which no planner can beat.

The eleventh family is the *index* rather than the ranking (roadmap 4.19), and it
is the one that shipped: `index: expand-pre` is what the store now does, and the
rows beside it are the variants it beat or was refused in favour of. `index:
plain` is the control — an in-memory rebuild of the pre-4.19 index, which is why
it now scores *below* `baseline (ships)`.

The twelfth is the **heading** family (roadmap 4.25), and it is the second thing
in this file to ship — over three items, one parameter at a time. A chunk's
`heading_path` was its whole ancestor chain, so a subsection's heading field was
a strict superset of its parent's; splitting the leaf heading from the ancestors
stops a query that matches an ancestor from boosting every descendant. What ships
now is `heading 3.0/0.5`, so that row and `baseline (ships)` are the same index
and must score identically — the control that says this family is measuring the
field split and nothing else. **`heading 2.0/0.5` is now the revert control**: it
is what shipped between roadmap 4.36 and 4.42, and its row prices going back.

Four results, all worth keeping. It does **not** move the case it was built for
— `u-1006` sits at 0.431 at every setting, including ancestors at zero, because
the child never won on the heading field at all (it wins on `text`, at 164 tokens
against 385). The **ancestor** weight was chosen where dev could see it: on
ours/dev it is a **plateau**, 0.25 through 0.75 scoring identically and 0.0
collapsing (0.539/0.577/0.719 against 0.523/0.577/0.688 at the leaf weight of the
day), so the ancestors carry real signal and 0.5 is the middle of the flat part
rather than a fitted optimum. The **leaf** weight was refused twice on the same
ground — it gained on the release sets and scored *exactly* the baseline on the
dev sets, which is a value read off the held-out set — and roadmap 4.39 removed
that ground by growing uv/dev from twelve judged cases to twenty-two. It reads
0.614 there against 0.609, and **4.0/0.5 reads 0.599, below the baseline**: an
interior optimum, on the dev side, disagreeing with the release sets, which is
what a dev set is for (roadmap 4.42, ADR-0070). The unsplit controls
(`heading 3.0/3.0`, `heading 4.0/4.0`) fail gate G3 on `exact`, which says the
split is what makes a higher leaf weight safe rather than the weight doing it
alone.

The thirteenth is the **length** family (roadmap 4.38), and **all five settings
are refused**. It began from a fact worth keeping on its own: `bm25()` normalises
by the *row's* total token count, not per column — two rows with an identical
matching heading and bodies of 20 against 400 tokens score -3.060e-6 and
-1.151e-6 on heading-only weights. So a heading match is damped by how long the
body is, and after 4.36 three of the four surface columns are a handful of tokens
against a `text` that runs to hundreds. Putting the short fields in their own
table is the only lever on that denominator which is neither a re-ranking nor a
change of unit.

It fails, and *how* it fails is the finding. The two cases 4.38 named are
**anti-correlated** under it: every setting that moves `u-1006` (0.431 → 0.631,
and `length rrf` takes it to **1.0000**, the incumbent's own score and the first
thing in this file ever to close it) makes `u-1007` *worse* (0.374 → 0.319 or
0.202). So the standing observation — a long section that answers a query
concedes to shorter ones — does not have one mechanism behind it, and a single
fix was never going to move both. `u-1007`'s heading match was being *helped* by
the joint computation more than it was hurt by the shared denominator, which is
the opposite of the hypothesis.

And the failure is not the scale error it looks like. Adding two BM25 scores from
tables with different average lengths is not a fusion, so `length rrf` fuses the
rank lists instead at spec 04 §3's k=60 — scale-free, no new constant — and it is
**worse**: uv/dev 0.646 against the baseline's 0.710, and `relationship` −53.8 %
and −61.3 % on the two release sets. Any split of the fields, added or fused,
loses the reinforcement a multi-part query needs between a chunk's heading and
its body. That is a stronger reason for ADR-0048's one-table decision than the
one it gave.

**One thing this file cannot see**: it scores answerable cases only, so gate G4
is outside its view. Open expansion wins three of four sets here and answers a
question the corpus cannot answer, which only the real `mycelium eval --gate`
reports (ADR-0048). A candidate that wins in this file is not a candidate that
ships.

The strategies are kept rather than deleted. A refusal nobody can re-run is a
claim, and the next attempt should start from the numbers instead of from prose.

The standing comparison has moved out of this file: `mycelium eval --against grep`
records the incumbent inside the run manifest, on every corpus CI scores, so the
question "are we still ahead" is answered by the product rather than by a tool an
operator has to remember to run (ADR-0049).
"""

import re
import sqlite3
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import (  # noqa: E402
    credit_judgments,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    section_of,
)
from mycelium.eval.retrievers import build_retriever, terms_of  # noqa: E402
from mycelium.store import SearchHit, SqliteStore  # noqa: E402
from mycelium.store.sqlite import (  # noqa: E402
    _FTS_TERM,
    STEM_WEIGHT,
    fts_query,
)
from mycelium.store.stemming import stem_text  # noqa: E402

DEPTH = 50
"""Candidate depth, matching the harness's retrieval limit."""
K = 10
OVERFETCH = 4
"""Candidates read per result when a strategy collapses several into one."""

Ranking = Callable[[SqliteStore, str], list[str]]

_SECTION_INDEX: dict[int, sqlite3.Connection] = {}


def _candidates(store: SqliteStore, query: str, depth: int) -> Sequence[SearchHit]:
    return store.search_chunks(" ".join(terms_of(query)), limit=depth)


# ---------------------------------------------------------------------------
# The chunk unit — what ships
# ---------------------------------------------------------------------------


def baseline(store: SqliteStore, query: str) -> list[str]:
    """What ships: field-weighted BM25 over chunks."""
    return [hit.chunk.anchor for hit in _candidates(store, query, DEPTH)]


# ---------------------------------------------------------------------------
# The three ADR-0031 refused
# ---------------------------------------------------------------------------


def section_max(store: SqliteStore, query: str) -> list[str]:
    """One section competes once, represented by its best-scoring chunk.

    ADR-0031 refused it: gate G3 failed it on the held-out release set. The
    regression **reproduces after 3.17's re-judging**, which closes the question
    that ADR left open — it was retrieval, not chunk-exact bookkeeping.
    """
    best: dict[str, SearchHit] = {}
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        section = section_of(hit.chunk.anchor)
        if section not in best or hit.score > best[section].score:
            best[section] = hit
    ordered = sorted(best.values(), key=lambda hit: (-hit.score, hit.chunk.anchor))
    return [hit.chunk.anchor for hit in ordered[:DEPTH]]


def length_prior(floor: int) -> Ranking:
    """Damp chunks shorter than `floor` tokens, on the theory that a fragment
    cannot be an answer. It can: `## License` and one line is 24 tokens."""

    def rank(store: SqliteStore, query: str) -> list[str]:
        scored = [
            (hit.score * min(1.0, hit.chunk.tokens / floor), hit.chunk.anchor)
            for hit in _candidates(store, query, DEPTH * OVERFETCH)
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [anchor for _, anchor in scored[:DEPTH]]

    return rank


def coverage_first(store: SqliteStore, query: str) -> list[str]:
    """Prefer passages containing more *distinct* query terms, then BM25 —
    coordination-level matching. Refused for losing on both corpora."""
    scored = []
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        covered = _covered(query, hit)
        scored.append(((covered, hit.score), hit.chunk.anchor))
    scored.sort(key=lambda pair: (-pair[0][0], -pair[0][1], pair[1]))
    return [anchor for _, anchor in scored[:DEPTH]]


# ---------------------------------------------------------------------------
# The section unit — ADR-0031's named hypothesis, in every form it has
#
# "Index and score at the *section* level — a second FTS table whose documents
# are sections — so length normalisation compares comparable units, then return
# the best chunk of the winning section."
#
# The index is built in memory from the store's own chunks. A hypothesis that
# fails should cost an afternoon, not a schema version.
# ---------------------------------------------------------------------------


def _section_index(store: SqliteStore) -> sqlite3.Connection:
    """One FTS5 row per section: its chunks' text, concatenated."""
    key = id(store)
    cached = _SECTION_INDEX.get(key)
    if cached is not None:
        return cached

    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    memory.execute(
        """
        CREATE VIRTUAL TABLE sections_fts USING fts5(
            section UNINDEXED, text, title, heading_path,
            tokenize='unicode61', prefix='2 3 4'
        )
        """
    )
    rows: dict[str, tuple[list[str], str, str]] = {}
    for doc_id in store.document_ids():
        document = store.get_document(doc_id)
        if document is None:  # pragma: no cover - ids come from the same store
            continue
        for chunk in store.chunks_of(doc_id):
            section = section_of(chunk.anchor)
            entry = rows.setdefault(section, ([], document.title, " ".join(chunk.heading_path)))
            entry[0].append(chunk.text)
    memory.executemany(
        "INSERT INTO sections_fts(section, text, title, heading_path) VALUES(?,?,?,?)",
        [
            (section, "\n\n".join(texts), title, heading_path)
            for section, (texts, title, heading_path) in rows.items()
        ],
    )
    memory.commit()
    _SECTION_INDEX[key] = memory
    return memory


def _section_ranking(store: SqliteStore, query: str, depth: int) -> list[str]:
    """Sections, best first, by BM25 over the section index."""
    match = fts_query(" ".join(terms_of(query)))
    if not match:
        return []
    rows = (
        _section_index(store)
        .execute(
            """
        SELECT section, bm25(sections_fts, ?, ?, ?, ?) AS score
        FROM sections_fts WHERE sections_fts MATCH ?
        ORDER BY score LIMIT ?
        """,
            [*_LEGACY_WEIGHTS, match, depth],
        )
        .fetchall()
    )
    return [str(row["section"]) for row in rows]


# ---------------------------------------------------------------------------
# The tokenizer family (roadmap 4.19) — same chunk unit, different index
#
# ADR-0044 measured the straight swap to `porter` and recorded that it wins
# overall and fails gate G3. The item that followed says to measure *expansion*
# first: keep the surface form and add the stem beside it, so a literal match
# keeps its edge instead of being replaced by an inflected one. All three live
# here over the same chunks, so the only variable is the index.
# ---------------------------------------------------------------------------

_TOKEN_INDEX: dict[tuple[int, str, float], sqlite3.Connection] = {}

_SURFACE_COLUMNS: Final = "{text title heading_path}"
_STEM_COLUMNS: Final = "{text_stem title_stem heading_path_stem}"

_LEGACY_WEIGHTS: Final = (0.0, 1.0, 3.0, 2.0)
"""The four columns the shipped index had before roadmap 4.36 split `heading_path`.

Pinned here rather than imported from the store, and that is the point. Every
in-memory index above this line is a *recorded refusal* — the section family
(ADR-0031, ADR-0041), the tokenizer family (ADR-0044, ADR-0048) — and a refusal
whose numbers move when an unrelated field is split is not re-runnable. These
rows keep the index they were measured on; the store's own
:data:`~mycelium.store.sqlite._SURFACE_WEIGHTS` moved on without them, which is
what `heading 2.0/2.0` is in the file to show."""


def _chunk_rows(store: SqliteStore) -> list[tuple[str, str, str, str]]:
    """`(anchor, text, document title, heading path)` for every published chunk."""
    rows = []
    for doc_id in store.document_ids():
        document = store.get_document(doc_id)
        if document is None:  # pragma: no cover - ids come from the same store
            continue
        for chunk in store.chunks_of(doc_id):
            rows.append((chunk.anchor, chunk.text, document.title, " / ".join(chunk.heading_path)))
    return rows


def _token_index(store: SqliteStore, variant: str, stem_weight: float) -> sqlite3.Connection:
    """An in-memory chunk index built the way `variant` says."""
    key = (id(store), variant, stem_weight)
    cached = _TOKEN_INDEX.get(key)
    if cached is not None:
        return cached

    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    rows = _chunk_rows(store)
    if variant.startswith("expand"):
        memory.execute(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                anchor UNINDEXED, text, title, heading_path,
                text_stem, title_stem, heading_path_stem,
                tokenize='unicode61', prefix='2 3 4'
            )
            """
        )
        memory.executemany(
            "INSERT INTO chunks_fts(anchor, text, title, heading_path,"
            " text_stem, title_stem, heading_path_stem) VALUES(?,?,?,?,?,?,?)",
            [(anchor, *fields, *(_stemmed(field) for field in fields)) for anchor, *fields in rows],
        )
    else:
        tokenizer = "porter unicode61" if variant == "porter" else "unicode61"
        memory.execute(
            f"""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                anchor UNINDEXED, text, title, heading_path,
                tokenize='{tokenizer}', prefix='2 3 4'
            )
            """
        )
        memory.executemany(
            "INSERT INTO chunks_fts(anchor, text, title, heading_path) VALUES(?,?,?,?)",
            rows,
        )
    memory.commit()
    _TOKEN_INDEX[key] = memory
    return memory


def _stemmed(text: str) -> str:
    return " ".join(stem_text(_FTS_TERM.findall(text)))


def _tokenizer_ranking(
    store: SqliteStore, query: str, variant: str, stem_weight: float
) -> list[str]:
    terms = terms_of(query)
    if not terms:
        return []
    if variant.startswith("expand"):
        surface = " OR ".join(f'"{term}"' for term in terms)
        stems = " OR ".join(f'"{term}"' for term in dict.fromkeys(stem_text(terms)))
        both = f"{_SURFACE_COLUMNS} : ({surface}) OR {_STEM_COLUMNS} : ({stems})"
        # `expand-pre` requires a surface hit before the stems may speak, which is
        # ADR-0025's precondition one layer down: a stem may reorder what the
        # surface index found and may not introduce a document of its own.
        match = (
            f"{_SURFACE_COLUMNS} : ({surface}) AND ({both})" if variant.endswith("pre") else both
        )
        if variant.endswith("gate"):
            # Roadmap 4.23. The precondition holds two rules at once, and only one
            # of them is what abstention needs. *Query*-level: does any word of
            # this query appear in this corpus as written? *Document*-level: must
            # every candidate carry such a word? The first is what keeps a
            # watchmaking query silent; the second is what costs recall. So the
            # gate asks the first question once, of the corpus, and leaves the
            # documents open. No threshold: a term either appears or it does not.
            probe = _token_index(store, variant, stem_weight).execute(
                "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
                [f"{_SURFACE_COLUMNS} : ({surface})"],
            )
            if probe.fetchone() is None:
                return []
            match = both
        weights = [*_LEGACY_WEIGHTS, *(stem_weight * w for w in _LEGACY_WEIGHTS[1:])]
    else:
        match = fts_query(" ".join(terms))
        weights = list(_LEGACY_WEIGHTS)
    placeholders = ", ".join("?" for _ in weights)
    rows = (
        _token_index(store, variant, stem_weight)
        .execute(
            f"""
            SELECT anchor, bm25(chunks_fts, {placeholders}) AS score
            FROM chunks_fts WHERE chunks_fts MATCH ?
            ORDER BY score LIMIT ?
            """,
            [*weights, match, DEPTH],
        )
        .fetchall()
    )
    return [str(row["anchor"]) for row in rows]


def query_words(strip: bool) -> Ranking:
    """The product's lexical leg, with and without the function-word boundary.

    Roadmap 4.28's evidence, and the only row in this file that varies the
    *query* rather than the index or the ranking. `query: raw` is what the
    product did before ADR-0057 — every word of the question, function words at
    full field weight — and `query: stopped` is what it does now. The whole
    family exists because no other row can show the difference: every retriever
    the harness scores has always been handed `terms_of(query)`, so the harness
    was measuring the fix four milestones before the product had it.
    """

    def rank(store: SqliteStore, query: str) -> list[str]:
        text = " ".join(terms_of(query)) if strip else query
        return [hit.chunk.anchor for hit in store.search_chunks(text, limit=DEPTH)]

    return rank


QUERY_FAMILY: Final[list[tuple[str, Ranking]]] = [
    ("query: raw", query_words(strip=False)),
    ("query: stopped", query_words(strip=True)),
]
"""`query: stopped` is what ships (ADR-0057) and must score what
`baseline (ships)` scores; `query: raw` is the control — the product as it stood
before roadmap 4.28, which is *not* what any earlier number in this file
measured."""


def tokenizer(variant: str, stem_weight: float = 0.0) -> Ranking:
    """One index variant, as a ranking the scorer can drive."""

    def rank(store: SqliteStore, query: str) -> list[str]:
        return _tokenizer_ranking(store, query, variant, stem_weight)

    return rank


TOKENIZER_FAMILY: Final[list[tuple[str, Ranking]]] = [
    ("index: plain", tokenizer("plain")),
    ("index: porter", tokenizer("porter")),
    ("index: expand 0.1", tokenizer("expand", 0.1)),
    ("index: expand 0.5", tokenizer("expand", 0.5)),
    ("index: expand-pre 0.1", tokenizer("expand-pre", 0.1)),
    ("index: expand-pre 0.5", tokenizer("expand-pre", 0.5)),
    ("index: expand-pre 1.0", tokenizer("expand-pre", 1.0)),
    ("index: expand-gate 0.05", tokenizer("expand-gate", 0.05)),
    ("index: expand-gate 0.075", tokenizer("expand-gate", 0.075)),
    ("index: expand-gate 0.1", tokenizer("expand-gate", 0.1)),
]
"""`plain` is the no-stem control — the index as it stood before roadmap 4.19 —
and `expand-gate 0.05` is the mirror of what ships today, which must score what
`baseline (ships)` scores or the harness is measuring the wrong thing.

The rows differ in two ways, and only two. How much weight the stem columns carry
relative to the surface ones (the family's single free parameter, chosen on the
dev sets and read off the release sets), and where the surface precondition sits:
`expand` has none and fails gate G4, `expand-pre` puts it inside the MATCH
expression as ADR-0048 shipped it, and `expand-gate` asks it once of the corpus
before the search — the same abstention with the document-level restriction
removed (roadmap 4.23, ADR-0054). Comparing a `pre` row with a `gate` row at the
*same* weight compares two things at once: the old expression named the surface
clause twice, so its nominal weight understates the surface side by roughly a
factor of two."""


def _best_chunk_per_section(store: SqliteStore, query: str) -> dict[str, str]:
    """The chunk-level ranking, reduced to the winner inside each section."""
    best: dict[str, tuple[float, str]] = {}
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        section = section_of(hit.chunk.anchor)
        current = best.get(section)
        if current is None or hit.score > current[0]:
            best[section] = (hit.score, hit.chunk.anchor)
    return {section: anchor for section, (_, anchor) in best.items()}


def section_fts(store: SqliteStore, query: str) -> list[str]:
    """The hypothesis as ADR-0031 wrote it: score sections, return their best chunk."""
    representatives = _best_chunk_per_section(store, query)
    out = []
    for section in _section_ranking(store, query, DEPTH):
        anchor = representatives.get(section) or f"{section}0"
        if store.get_chunk(anchor) is not None:
            out.append(anchor)
    return out[:DEPTH]


def section_open(store: SqliteStore, query: str) -> list[str]:
    """Score sections, return the chunk that *opens* each one.

    Every case the incumbent won on the second corpus, it won with a `/0` — the
    chunk that opens a section. Document order, not a tuned constant. The best
    of the family on the second corpus, and the one that fails gate G3 on ours.
    """
    out = []
    for section in _section_ranking(store, query, DEPTH):
        anchor = f"{section}0"
        if store.get_chunk(anchor) is not None:
            out.append(anchor)
    return out[:DEPTH]


def section_ordered(store: SqliteStore, query: str) -> list[str]:
    """Let the section index *order* the chunk candidates, and remove none of them.

    Written after the case-level diagnosis said the damage was deletion:
    collapsing a section to one chunk drops its other chunks out of the ranking,
    and a judgment naming one of those then scores zero. Here the candidate set
    is exactly what the chunk leg found — recall untouched by construction — and
    the section index decides only which section's chunks come first.
    """
    candidates = list(_candidates(store, query, DEPTH * OVERFETCH))
    if not candidates:
        return []
    grouped: dict[str, list[tuple[float, str]]] = {}
    for hit in candidates:
        grouped.setdefault(section_of(hit.chunk.anchor), []).append((hit.score, hit.chunk.anchor))
    order = {
        section: rank
        for rank, section in enumerate(_section_ranking(store, query, DEPTH * OVERFETCH))
    }
    unranked = len(order)

    def key(section: str) -> tuple[int, float]:
        # A section the section index did not return keeps its chunk-leg standing,
        # after every section it did — never dropped.
        return (order.get(section, unranked), -max(score for score, _ in grouped[section]))

    out: list[str] = []
    for section in sorted(grouped, key=key):
        out.extend(anchor for _, anchor in sorted(grouped[section], key=lambda p: (-p[0], p[1])))
    return out[:DEPTH]


def section_fused(store: SqliteStore, query: str) -> list[str]:
    """Fuse the chunk leg with the section leg instead of replacing it.

    The chunk leg is what makes `exact` work — a phrase lives in one chunk — and
    the section leg is what makes length normalisation compare comparable units.
    RRF is already the project's fusion primitive (spec 04 §3, k=60), so this
    invents no constant.
    """
    return _rrf([baseline(store, query), section_fts(store, query)])


def open_if_candidate(store: SqliteStore, query: str) -> list[str]:
    """A section speaks through its opener, but only when the opener is evidence.

    The best-scoring chunk representing its section *is* the short-fragment bias
    (a three-token code fence outranking the paragraph that answers). Promoting
    the opener unconditionally is the same mistake mirrored: on
    `BEGIN IMMEDIATE transaction` it promotes a 14-token lead-in over the
    92-token paragraph carrying the phrase. So this asks the retriever — promote
    the opener only when BM25 already put it in the candidate set.

    The last member of the family, and it still loses on our own dev set.
    """
    hits = list(_candidates(store, query, DEPTH * OVERFETCH))
    present = {hit.chunk.anchor for hit in hits}
    out: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        section = section_of(hit.chunk.anchor)
        if section in seen:
            continue
        seen.add(section)
        opener = f"{section}0"
        out.append(opener if opener in present else hit.chunk.anchor)
    return out[:DEPTH]


def grep_formula(store: SqliteStore, query: str) -> list[str]:
    """The incumbent's own ranking function, over our candidate set.

    grep ranks by `(distinct terms, total occurrences)` with **no length
    normalisation anywhere** — which is not the `coverage-first` candidate
    ADR-0031 refused, because that one kept BM25 as its tie-break and the length
    bias survived in the second key. Measured because our candidate set has
    better recall than the incumbent's, so borrowing its ranking looked free.

    It is not: the incumbent's selection and its ranking are a package.
    """
    scored = []
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        scored.append(((_covered(query, hit), _occurrences(query, hit)), hit.chunk.anchor))
    scored.sort(key=lambda pair: (-pair[0][0], -pair[0][1], pair[1]))
    return [anchor for _, anchor in scored[:DEPTH]]


def grep(store: SqliteStore, query: str) -> list[str]:
    """The incumbent D-010 measures against."""
    return build_retriever("grep", store).search(query, DEPTH)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

RRF_K: Final = 60
"""spec 04 §3's fusion constant, reused so a fused leg adds no new parameter."""


def _rrf(lists: Sequence[Sequence[str]], limit: int = DEPTH) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in lists:
        for rank, anchor in enumerate(ranking, start=1):
            scores[anchor] = scores.get(anchor, 0.0) + 1.0 / (RRF_K + rank)
    return [anchor for anchor, _ in sorted(scores.items(), key=lambda i: (-i[1], i[0]))[:limit]]


def _patterns(query: str) -> list[re.Pattern[str]]:
    return [re.compile(rf"\b{re.escape(term)}", re.IGNORECASE) for term in terms_of(query)]


def _haystack(hit: SearchHit) -> str:
    return f"{hit.title} {' '.join(hit.chunk.heading_path)} {hit.chunk.text}"


def _covered(query: str, hit: SearchHit) -> int:
    haystack = _haystack(hit)
    return sum(1 for pattern in _patterns(query) if pattern.search(haystack))


def _occurrences(query: str, hit: SearchHit) -> int:
    haystack = _haystack(hit)
    return sum(len(pattern.findall(haystack)) for pattern in _patterns(query))


# ---------------------------------------------------------------------------
# The heading family (roadmap 4.25) — same chunks, same tokenisation, one field
# split in two
#
# A chunk's `heading_path` is its whole ancestor chain, so a subsection's
# heading field is a strict *superset* of its parent's. Every word that made a
# query match the parent's heading also matches the child's, at the same field
# weight of 2.0 — and the child adds its own words on top. The uv/release case
# `u-1006` is that shape exactly: "which Python version formats can I request"
# puts `Requesting a version / Python version files` above `Requesting a
# version`, and only the second one lists the formats.
#
# The hypothesis is that the leaf heading — the one that names what *this* chunk
# is about — and the ancestors — which name where it sits — are different
# evidence and should not share a weight. It is an indexing change rather than a
# re-ranking, which is the family the two changes that actually closed the gap
# came from (roadmap 4.19, 4.15).
# ---------------------------------------------------------------------------

_HEADING_INDEX: dict[tuple[int, float, float], sqlite3.Connection] = {}

_HEADING_SURFACE: Final = "{text title heading ancestors}"
_HEADING_STEMS: Final = "{text_stem title_stem heading_stem ancestors_stem}"


def _split_chunk_rows(store: SqliteStore) -> list[tuple[str, str, str, str, str]]:
    """`(anchor, text, title, leaf heading, ancestor headings)` per chunk."""
    rows = []
    for doc_id in store.document_ids():
        document = store.get_document(doc_id)
        if document is None:  # pragma: no cover - ids come from the same store
            continue
        for chunk in store.chunks_of(doc_id):
            path = list(chunk.heading_path)
            leaf = path[-1] if path else ""
            rows.append((chunk.anchor, chunk.text, document.title, leaf, " / ".join(path[:-1])))
    return rows


def _heading_index(store: SqliteStore, leaf: float, ancestors: float) -> sqlite3.Connection:
    key = (id(store), leaf, ancestors)
    cached = _HEADING_INDEX.get(key)
    if cached is not None:
        return cached
    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    memory.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            anchor UNINDEXED, text, title, heading, ancestors,
            text_stem, title_stem, heading_stem, ancestors_stem,
            tokenize='unicode61', prefix='2 3 4'
        )
        """
    )
    memory.executemany(
        "INSERT INTO chunks_fts(anchor, text, title, heading, ancestors,"
        " text_stem, title_stem, heading_stem, ancestors_stem) VALUES(?,?,?,?,?,?,?,?,?)",
        [(anchor, *fields, *(_stemmed(field) for field in fields)) for anchor, *fields in rows]
        if (rows := _split_chunk_rows(store))
        else [],
    )
    memory.commit()
    _HEADING_INDEX[key] = memory
    return memory


def heading_split(leaf: float, ancestors: float) -> Ranking:
    """The shipping index with `heading_path` split into leaf and ancestors.

    Everything else is held fixed on purpose: the same chunks, the same
    `unicode61` tokenisation, the same surface-and-stem expansion at the shipped
    :data:`STEM_WEIGHT`, and the same query-level abstention gate. `leaf` and
    `ancestors` are the only free parameters, and setting both to 2.0 must
    reproduce `baseline (ships)` — otherwise this row is measuring something else.
    """

    def rank(store: SqliteStore, query: str) -> list[str]:
        terms = terms_of(query)
        if not terms:
            return []
        surface = " OR ".join(f'"{term}"' for term in terms)
        stems = " OR ".join(f'"{term}"' for term in dict.fromkeys(stem_text(terms)))
        index = _heading_index(store, leaf, ancestors)
        probe = index.execute(
            "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
            [f"{_HEADING_SURFACE} : ({surface})"],
        )
        if probe.fetchone() is None:
            return []
        match = f"{_HEADING_SURFACE} : ({surface}) OR {_HEADING_STEMS} : ({stems})"
        surfaces = (1.0, 3.0, leaf, ancestors)
        weights = [0.0, *surfaces, *(STEM_WEIGHT * weight for weight in surfaces)]
        placeholders = ", ".join("?" for _ in weights)
        rows = index.execute(
            f"""
            SELECT anchor, bm25(chunks_fts, {placeholders}) AS score
            FROM chunks_fts WHERE chunks_fts MATCH ?
            ORDER BY score LIMIT ?
            """,
            [*weights, match, DEPTH],
        ).fetchall()
        return [str(row["anchor"]) for row in rows]

    return rank


# ---------------------------------------------------------------------------
# The length family (roadmap 4.38) — same chunks, same weights, one denominator
# split in two
#
# `bm25()` normalises by the **row's** total token count, not per column. That is
# a measured fact, not a reading of the docs: two rows with an identical matching
# heading and text of 20 against 400 tokens score -3.060e-6 and -1.151e-6 on
# heading-only weights. So a heading match's contribution is damped by how long
# the *body* is — a property of the section, not of the heading match.
#
# After roadmap 4.36 the index has four surface columns and three of them are
# short: `title`, `heading`, `ancestors` are a handful of tokens each while
# `text` runs to hundreds. They share one denominator, so the long section that
# answers a query is penalised on every field at once. That is the mechanism
# behind both of 4.38's named cases — `u-1007`'s judged chunk is the longest in
# its candidate set at 409 tokens and its heading is literally "Installing
# tools"; `u-1006`'s is 385 against a 164-token sibling.
#
# The candidate is the only lever that touches the denominator without touching
# the ranking function or the unit of indexing (the two families already refused,
# ADR-0031/0041): put the short fields in their own table so they normalise
# against comparable lengths, and add the two BM25 scores. Adding is where it
# gets its free parameter, so `length 1.0` — equal weight, no constant to tune —
# is the row that either works or does not.
# ---------------------------------------------------------------------------

_LENGTH_INDEX: dict[tuple[int, str], sqlite3.Connection] = {}

_SHORT_SURFACE: Final = "{title heading ancestors}"
_SHORT_STEMS: Final = "{title_stem heading_stem ancestors_stem}"
_BODY_SURFACE: Final = "{text}"
_BODY_STEMS: Final = "{text_stem}"


def _length_indexes(store: SqliteStore) -> tuple[sqlite3.Connection, sqlite3.Connection]:
    """The shipping columns, split into a short-field table and a body table."""
    key = (id(store), "length")
    cached = _LENGTH_INDEX.get(key)
    if cached is not None:
        return cached, _LENGTH_INDEX[(id(store), "length-body")]

    rows = _split_chunk_rows(store)
    short = sqlite3.connect(":memory:")
    short.row_factory = sqlite3.Row
    short.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            anchor UNINDEXED, title, heading, ancestors,
            title_stem, heading_stem, ancestors_stem,
            tokenize='unicode61', prefix='2 3 4'
        )
        """
    )
    short.executemany(
        "INSERT INTO chunks_fts(anchor, title, heading, ancestors,"
        " title_stem, heading_stem, ancestors_stem) VALUES(?,?,?,?,?,?,?)",
        [
            (anchor, title, heading, ancestors, *(_stemmed(f) for f in (title, heading, ancestors)))
            for anchor, _text, title, heading, ancestors in rows
        ],
    )
    body = sqlite3.connect(":memory:")
    body.row_factory = sqlite3.Row
    body.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            anchor UNINDEXED, text, text_stem,
            tokenize='unicode61', prefix='2 3 4'
        )
        """
    )
    body.executemany(
        "INSERT INTO chunks_fts(anchor, text, text_stem) VALUES(?,?,?)",
        [(anchor, text, _stemmed(text)) for anchor, text, *_ in rows],
    )
    short.commit()
    body.commit()
    _LENGTH_INDEX[key] = short
    _LENGTH_INDEX[(id(store), "length-body")] = body
    return short, body


def length_split(weight: float) -> Ranking:
    """The shipping index with the short fields normalised on their own lengths.

    `weight` scales the short-field table's contribution before the two BM25
    scores are added. At 0.0 this is `text` alone, which is the control that says
    how much the short fields were contributing at all.
    """

    def rank(store: SqliteStore, query: str) -> list[str]:
        terms = terms_of(query)
        if not terms:
            return []
        surface = " OR ".join(f'"{term}"' for term in terms)
        stems = " OR ".join(f'"{term}"' for term in dict.fromkeys(stem_text(terms)))
        short, body = _length_indexes(store)

        # The shipped abstention gate, asked of the same fields it is asked of
        # today: a literal foothold anywhere in the row.
        probe = body.execute(
            "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
            [f"{_BODY_SURFACE} : ({surface})"],
        ).fetchone()
        if probe is None:
            probe = short.execute(
                "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
                [f"{_SHORT_SURFACE} : ({surface})"],
            ).fetchone()
        if probe is None:
            return []

        scores: dict[str, float] = {}
        for conn, fields, stem_fields, weights in (
            (body, _BODY_SURFACE, _BODY_STEMS, (1.0,)),
            (short, _SHORT_SURFACE, _SHORT_STEMS, (3.0, 2.0, 0.5)),
        ):
            scale = 1.0 if conn is body else weight
            if scale == 0.0:
                continue
            match = f"{fields} : ({surface}) OR {stem_fields} : ({stems})"
            columns = [0.0, *weights, *(STEM_WEIGHT * w for w in weights)]
            placeholders = ", ".join("?" for _ in columns)
            for row in conn.execute(
                f"""
                SELECT anchor, bm25(chunks_fts, {placeholders}) AS score
                FROM chunks_fts WHERE chunks_fts MATCH ?
                """,
                [*columns, match],
            ):
                scores[str(row["anchor"])] = scores.get(str(row["anchor"]), 0.0) + scale * float(
                    row["score"]
                )
        return [anchor for anchor, _ in sorted(scores.items(), key=lambda item: item[1])][:DEPTH]

    return rank


def length_rrf(store: SqliteStore, query: str) -> list[str]:
    """The same two tables, fused by RRF instead of added.

    The obvious answer to why `length 1.0` breaks `relationship`: two BM25 scores
    over tables with different average lengths are not on one scale, so adding
    them is a scale error rather than a fusion. RRF at spec 04 §3's k=60 is
    scale-free by construction and needs no new constant — it is the only
    combination this project already sanctions.
    """
    terms = terms_of(query)
    if not terms:
        return []
    surface = " OR ".join(f'"{term}"' for term in terms)
    stems = " OR ".join(f'"{term}"' for term in dict.fromkeys(stem_text(terms)))
    short, body = _length_indexes(store)
    if (
        body.execute(
            "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
            [f"{_BODY_SURFACE} : ({surface})"],
        ).fetchone()
        is None
        and short.execute(
            "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
            [f"{_SHORT_SURFACE} : ({surface})"],
        ).fetchone()
        is None
    ):
        return []

    fused: dict[str, float] = {}
    for conn, fields, stem_fields, weights in (
        (body, _BODY_SURFACE, _BODY_STEMS, (1.0,)),
        (short, _SHORT_SURFACE, _SHORT_STEMS, (3.0, 2.0, 0.5)),
    ):
        match = f"{fields} : ({surface}) OR {stem_fields} : ({stems})"
        columns = [0.0, *weights, *(STEM_WEIGHT * w for w in weights)]
        placeholders = ", ".join("?" for _ in columns)
        ranked = conn.execute(
            f"""
            SELECT anchor, bm25(chunks_fts, {placeholders}) AS score
            FROM chunks_fts WHERE chunks_fts MATCH ?
            ORDER BY score LIMIT ?
            """,
            [*columns, match, DEPTH],
        ).fetchall()
        for position, row in enumerate(ranked, 1):
            anchor = str(row["anchor"])
            fused[anchor] = fused.get(anchor, 0.0) + 1.0 / (RRF_K + position)
    return [anchor for anchor, _ in sorted(fused.items(), key=lambda item: -item[1])][:DEPTH]


LENGTH_FAMILY: Final[tuple[tuple[str, Ranking], ...]] = (
    ("length 0.0", length_split(0.0)),
    ("length 0.5", length_split(0.5)),
    ("length 1.0", length_split(1.0)),
    ("length 2.0", length_split(2.0)),
    ("length rrf", length_rrf),
)
"""`length 0.0` is the control — `text` alone, no short fields at all."""


HEADING_FAMILY: Final[tuple[tuple[str, Ranking], ...]] = (
    ("heading 2.0/2.0", heading_split(2.0, 2.0)),
    ("heading 2.0/1.0", heading_split(2.0, 1.0)),
    ("heading 2.0/0.75", heading_split(2.0, 0.75)),
    ("heading 2.0/0.5", heading_split(2.0, 0.5)),
    ("heading 2.0/0.25", heading_split(2.0, 0.25)),
    ("heading 2.0/0.0", heading_split(2.0, 0.0)),
    ("heading 3.0/0.5", heading_split(3.0, 0.5)),
    ("heading 3.0/1.0", heading_split(3.0, 1.0)),
    ("heading 3.0/3.0", heading_split(3.0, 3.0)),
    ("heading 4.0/0.5", heading_split(4.0, 0.5)),
    ("heading 4.0/4.0", heading_split(4.0, 4.0)),
)
"""Three controls, and they bracket the shipped setting on every side.

`heading 2.0/2.0` is the *unsplit* control: one field split in two, both halves
at the weight the single field had, which is what the index did before roadmap
4.36. `heading 2.0/0.5` is the **revert** control — what shipped between 4.36 and
4.42 — so its row is the price of going back. `heading 3.0/0.5` is what ships
now, so it must score what `baseline (ships)` scores; if it does not, this family
is measuring something other than the field weights (ADR-0063, ADR-0070)."""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SECTION_FAMILY: Final[tuple[tuple[str, Ranking], ...]] = (
    ("section:max", section_max),
    ("section-fts", section_fts),
    ("section-open", section_open),
    ("section-ordered", section_ordered),
    ("section-fused", section_fused),
    ("open-if-candidate", open_if_candidate),
)
"""Every way of making a section the unit that has been measured (ADR-0041)."""


def score(
    root: Path, set_name: str, rank: Ranking
) -> tuple[tuple[float, float, float], dict[str, float]]:
    """Overall (nDCG@10, MRR, R@10) and per-slice nDCG@10 for one strategy."""
    cases = [case for case in load_cases(root / "eval" / f"{set_name}.jsonl") if case.answerable]
    totals = [0.0, 0.0, 0.0]
    per_slice: dict[str, list[float]] = {}
    with SqliteStore.open(root, read_only=True) as store:
        for case in cases:
            judged = {relevant.anchor: relevant.grade for relevant in case.relevant}
            credited = credit_judgments(rank(store, case.query), judged)
            value = ndcg_at_k(credited, judged, K)
            totals[0] += value
            totals[1] += reciprocal_rank(credited, judged)
            totals[2] += recall_at_k(credited, judged, K)
            for member in case.slices or ():
                per_slice.setdefault(member.value, []).append(value)
    count = len(cases)
    means = {name: sum(xs) / len(xs) for name, xs in sorted(per_slice.items())}
    return (totals[0] / count, totals[1] / count, totals[2] / count), means


def oracle(root: Path, set_name: str) -> tuple[float, float, float]:
    """The family's ceiling: per case, the best of the chunk unit and every
    section-unit strategy. **No planner can beat this**, because it chooses with
    foresight the query does not carry — which is what makes it a bound rather
    than a proposal."""
    cases = [case for case in load_cases(root / "eval" / f"{set_name}.jsonl") if case.answerable]
    chunk = family = best = 0.0
    with SqliteStore.open(root, read_only=True) as store:
        for case in cases:
            judged = {relevant.anchor: relevant.grade for relevant in case.relevant}

            def of(rank: Ranking, judged: dict[str, int] = judged, case=case) -> float:  # type: ignore[no-untyped-def]
                return ndcg_at_k(credit_judgments(rank(store, case.query), judged), judged, K)

            here = of(baseline)
            theirs = max(of(rank) for _, rank in SECTION_FAMILY)
            chunk += here
            family += theirs
            best += max(here, theirs)
    count = len(cases)
    return chunk / count, family / count, best / count


def _report(
    label: str, root: Path, set_name: str, strategies: Sequence[tuple[str, Ranking]]
) -> None:
    slices: dict[str, dict[str, float]] = {}
    for name, rank in strategies:
        _SECTION_INDEX.clear()
        _TOKEN_INDEX.clear()
        _HEADING_INDEX.clear()
        (ndcg, mrr, recall), means = score(root, set_name, rank)
        slices[name] = means
        print(f"{label:<13} {name:<18} {ndcg:8.3f} {mrr:7.3f} {recall:7.3f}")
    if set_name != "release":
        return
    names = sorted({name for means in slices.values() for name in means})
    print(f"\n{'  per-slice nDCG@10':<32}" + "".join(f"{name:>14}" for name in names))
    for name, means in slices.items():
        print(f"  {name:<30}" + "".join(f"{means.get(n, 0.0):14.4f}" for n in names))
    ships = slices["baseline (ships)"]
    print(f"\n  {'gate G3: worst slice vs baseline':<30}")
    for name, means in slices.items():
        if name in {"baseline (ships)", "grep (incumbent)"}:
            continue
        worst = min(((means.get(n, 0.0) - ships[n]) / ships[n], n) for n in names if ships.get(n))
        verdict = "FAIL" if worst[0] < -0.02 else "pass"
        print(f"  {name:<30}{worst[1]:>14} {worst[0]:+8.1%}  {verdict}")
    print()


def stem_frequencies(root: Path, case_set: str) -> list[tuple[str, int, int, set[str]]]:
    """Every judged query's stems, by how many chunks carry them.

    Roadmap 4.28's first candidate fix was an IDF floor on the stem side: drop a
    stem that is too common to be evidence. This is the table that refuses it.
    A function word and a corpus's own central noun are not separable by document
    frequency — and BM25 already discounts by IDF, so the stem that broke
    `u-0007` is *rare* rather than common (ADR-0057).
    """
    stems: dict[str, set[str]] = {}
    for case in load_cases(root / "eval" / f"{case_set}.jsonl"):
        terms = _FTS_TERM.findall(case.query)
        for term, stem in zip(terms, stem_text(terms), strict=True):
            stems.setdefault(stem, set()).add(term.lower())
    with SqliteStore.open(root, read_only=True) as store:
        connection = store._connection  # noqa: SLF001 - a measurement, not a caller
        total = int(connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0])
        counts: dict[str, int] = dict.fromkeys(stems, 0)
        for row in connection.execute(
            "SELECT text_stem, title_stem, heading_path_stem FROM chunks_fts"
        ):
            carried: set[str] = set()
            for column in row:
                carried.update((column or "").split())
            for stem in stems:
                if stem in carried:
                    counts[stem] += 1
    return [
        (stem, counts[stem], total, stems[stem]) for stem in sorted(stems, key=lambda s: -counts[s])
    ]


def _report_stems(label: str, root: Path, case_set: str) -> None:
    rows = stem_frequencies(root, case_set)
    print()
    print(f"{label}/{case_set}: {rows[0][2] if rows else 0} chunks")
    for stem, count, total, words in rows[:12]:
        share = count / total if total else 0.0
        print(f"   {count:5} {share:6.1%}  {stem:14} <- {', '.join(sorted(words))}")


def main() -> int:
    flags = {arg for arg in sys.argv[1:] if arg.startswith("--")}
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    ours = Path(args[0]) if args else ROOT
    corpora = [("ours", ours), ("uv", ROOT / "eval" / "corpora" / "uv-docs")]
    strategies: list[tuple[str, Ranking]] = [
        ("baseline (ships)", baseline),
        *QUERY_FAMILY,
        *TOKENIZER_FAMILY,
        *HEADING_FAMILY,
        *LENGTH_FAMILY,
        *SECTION_FAMILY,
        ("length>=60", length_prior(60)),
        ("length>=120", length_prior(120)),
        ("coverage-first", coverage_first),
        ("grep-formula", grep_formula),
        ("grep (incumbent)", grep),
    ]

    print(f"{'set':<13} {'strategy':<18} {'nDCG@10':>8} {'MRR':>7} {'R@10':>7}")
    for corpus, root in corpora:
        _report(f"{corpus}/dev", root, "dev", strategies)
    if "--release" in flags:
        print("\n=== the gate view: release sets, per slice. Read, never tuned against. ===\n")
        for corpus, root in corpora:
            _report(f"{corpus}/release", root, "release", strategies)
    if "--stems" in flags:
        print()
        print("=== stem document frequency: why an IDF floor cannot find a function word ===")
        for corpus, root in corpora:
            for set_name in ("dev", "release"):
                _report_stems(corpus, root, set_name)
        print(
            "\nRead the two corpora together. Nothing separates the classes: on this "
            "repository `what` reaches 37 % of chunks and `adr` 60 %; on uv's "
            "documentation `mean` reaches 2.8 % and `uv` itself 88 %. A floor that "
            "dropped the first of each pair would drop the second (ADR-0057)."
        )
    if "--oracle" in flags:
        print("\n=== the family's ceiling — no planner can beat it ===\n")
        print(f"{'set':<13} {'chunk':>8} {'family':>8} {'oracle':>8} {'vs grep':>9}")
        for corpus, root in corpora:
            for set_name in ("dev", "release"):
                _SECTION_INDEX.clear()
                _TOKEN_INDEX.clear()
                chunk, family, best = oracle(root, set_name)
                (theirs, _, _), _ = score(root, set_name, grep)
                print(
                    f"{corpus + '/' + set_name:<13} {chunk:8.3f} {family:8.3f} "
                    f"{best:8.3f} {best - theirs:+9.3f}"
                )

    print("\nDev sets are what tuning may read. A candidate that wins here still has to")
    print("clear gate G3 on the release sets - `--release` shows that view, and every")
    print("strategy in this file has failed one or the other (ADR-0031, ADR-0041).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
