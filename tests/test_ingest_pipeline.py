# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evidence lane end to end (roadmap 4.2): acquire, store, guard, parse, store — and
the order those five happen in, which is the part that is a decision rather than a list."""

import shutil
from pathlib import Path

import pytest

from mycelium.ingest import (
    Custody,
    Quarantine,
    Registry,
    encode_kir,
    encode_report,
    ingest_source,
    quarantine_root,
    write_projection,
)
from mycelium.ingest.errors import (
    ConnectorError,
    GuardError,
    LossBudgetError,
    ParseError,
    UnsupportedMediaTypeError,
)
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.sdk.identity import canonical_json, digest_bytes
from mycelium.sdk.types import CustodyKind, QuarantineStage, SourceTrust

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
HOSTILE = FIXTURES / "hostile"
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None


@pytest.fixture(scope="module")
def registry() -> Registry:
    names = ["markdown", "docling", "pdf"] + (["pandoc"] if HAVE_PANDOC else [])
    return Registry.resolve(parsers=names, connectors=["file"], roots=[FIXTURES, HOSTILE])


@pytest.fixture
def mycelium_dir(tmp_path: Path) -> Path:
    return tmp_path / ".mycelium"


@pytest.mark.parametrize(
    ("name", "parser_id"),
    [("source.md", "markdown"), ("source.docx", "docling"), ("text-layer.pdf", "pdf")],
)
def test_a_source_ends_up_in_custody_with_its_kir(
    name: str, parser_id: str, registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / name), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)

    assert result.parser_id == parser_id
    assert custody.get(result.original.digest) == (FIXTURES / name).read_bytes()
    assert custody.get(result.kir_digest) == encode_kir(result.kir)

    original = custody.record(result.original.digest)
    kir_record = custody.record(result.kir_digest)
    assert original is not None and kir_record is not None
    assert original.kind is CustodyKind.ORIGINAL
    assert original.kir_digest == result.kir_digest
    assert kir_record.kind is CustodyKind.KIR
    assert kir_record.derived_from == original.digest
    # The parser that produced it is on the record, so a snapshot can explain
    # which engine compiled which document (spec 05 §4.2).
    assert kir_record.connector == parser_id


def test_the_kir_blob_is_canonical_json(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.md"), doc_id=DOC_ID)
    stored = Custody(mycelium_dir).get(result.kir_digest)
    assert stored is not None
    # Canonical, so the digest of a compiled document is a fact about the
    # document rather than about the machine that compiled it (spec 03 §1).
    assert stored.decode("utf-8") == canonical_json(result.kir.model_dump(mode="json"))
    assert result.kir_digest == digest_bytes(stored)


def test_ingesting_twice_changes_nothing(registry: Registry, mycelium_dir: Path) -> None:
    first = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    second = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert second.original == first.original
    assert second.kir_digest == first.kir_digest
    assert second.fidelity_digest == first.fidelity_digest
    assert second.projection == first.projection
    kinds = sorted(record.kind.value for record in Custody(mycelium_dir).records())
    assert kinds == ["fidelity", "kir", "original"], "one of each, not two"


def test_the_original_is_kept_even_when_the_parse_is_refused(
    registry: Registry, mycelium_dir: Path
) -> None:
    with pytest.raises(ParseError):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "bomb.docx"), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)
    records = list(custody.records())
    assert [record.kind for record in records] == [CustodyKind.ORIGINAL]
    assert custody.get(records[0].digest) == (HOSTILE / "bomb.docx").read_bytes()
    assert records[0].kir_digest is None, "nothing compiled, so nothing linked"


def test_a_source_outside_the_roots_never_reaches_custody(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# nope\n", encoding="utf-8")
    with pytest.raises(ConnectorError, match="outside the declared root"):
        ingest_source(mycelium_dir, registry, str(outside), doc_id=DOC_ID)
    # Custody is for what was acquired; a refused acquisition acquired nothing.
    assert not Custody(mycelium_dir).root.exists()


def test_a_media_type_no_parser_reads_is_refused_before_the_write(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    (tmp_path / "page.html").write_text("<p>x</p>", encoding="utf-8")
    lexical_only = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    with pytest.raises(UnsupportedMediaTypeError):
        ingest_source(mycelium_dir, lexical_only, str(tmp_path / "page.html"), doc_id=DOC_ID)
    assert not Custody(mycelium_dir).root.exists()


def test_the_ingested_document_carries_the_identity_it_was_given(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert result.kir.doc_id == DOC_ID
    assert result.kir.source_digest == result.original.digest


# ---------------------------------------------------------------------------
# The fidelity report, the budget, and the projection (roadmap 4.3)
# ---------------------------------------------------------------------------


def test_the_fidelity_report_is_stored_and_linked(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)

    assert custody.get(result.fidelity_digest) == encode_report(result.report)
    record = custody.record(result.fidelity_digest)
    assert record is not None
    assert record.kind is CustodyKind.FIDELITY
    assert record.derived_from == result.original.digest
    # And the original names it, so a build holding only the digest can find it.
    assert result.original.fidelity_digest == result.fidelity_digest


def test_a_clean_source_reports_no_loss(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert result.report.lost == 0
    assert result.report.elements > 0
    assert result.report.parser == result.parser_id


def test_a_source_over_budget_is_refused_but_still_accounted_for(
    registry: Registry, mycelium_dir: Path
) -> None:
    """The order in ADR-0034: the report is stored before the budget is applied.

    A refusal with no evidence behind it is not a diagnosis — an operator needs to
    see *what* was lost to decide whether to raise the budget or drop the source.
    """
    with pytest.raises(ParseError, match="did not survive parsing"):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "no-text-layer.pdf"), doc_id=DOC_ID)
    kinds = [record.kind for record in Custody(mycelium_dir).records()]
    assert CustodyKind.ORIGINAL in kinds
    assert CustodyKind.FIDELITY in kinds, "the report survives the refusal"


def test_the_budget_can_be_raised_to_admit_a_total_loss(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(
        mycelium_dir,
        registry,
        str(HOSTILE / "no-text-layer.pdf"),
        doc_id=DOC_ID,
        max_failed_elements=1.0,
    )
    assert result.report.loss == 1.0
    # The projection says so where a person reads it, not only in the report.
    assert "[!missing]" in result.projection.text


def test_the_projection_is_written_under_the_evidence_folder(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    written = write_projection(tmp_path, result)
    assert written == tmp_path / result.projection.path
    assert written.parent.name == "evidence"
    assert written.read_text(encoding="utf-8") == result.projection.text


def test_writing_the_same_projection_twice_changes_nothing(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    first = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    written = write_projection(tmp_path, first)
    stamp = written.stat().st_mtime_ns
    second = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert write_projection(tmp_path, second) == written
    assert written.stat().st_mtime_ns == stamp, "an unchanged source leaves no diff"


def test_ingesting_writes_nothing_into_the_repository_by_itself(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    # `ingest_source` writes only into `.mycelium/`; putting a file into someone's
    # Git working tree is `write_projection`'s decision to be asked for.
    ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert not (tmp_path / "knowledge").exists()


# ---------------------------------------------------------------------------
# `[sources]` — trust stamped at acquisition (roadmap 4.5, D-021)
# ---------------------------------------------------------------------------


def test_trust_is_resolved_from_the_uri_the_connector_produced(
    registry: Registry, mycelium_dir: Path
) -> None:
    """The resolver is handed down, not the answer.

    `[sources]` classifies an *origin*, and the origin is only known once the
    connector has turned a source into a URI — so the caller passes the function.
    """
    seen: list[str] = []

    def trust_for(uri: str) -> SourceTrust | None:
        seen.append(uri)
        return SourceTrust.MEDIUM

    result = ingest_source(
        mycelium_dir,
        registry,
        str(FIXTURES / "source.md"),
        doc_id=DOC_ID,
        trust_for=trust_for,
    )
    # Relative, and that is the point: this URI is copied into a document that
    # gets committed, so it must read the same on every machine (BUG-0017).
    assert seen == ["file:source.md"]
    assert "source_trust: medium" in result.projection.text


def test_an_origin_nothing_matches_leaves_the_document_unlabelled(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(
        mycelium_dir,
        registry,
        str(FIXTURES / "source.md"),
        doc_id=DOC_ID,
        trust_for=lambda _uri: None,
    )
    assert "source_trust" not in result.projection.text


def test_an_explicit_trust_wins_over_the_resolver(registry: Registry, mycelium_dir: Path) -> None:
    # A caller that says "I know what this is" is not overruled by a pattern.
    result = ingest_source(
        mycelium_dir,
        registry,
        str(FIXTURES / "source.md"),
        doc_id=DOC_ID,
        source_trust=SourceTrust.HIGH,
        trust_for=lambda _uri: SourceTrust.UNKNOWN,
    )
    assert "source_trust: high" in result.projection.text


# ---------------------------------------------------------------------------
# Quarantine and the secret scan (roadmap 4.6)
# ---------------------------------------------------------------------------


def test_a_refused_source_is_recorded_where_it_can_be_found(
    registry: Registry, mycelium_dir: Path
) -> None:
    """Spec 02 §5's first verb. Skipping and reporting were already true at 4.1."""
    source = HOSTILE / "truncated.pdf"
    with pytest.raises(ParseError):
        ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)

    record = Quarantine(mycelium_dir).get(f"file:hostile/{source.name}")
    assert record is not None
    assert record.stage is QuarantineStage.PARSE
    assert record.media_type == "application/pdf"
    # The bytes are in custody because acquisition stores before it parses
    # (ADR-0033), which is what makes this re-examinable rather than counted.
    assert record.source_digest is not None
    assert Custody(mycelium_dir).get(record.source_digest) == source.read_bytes()


