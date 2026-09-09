#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-run gate G2, record its verdict, and refuse to let that record go stale.

    python tools/measure_hybrid_gate.py                  # every corpus, both sets
    python tools/measure_hybrid_gate.py --cases u-1023 u-1024
    python tools/measure_hybrid_gate.py <corpus-root>
    python tools/measure_hybrid_gate.py --check          # G2's runner (roadmap 4.40)
    python tools/measure_hybrid_gate.py --record         # write the verdict down

Three questions, and the file exists because none of them was being asked.

**Is the recorded verdict still about this product?** — `--check`, and it is what
`tools/verify.py` and CI run. G2's arms move independently: a verdict is only
about the shipped product for as long as the lexical leg it was measured against
is the one that ships. So the verdict is *committed*, with the fingerprints that
date it — the retrieval configuration, the corpora, the judged sets — and the
check fails when any of them has moved since. That much needs no model, which is
why CI can run it. **With** the model present the check goes further and
re-measures, comparing verdicts rather than floats: ONNX inference is not
promised identical across machines (ADR-0017), so a float comparison would fail
on a second machine for a reason that has nothing to do with retrieval.

**Does hybrid earn the default yet?** Gate G2 is a *comparison* — hybrid against
lexical on the same cases, ≥ +5 % nDCG@10 with no slice worse than −2 % (spec 04
§7.3) — and it only runs when someone passes `--retriever hybrid`. CI never does,
because CI has no embedding model (D-013: nothing is downloaded unless
configured). So G2's verdict has been carried as prose since ADR-0017 while the
lexical leg it is measured against moved four times underneath it: packing
(roadmap 4.15), stemming (4.19), function-word stripping (4.28), and the heading
split (4.36). A gate whose two arms move independently and are never re-compared
is a claim, not a gate.

**Which leg can reach this case at all?** When a judged case scores 0.0000, the
useful question is not "why is the ranking bad" but *where the judged anchor sits
in each candidate list*: the lexical list, the vector list, and the fused one.
Those three numbers separate a reach failure from a ranking failure from a
fusion-depth failure, and they are what roadmap 4.33 turned out to need — the two
cases it was filed for have different answers on all three.

**What this file cannot see** is the same blind spot `measure_ranking.py` has: it
scores answerable cases only, so gate G4 is outside its view.

**And it deliberately does not print latency.** It did, for one revision, and the
numbers moved by 10× between two runs of the same tree on the same machine
(lexical p95 15 ms then 141 ms) while every nDCG stayed identical to four
decimals. A figure that unstable printed beside "budget 150 ms" invites a
conclusion it cannot support, so gate G5 is left to the harness, which measures it
where the product actually runs. The scores here are deterministic; that is the
difference.

**What `--check` deliberately does not do is fail because hybrid lost.** "Ship
lexical-only" is a legitimate G2 outcome — the milestone goal says so in as many
words — so a runner that exited non-zero on it would be red on every correct
build. What it fails on is a verdict that no longer describes the product, which
is a mistake someone can act on. That distinction is why `mycelium eval
--retriever hybrid --gate` could not have been the runner: `--gate` exits
non-zero when *any* gate reports `passed=False`, and for G2 that was the shipped
configuration. G2 reports rather than fails since roadmap 4.41, so that command
runs — but it still cannot be the runner, because one set cannot decide a default
decided over every frozen release set (ADR-0069).

