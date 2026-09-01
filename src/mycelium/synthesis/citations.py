# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The citation contract — the deterministic half of a non-deterministic lane.

D-020 is a claim about *verifiability*: an LLM may author documentation, but every
claim-bearing statement must cite the evidence layer, so that "100 % source truth"
is something a machine can check rather than something a model asserts. This
module is that check, and it is the reason the synthesis lane is allowed to exist
at all.

Three rules, in the order they matter:

1. **No fabricated citation.** Every wikilink in the document resolves to a
   document in the evidence set, and — when it names a section — to a heading that
   document actually has. A model that invents a plausible citation has produced
   the single most dangerous artifact this project could ship: prose that *looks*
   grounded. This rule fails the document, always.
2. **Something is cited.** A candidate document with no citation is prose with a
   provenance stamp, which is worse than no document.
3. **Claim-bearing blocks are covered.** Coverage is measured, compared against
   `[synthesis] min_citation_coverage`, and recorded.

**What a "claim-bearing statement" is here, exactly.** A KIR `paragraph` or
`list_item` node whose text carries at least :data:`MIN_CLAIM_WORDS` words. It is
a *block*, not a sentence, and that is a deliberate choice rather than an
approximation of one: KIR states block boundaries exactly and says nothing about
sentence boundaries, so a sentence-level measure would be this module inventing a
structure the compiler does not have — and a grounding number is only worth
anything if two runs of it agree. Gate G7's threshold (roadmap 4.5) is applied to
*this* measure; moving to sentence granularity later changes what the number
means and has to be re-judged, not patched.

Short blocks are excluded because they are not claims: `For example:`, `Notes`,
`See also` carry no assertion to support, and requiring a citation on them would
teach an operator to lower the floor rather than raise the grounding.