def test_a_source_no_parser_reads_is_quarantined_at_dispatch(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    odd = tmp_path / "notes.rst"
    odd.write_text("Title\n=====\n", encoding="utf-8")
    narrow = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    with pytest.raises(UnsupportedMediaTypeError):
        ingest_source(mycelium_dir, narrow, str(odd), doc_id=DOC_ID)

    record = Quarantine(mycelium_dir).get(f"file:{odd.name}")
    assert record is not None
    # Not `acquire`: the bytes were readable, and the remedy is a configuration
    # edit rather than anything to do with the file.
    assert record.stage is QuarantineStage.DISPATCH
    assert record.source_digest is None


def test_a_source_that_cannot_be_acquired_is_quarantined_by_the_name_asked_for(
    registry: Registry, mycelium_dir: Path
) -> None:
    with pytest.raises(ConnectorError):
        ingest_source(mycelium_dir, registry, str(FIXTURES / "absent.md"), doc_id=DOC_ID)
    (record,) = list(Quarantine(mycelium_dir).records())
    assert record.stage is QuarantineStage.ACQUIRE
    assert record.source_digest is None


def test_a_guard_breach_is_quarantined_as_a_guard_breach(
    registry: Registry, mycelium_dir: Path
) -> None:
    with pytest.raises(GuardError):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "nested.html"), doc_id=DOC_ID)
    (record,) = list(Quarantine(mycelium_dir).records())
    assert record.stage is QuarantineStage.GUARD