The measurement itself needs the embedding model. Without it the table cannot be
printed at all, and the file says so rather than printing a lexical-only one that
looks like a result.
"""

import argparse
import json
import statistics
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.__about__ import __version__  # noqa: E402
from mycelium.config import RetrievalConfig  # noqa: E402
from mycelium.embedding import (  # noqa: E402
    DEFAULT_MODEL_ID,
    Embedder,
    EmbeddingError,
    build_embedder,
)
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.harness import (  # noqa: E402
    G2_OVERALL_MIN,
    G2_SLICE_FLOOR,
    case_set_digest,
    corpus_fingerprint_of,
    g2_regressions,
)
from mycelium.eval.metrics import credit_judgments, ndcg_at_k  # noqa: E402
from mycelium.eval.retrievers import build_retriever  # noqa: E402
from mycelium.retrieval import VECTOR_CANDIDATES, retrieval_identity  # noqa: E402
from mycelium.sdk.types import EvalCase  # noqa: E402
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, SqliteStore  # noqa: E402

CORPORA: Final = (
    ("ours", ROOT),
    ("uv", ROOT / "eval" / "corpora" / "uv-docs"),
    ("uv-ingested", ROOT / "eval" / "corpora" / "uv-docs-ingested"),
)

SETS: Final = ("dev", "release")

DEPTH: Final = 10
"""The k every judged metric in this project is taken at."""

VERDICT_PATH: Final = ROOT / "eval" / "g2-verdict.json"
VERDICT_SCHEMA: Final = "mycelium/g2-verdict/v0"

DATED_CORPORA: Final = ("uv", "uv-ingested")
"""Which corpora's fingerprints the currency check is allowed to fail on.

`ours` is this repository, and every pull request moves it — this file, an ADR, a
roadmap line. Its content fingerprint therefore changes on changes that cannot
touch retrieval at all, and a check that failed on it would demand a
re-measurement of gate G2 for a typo in a README. So `ours` is measured, recorded
and *reported*; the two vendored corpora, which change only when someone vendors
something, are what the check is keyed on.

That is the same distinction gate G3 already makes between what it enforces and
what it reports, and it is made for the same reason: a control that fires on
everything selects for being ignored."""


@dataclass(frozen=True, slots=True)
class Scored:
    """One retriever's scores over one judged set."""

    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _score(cases: Sequence[EvalCase], retriever: object) -> Scored:
    per_case: dict[str, float] = {}
    slices: dict[str, list[float]] = {}
    for case in cases:
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        ranked = retriever.search(case.query, DEPTH)  # type: ignore[attr-defined]
        score = ndcg_at_k(credit_judgments(ranked, judged), judged, DEPTH)
        per_case[case.case_id] = score
        for name in case.slices:
            slices.setdefault(name, []).append(score)
    overall = statistics.fmean(per_case.values()) if per_case else 0.0
    return Scored(
        overall=overall,
        per_slice={name: statistics.fmean(values) for name, values in slices.items()},
        per_case=per_case,
    )


def _relative(after: float, before: float) -> float:
    """The gate's own convention: a zero baseline cannot regress (harness `_relative`)."""
    if before == 0.0:
        return 1.0 if after > 0.0 else 0.0
    return (after - before) / before


def _verdict(
    hybrid: Scored, lexical: Scored, slices: Mapping[str, Sequence[str]] | None = None
) -> tuple[bool, str, list[str]]:
    """The two conditions, and the cases behind any slice that trips the second.

    Naming them is what roadmap 4.41 turned out to need: it was filed believing
    the trips were noise a thin slice cannot distinguish from a change, and
    `conceptual -13.1%` on its own cannot tell you either way. Decomposed, six of
    the seven are one case, and every one is a large real loss (ADR-0069).
    """
    overall = _relative(hybrid.overall, lexical.overall)
    regressions = g2_regressions(
        hybrid.per_slice,
        lexical.per_slice,
        {
            name: [
                (case_id, lexical.per_case.get(case_id, 0.0), hybrid.per_case.get(case_id, 0.0))
                for case_id in ids
            ]
            for name, ids in (slices or {}).items()
        },
    )
    passed = overall >= G2_OVERALL_MIN and not regressions
    detail = f"{overall:+.1%} overall (needs {G2_OVERALL_MIN:+.0%})"
    if regressions:
        detail += f"; regressions past {G2_SLICE_FLOOR:.0%}: {', '.join(regressions)}"
    return passed, detail, regressions


