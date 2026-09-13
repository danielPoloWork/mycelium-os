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

The last check here is about the *renderer* rather than the corpus: the PDFs say which typst
made them, `pyproject.toml` says which one is installed to remake them, and the two have to
agree or the pin is describing a rendering nobody has (roadmap 5.27, ADR-0098).
"""

import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from mycelium.eval.cases import load_cases

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from build_ingested_corpus import require_pandoc, require_typst  # noqa: E402

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


# ---------------------------------------------------------------------------
# Collapsed anchors: several judged units, one twin chunk (roadmap 5.33)
# ---------------------------------------------------------------------------


def test_merging_takes_the_highest_grade_that_landed_on_the_chunk() -> None:
    """The rule, on its own, without a corpus (ADR-0104)."""
    from build_ingested_cases import Landing, merge_landings

    anchors, collapsed = merge_landings(
        [
            Landing(twin="t.md#/0", source="s.md#section/", case_id="u-1", grade=3),
            Landing(twin="t.md#/0", source="s.md#/0", case_id="u-1", grade=2),
            Landing(twin="t.md#/1", source="s.md#other/0", case_id="u-1", grade=1),
        ]
    )
    assert [(item.anchor, item.grade) for item in anchors] == [("t.md#/0", 3), ("t.md#/1", 1)]
    assert collapsed == ["t.md#/0"]


def test_one_source_anchor_reaching_one_chunk_is_not_a_collapse() -> None:
    """Two cases judging the same passage is ordinary, and true of the source too."""
    from build_ingested_cases import Landing, merge_landings

    anchors, collapsed = merge_landings(
        [Landing(twin="t.md#/0", source="s.md#a/0", case_id="u-1", grade=3)]
    )
    assert [(item.anchor, item.grade) for item in anchors] == [("t.md#/0", 3)]
    assert collapsed == []


@pytest.fixture(scope="module")
def receipt() -> dict[str, object]:
    payload = (CORPUS / "eval" / "carry.json").read_text(encoding="utf-8")
    parsed: dict[str, object] = json.loads(payload)
    return parsed


def test_the_receipt_records_every_chunk_several_judged_units_landed_on(
    receipt: dict[str, object],
) -> None:
    """The `collapsed` block agrees with the anchor map it sits beside.

    Derived from the same run, so the two can only disagree if one was edited by
    hand — which is the failure `--check` exists to catch and this makes visible
    in a unit test rather than a four-minute regeneration.
    """
    anchors = receipt["anchors"]
    collapsed = receipt["collapsed"]
    assert isinstance(anchors, dict) and isinstance(collapsed, dict)

    by_twin: dict[str, set[str]] = {}
    for source, row in anchors.items():
        by_twin.setdefault(row["twin"], set()).add(source)

    expected = {twin for twin, sources in by_twin.items() if len(sources) > 1}
    assert set(collapsed) == expected

    for twin, landed in collapsed.items():
        assert {item["source"] for item in landed} == by_twin[twin]


def test_a_collapsed_case_keeps_the_highest_grade_its_units_carried(
    receipt: dict[str, object],
) -> None:
    """What the twin's set says about a merged chunk matches what reached it."""
    collapsed = receipt["collapsed"]
    assert isinstance(collapsed, dict)

    carried = {
        case.case_id: {item.anchor: item.grade for item in case.relevant}
        for name in ("dev.jsonl", "release.jsonl")
        for case in load_cases(CORPUS / "eval" / name)
    }
    checked = 0
    for twin, landed in collapsed.items():
        by_case: dict[str, list[int]] = {}
        for item in landed:
            by_case.setdefault(item["case"], []).append(item["grade"])
        for case_id, grades in by_case.items():
            if len(grades) < 2:
                continue  # collapsed across cases, not within one: nothing merged
            assert carried[case_id][twin] == max(grades)
            checked += 1
    assert checked, "no within-case collapse in the committed sets - update this test"


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


# ---------------------------------------------------------------------------
# The renderer the PDFs name, and the one the repository declares (roadmap 5.27)
# ---------------------------------------------------------------------------

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
_PIN = re.compile(r"^typst==(?P<version>[0-9][0-9A-Za-z.\-]*)$")


def pinned_typst() -> str:
    """The exact version `[dependency-groups] render` declares."""
    groups = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]
    render = groups["render"]
    assert len(render) == 1, "the render group is the PDF renderer and nothing else"
    match = _PIN.match(render[0])
    assert match is not None, f"the renderer must be pinned exactly, not {render[0]!r}"
    return match.group("version")


