#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Score candidate re-rankings of the lexical leg (ADR-0031, ADR-0041).

    python tools/measure_ranking.py [repository-root]      # the dev sets
    python tools/measure_ranking.py --release              # ...and the gate view
    python tools/measure_ranking.py --oracle               # the family's ceiling

Roadmap 4.8 is open because the grep incumbent beats the product on the second
corpus. This is where a candidate fix is measured before it is proposed, and it
reads the **dev** sets by default on purpose: the release sets are what gate G3
judges the outcome with, and a change developed against them cannot be told apart
from a change fitted to them (spec 04 §7.1).

Ten candidate strategies live here, and **all ten are refused**. Four rows by
ADR-0031 (a length prior at two floors, coverage-first, section aggregation) and
six more by ADR-0041 — the section-level *indexing* hypothesis ADR-0031 named as
the next thing to try, in every form it has, plus the incumbent's own ranking
function. `--release` prints the per-slice deltas gate G3 reads, and
`--oracle` prints the ceiling of the whole family: the per-case best of every
section-unit strategy, which no planner can beat.

The strategies are kept rather than deleted. A refusal nobody can re-run is a
claim, and the next attempt should start from the numbers instead of from prose.
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
from mycelium.store.sqlite import _BM25_WEIGHTS, fts_query  # noqa: E402

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
            [*_BM25_WEIGHTS, match, depth],
        )
        .fetchall()
    )
    return [str(row["section"]) for row in rows]


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


def main() -> int:
    flags = {arg for arg in sys.argv[1:] if arg.startswith("--")}
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    ours = Path(args[0]) if args else ROOT
    corpora = [("ours", ours), ("uv", ROOT / "eval" / "corpora" / "uv-docs")]
    strategies: list[tuple[str, Ranking]] = [
        ("baseline (ships)", baseline),
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
    if "--oracle" in flags:
        print("\n=== the family's ceiling — no planner can beat it ===\n")
        print(f"{'set':<13} {'chunk':>8} {'family':>8} {'oracle':>8} {'vs grep':>9}")
        for corpus, root in corpora:
            for set_name in ("dev", "release"):
                _SECTION_INDEX.clear()
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