def _legs(
    store: SqliteStore, embedder: Embedder, case: EvalCase
) -> list[tuple[str, int, str, str, str]]:
    """Where each judged anchor sits in the lexical, vector and fused lists.

    The whole point of the row: a case scoring 0.0000 is a *reach* failure if the
    anchor is absent from both candidate lists, a *ranking* failure if it is deep
    in one of them, and a *fusion-depth* failure if it is shallow in the vector
    list and still misses the top ten.
    """
    lexical = store.search_chunks(case.query, limit=100_000)
    lexical_rank = {hit.chunk.anchor: index for index, hit in enumerate(lexical, 1)}
    vectors = store.search_vectors(
        embedder.embed_query(case.query), model_id=embedder.model_id, limit=100_000
    )
    vector_rank = {hit.chunk.anchor: index for index, hit in enumerate(vectors, 1)}
    fused = build_retriever("hybrid", store, embedder).search(case.query, DEPTH)
    fused_rank = {anchor: index for index, anchor in enumerate(fused, 1)}

    def place(rank: int | None, population: int) -> str:
        return "-" if rank is None else f"{rank}/{population}"

    return [
        (
            anchor.anchor,
            anchor.grade,
            place(lexical_rank.get(anchor.anchor), len(lexical)),
            place(vector_rank.get(anchor.anchor), len(vectors)),
            "-" if anchor.anchor not in fused_rank else str(fused_rank[anchor.anchor]),
        )
        for anchor in case.relevant
    ]


@dataclass(frozen=True, slots=True)
class SetVerdict:
    """G2 on one judged set: both arms, the verdict, and what dates it."""

    name: str
    lexical: float
    hybrid: float
    passed: bool
    detail: str
    regressions: tuple[str, ...]
    cases: int
    cases_digest: str
    per_slice: dict[str, tuple[float, float, int]]

    def as_record(self) -> dict[str, Any]:
        return {
            "verdict": "pass" if self.passed else "fail",
            "lexical_ndcg_at_10": round(self.lexical, 6),
            "hybrid_ndcg_at_10": round(self.hybrid, 6),
            "detail": self.detail,
            "regressions": list(self.regressions),
            "cases": self.cases,
            "cases_digest": self.cases_digest,
            "per_slice": {
                name: {
                    "lexical": round(before, 6),
                    "hybrid": round(after, 6),
                    "cases": count,
                }
                for name, (before, after, count) in sorted(self.per_slice.items())
            },
        }


def _measure_set(label: str, root: Path, set_name: str, embedder: Embedder) -> SetVerdict | None:
    """Score both arms on one set, or `None` when the set does not exist."""
    path = root / "eval" / f"{set_name}.jsonl"
    if not path.is_file():
        return None
    cases = [case for case in load_cases(path) if case.answerable]
    store = SqliteStore.open(root, read_only=True)
    try:
        lexical = _score(cases, build_retriever("mycelium", store))
        hybrid = _score(cases, build_retriever("hybrid", store, embedder))
    finally:
        store.close()

    by_slice: dict[str, list[str]] = {}
    for case in cases:
        for name in case.slices:
            by_slice.setdefault(name, []).append(case.case_id)

    passed, detail, regressions = _verdict(hybrid, lexical, by_slice)
    return SetVerdict(
        name=f"{label}/{set_name}",
        lexical=lexical.overall,
        hybrid=hybrid.overall,
        passed=passed,
        detail=detail,
        regressions=tuple(regressions),
        cases=len(cases),
        cases_digest=case_set_digest(cases),
        per_slice={
            name: (
                lexical.per_slice.get(name, 0.0),
                hybrid.per_slice.get(name, 0.0),
                sum(1 for case in cases if name in case.slices),
            )
            for name in sorted(set(lexical.per_slice) | set(hybrid.per_slice))
        },
    )


