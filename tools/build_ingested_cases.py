#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Carry the second corpus's frozen judgements across to its ingested twin.

    python tools/build_ingested_cases.py

Writes `eval/corpora/uv-docs-ingested/eval/{dev,release}.jsonl` and, since roadmap
6.23, `tasks.jsonl` beside them: the judged case sets and the agent-task suite are
both *judgements about passages*, they cross the same projection, and a second
tool would be a second answer to the question this one already answers. The file
name says `cases` for the reason its `--check` exists at all — renaming a
generator that CI, the ladder and four ADRs call by name is a change to
everything except what it does.

**Nothing here is judged.** Every query, every grade, every slice — and every task
prompt and kind — is copied verbatim from `eval/corpora/uv-docs/eval/*`, which
were frozen before this corpus existed and cannot have been fitted to it. What
this tool computes is the *anchor*: where, in the document projected from a
rendered copy of the same file, the passage the judgement already picked ended up.

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
   the judged text's *distinct* word tokens the candidate contains. The
   best-covered chunk wins.
4. Below `MIN_COVERAGE` nothing wins. The anchor is dropped, the case is reported,
   and if a case loses every anchor it is dropped whole — because a case whose
   answer is not in the corpus is not a hard case, it is a broken one.
5. The winner's **`whole`** is recorded beside its coverage: the share of the
   passage's word *occurrences* it can account for. Coverage answers "are the
   passage's words here"; `whole` answers "is the passage here". Below
   `MIN_WHOLE` the anchor is dropped too — not because a better candidate
   exists, but because none of them is the passage (roadmap 5.41).
6. Several judged units can land on **one** twin chunk, because a headingless PDF
   is one page-sized block where the Markdown had sections. Within a case they
   are merged into a single anchor at the highest grade that reached it; across
   cases nothing is merged, because nothing can be. Either way the chunk and
   every unit that reached it are recorded under `collapsed` in the receipt.

## What a collapsed anchor means, and why no case is dropped for it

A twin chunk that several *distinct* judged units land on is a distinction the
projection destroyed. Four cases — `u-1005`, `u-1006`, `u-1019`, `u-1024` — judge
`python-versions-pdf-*.md#/0` as their grade-3 answer where their sources named
four different passages of `python-versions.md`; a retriever that returns that one
block has answered all four, and on the Markdown it would have had to find four.

That is not a defect to repair. It is the measurement: a corpus that cannot
represent a distinction is exactly what this twin exists to detect, and dropping
the cases would delete the finding rather than report it (roadmap 5.33). What it
*does* mean is that such a case's twin score is not comparable to its source's —
it is the largest reason a twin case outscores the document it was projected from
(ADR-0097) — so `tools/measure_projection_cost.py` marks every case whose judged
unit shares its chunk, and the receipt names the chunk and the units.

The one shape that **is** a defect is the same case landing two units on one
chunk, because the carried file then names an anchor twice and `run_evaluation`
builds `{anchor: grade}` — the duplicate disappeared into whichever grade came
last, which was the lower one. `u-1001` and `u-1003` both did this for four
milestones and nothing on either side said so. They are merged now, at the highest
grade, which is a claim about the chunk and not about the score: with one judged
anchor left, the grade cancels out of every metric the harness computes.

## Why `whole` is recorded, and what coverage cannot see

Coverage is over distinct tokens, so it is nearly blind to a passage that got
**split** between two chunks — a section's vocabulary repeats across its
examples while its topic sentence occurs once, so the chunk holding the examples
can score high while the sentence that states the rule went next door. That is
not hypothetical either: it is `u-1004` (roadmap 5.31, ADR-0102). Its section
carries at coverage **0.9533**, comfortably the best of the document's six
chunks — and `whole` is **0.8955**, because a PDF page boundary fell mid-section
and left the opening in the chunk before. The case scores 0.000 on the twin and
0.387 on its source, and for a session nobody could say why from the receipt.

`whole` still does **not** choose the anchor, and that refusal is the point of
ADR-0102: which of two plausible chunks best holds a passage is a question about
the projection, and re-deciding it by a second metric is how a carry starts being
fitted. What roadmap 5.41 added is the other half, which choosing and rejecting do
not share — **a floor**. Refusing to claim a passage is present when *no* candidate
holds it is not a preference between candidates; it is the same statement
`MIN_COVERAGE` already makes, on the metric that can see a split.

