# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The synthesis lane end to end (roadmap 4.4).

The load-bearing test here is
:func:`test_a_candidate_compiles_into_a_cited_labelled_document`: a synthesized
document is written to `knowledge/candidate/`, `mycelium build` compiles it like
any other authored file, and what comes out is labelled `candidate`, carries the
identity of the model that wrote it, and its citations are `cites` edges in the
graph. That is the whole of D-020's claim — an LLM may write documentation
because the result is checkable — reduced to something a test can assert.
"""

from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pytest

from fakes import ScriptedProvider
from mycelium.build import build
from mycelium.ingest.custody import Custody
from mycelium.markdown.adapter import parse_markdown
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.sdk.types import (
    CustodyKind,
    EdgeType,
    ProvenanceOrigin,
    SynthesisRecord,
    TrustClass,
    VerificationStatus,
)
from mycelium.store import SqliteStore
from mycelium.synthesis import (
    UngroundedError,
    WikiSynthesizer,
    candidate_path,
    evidence_of,
    synthesize_candidate,
    topic_of,
    write_candidate,
)

EVIDENCE_TEXT = """\
---
title: Retry Policy
origin: ingested
source: file:///sources/retry.pdf
source_trust: high
---

# Retry Policy

Webhook deliveries are retried five times.

## Backoff

Backoff doubles after every failed attempt.
"""

GOOD = """\
# Retry Behaviour