def _print_set(verdict: SetVerdict) -> None:
    print(
        f"{verdict.name:<20} lexical {verdict.lexical:.4f}  hybrid {verdict.hybrid:.4f}  "
        f"G2 {'pass' if verdict.passed else 'FAIL'}  {verdict.detail}"
    )
    for name, (before, after, count) in sorted(verdict.per_slice.items()):
        print(
            f"    {name:<14} {before:.4f} -> {after:.4f}  "
            f"({_relative(after, before):+.1%})  {count} case(s)"
        )


def _report_set(label: str, root: Path, set_name: str, embedder: Embedder) -> SetVerdict | None:
    verdict = _measure_set(label, root, set_name, embedder)
    if verdict is None:
        print(f"{label}/{set_name:<8} no such case set")
        return None
    _print_set(verdict)
    return verdict


def _report_cases(names: Sequence[str], embedder: Embedder) -> None:
    print(f"\n=== which leg reaches it (vector leg fuses its top {VECTOR_CANDIDATES}) ===\n")
    header = f"{'set':<20} {'case':<8} {'judged anchor':<58} {'gr':>2}"
    print(f"{header} {'lex':>10} {'vec':>10} {'fused':>5}")
    for label, root in CORPORA:
        for set_name in SETS:
            path = root / "eval" / f"{set_name}.jsonl"
            if not path.is_file():
                continue
            wanted = [case for case in load_cases(path) if case.case_id in set(names)]
            if not wanted:
                continue
            store = SqliteStore.open(root, read_only=True)
            try:
                for case in wanted:
                    for anchor, grade, lex, vec, fused in _legs(store, embedder, case):
                        where = f"{label + '/' + set_name:<20} {case.case_id:<8}"
                        print(
                            f"{where} {anchor[:58]:<58} {grade:>2} {lex:>10} {vec:>10} {fused:>5}"
                        )
            finally:
                store.close()


# ---------------------------------------------------------------------------
# The committed verdict, and whether it still describes this product
# ---------------------------------------------------------------------------


def decision_of(verdicts: Mapping[str, Any]) -> str:
    """Which profile the measurement supports: the *release* rows decide.

    Spec 04 §7.3 puts the burden on hybrid — it must earn the default — so
    anything short of clearing G2 on every frozen release set leaves the default
    where it is. Dev rows are what tuning may read and are recorded for that
    purpose; they do not vote (ADR-0027).
    """
    release = {name: row for name, row in verdicts.items() if str(name).endswith("/release")}
    if release and all(_verdict_of(row) == "pass" for row in release.values()):
        return "hybrid"
    return "lexical"


def _verdict_of(row: Any) -> str:
    if isinstance(row, SetVerdict):
        return "pass" if row.passed else "fail"
    return str(row.get("verdict", "")) if isinstance(row, dict) else ""


def build_record(verdicts: Sequence[SetVerdict], *, model_id: str) -> dict[str, Any]:
    """Assemble the record `--record` commits."""
    sets = {verdict.name: verdict.as_record() for verdict in verdicts}
    decision = decision_of({verdict.name: verdict for verdict in verdicts})
    return {
        "schema_version": VERDICT_SCHEMA,
        "recorded_at": datetime.now(tz=UTC).date().isoformat(),
        "decision": decision,
        "shipped_profile": RetrievalConfig().profile,
        "retrieval_identity": retrieval_identity(),
        "model_id": model_id,
        "toolchain": {"mycelium": __version__},
        "dated_corpora": list(DATED_CORPORA),
        "corpora": {
            label: {
                "content_digest": fingerprint.content,
                "chunks_digest": fingerprint.chunks,
                "dated": label in DATED_CORPORA,
            }
            for label, fingerprint in (
                (label, corpus_fingerprint_of(root)) for label, root in CORPORA
            )
        },
        "sets": sets,
    }