It had to be added because coverage cannot see one. `u-0017` (query `uv venv`)
grades uv's feature list at 1; the HTML lane turns that list into a heading per
item, so the 201-token passage is shattered across five chunks and **none holds
more than a third of it**. Coverage is over distinct tokens and a feature list's
vocabulary is nearly uniform across its items, so the winner was decided by
scaffolding: `uv pip compile: …` at 0.5269, against the chunk that actually holds
`uv venv: Create a new virtual environment.` at 0.4731. The floor sat *between*
them and kept the one that never mentions the command.

The distribution is what makes a floor defensible rather than tuned. Over the 63
mapped anchors, `u-0017`'s 0.3383 is the **lowest**, and the next is 0.5088 — a
gap of 0.17, the widest at the bottom of the range. Every value from 0.35 to 0.50
drops exactly that one anchor and nothing else, so the constant sits in the middle
of a basin rather than on a cliff.

Three sibling anchors of the same document — `u-0006`, `u-0018` and `u-1007`, all
grading a feature list — were **already** dropped by `MIN_COVERAGE` at 0.39-0.42,
for the same underlying reason. After 5.41 all four are dropped, which is the
consistency the floor buys: one projection shape, one outcome.

What was refused, and why the query is not consulted: the most direct repair is to
keep the candidate that contains the query's own terms, and it is the one thing
this tool must not do. A carry that reads the query stops being a projection
measurement and starts handing the twin a chunk that lexically matches what is
about to be searched for — which is ADR-0027's trap with the evidence removed.
Preferring the same heading slug was measured too and is worse: on `u-0003`,
`u-0020` and `u-1019` the same-slug candidate scores 0.19, 0.39 and 0.21 against
winners of 0.75, 0.91 and 0.62, because the projection re-heads a document and the
slug that survives is a stub.

Measured over the current receipt, 43 of 53 anchors land whole and the lowest is
0.5088; the two largest
negatives in `tools/measure_projection_cost.py`'s per-case block are the two
lowest `whole` values among scored cases, and the largest *gain* is also a split
passage — so this is a number to read a case with, never a predictor.

## Why both builds are clean, and why that is the whole defect

Both sides of the coverage comparison are chunker output, so the carry is only
meaningful if both corpora are compiled the way the repository compiles them.
`build()` is **incremental**: it recompiles what its `doc_state` says is dirty,
and a chunking *policy* that arrived from outside `mycelium.toml` — as it does
when a measurement session forces one — leaves nothing dirty to notice. A store
built that way survives on disk, and the next carry reads it as if it were the
default.

That is not hypothetical: it is [BUG-0018]. A leftover `pack_atomic` store made
this tool compare packed judged text against unpacked twin chunks, four anchors
fell through the coverage floor, and the committed sets stopped reproducing. So
both builds here are `clean=True`, and `--check` regenerates and compares rather
than trusting that they still match.

Coverage rather than F1 on purpose: an ingested chunk is often *larger* than the
Markdown chunk it corresponds to (a PDF page holds several sections), and
penalising it for that would measure the chunker, not the projection.

Every dropped anchor is printed, and every *mapped* one is written to
`eval/carry.json` beside the sets — the receipt. Printing alone was not enough:
the coverage of a surviving anchor is what moves first when something drifts, and
a number nobody commits cannot show up in a diff. The closest mapped anchor sits
at **0.6207** against the 0.50 floor, and the closest on `whole` at **0.5088**
against 0.40 — room a reviewer should be able to see rather than discover. The
anchors that fall *through* either floor are printed as drops and are not in the
receipt at all, which is why the four from uv's feature list do not appear there.

A silent drop would quietly make the ingested corpus easier than its twin, which
is the one way this comparison could lie.
"""

import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import (  # noqa: E402
    encode_cases,
    load_cases,
    validate_judged_set,
    write_cases,
)
from mycelium.eval.tasks import (  # noqa: E402
    AgentTask,
    encode_tasks,
    load_tasks,
    write_tasks,
)
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

MIN_WHOLE = 0.4
"""Two fifths of the passage's word *occurrences* have to be in the winner.

