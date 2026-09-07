# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The third judged corpus holds together (roadmap 4.10).

Structural checks only, and deliberately so: whether the corpus *scores* well is the
evaluation's business and CI gates it (`eval / gates G1-G6`), and whether it still matches a
fresh ingestion is `build_ingested_corpus.py --check`'s (`ingest / lanes`). What is left over
is the part neither of those can see — whether the corpus still agrees with its own
provenance record, and whether the judgements carried onto it still point at documents that
are in it.

That matters because the corpus is *derived*. Its evidence documents are named after the
digest of the source they came from, so a re-render moves every filename, and a set of
judgements that quietly stopped pointing anywhere would score zero without anything saying
why (ADR-0039).
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from mycelium.eval.cases import load_cases

CORPUS = Path(__file__).parent.parent / "eval" / "corpora" / "uv-docs-ingested"
TWIN = Path(__file__).parent.parent / "eval" / "corpora" / "uv-docs"
FORMATS = ("docx", "html", "pdf")


@pytest.fixture(scope="module")
def manifest() -> dict[str, dict[str, str]]:
    payload = (CORPUS / "provenance.json").read_text(encoding="utf-8")
    parsed: dict[str, dict[str, str]] = json.loads(payload)
    return parsed


def test_the_manifest_names_every_document_of_the_twin(manifest: dict[str, dict[str, str]]) -> None:
    twin = {path.relative_to(TWIN).as_posix() for path in (TWIN / "docs").rglob("*.md")}
    assert set(manifest) == twin, "the ingested corpus and its Markdown twin differ in population"


def test_every_manifest_entry_points_at_files_that_exist(
    manifest: dict[str, dict[str, str]],
) -> None:
    for document, entry in manifest.items():
        assert (CORPUS / entry["source"]).is_file(), f"{document}: missing source"
        assert (CORPUS / entry["evidence"]).is_file(), f"{document}: missing evidence"


def test_no_evidence_document_is_unaccounted_for(manifest: dict[str, dict[str, str]]) -> None:
    # The other direction, which is the one that catches a stale file: a rename
    # leaves the old evidence document behind, and it would be indexed.
    on_disk = {
        path.relative_to(CORPUS).as_posix()
        for path in (CORPUS / "knowledge" / "evidence").glob("*.md")
    }
    assert on_disk == {entry["evidence"] for entry in manifest.values()}


def test_all_three_formats_are_present(manifest: dict[str, dict[str, str]]) -> None:
    counts = {fmt: sum(1 for e in manifest.values() if e["format"] == fmt) for fmt in FORMATS}
    assert all(counts[fmt] > 0 for fmt in FORMATS), (
        f"an ingestion corpus missing a format: {counts}"
    )


def judged_documents() -> set[str]:
    return {
        relevant.anchor.partition("#")[0]
        for name in ("dev.jsonl", "release.jsonl")
        for case in load_cases(TWIN / "eval" / name)
        for relevant in case.relevant
    }


def test_the_judged_documents_take_the_formats_in_rotation(
    manifest: dict[str, dict[str, str]],
) -> None:
    """The assignment is a rotation over the recorded order, not over sorted paths.

    Asserted rather than trusted: an assignment chosen after seeing a result is
    the one way the per-format comparison could be made to say what we wanted.

    The order is *recorded* since roadmap 4.26 rather than recomputed by sorting,
    because sorting made the corpus unable to grow — a newly judged document
    sorts between existing ones and re-rolls the format of every document after
    it, and those renderings are committed provenance (ADR-0039, ADR-0056).
    """
    order = json.loads((CORPUS / "format-rotation.json").read_text(encoding="utf-8"))
    assert [manifest[path]["format"] for path in order] == [
        FORMATS[index % len(FORMATS)] for index in range(len(order))
    ]


def test_every_judged_document_has_a_recorded_slot() -> None:
    """A judgement pointing at a document with no recorded format has no plan.

    The other direction is deliberately *not* asserted: append-only means a
    document that stops being judged keeps its slot, so the record may be a
    strict superset of what is judged today.
    """
    order = json.loads((CORPUS / "format-rotation.json").read_text(encoding="utf-8"))
    missing = sorted(judged_documents() - set(order))
    assert not missing, f"judged with no recorded format slot: {missing}"


def test_the_recorded_order_holds_each_document_once() -> None:
    order = json.loads((CORPUS / "format-rotation.json").read_text(encoding="utf-8"))
    assert len(order) == len(set(order)), "a repeated slot would double-assign a format"


def test_a_newly_judged_document_appends_and_moves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The property the whole change exists for (roadmap 4.26).

    Inserting a document that sorts *first* must leave every existing assignment
    exactly where it was, and take the next slot itself.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    import build_ingested_corpus as builder

    monkeypatch.setattr(builder, "markdown_documents", lambda: iter(()))
    before = builder.assignment()
    order = builder.rotation_order()

    intruder = "docs/aaa-sorts-first.md"
    after = builder.assignment(judged=(*order, intruder))

    assert {path: after[path] for path in order} == {path: before[path] for path in order}
    assert after[intruder] == FORMATS[len(order) % len(FORMATS)]


@pytest.mark.parametrize("name", ["dev.jsonl", "release.jsonl"])
def test_carried_judgements_point_into_this_corpus(
    name: str, manifest: dict[str, dict[str, str]]
) -> None:
    evidence = {entry["evidence"] for entry in manifest.values()}
    for case in load_cases(CORPUS / "eval" / name):
        for relevant in case.relevant:
            document = relevant.anchor.partition("#")[0]
            assert document in evidence, f"{case.case_id}: {document} is not in the corpus"


@pytest.mark.parametrize("name", ["dev.jsonl", "release.jsonl"])
def test_a_carried_case_keeps_the_query_and_the_grade_it_was_given(name: str) -> None:
    """Only the anchor is derived. Everything a judgement *is* comes across untouched.

    If a query or a grade could drift, the two corpora would no longer be
    measuring the same thing and the paired comparison would be meaningless.
    """
    original = {case.case_id: case for case in load_cases(TWIN / "eval" / name)}
    for case in load_cases(CORPUS / "eval" / name):
        source = original[case.case_id]
        assert case.query == source.query
        assert case.slices == source.slices
        assert case.answerable == source.answerable
        # An anchor may be *dropped* in the carry when nothing in the twin covers
        # the passage; it may never be added, and a grade may never be rewritten.
        carried = Counter(item.grade for item in case.relevant)
        given = Counter(item.grade for item in source.relevant)
        assert carried <= given, f"{case.case_id}: grades changed in the carry"


def test_a_projected_document_carries_no_pinned_identity() -> None:
    """`mycelium build` pins `mycelium_id`; the projector does not write one.

    Committing a built tree would make the corpus stop matching a fresh ingestion,
    which is what `build_ingested_corpus.py --check` compares — so the state that
    is committed has to be the projected one.
    """
    for path in (CORPUS / "knowledge" / "evidence").glob("*.md"):
        head = path.read_text(encoding="utf-8").split("---", 2)[1]
        assert "mycelium_id" not in head, f"{path.name} was committed after a build"


def test_every_evidence_document_names_its_source_relatively() -> None:
    """BUG-0017: an absolute path here would be one machine's layout, committed."""
    for path in (CORPUS / "knowledge" / "evidence").glob("*.md"):
        head = path.read_text(encoding="utf-8").split("---", 2)[1]
        assert 'source: "file:sources/' in head, f"{path.name} carries a non-portable source"