def read_record() -> dict[str, Any] | None:
    """The committed verdict, or `None` when there is none to read."""
    if not VERDICT_PATH.is_file():
        return None
    try:
        loaded = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def write_record(record: Mapping[str, Any]) -> Path:
    """Commit the verdict, deterministically formatted so a diff is readable."""
    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return VERDICT_PATH


def check_currency(record: Mapping[str, Any] | None) -> tuple[list[str], list[str]]:
    """Is the recorded verdict still about this product? `(failures, notes)`.

    Every criterion here is computable **without the embedding model**, which is
    the whole point: CI cannot re-measure G2, but it can refuse to let a verdict
    that no longer describes the product pass unnoticed (roadmap 4.40).
    """
    failures: list[str] = []
    notes: list[str] = []
    if record is None:
        return (
            [
                f"no recorded G2 verdict at {VERDICT_PATH.relative_to(ROOT).as_posix()}; "
                "run `python tools/measure_hybrid_gate.py --record` (needs the model)"
            ],
            notes,
        )
    if record.get("schema_version") != VERDICT_SCHEMA:
        failures.append(
            f"the recorded verdict declares {record.get('schema_version')!r} and this tool "
            f"reads {VERDICT_SCHEMA!r}"
        )
        return failures, notes

    recorded_at = str(record.get("recorded_at", "an unrecorded date"))
    toolchain = record.get("toolchain")
    built_by = toolchain.get("mycelium", "?") if isinstance(toolchain, dict) else "?"
    notes.append(f"recorded {recorded_at} on mycelium {built_by}, model {record.get('model_id')}")

    shipped = RetrievalConfig().profile
    if record.get("shipped_profile") != shipped:
        failures.append(
            f"the verdict was recorded against `[retrieval] profile = "
            f"{record.get('shipped_profile')!r}` and the shipped default is now {shipped!r}"
        )
    if record.get("decision") != shipped:
        failures.append(
            f"the measurement supports {record.get('decision')!r} and the shipped default is "
            f"{shipped!r}; flip the default or re-measure — a decision the product does not "
            "follow is not a decision"
        )

    identity = retrieval_identity()
    if record.get("retrieval_identity") != identity:
        failures.append(
            "the retrieval configuration changed since the verdict was recorded on "
            f"{recorded_at} (field weights, stem weight, stopwords, fusion constants or the "
            "FTS schema). G2 compares hybrid against *that* lexical leg, so the verdict is "
            "about a product that no longer exists: re-run "
            "`python tools/measure_hybrid_gate.py --record` (needs the model)"
        )
    else:
        notes.append(f"retrieval identity unchanged ({identity[:19]}…)")

    failures.extend(_check_corpora(record, notes))
    failures.extend(_check_sets(record, notes))
    return failures, notes


def _check_corpora(record: Mapping[str, Any], notes: list[str]) -> list[str]:
    """Have the corpora the verdict was measured on moved?"""
    failures: list[str] = []
    recorded = record.get("corpora")
    if not isinstance(recorded, dict):
        return ["the recorded verdict carries no corpus fingerprints"]
    for label, root in CORPORA:
        entry = recorded.get(label)
        if not isinstance(entry, dict):
            failures.append(f"the recorded verdict says nothing about the {label!r} corpus")
            continue
        if not (root / STORE_DIRNAME / STORE_FILENAME).is_file():
            notes.append(f"{label}: not built here, so its fingerprint was not compared")
            continue
        fingerprint = corpus_fingerprint_of(root)
        if fingerprint.chunks != entry.get("chunks_digest"):
            notes.append(f"{label}: chunk boundaries moved since the verdict was recorded")
        if fingerprint.content == entry.get("content_digest"):
            continue
        if label not in DATED_CORPORA:
            # Expected, and the reason `ours` is reported rather than gated.
            notes.append(f"{label}: content moved (reported, never gated - see DATED_CORPORA)")
            continue
        failures.append(
            f"the {label!r} corpus changed since the verdict was recorded; re-run "
            "`python tools/measure_hybrid_gate.py --record` (needs the model)"
        )
    return failures