def test_the_declared_renderer_is_the_one_that_made_every_committed_pdf() -> None:
    """The pin is read out of the corpus, not chosen (ADR-0098).

    typst writes `Creator: Typst <version>` into each PDF it compiles, so the
    provenance of these renderings lives in the artifacts themselves — a better
    record than a manifest field, because nothing can restamp it without
    recompiling. The pin exists to say which typesetter a *re-render* would use,
    and it is only meaningful while it names the one already on disk. Bumping it
    without re-rendering, or re-rendering without bumping it, fails here.

    The bytes are still not reproducible — typst stamps a creation timestamp, and
    ADR-0039 measured that `SOURCE_DATE_EPOCH` does not fix it. This pins the
    typesetter, which is what governs layout and the text layer a parser reads
    back, not the bytes.
    """
    pdfium = pytest.importorskip("pypdfium2", reason="the `ingest` extra is not installed")
    expected = f"Typst {pinned_typst()}"
    pdfs = sorted((CORPUS / "sources").rglob("*.pdf"))
    assert pdfs, "the ingested corpus should hold rendered PDFs"
    creators = {path.name: pdfium.PdfDocument(path).get_metadata_value("Creator") for path in pdfs}
    disagree = {name: value for name, value in creators.items() if value != expected}
    assert not disagree, (
        f"pyproject pins {expected!r}; these PDFs were made by something else: {disagree}. "
        "Re-render with `uv sync --group render && python tools/build_ingested_corpus.py "
        "--render`, or correct the pin to what the artifacts say"
    )


def test_a_pending_pdf_without_the_renderer_names_the_command_that_installs_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It refuses *before* writing, and the message is a command (roadmap 5.27).

    The import used to fail at the first PDF — after pandoc had already written
    several DOCX and HTML files — so a maintainer met it with a half-rendered
    provenance act on disk and `pip install typst` as the only guidance. Neither
    half was right: the group is not on PyPI's side of the problem, and the
    default sync deliberately removes it again.
    """
    import build_ingested_corpus

    monkeypatch.setattr(build_ingested_corpus.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(SystemExit) as caught:
        require_typst(9)
    message = str(caught.value)
    assert "uv sync --group render" in message
    assert "9 PDF(s)" in message
    assert "pip install" not in message


def test_nothing_is_required_when_no_pdf_is_pending() -> None:
    """A render that has only DOCX and HTML to write needs no typesetter."""
    assert require_typst(0) == ""


# ---------------------------------------------------------------------------
# pandoc: a floor, not a pin - checked directly, not asserted (roadmap 5.34)
# ---------------------------------------------------------------------------


def test_no_committed_source_carries_a_pandoc_identifier() -> None:
    """The premise `require_pandoc` is built on: there is nothing to check later.

    A typst PDF stamps `Creator: Typst <version>` into itself; pandoc's docx
    writer stamps a hard-coded `Microsoft Word 12.0.0` regardless of which
    pandoc ran, and its html5 writer (without `--standalone`) emits a bare
    fragment with no `<head>` at all. Read directly from every committed
    source so the claim in the generator's docstring is a fact, not folklore.
    """
    sources = sorted((CORPUS / "sources").rglob("*.docx")) + sorted(
        (CORPUS / "sources").rglob("*.html")
    )
    assert sources, "the ingested corpus should hold rendered DOCX and HTML"
    for path in sources:
        text = path.read_bytes()
        assert b"pandoc" not in text.lower(), f"{path.name} names pandoc; update the docstring"


def test_a_pending_render_without_pandoc_names_the_command_that_installs_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It refuses before writing, the same shape `require_typst` does."""
    import build_ingested_corpus

    monkeypatch.setattr(build_ingested_corpus.shutil, "which", lambda name: None)  # noqa: ARG005
    with pytest.raises(SystemExit) as caught:
        require_pandoc(7)
    message = str(caught.value)
    assert "pandoc.org/installing.html" in message
    assert "7 DOCX/HTML document(s)" in message
    assert "D-013" in message


def test_a_pandoc_below_the_floor_is_refused_by_its_own_reported_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import build_ingested_corpus

    monkeypatch.setattr(
        build_ingested_corpus.shutil,
        "which",
        lambda name: "/usr/bin/pandoc",  # noqa: ARG005
    )
    monkeypatch.setattr(
        build_ingested_corpus.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="pandoc 2.9.2.1"),  # noqa: ARG005
    )
    with pytest.raises(SystemExit) as caught:
        require_pandoc(2)
    assert "reports 2.9.2.1" in str(caught.value)
    assert "3.x or newer" in str(caught.value)


def test_nothing_is_required_when_only_pdfs_are_pending() -> None:
    """A render with no DOCX or HTML to write needs no pandoc."""
    assert require_pandoc(0) == ""