Webhook deliveries are retried up to five times [[retry-policy#Retry Policy]].

## The delay between attempts

The delay doubles after every failed attempt [[retry-policy#Backoff]].
"""

FABRICATED = "# Retry Behaviour\n\nDeliveries are retried five times [[nowhere#Nothing]].\n"

EVIDENCE_PATH = PurePosixPath("knowledge/evidence/retry-policy.md")


@pytest.fixture
def evidence() -> EvidenceDocument:
    return evidence_of(EVIDENCE_PATH, EVIDENCE_TEXT)


def synthesizer(*answers: str) -> WikiSynthesizer:
    return WikiSynthesizer(ScriptedProvider(*answers))


# ---------------------------------------------------------------------------
# Reading the evidence the compiler will read
# ---------------------------------------------------------------------------


def test_evidence_is_read_through_the_parser_the_build_uses(evidence: EvidenceDocument) -> None:
    assert evidence.title == "Retry Policy"
    assert evidence.headings == ("Retry Policy", "Backoff")
    assert evidence.source_uri == "file:///sources/retry.pdf"
    assert evidence.source_trust is not None and evidence.source_trust.value == "high"


def test_the_topic_defaults_to_the_evidence_s_own_title(evidence: EvidenceDocument) -> None:
    # Asking the model to invent a topic would put an ungrounded sentence at the
    # top of every candidate document: its title.
    assert topic_of([evidence]) == "Retry Policy"
    assert topic_of([]) == "Untitled"


# ---------------------------------------------------------------------------
# The candidate document
# ---------------------------------------------------------------------------


def test_a_candidate_lands_in_the_folder_that_is_its_status(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    result = synthesize_candidate(
        tmp_path / ".mycelium", synthesizer(GOOD), [evidence], topic="Retry Behaviour"
    )
    assert result.candidate.path == PurePosixPath("knowledge/candidate/retry-behaviour.md")
    assert candidate_path("Retry Behaviour").parts[1] == "candidate"


def test_the_frontmatter_declares_what_wrote_it_and_nothing_more(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    result = synthesize_candidate(
        tmp_path / ".mycelium", synthesizer(GOOD), [evidence], topic="Retry Behaviour"
    )
    parsed = parse_markdown(result.candidate.text)
    frontmatter = parsed.frontmatter
    assert frontmatter.origin is ProvenanceOrigin.SYNTHESIZED
    assert frontmatter.generated_by == "scripted/scripted-1"
    assert frontmatter.source == "file:///sources/retry.pdf"
    assert frontmatter.source_digest == result.record_digest
    # `grounding` belongs to `mycelium verify` (spec 03 §3): a synthesizer
    # stamping its own grade is the document marking its own homework.
    assert frontmatter.grounding is None
    assert frontmatter.verified_by is None


def test_the_body_is_written_through_untouched(tmp_path: Path, evidence: EvidenceDocument) -> None:
    result = synthesize_candidate(
        tmp_path / ".mycelium", synthesizer(GOOD), [evidence], topic="Retry Behaviour"
    )
    assert result.candidate.text.endswith(GOOD)


# ---------------------------------------------------------------------------
# The run record, in custody
# ---------------------------------------------------------------------------


def test_the_run_is_recorded_in_tier_one_custody(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    mycelium_dir = tmp_path / ".mycelium"
    result = synthesize_candidate(
        mycelium_dir,
        synthesizer(GOOD),
        [evidence],
        topic="Retry Behaviour",
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    )
    custody = Custody(mycelium_dir)
    record = custody.record(result.record_digest)
    assert record is not None
    assert record.kind is CustodyKind.SYNTHESIS

    blob = custody.get(result.record_digest)
    assert blob is not None
    run = SynthesisRecord.model_validate_json(blob.decode("utf-8"))
    assert run.plugin == "wiki"
    assert run.provider == "scripted"
    assert run.model == "scripted-1"
    assert run.attempts == 1
    assert run.coverage == 1.0
    assert run.citations == (
        "knowledge/evidence/retry-policy.md#Retry Policy",
        "knowledge/evidence/retry-policy.md#Backoff",
    )
    assert run.evidence == (evidence.kir.source_digest,)


def test_the_record_survives_a_repair_and_says_how_many_attempts_it_took(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    result = synthesize_candidate(
        tmp_path / ".mycelium",
        synthesizer(FABRICATED, GOOD),
        [evidence],
        topic="Retry Behaviour",
    )
    assert result.record.attempts == 2


def test_a_refused_document_leaves_no_file_and_no_candidate(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    with pytest.raises(UngroundedError):
        synthesize_candidate(
            tmp_path / ".mycelium",
            synthesizer(FABRICATED, FABRICATED),
            [evidence],
            topic="Retry Behaviour",
        )
    assert not (tmp_path / "knowledge" / "candidate").exists()


# ---------------------------------------------------------------------------
# Writing into the working tree
# ---------------------------------------------------------------------------


def test_writing_the_same_candidate_twice_leaves_no_diff(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    result = synthesize_candidate(
        tmp_path / ".mycelium",
        synthesizer(GOOD),
        [evidence],
        topic="Retry Behaviour",
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    )
    first = write_candidate(tmp_path, result)
    stamp = first.stat().st_mtime_ns
    second = write_candidate(tmp_path, result)
    assert first == second
    assert second.stat().st_mtime_ns == stamp, "an unchanged candidate is not rewritten"


# ---------------------------------------------------------------------------
# What the compiler makes of it — the claim D-020 rests on
# ---------------------------------------------------------------------------


def test_a_candidate_compiles_into_a_cited_labelled_document(
    tmp_path: Path, evidence: EvidenceDocument
) -> None:
    knowledge = tmp_path / "knowledge"
    (knowledge / "evidence").mkdir(parents=True)
    (knowledge / EVIDENCE_PATH.name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / EVIDENCE_PATH).write_text(EVIDENCE_TEXT, encoding="utf-8", newline="\n")

    result = synthesize_candidate(
        tmp_path / ".mycelium", synthesizer(GOOD), [evidence], topic="Retry Behaviour"
    )
    written = write_candidate(tmp_path, result)
    assert written.exists()

    build(tmp_path)

    store = SqliteStore.open(tmp_path, read_only=True)
    try:
        candidate = store.get_document_by_path("knowledge/candidate/retry-behaviour.md")
        assert candidate is not None

        # Status comes from the folder, and nothing else can move it (D-021).
        assert candidate.verification_status is VerificationStatus.CANDIDATE
        assert candidate.provenance.origin is ProvenanceOrigin.SYNTHESIZED
        # The authority *layer* is tier 2; what makes it untrusted is the status.
        assert candidate.trust_class is TrustClass.AUTHORED

        # The identity of the run, recovered from custody through one frontmatter
        # key — the same mechanism a projection uses for its fidelity report.
        synth = candidate.provenance.synthesizer
        assert synth is not None
        assert synth.provider == "scripted"
        assert synth.model == "scripted-1"
        assert synth.prompt_digest.startswith("sha256:")
        # `source_digest` named the run, not acquired bytes; it must not survive
        # as a claim that there is a tier-1 original behind the prose.
        assert candidate.provenance.source_digest is None

        edges = list(store.all_edges())
        cites = [edge for edge in edges if edge.type is EdgeType.CITES]
        assert len(cites) == 2, "both citations are typed as citations"
        assert all(edge.from_ == "doc:knowledge/candidate/retry-behaviour.md" for edge in cites)
        assert all("knowledge/evidence/retry-policy.md" in edge.to for edge in cites)
        assert all(edge.type is not EdgeType.LINKS_TO for edge in cites)
    finally:
        store.close()