def _check_sets(record: Mapping[str, Any], notes: list[str]) -> list[str]:
    """Have the judgements the verdict is a mean over moved?"""
    failures: list[str] = []
    recorded = record.get("sets")
    if not isinstance(recorded, dict):
        return ["the recorded verdict carries no judged sets"]
    for label, root in CORPORA:
        for set_name in SETS:
            path = root / "eval" / f"{set_name}.jsonl"
            if not path.is_file():
                continue
            entry = recorded.get(f"{label}/{set_name}")
            if not isinstance(entry, dict):
                failures.append(f"the recorded verdict says nothing about {label}/{set_name}")
                continue
            digest = case_set_digest([case for case in load_cases(path) if case.answerable])
            if digest == entry.get("cases_digest"):
                continue
            if label not in DATED_CORPORA:
                notes.append(f"{label}/{set_name}: judgements moved (reported, never gated)")
                continue
            failures.append(
                f"{label}/{set_name}'s judgements changed since the verdict was recorded; "
                "re-run `python tools/measure_hybrid_gate.py --record` (needs the model)"
            )
    return failures


def compare_measurement(
    record: Mapping[str, Any], measured: Sequence[SetVerdict], notes: list[str] | None = None
) -> list[str]:
    """Does a fresh measurement still reach the recorded verdicts?

    Verdicts, not floats. ADR-0017 declares the embedder non-deterministic across
    platforms and runtime versions, so two machines may legitimately differ in the
    fourth decimal; what may not differ is whether hybrid clears the bar. The
    numbers are printed beside the recorded ones so drift is visible without being
    gated on.

    **A flip on an undated corpus is a note, not a failure**, which is the same
    carve-out :func:`_check_corpora` and :func:`_check_sets` make and for the
    reason :data:`DATED_CORPORA` states: `ours` is this repository, so every pull
    request moves it. This function did not make it, and the omission had a shape
    — CI has no model and never re-measures, so only a contributor who *has* one
    saw it, and what they saw was `verify.py` going red because they wrote the ADR
    documenting their own change. That is the local-versus-CI divergence ADR-0059
    exists to remove, arriving through the one path that runs in only one of the
    two (roadmap 4.42, ADR-0070).

    What stays a failure is the **decision**: if the measurement no longer supports
    the default the record names, that is true wherever the drift came from.
    """
    failures: list[str] = []
    recorded = record.get("sets")
    if not isinstance(recorded, dict):
        return ["the recorded verdict carries no judged sets to compare against"]
    for verdict in measured:
        entry = recorded.get(verdict.name)
        if not isinstance(entry, dict):
            failures.append(f"{verdict.name} is measured here and absent from the record")
            continue
        was, now = str(entry.get("verdict")), "pass" if verdict.passed else "fail"
        if was == now:
            continue
        moved = (
            f"{verdict.name}: recorded {was}, measured {now} "
            f"(lexical {entry.get('lexical_ndcg_at_10')} -> {verdict.lexical:.4f}, "
            f"hybrid {entry.get('hybrid_ndcg_at_10')} -> {verdict.hybrid:.4f})"
        )
        if verdict.name.split("/", 1)[0] in DATED_CORPORA:
            failures.append(moved)
        elif notes is not None:
            notes.append(f"{moved} - undated corpus, reported (see DATED_CORPORA)")
    supported = decision_of({verdict.name: verdict for verdict in measured})
    if len(measured) == len(recorded) and supported != record.get("decision"):
        failures.append(
            f"the measurement now supports {supported!r} and the record says "
            f"{record.get('decision')!r}"
        )
    return failures


def _load_embedder() -> Embedder | None:
    """The embedder, or `None` when this machine has no model."""
    try:
        found = build_embedder(provider="local-onnx", model_id=DEFAULT_MODEL_ID)
    except EmbeddingError:
        return None
    return found


