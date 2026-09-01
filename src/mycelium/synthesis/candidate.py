# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The candidate document: where synthesized prose lands, and what it declares.

`knowledge/candidate/` is not a folder, it is the verification status (D-021).
Writing here is the whole of what the synthesis lane is allowed to do to tier 2:
a document arrives *unverified by construction*, retrieval labels it, and it
reaches `verified/` only through `mycelium promote` — a human, in Git (roadmap
4.5). Nothing in this module can produce a verified document, which is the point.

Frontmatter carries exactly what spec 03 §3's ownership table gives `mycelium
ingest` on a generated document, and not one field more:

- `origin: synthesized` — the provenance class, which is what makes retrieval and
  `mycelium verify` treat it as a claim rather than a source.
- `source` / `source_trust` — the evidence's own origin, carried through.
- `generated_by` — `<provider>/<model>`, spec 03 §3's own spelling.
- `source_digest` — the link to the synthesis record in tier-1 custody, the same
  one-key mechanism a projected document uses for its fidelity report (ADR-0034).
  From it the compiler recovers provider, model, prompt digest, parameters and
  the citation coverage, so five facts cannot drift from the run they describe.

There is deliberately no `grounding:` here. That field belongs to `mycelium
verify` (spec 03 §3), and a synthesizer stamping its own grade would be the
document marking its own homework.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

import yaml

from mycelium.sdk.types import ProvenanceOrigin, Sha256Digest, SourceTrust

__all__ = ["CANDIDATE_DIRNAME", "Candidate", "candidate_path", "render"]

CANDIDATE_DIRNAME: Final = "candidate"
"""Under `knowledge/`: the folder that *is* the verification status (D-021)."""

_SLUG_STRIP: Final = re.compile(r"[^a-z0-9]+")
_TITLE: Final = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One synthesized document, before it is written."""

    path: PurePosixPath
    text: str
    title: str


def candidate_path(title: str, *, knowledge_dir: str = "knowledge") -> PurePosixPath:
    """Where a synthesized document goes, named after what it is about.

    Slugified from the title rather than from the source filename: a candidate is
    a document *about* something, and a reader browsing `knowledge/candidate/`
    should see topics. No digest suffix — two synthesis runs on the same topic are
    the same document, and the second should replace the first rather than
    accumulate beside it, which is the opposite of the evidence lane's rule (a
    projection is evidence of specific bytes; a candidate is prose about a subject).
    """
    slug = _SLUG_STRIP.sub("-", title.strip().lower()).strip("-") or "candidate"
    return PurePosixPath(knowledge_dir) / CANDIDATE_DIRNAME / f"{slug}.md"


def title_of(markdown: str, fallback: str) -> str:
    """The document's own H1, or the topic it was asked to write about."""
    match = _TITLE.search(markdown)
    return match.group(1).strip() if match else fallback


def render(
    markdown: str,
    *,
    title: str,
    source_uri: str | None,
    source_digest: Sha256Digest,
    generated_by: str,
    source_trust: SourceTrust | None = None,
    knowledge_dir: str = "knowledge",
) -> Candidate:
    """Wrap synthesized Markdown in its provenance frontmatter.

    The body is written through untouched. It has already passed the citation
    contract, and a renderer that reflowed, re-headed or "tidied" it would be
    changing a document after the thing that vouches for it has run.
    """
    fields: dict[str, str] = {
        "title": title,
        "origin": ProvenanceOrigin.SYNTHESIZED.value,
    }
    if source_uri:
        fields["source"] = source_uri
    fields["source_digest"] = source_digest
    if source_trust is not None:
        fields["source_trust"] = source_trust.value
    fields["generated_by"] = generated_by

    block = yaml.safe_dump(fields, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = markdown if markdown.endswith("\n") else markdown + "\n"
    return Candidate(
        path=candidate_path(title, knowledge_dir=knowledge_dir),
        text=f"---\n{block}---\n\n{body}",
        title=title,
    )
