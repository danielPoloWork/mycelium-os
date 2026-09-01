# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The synthesis lane, end to end: evidence → prose → custody → candidate.

The *second* lane (D-020). The evidence lane always runs and is deterministic;
this one runs additionally, only when a provider is configured, and is
non-deterministic by declaration. Everything here is arranged around keeping
those two facts from contaminating each other:

1. **Read the evidence the compiler will read.** The citable set is built by
   parsing the projected evidence documents with the same Profile v1 parser the
   build uses, so a citation checked here resolves there.
2. **Synthesize, check, repair once, or refuse** — the plugin's business
   (:mod:`mycelium.synthesis.wiki`).
3. **Record the run in tier-1 custody** *before* the document is rendered, so the
   candidate can name it. A candidate document whose synthesis record is missing
   is a claim with no receipt; writing the receipt first makes that state
   unreachable rather than merely unlikely.
4. **Render the candidate.** Returned, not written: putting a file into someone's
   Git working tree is the caller's decision, exactly as it is for a projection.

What the lane never does is fail the ingestion it rides on. A missing provider, a
refused document, a model that declined — each is returned to the caller as an
error to report, because the evidence lane already produced everything the
compiler needs and D-020 makes synthesis the *additional* lane, not a
precondition.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from mycelium.ingest.custody import Custody
from mycelium.markdown.adapter import parse_markdown
from mycelium.sdk.identity import canonical_json
from mycelium.sdk.protocols import EvidenceDocument, SynthesisContext
from mycelium.sdk.types import (
    CustodyKind,
    NodeKind,
    Sha256Digest,
    SourceTrust,
    SynthesisRecord,
)
from mycelium.synthesis.candidate import Candidate, render, title_of
from mycelium.synthesis.citations import CitationReport
from mycelium.synthesis.wiki import WikiSynthesizer

__all__ = [
    "Synthesized",
    "encode_record",
    "evidence_of",
    "synthesize_candidate",
    "topic_of",
    "write_candidate",
]


@dataclass(frozen=True, slots=True)
class Synthesized:
    """One candidate document, its run record, and the grounding it was accepted on."""

    candidate: Candidate
    record: SynthesisRecord
    record_digest: Sha256Digest
    report: CitationReport


def evidence_of(
    path: PurePosixPath,
    text: str,
    *,
    source_uri: str = "",
    source_trust: SourceTrust | None = None,
) -> EvidenceDocument:
    """Read one projected evidence document as the synthesizer must see it.

    Parsed rather than passed through: the headings a citation may name are the
    ones the *parser* finds, and reading them off the raw text with a regex would
    be a second opinion about the document's structure — the exact drift the
    citation contract exists to prevent.
    """
    parsed = parse_markdown(text)
    headings = tuple(
        node.text for node in parsed.kir.nodes if node.kind is NodeKind.HEADING and node.text
    )
    title = parsed.frontmatter.title or (headings[0] if headings else path.stem)
    return EvidenceDocument(
        path=path,
        title=title,
        kir=parsed.kir,
        headings=headings,
        source_uri=source_uri or parsed.frontmatter.source or "",
        source_trust=source_trust or parsed.frontmatter.source_trust,
    )


def encode_record(record: SynthesisRecord) -> bytes:
    """Serialize a synthesis record to the bytes custody stores (canonical JSON)."""
    return canonical_json(record.model_dump(mode="json")).encode("utf-8")


def synthesize_candidate(
    mycelium_dir: Path,
    synthesizer: WikiSynthesizer,
    evidence: Sequence[EvidenceDocument],
    *,
    topic: str,
    instructions: str = "",
    knowledge_dir: str = "knowledge",
    now: datetime | None = None,
) -> Synthesized:
    """Write one candidate document from `evidence`, and record what wrote it.

    Raises :class:`~mycelium.synthesis.errors.UngroundedError` when the citation
    contract cannot be satisfied and
    :class:`~mycelium.synthesis.errors.ProviderError` when the model cannot be
    reached. Neither leaves a file behind: a candidate exists only if its
    citations were checked.
    """
    context = SynthesisContext(topic=topic, evidence=tuple(evidence), instructions=instructions)
    draft = synthesizer.draft(context)

    record = SynthesisRecord(
        plugin=synthesizer.meta.id,
        plugin_version=synthesizer.meta.version,
        provider=draft.synthesis.provider,
        model=draft.synthesis.model,
        prompt_digest=draft.synthesis.prompt_digest,
        parameters=draft.synthesis.parameters,
        attempts=draft.synthesis.attempts,
        evidence=tuple(sorted(item.kir.source_digest for item in evidence)),
        citations=draft.report.citations,
        claims=draft.report.claims,
        cited_claims=draft.report.cited_claims,
        synthesized_at=now or datetime.now(tz=UTC),
    )
    stored = Custody(mycelium_dir).put(
        encode_record(record),
        kind=CustodyKind.SYNTHESIS,
        media_type="application/json",
        connector=synthesizer.meta.id,
        connector_version=synthesizer.meta.version,
    )

    first = evidence[0]
    candidate = render(
        draft.synthesis.markdown,
        title=title_of(draft.synthesis.markdown, topic),
        source_uri=first.source_uri or None,
        source_digest=stored.digest,
        generated_by=f"{draft.synthesis.provider}/{draft.synthesis.model}",
        source_trust=first.source_trust,
        knowledge_dir=knowledge_dir,
    )
    return Synthesized(
        candidate=candidate,
        record=record,
        record_digest=stored.digest,
        report=draft.report,
    )


def write_candidate(root: Path, synthesized: Synthesized) -> Path:
    """Write the candidate document into the repository at `root`.

    The one step that touches tier 2. Unchanged text rewrites nothing, so a
    repeated run leaves no spurious diff — but a *changed* document does replace
    the previous one, because a candidate is prose about a subject and two runs on
    one subject are two drafts of the same document, not two documents. The old
    draft is in Git; that is where a superseded draft belongs.
    """
    destination = root / synthesized.candidate.path
    text = synthesized.candidate.text
    if destination.exists() and destination.read_text(encoding="utf-8") == text:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")
    return destination


def topic_of(evidence: Sequence[EvidenceDocument]) -> str:
    """A default topic: the single document's title, or a list of them.

    Deliberately plain. Asking the model to invent a topic from the evidence would
    put an ungrounded sentence at the top of every candidate document — the title.
    """
    if not evidence:
        return "Untitled"
    if len(evidence) == 1:
        return evidence[0].title
    return ", ".join(item.title for item in evidence)