The companion floor, and the one that catches a **split** passage, which coverage
is nearly blind to: a shattered section leaves every fragment sharing the whole
section's vocabulary, so coverage stays respectable while no fragment holds the
passage. Above this floor the carry claims "the passage is here"; below it the
honest claim is that it is not anywhere, and the anchor is dropped and reported.

Sited in a basin, not on a cliff: the lowest `whole` among the 63 mapped anchors
is 0.3383 and the next is 0.5088, so anything in [0.35, 0.50] drops the same
single anchor (roadmap 5.41). It does not *choose* between candidates — that is
still refused (ADR-0102).
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


def whole(judged: Sequence[str], candidate: Sequence[str]) -> float:
    """The share of the passage's word *occurrences* `candidate` can account for.

    A multiset intersection, so a word the passage uses six times and the
    candidate twice contributes two rather than one — which is exactly the
    difference that makes this see a split where :func:`coverage` cannot. 1.0
    means the passage is in this chunk entire; anything less means part of it is
    somewhere else, and the remainder is usually the neighbouring chunk.

    Not used to choose an anchor and not floored. It is recorded (roadmap 5.31).
    """
    if not judged:
        return 0.0
    have = Counter(candidate)
    return sum(min(count, have[word]) for word, count in Counter(judged).items()) / len(judged)


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


@dataclass(frozen=True, slots=True)
class Landing:
    """One judged unit, where it came from and where it landed (roadmap 5.33)."""

    twin: str
    source: str
    case_id: str
    grade: int


def merge_landings(landings: Sequence[Landing]) -> tuple[tuple[RelevantAnchor, ...], list[str]]:
    """One judged anchor per twin chunk, at the highest grade that landed on it.

    A headingless PDF is one page-sized chunk where the Markdown had sections, so
    two judged units of the *same case* can land on it — `u-1001` and `u-1003`
    each judge `indexes.md#defining-an-index/` at 3 and the document preamble at
    2, and both carry onto `indexes-pdf-*.md#/0` (roadmap 5.33).

    Merging is not a choice about scoring, because there is none to make: for a
    case left holding a single judged anchor the grade **cancels** in every
    metric the harness computes — nDCG divides by an ideal built from the same
    gain, recall counts anchors, and reciprocal rank reads only a position. The
    choice is about what the file *says*, and the highest grade is what is true
    of the merged chunk: it contains the passage that was graded highest, and
    calling it a 2 would understate what a retriever returning it actually found.

    Writing the anchor twice instead — which is what this tool did until 5.33 —
    says something `run_evaluation` cannot represent: it builds `{anchor: grade}`
    and the duplicate disappears into whichever grade happened to come last,
    which was the *lower* one. Nothing reported it, on either side.

    Returns the merged anchors in the case's own order, and the twin anchors that
    received more than one judged unit.
    """
    by_twin: dict[str, list[Landing]] = {}
    for landing in landings:
        by_twin.setdefault(landing.twin, []).append(landing)

    anchors = tuple(
        RelevantAnchor(anchor=twin, grade=max(item.grade for item in landed))
        for twin, landed in by_twin.items()
    )
    collapsed = [
        twin for twin, landed in by_twin.items() if len({item.source for item in landed}) > 1
    ]
    return anchors, collapsed


CARRY_RECEIPT = "carry.json"
"""Where each mapped anchor's coverage is recorded, beside the sets it explains."""

TASK_CARRY_RECEIPT = "tasks-carry.json"
"""The same receipt for the agent-task suite, in a file of its own.

Two receipts rather than one document with two sections, because `carry.json` is
read by `tools/measure_projection_cost.py` and pinned by tests: a schema bump
there would be a change to the *case* carry's record, taken in a change that does
not touch a single judged case (roadmap 6.23).
"""