def test_a_document_over_its_loss_budget_is_quarantined_as_a_budget_failure(
    registry: Registry, mycelium_dir: Path
) -> None:
    with pytest.raises(LossBudgetError):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "no-text-layer.pdf"), doc_id=DOC_ID)
    (record,) = list(Quarantine(mycelium_dir).records())
    # A document that *parsed* and arrived too damaged to project is a different
    # problem from one that could not be read, and needs a different answer.
    assert record.stage is QuarantineStage.BUDGET
    assert record.source_digest is not None


def test_a_source_that_starts_working_leaves_the_quarantine(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    """The lifecycle that keeps the list honest: success clears."""
    source = tmp_path / "notes.md"
    source.write_bytes(b"not\xffutf8")
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    with pytest.raises(ParseError):
        ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)
    assert Quarantine(mycelium_dir).count() == 1

    source.write_text("# Fixed\n\nIt reads now.\n", encoding="utf-8")
    ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)
    assert Quarantine(mycelium_dir).count() == 0


def test_a_healthy_source_never_writes_a_quarantine_directory(
    registry: Registry, mycelium_dir: Path
) -> None:
    ingest_source(mycelium_dir, registry, str(FIXTURES / "source.md"), doc_id=DOC_ID)
    assert not quarantine_root(mycelium_dir).exists()


def test_a_credential_is_redacted_before_the_kir_is_stored(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    """The rule ADR-0037 rests on: the secret exists in exactly one artifact.

    The tier-1 original holds the bytes verbatim, because that is what a citation
    is checked against. Everything derived from it — the KIR blob, the projection,
    and therefore the chunks and the index — carries a placeholder.
    """
    source = tmp_path / "runbook.md"
    source.write_text(
        "# Runbook\n\nThe key is AKIAIOSFODNN7EXAMPLE and it rotates monthly.\n",
        encoding="utf-8",
    )
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    result = ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)

    assert result.secret_flags == ("aws-access-key-id",)
    assert result.redacted is True
    assert "AKIAIOSFODNN7EXAMPLE" not in result.projection.text
    assert "[redacted: aws-access-key-id]" in result.projection.text

    custody = Custody(mycelium_dir)
    assert b"AKIAIOSFODNN7EXAMPLE" in (custody.get(result.original.digest) or b"")
    assert b"AKIAIOSFODNN7EXAMPLE" not in (custody.get(result.kir_digest) or b"")


def test_the_flags_are_recorded_on_the_originals_custody_record(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    # ADR-0034's mechanism: the projected document carries one link, and every
    # fact about the evidence is read back from the record it points at.
    source = tmp_path / "runbook.md"
    source.write_text("# Runbook\n\nid AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    result = ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)

    record = Custody(mycelium_dir).record(result.original.digest)
    assert record is not None
    assert record.secret_flags == ("aws-access-key-id",)


def test_redaction_off_still_flags_and_writes_the_credential_through(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    """Flagging is the observation; redaction is the action (ADR-0037).

    An operator who wants the verbatim text should not also lose the record that a
    secret is in it — otherwise one setting silently removes two things.
    """
    source = tmp_path / "runbook.md"
    source.write_text("# Runbook\n\nid AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    result = ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID, redact_secrets=False)

    assert result.secret_flags == ("aws-access-key-id",)
    assert result.redacted is False
    assert "AKIAIOSFODNN7EXAMPLE" in result.projection.text
    record = Custody(mycelium_dir).record(result.original.digest)
    assert record is not None and record.secret_flags == ("aws-access-key-id",)


def test_a_document_with_no_credentials_records_no_flags(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.md"), doc_id=DOC_ID)
    assert result.secret_flags == ()
    assert result.redacted is False
    record = Custody(mycelium_dir).record(result.original.digest)
    assert record is not None and record.secret_flags == ()