def run_check() -> int:
    """Gate G2's runner: currency always, and the measurement where it is possible."""
    record = read_record()
    failures, notes = check_currency(record)
    for note in notes:
        print(f"  {note}")

    if failures:
        # One cause, not a cascade. A record already known not to describe this
        # product would produce "the verdict flipped" as a *symptom* of the thing
        # above, and the remedy is the same command either way — which prints the
        # fresh table. Loading the model to say so twice would be the slow way to
        # be less clear.
        print("  G2 not re-measured: the recorded verdict is stale, and --record is the answer")
    elif (embedder := _load_embedder()) is None:
        # Named, not silent — the same shape the embeddings tests skip in. A run
        # that could not re-measure must say so, or "no output" reads as "passed".
        print(
            "  G2 not re-measured here: the hybrid arm needs the local embedding model, "
            "and nothing downloads it unless configured (D-013). The recorded verdict's "
            "currency is what was checked."
        )
    elif record is not None:
        measured = [
            verdict
            for label, root in CORPORA
            for set_name in SETS
            if (verdict := _measure_set(label, root, set_name, embedder)) is not None
        ]
        reported: list[str] = []
        drift = compare_measurement(record, measured, reported)
        failures.extend(drift)
        for note in reported:
            print(f"  {note}")
        if not drift:
            print(f"  G2 re-measured on {len(measured)} set(s): every gated verdict reproduced")
        for verdict in measured:
            _print_set(verdict)

    if failures:
        print("\ngate G2: the recorded verdict does not describe this product")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    decision = record.get("decision") if record else None
    print(f"\ngate G2: the recorded verdict is current - the default is {decision!r}")
    return 0


def run_record() -> int:
    """Re-measure G2 everywhere and commit the verdict."""
    embedder = _load_embedder()
    if embedder is None:
        print("recording a verdict needs the embedding model, and it is unavailable here")
        return 1
    measured = [
        verdict
        for label, root in CORPORA
        for set_name in SETS
        if (verdict := _measure_set(label, root, set_name, embedder)) is not None
    ]
    if not measured:
        print("no judged set could be measured; build the corpora first")
        return 1
    for verdict in measured:
        _print_set(verdict)
    record = build_record(measured, model_id=embedder.model_id)
    path = write_record(record)
    print(f"\nrecorded {len(measured)} set(s) in {path.relative_to(ROOT).as_posix()}")
    print(f"the measurement supports the {record['decision']!r} default")
    if record["decision"] != record["shipped_profile"]:
        print(
            f"...and the shipped default is {record['shipped_profile']!r}. "
            "That disagreement is a decision to make, and --check will fail until it is."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="one corpus root, or all three")
    parser.add_argument("--cases", nargs="*", default=[], help="per-leg view for these case ids")
    parser.add_argument(
        "--check",
        action="store_true",
        help="gate G2's runner: is the recorded verdict still about this product?",
    )
    parser.add_argument(
        "--record", action="store_true", help="re-measure everywhere and commit the verdict"
    )
    args = parser.parse_args()

    if args.check and args.record:
        print("--check and --record ask opposite questions; pass one")
        return 2
    if args.check:
        return run_check()
    if args.record:
        return run_record()

    embedder = _load_embedder()
    if embedder is None:
        print("the hybrid arm needs the embedding model, and it is unavailable here")
        print("nothing is printed rather than a lexical-only table that looks like a result.")
        print("`--check` is the form that works without it (roadmap 4.40).")
        return 1

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    print(f"{'set':<20} {'gate G2 — hybrid must earn the default (spec 04 §7.3)'}")
    for label, root in corpora:
        for set_name in SETS:
            _report_set(label, root, set_name, embedder)

    if args.cases:
        _report_cases(args.cases, embedder)

    print("\nDev sets are what tuning may read. G2's verdict is the release rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