def map_anchor(
    source_store: SqliteStore,
    twin_store: SqliteStore,
    manifest: dict[str, dict[str, str]],
    anchor: str,
) -> tuple[str, float, float] | str:
    """Where one judged anchor's passage landed in the twin, or why it did not.

    The whole derivation, in one place, because the cases and the agent tasks
    carry the *same* judgements across the same projection and two copies of this
    would be two answers to one question (roadmap 6.23). Returns the winning twin
    anchor with its coverage and `whole`, or a sentence saying why nothing won.
    """
    entry = manifest.get(anchor.partition("#")[0])
    if entry is None:
        return "no twin"
    wanted = tokens(judged_text(source_store, anchor))
    best, score, share = None, 0.0, 0.0
    for chunk in chunks_of_path(twin_store, entry["evidence"]):
        candidate = tokens(chunk.text)
        found = coverage(wanted, candidate)
        if found > score:
            best, score = chunk.anchor, found
            share = whole(wanted, candidate)
    if best is None or score < MIN_COVERAGE:
        return f"best coverage {score:.2f}"
    if share < MIN_WHOLE:
        # Not "a better candidate exists" — none of them is the passage. Coverage
        # cannot see a split, so it ranked the fragments of a shattered section by
        # their shared scaffolding (roadmap 5.41).
        return (
            f"coverage {score:.2f} but whole {share:.2f}: the passage is split, "
            f"and {best} holds too little of it to be it"
        )
    return best, score, share


def carry_tasks(
    tasks: Sequence[AgentTask],
    source_store: SqliteStore,
    twin_store: SqliteStore,
    manifest: dict[str, dict[str, str]],
) -> tuple[tuple[AgentTask, ...], list[tuple[str, str, float, float]], list[str], list[str]]:
    """Carry the agent-task suite across, and drop a task that loses any anchor.

    Nothing here is judged either: the prompt, the kind and the note are copied
    verbatim from `eval/corpora/uv-docs/eval/tasks.jsonl`, and only the anchor is
    computed — the same refusal to re-judge that keeps the carried *cases*
    measuring retrieval rather than the agent that wrote them (ADR-0027,
    ADR-0039).

    **A task that loses one anchor is dropped whole**, where a case keeps the
    anchors that survived. The two are scored differently and the difference is
    the reason: a case is graded per anchor, so losing one costs it the grade it
    held; a task is `found` only when **every** required anchor reached the agent,
    so dropping one silently *weakens the conjunction* — the carried task would be
    easier than the task it claims to be, and the twin's rate would rise for a
    reason that has nothing to do with retrieval. Dropping it says the honest
    thing instead: this projection cannot put the evidence this task asks for in
    front of a model (roadmap 6.23).

    Two required anchors that land on **one** twin chunk are merged, exactly as
    they are for a case: a headingless page is one block where the Markdown had
    sections, the suite reads `requires` as a set, and a file naming an anchor
    twice says something the harness cannot represent (roadmap 5.33).
    """
    carried: list[AgentTask] = []
    mapped: list[tuple[str, str, float, float]] = []
    dropped: list[str] = []
    collapsed: list[str] = []
    for task in tasks:
        landed: list[tuple[str, str, float, float]] = []
        lost: list[str] = []
        for anchor in task.requires:
            result = map_anchor(source_store, twin_store, manifest, anchor)
            if isinstance(result, str):
                lost.append(f"{anchor} — {result}")
                continue
            landed.append((anchor, *result))
        if lost or not landed:
            dropped.append(f"{task.task_id}: {'; '.join(lost) or 'no required anchor'}")
            continue
        mapped.extend(landed)
        twins = tuple(dict.fromkeys(twin for _, twin, _, _ in landed))
        if len(twins) < len(landed):
            collapsed.append(f"{task.task_id}: {twins[0]}")
        carried.append(task.model_copy(update={"requires": twins}))
    return tuple(carried), mapped, dropped, collapsed


