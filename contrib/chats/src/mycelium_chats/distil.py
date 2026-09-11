# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Distillation: the synthesis lane, pointed at a conversation (doc 08 §7).

Doc 08 §7's optional half — *"an LLM-authored summary doc (decisions and
outcomes of this conversation) written to `knowledge/candidate/…` with `cites`
wikilinks into the transcript — subject to `mycelium verify`/`promote` exactly
like every synthesized doc"*. Everything in that sentence already exists in the
core; this module contributes the evidence and the topic, and takes none of the
decisions.

**It is not a pipeline stage, and that is a finding rather than a shortcut**
(roadmap 5.15, ADR-0087). The item that filed this expected D-023's first
pipeline stage here. A distillation writes `knowledge/candidate/…`, which is
tier 2, and spec 02 §2 is unconditional: *"The build (`mycelium build`) remains
a pure function and never writes tiers 1–2"*. So a distillation is an
**authoring-time** act, like `mycelium ingest` and like every other command this
module offers — and the pipeline-stage mechanism still has no consumer. Building
it here would have frozen a contract against nobody, which is what roadmap 5.1
refused for `Extractor`, 5.5 for three mechanisms, and 5.14 for the SDK façade.

**What a distilled conversation cites is the decision this module does take.**
A projection carries one section per message (:mod:`mycelium_chats.projection`),
so `[[conversation#12 · assistant]]` was already resolvable with no core change —
but so were `[[conversation]]` and `[[conversation#<title>]]`, and both mean
*somewhere in this conversation*. Measured on the fixture corpus, the title
heading's section text **is** the whole document, byte for byte, so the two
coarse forms are one problem wearing two spellings. Handing gate G7's judge a
whole conversation and asking whether one sentence is in there somewhere is the
question it answers most charitably, which is the opposite of grounding.

So the evidence this module hands the synthesizer says **cite me by section**,
and its citable headings are the message headings and nothing else. The core
honours both halves — the vocabulary stops offering the coarse form and the
contract stops accepting it (`EvidenceDocument.cite_sections_only`) — which is
the third API fix doc 08 §10's sixth gate has produced, and the reason the gate
is worth having.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path, PurePosixPath

from mycelium.sdk.identity import heading_slug
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.synthesis import (
    Synthesized,
    WikiSynthesizer,
    evidence_of,
    synthesize_candidate,
    write_candidate,
)
from mycelium_chats.paths import MYCELIUM_DIRNAME
from mycelium_chats.projection import message_heading
from mycelium_chats.record import Conversation, Transcript

__all__ = [
    "citable_evidence",
    "distil_conversation",
    "message_citations",
    "topic_of",
    "write_distillation",
]


def topic_of(conversation: Conversation) -> str:
    """What the model is asked to write, in doc 08 §7's own words.

    The conversation's title carries the subject and the framing carries the
    genre, and neither is invented: a topic assembled from the record cannot put
    an ungrounded sentence at the top of the document, which is the reason the
    core's own `topic_of` is equally plain.
    """
    return f"Decisions and outcomes of the conversation {conversation.title!r}"


def citable_evidence(
    transcript: Transcript, projection_path: PurePosixPath, text: str
) -> EvidenceDocument:
    """The projection as evidence a claim must cite **by message**.

    Parsed through the core's own :func:`~mycelium.synthesis.lane.evidence_of`, so
    a citation checked here resolves the way the compiler will resolve it, and
    then narrowed in exactly two ways:

    `headings` keeps only the sections that *are* messages. The projection's other
    heading is its title, whose section text is the whole document — so leaving it
    citable would leave the coarse citation available under a section's name.
    Which headings those are is decided by intersecting what the parser found with
    what the record says its messages are called, rather than by dropping the
    first: a projection-shape change can then narrow this set but never widen it
    silently.

    `cite_sections_only` is the flag that closes the other spelling. Together they
    leave the model one honest way to cite a conversation — the message the claim
    came from.
    """
    parsed = evidence_of(projection_path, text)
    wanted = {heading_slug(message_heading(line)) for line in transcript.lines}
    headings = tuple(heading for heading in parsed.headings if heading_slug(heading) in wanted)
    return replace(parsed, headings=headings, cite_sections_only=True)


def distil_conversation(
    root: Path,
    synthesizer: WikiSynthesizer,
    transcript: Transcript,
    projection_path: PurePosixPath,
    *,
    instructions: str = "",
    knowledge_dir: str = "knowledge",
    now: datetime | None = None,
) -> Synthesized:
    """Write one conversation's distillation, or refuse to (D-020).

    Raises :class:`~mycelium.synthesis.errors.UngroundedError` when the citation
    contract cannot be satisfied from this conversation and
    :class:`~mycelium.synthesis.errors.ProviderError` when the model cannot be
    reached. Neither leaves a document behind, and the caller reports rather than
    fails: a conversation that cannot be distilled is still archived, still
    projected and still searchable, which is the whole of what this module
    promises (doc 08 §7 calls distillation *optional*).

    Nothing is written to tier 2 here. `write_distillation` is a separate call for
    the reason the core's lane keeps them separate: putting a file into somebody's
    Git working tree is the caller's decision.
    """
    text = (root / projection_path).read_text(encoding="utf-8")
    evidence = citable_evidence(transcript, projection_path, text)
    return synthesize_candidate(
        root / MYCELIUM_DIRNAME,
        synthesizer,
        [evidence],
        topic=topic_of(transcript.conversation),
        instructions=instructions,
        knowledge_dir=knowledge_dir,
        now=now,
    )


def write_distillation(root: Path, synthesized: Synthesized) -> Path:
    """Write the candidate document, through the core's own writer.

    A one-line passthrough on purpose. A distilled conversation is a synthesized
    document and nothing else — same folder, same provenance frontmatter, same
    `mycelium verify` and `mycelium promote` (D-021) — and a module that wrote its
    own candidate file would be a second opinion about what a candidate is.
    """
    return write_candidate(root, synthesized)


def message_citations(citations: Sequence[str]) -> tuple[str, ...]:
    """The distinct message anchors a distillation cited, in order of first use.

    Reported by the CLI because it is the number that says whether the document
    read the conversation or skimmed it: eight claims citing one message is a
    summary of one turn, and the operator can see that before promoting it.
    """
    seen: dict[str, None] = {}
    for citation in citations:
        _, _, fragment = citation.partition("#")
        if fragment:
            seen.setdefault(citation, None)
    return tuple(seen)