Resolution goes through the real parser (ADR-0006) rather than a regex over the
text: `[[…]]` inside a fenced code block is not a citation, and the one place
that knows the difference is the Profile v1 parser the compiler itself uses.
"""

import re
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from mycelium.markdown.adapter import MarkdownError, parse_markdown
from mycelium.markdown.frontmatter import FrontmatterError
from mycelium.sdk.identity import heading_slug
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.sdk.types import KirDocument, KirNode, NodeKind
from mycelium.synthesis.errors import UngroundedError

__all__ = [
    "MIN_CLAIM_WORDS",
    "CitationReport",
    "check",
    "citable_names",
    "claim_blocks",
    "claim_owner",
    "index_evidence",
    "resolve_target",
    "review",
]

MIN_CLAIM_WORDS: Final = 5
"""Words below which a block is structure, not a claim."""

_CLAIM_KINDS: Final = frozenset({NodeKind.PARAGRAPH, NodeKind.LIST_ITEM})
_WORD: Final = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class CitationReport:
    """What the contract found, whether or not it passed."""

    citations: tuple[str, ...]
    """Every resolved wikilink target, as `path` or `path#heading`, in order."""

    cited_documents: tuple[str, ...]
    """The distinct evidence documents cited, in path order."""

    claims: int
    """Claim-bearing blocks in the document."""

    cited_claims: int
    claim_citations: dict[str, tuple[str, ...]]
    """Which citations each covered claim-bearing block carries, keyed by node id.

    Recorded because `mycelium verify` needs it (roadmap 4.5): sampled entailment
    judges a claim against *the evidence that claim cited*, and rebuilding the
    mapping there would be a second walk of the same tree with a second chance to
    disagree about which block a citation belongs to."""

    violations: tuple[str, ...]
    """Human-readable, quotable back to the model: each names the offending link
    or block and what was wrong with it."""

    @property
    def coverage(self) -> float:
        """Cited claim-bearing blocks over claim-bearing blocks.

        A document with no claims at all scores 1.0 rather than dividing by zero:
        nothing was asserted, so nothing is unsupported. Rule 2 catches the
        document that says something and cites nothing.
        """
        if self.claims == 0:
            return 1.0
        return self.cited_claims / self.claims

    def as_dict(self) -> dict[str, object]:
        return {
            "citations": list(self.citations),
            "cited_documents": list(self.cited_documents),
            "claims": self.claims,
            "cited_claims": self.cited_claims,
            "coverage": round(self.coverage, 4),
            "violations": list(self.violations),
        }


def index_evidence(evidence: Sequence[EvidenceDocument]) -> dict[str, EvidenceDocument]:
    """Every name a wikilink may legitimately use, mapped to its document.

    Both the stem and the full repository path, case-folded, because a vault
    author writes `[[retry-policy]]` and a careful one writes the path. The same
    two forms the compiler's own resolution accepts (spec 03 §3.1).
    """
    index: dict[str, EvidenceDocument] = {}
    for document in evidence:
        index.setdefault(_normalise(document.path.stem), document)
        index.setdefault(_normalise(document.path.as_posix()), document)
    return index


def _normalise(value: str) -> str:
    text = value.strip().replace("\\", "/").casefold()
    return text.removesuffix(".md")


def resolve_target(
    target: str, index: Mapping[str, EvidenceDocument]
) -> tuple[EvidenceDocument | None, str, str]:
    """Split a wikilink target and resolve its document half.

    Returns ``(document, fragment, reason)``; `document` is ``None`` when nothing
    in the evidence set answers to that name, and `reason` says which half failed.
    """
    name, _, fragment = target.partition("#")
    document = index.get(_normalise(name))
    if document is None:
        return None, fragment.strip(), f"no evidence document is named {name.strip()!r}"
    return document, fragment.strip(), ""


def claim_blocks(nodes: Sequence[KirNode]) -> list[KirNode]:
    return [
        node
        for node in nodes
        if node.kind in _CLAIM_KINDS and len(_WORD.findall(node.text or "")) >= MIN_CLAIM_WORDS
    ]


def review(kir: KirDocument, evidence: Sequence[EvidenceDocument]) -> CitationReport:
    """Check a parsed candidate document against the evidence set.

    Pure: no IO, no provider, no configuration. Everything the lane decides about
    grounding is decided here, which is what makes the decision testable without
    a model in the loop.
    """
    index = index_evidence(evidence)
    by_id = {node.id: node for node in kir.nodes}
    claims = claim_blocks(kir.nodes)
    claim_ids = {node.id for node in claims}

    citations: list[str] = []
    documents: set[str] = set()
    cited_claims: set[str] = set()
    per_claim: dict[str, list[str]] = {}
    violations: list[str] = []

    for node in kir.nodes:
        if node.kind is not NodeKind.WIKILINK:
            continue
        target = (node.target or "").strip()
        if not target:
            violations.append("an empty wikilink cites nothing")
            continue
        document, fragment, reason = resolve_target(target, index)
        if document is None:
            violations.append(f"[[{target}]] cites nothing in the evidence set: {reason}")
            continue
        if fragment:
            slugs = {heading_slug(heading) for heading in document.headings}
            if heading_slug(fragment) not in slugs:
                available = ", ".join(document.headings) or "(no headings)"
                violations.append(
                    f"[[{target}]] names a section {document.path.name} does not have; "
                    f"its headings are: {available}"
                )
                continue
        path = document.path.as_posix()
        citation = f"{path}#{fragment}" if fragment else path
        citations.append(citation)
        documents.add(path)
        owner = claim_owner(node, by_id, claim_ids)
        if owner is not None:
            cited_claims.add(owner)
            per_claim.setdefault(owner, []).append(citation)

    for node in claims:
        if node.id not in cited_claims:
            excerpt = (node.text or "")[:80]
            violations.append(f"this block cites nothing: {excerpt!r}")

    return CitationReport(
        citations=tuple(citations),
        cited_documents=tuple(sorted(documents)),
        claims=len(claims),
        cited_claims=len(cited_claims),
        claim_citations={key: tuple(value) for key, value in per_claim.items()},
        violations=tuple(violations),
    )


def claim_owner(
    node: KirNode, by_id: Mapping[str, KirNode], claim_ids: AbstractSet[str]
) -> str | None:
    """The claim-bearing block a wikilink belongs to, walking up the KIR tree.

    A wikilink's parent is the block that contains it, but a citation inside a
    nested list item or a callout is several steps down; walking up means a
    citation counts for the block a reader sees it in, wherever the syntax put it.
    """
    current: str | None = node.parent
    seen = 0
    while current is not None and seen < 16:
        if current in claim_ids:
            return current
        parent = by_id.get(current)
        current = parent.parent if parent is not None else None
        seen += 1
    return None


def check(
    markdown: str,
    evidence: Sequence[EvidenceDocument],
    *,
    min_coverage: float = 1.0,
    doc_id: str,
) -> tuple[CitationReport, KirDocument]:
    """Parse `markdown` and enforce the contract, or raise :class:`UngroundedError`.

    The one entry point the lane calls, and the one place the three rules are
    ordered. The parsed KIR comes back with the report because the caller needs
    it — the title, the body, the structure — and parsing twice would be two
    chances to disagree about what the document says.
    """
    try:
        parsed = parse_markdown(markdown, doc_id=doc_id)
    except (MarkdownError, FrontmatterError) as error:
        msg = f"the synthesized text is not valid Mycelium Markdown: {error}"
        raise UngroundedError(msg, (str(error),)) from error

    report = review(parsed.kir, evidence)

    # Rule 1 before rule 2, and the order is not cosmetic: a document whose only
    # citation was invented satisfies neither, and "cites nothing" would be a true
    # sentence that sends the reader — and the repair round-trip — after the wrong
    # problem. The fabricated citation is the finding.
    unresolved = tuple(item for item in report.violations if item.startswith("[["))
    if unresolved:
        msg = f"the synthesized document cites {len(unresolved)} thing(s) that do not exist"
        raise UngroundedError(msg, report.violations)

    if not report.citations:
        msg = "the synthesized document cites nothing; every claim must cite the evidence (D-020)"
        raise UngroundedError(msg, report.violations)

    if report.coverage < min_coverage:
        msg = (
            f"citation coverage {report.coverage:.2f} is below the required "
            f"{min_coverage:.2f}: {report.claims - report.cited_claims} of {report.claims} "
            "claim-bearing blocks cite nothing"
        )
        raise UngroundedError(msg, report.violations)
    return report, parsed.kir


def citable_names(evidence: Sequence[EvidenceDocument]) -> tuple[str, ...]:
    """Every `[[document#Heading]]` form the prompt may offer, in document order.

    Handing the model the exact citable strings is what turns "cite your sources"
    from an instruction into a closed vocabulary — and a closed vocabulary is what
    makes rule 1 something a model can satisfy rather than a trap it walks into.
    """
    names: list[str] = []
    for document in evidence:
        stem = PurePosixPath(document.path).stem
        names.append(f"[[{stem}]]")
        names.extend(f"[[{stem}#{heading}]]" for heading in document.headings)
    return tuple(names)