def encode_task_receipt(mapped: Sequence[tuple[str, str, float, float]], dropped: int) -> str:
    """The task carry as committed evidence, in the shape `carry.json` already has."""
    document = {
        "schema_version": "mycelium/eval-task-carry/v1",
        "min_coverage": MIN_COVERAGE,
        "min_whole": MIN_WHOLE,
        "dropped_tasks": dropped,
        "anchors": {
            source: {"twin": twin, "coverage": round(score, 4), "whole": round(share, 4)}
            for source, twin, score, share in sorted(mapped)
        },
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def encode_receipt(
    mapped: Sequence[tuple[str, str, float, float]], landings: Sequence[Landing]
) -> str:
    """The carry as committed evidence: source anchor → twin anchor, and two numbers.

    Sorted and rounded so two runs of the same inputs produce the same bytes, and
    so a review reads a diff of *numbers* — the coverage of a surviving anchor is
    what moves first when the derivation drifts.

    `whole` joined `coverage` at roadmap 5.31, because the two answer different
    questions and only the second one was on the record: coverage says the
    passage's words are here, `whole` says the passage is. A split passage moved
    neither number enough to notice, and the case that exposed it took a session
    to explain from a receipt that could have said so (ADR-0102).

    `collapsed` joined both at roadmap 5.33, and it is the same argument a third
    time. A twin chunk that several *distinct* judged units land on is a passage
    the projection can no longer tell apart — four cases judge
    `python-versions-pdf-*.md#/0` as their grade-3 answer where their sources
    named four different passages — and that is not a defect to repair but the
    measurement this twin exists to take. It is recorded per twin anchor with
    every judged unit that reached it, so "two units of one case" (which merges,
    :func:`merge_landings`) and "one unit each from four cases" (which does not)
    are the same fact read two ways rather than two bookkeeping systems.
    """
    by_twin: dict[str, list[Landing]] = {}
    for landing in landings:
        by_twin.setdefault(landing.twin, []).append(landing)

    document = {
        "schema_version": "mycelium/eval-carry/v2",
        "min_coverage": MIN_COVERAGE,
        "min_whole": MIN_WHOLE,
        "anchors": {
            source: {"twin": twin, "coverage": round(score, 4), "whole": round(share, 4)}
            for source, twin, score, share in sorted(mapped)
        },
        "collapsed": {
            twin: [
                {"case": item.case_id, "grade": item.grade, "source": item.source}
                for item in sorted(landed, key=lambda item: (item.case_id, item.source))
            ]
            for twin, landed in sorted(by_twin.items())
            if len({item.source for item in landed}) > 1
        },
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:  # noqa: C901 - a report is a sequence of stated steps
    check_only = "--check" in sys.argv[1:]
    manifest_path = INGESTED_CORPUS / "provenance.json"
    if not manifest_path.is_file():
        print(f"missing {manifest_path}; run tools/build_ingested_corpus.py first")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Clean, not incremental: see the module docstring and [BUG-0018]. A derived
    # artifact that inherits whatever the local store happens to hold records the
    # machine it was generated on, not the corpus it claims to describe.
    # `pin_identity=False`: both corpora are committed, and a generator that
    # dirties 81 tracked files every time it runs is a generator nobody can run
    # from a clean tree (roadmap 4.14/4.15, ADR-0046).
    build(MARKDOWN_CORPUS, clean=True, pin_identity=False)
    build(INGESTED_CORPUS, clean=True, pin_identity=False)

    dropped_anchors: list[str] = []
    dropped_cases: list[str] = []
    mapped: list[tuple[str, str, float, float]] = []
    landings: list[Landing] = []
    collapsed: list[str] = []

    with (
        SqliteStore.open(MARKDOWN_CORPUS, read_only=True) as source_store,
        SqliteStore.open(INGESTED_CORPUS, read_only=True) as twin_store,
    ):
        written: dict[str, tuple[EvalCase, ...]] = {}
        for name in ("dev", "release"):
            carried: list[EvalCase] = []
            for case in load_cases(MARKDOWN_CORPUS / "eval" / f"{name}.jsonl"):
                landed: list[Landing] = []
                for relevant in case.relevant:
                    result = map_anchor(source_store, twin_store, manifest, relevant.anchor)
                    if isinstance(result, str):
                        dropped_anchors.append(f"{case.case_id}: {relevant.anchor} — {result}")
                        continue
                    best, score, share = result
                    mapped.append((relevant.anchor, best, score, share))
                    landed.append(
                        Landing(
                            twin=best,
                            source=relevant.anchor,
                            case_id=case.case_id,
                            grade=relevant.grade,
                        )
                    )

                if case.answerable and not landed:
                    dropped_cases.append(case.case_id)
                    continue
                landings.extend(landed)
                # Several judged units of one case can land on one twin chunk, and
                # a set naming an anchor twice is a shape the harness cannot
                # represent (roadmap 5.33).
                anchors, merged = merge_landings(landed)
                collapsed.extend(f"{case.case_id}: {twin}" for twin in merged)
                carried.append(case.model_copy(update={"relevant": anchors}))
            written[name] = tuple(carried)

        errors, warnings = validate_judged_set(written["dev"] + written["release"], twin_store)

        # The agent-task suite travels the same way and for the same reason: it
        # is a judgement about passages, the twin holds the same passages in a
        # different shape, and re-judging it here would answer a question about
        # this agent rather than about retrieval (roadmap 6.23, ADR-0027).
        source_tasks = load_tasks(MARKDOWN_CORPUS / "eval" / "tasks.jsonl")
        tasks, task_mapped, dropped_tasks, collapsed_tasks = carry_tasks(
            source_tasks, source_store, twin_store, manifest
        )
        rotted = [
            f"{task.task_id}: {anchor}"
            for task in tasks
            for anchor in task.requires
            if twin_store.get_chunk(anchor) is None
        ]

    for anchor, best, score, share in mapped:
        # Stated as the fact the number is, never as a verdict: 0.98 and 0.51
        # are both "not all here" and they do not mean the same thing, so the
        # reader is given the share and no threshold (roadmap 5.31).
        split = "  (part of the passage is elsewhere)" if share < 1.0 else ""
        print(f"  {score:.2f}  whole {share:.2f}  {anchor}  ->  {best}{split}")
    for line in dropped_anchors:
        print(f"  dropped anchor  {line}")
    for case_id in dropped_cases:
        print(f"  dropped case    {case_id} — no anchor survived")
    for line in collapsed:
        # Printed as what it is: the projection lost a distinction the judgement
        # was written to rely on. The case is kept, because a corpus that cannot
        # represent a distinction is what this twin exists to measure (5.33).
        print(f"  merged anchors  {line} — two judged units, one twin chunk")
    for line in dropped_tasks:
        # A dropped *task*, never a dropped anchor: `requires` is a conjunction, so
        # carrying it one anchor lighter would hand the twin an easier task than
        # the one it claims to be (roadmap 6.23).
        print(f"  dropped task    {line}")
    for line in collapsed_tasks:
        print(f"  merged anchors  {line} — two required passages, one twin chunk")
    for warning in warnings:
        print(f"  warning: {warning}")
    if errors or rotted:
        print("The carried set does not hold against the ingested corpus:")
        for error in (*errors, *(f"{line} — no such chunk" for line in rotted)):
            print(f"  {error}")
        return 1

    destination = INGESTED_CORPUS / "eval"
    receipt = encode_receipt(mapped, landings)
    task_receipt = encode_task_receipt(task_mapped, len(dropped_tasks))
    summary = (
        f"carried {len(written['dev'])} dev and {len(written['release'])} release cases; "
        f"{len(mapped)} anchors mapped, {len(dropped_anchors)} dropped, "
        f"{len(collapsed)} merged onto a shared chunk; "
        f"carried {len(tasks)} of {len(source_tasks)} agent tasks"
    )

    if check_only:
        # The point of --check: a derived artifact whose generator no longer
        # reproduces it is the defect, not the trigger for a quiet regeneration.
        differences: list[str] = []
        for name in ("dev", "release"):
            path = destination / f"{name}.jsonl"
            expected = encode_cases(written[name])
            actual = path.read_text(encoding="utf-8") if path.is_file() else ""
            if expected != actual:
                differences.append(path.relative_to(ROOT).as_posix())
        for path, expected in (
            (destination / CARRY_RECEIPT, receipt),
            (destination / "tasks.jsonl", encode_tasks(tasks)),
            (destination / TASK_CARRY_RECEIPT, task_receipt),
        ):
            actual = path.read_text(encoding="utf-8") if path.is_file() else ""
            if expected != actual:
                differences.append(path.relative_to(ROOT).as_posix())
        print(summary)
        if differences:
            print("the carried set does not reproduce from this tree:")
            for relative in differences:
                print(f"  {relative}")
            print("re-run `python tools/build_ingested_cases.py` and review the diff")
            return 1
        print("carried set reproduces byte-for-byte")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", written["dev"])
    write_cases(destination / "release.jsonl", written["release"])
    (destination / CARRY_RECEIPT).write_text(receipt, encoding="utf-8", newline="\n")
    write_tasks(destination / "tasks.jsonl", tasks)
    (destination / TASK_CARRY_RECEIPT).write_text(task_receipt, encoding="utf-8", newline="\n")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
