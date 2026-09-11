# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The citation contract (roadmap 4.4).

This is the file that decides whether the synthesis lane is allowed to exist. D-020
lets an LLM author documentation *because* every claim can be checked against the
evidence layer; if the check is wrong, the permission is void. So the rules are
tested one at a time, against documents written by hand rather than by a model —
nothing here needs a provider, and nothing here is allowed to be approximate.
"""

from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from mycelium.markdown.adapter import parse_markdown
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.synthesis.citations import (
    MIN_CLAIM_WORDS,
    check,
    citable_names,
    resolve_target,
    review,
)
from mycelium.synthesis.errors import UngroundedError

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"

EVIDENCE_TEXT = """\
# Retry Policy

Webhook deliveries are retried five times.

## Backoff

Backoff doubles after every failed attempt.
"""


def evidence(name: str = "retry-policy", text: str = EVIDENCE_TEXT) -> EvidenceDocument:
    parsed = parse_markdown(text)
    headings = tuple(
        node.text for node in parsed.kir.nodes if node.kind.value == "heading" and node.text
    )
    return EvidenceDocument(
        path=PurePosixPath(f"knowledge/evidence/{name}.md"),
        title=headings[0] if headings else name,
        kir=parsed.kir,
        headings=headings,
        source_uri=f"file:///{name}.pdf",
    )


def reviewed(markdown: str, *documents: EvidenceDocument):  # type: ignore[no-untyped-def]
    parsed = parse_markdown(markdown, doc_id=DOC_ID)
    return review(parsed.kir, documents or (evidence(),))


# ---------------------------------------------------------------------------
# Rule 1 — no fabricated citation
# ---------------------------------------------------------------------------


def test_a_citation_to_a_document_that_does_not_exist_is_a_violation() -> None:
    report = reviewed("Deliveries are retried five times [[invented-doc]].\n")
    assert report.violations
    assert "invented-doc" in report.violations[0]
    assert report.citations == ()


def test_a_citation_to_a_section_that_does_not_exist_is_a_violation() -> None:
    report = reviewed("Deliveries are retried five times [[retry-policy#Nonsense]].\n")
    assert any("does not have" in item for item in report.violations)
    # The message lists what *is* citable, because the repair round-trip quotes it
    # back to the model and "wrong section" without the right ones is not actionable.
    assert any("Backoff" in item for item in report.violations)


def test_check_refuses_a_document_with_a_fabricated_citation() -> None:
    with pytest.raises(UngroundedError, match="do not exist"):
        check(
            "Deliveries are retried five times [[invented-doc]].\n",
            [evidence()],
            doc_id=DOC_ID,
        )


def test_a_fabricated_citation_is_refused_even_when_coverage_would_pass() -> None:
    # Coverage counts *cited* blocks; an unresolvable link cites nothing, so the
    # two rules must not be able to cancel each other out.
    markdown = (
        "Deliveries are retried five times [[retry-policy#Retry Policy]].\n\n"
        "The backoff doubles after each attempt [[invented-doc]].\n"
    )
    with pytest.raises(UngroundedError, match="do not exist"):
        check(markdown, [evidence()], min_coverage=0.0, doc_id=DOC_ID)


# ---------------------------------------------------------------------------
# Rule 2 — something is cited
# ---------------------------------------------------------------------------


def test_a_document_with_no_citation_at_all_is_refused() -> None:
    with pytest.raises(UngroundedError, match="cites nothing"):
        check("Deliveries are retried five times, apparently.\n", [evidence()], doc_id=DOC_ID)


def test_an_empty_wikilink_cites_nothing() -> None:
    report = reviewed("Deliveries are retried five times [[]].\n")
    assert report.citations == ()


# ---------------------------------------------------------------------------
# Rule 3 — claim-bearing blocks are covered
# ---------------------------------------------------------------------------


def test_a_cited_paragraph_counts_as_covered() -> None:
    report = reviewed("Deliveries are retried five times [[retry-policy#Backoff]].\n")
    assert report.claims == 1
    assert report.cited_claims == 1
    assert report.coverage == 1.0
    assert report.citations == ("knowledge/evidence/retry-policy.md#Backoff",)


def test_an_uncited_paragraph_lowers_coverage_and_is_named() -> None:
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "Something else entirely that nobody supported here.\n"
    )
    report = reviewed(markdown)
    assert report.claims == 2
    assert report.cited_claims == 1
    assert report.coverage == 0.5
    assert any("cites nothing" in item for item in report.violations)


def test_a_short_block_is_structure_and_needs_no_citation() -> None:
    short = " ".join(["word"] * (MIN_CLAIM_WORDS - 1))
    markdown = f"Deliveries are retried five times [[retry-policy]].\n\n{short}\n"
    report = reviewed(markdown)
    assert report.claims == 1, "the short block is not a claim"
    assert report.coverage == 1.0


def test_list_items_are_claim_bearing_blocks() -> None:
    markdown = (
        "- the first retry happens after one second [[retry-policy#Backoff]]\n"
        "- the second retry happens after two seconds\n"
    )
    report = reviewed(markdown)
    assert report.claims == 2
    assert report.cited_claims == 1


def test_headings_are_never_claim_bearing() -> None:
    markdown = (
        "# A heading long enough to look like a claim\n\n"
        "Deliveries are retried five times in total [[retry-policy]].\n"
    )
    assert reviewed(markdown).claims == 1


def test_a_citation_inside_a_nested_list_covers_the_item_it_sits_in() -> None:
    markdown = (
        "- the outer item makes a claim about retries [[retry-policy]]\n"
        "    - the inner item makes another claim entirely [[retry-policy#Backoff]]\n"
    )
    report = reviewed(markdown)
    assert report.claims == 2
    assert report.cited_claims == 2


def test_coverage_below_the_floor_is_refused_with_the_number() -> None:
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "Something else entirely that nobody supported here.\n"
    )
    with pytest.raises(UngroundedError, match="0.50 is below the required 1.00"):
        check(markdown, [evidence()], doc_id=DOC_ID)


def test_the_floor_can_be_relaxed_deliberately() -> None:
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "Something else entirely that nobody supported here.\n"
    )
    report, _ = check(markdown, [evidence()], min_coverage=0.5, doc_id=DOC_ID)
    assert report.coverage == 0.5


# ---------------------------------------------------------------------------
# What counts as a citation at all
# ---------------------------------------------------------------------------


def test_a_wikilink_inside_a_code_fence_is_not_a_citation() -> None:
    """The reason resolution goes through the parser and not a regex."""
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "```text\n[[invented-doc#Nowhere]]\n```\n"
    )
    report, _ = check(markdown, [evidence()], doc_id=DOC_ID)
    assert report.citations == ("knowledge/evidence/retry-policy.md",)
    assert report.violations == ()


def test_a_document_may_be_named_by_stem_or_by_path() -> None:
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "The backoff doubles after each failed attempt "
        "[[knowledge/evidence/retry-policy.md#Backoff]].\n"
    )
    report, _ = check(markdown, [evidence()], doc_id=DOC_ID)
    assert report.cited_documents == ("knowledge/evidence/retry-policy.md",)
    assert len(report.citations) == 2


def test_resolution_is_case_and_suffix_insensitive() -> None:
    index = {"retry-policy": evidence()}
    document, fragment, reason = resolve_target("Retry-Policy.md#Backoff", index)
    assert document is not None
    assert fragment == "Backoff"
    assert reason == ""


def test_a_section_is_matched_by_slug_the_way_the_compiler_matches_it() -> None:
    # `[[doc#Backoff]]` and `[[doc#backoff]]` resolve to the same anchor at build
    # time (spec 03 §3.1); the contract must agree, or it refuses a citation the
    # compiler would have accepted.
    report, _ = check(
        "Deliveries are retried five times [[retry-policy#backoff]].\n",
        [evidence()],
        doc_id=DOC_ID,
    )
    assert report.violations == ()


def test_several_evidence_documents_are_all_citable() -> None:
    other = evidence("limits", "# Limits\n\nThe maximum payload is 256 KiB.\n")
    markdown = (
        "Deliveries are retried five times [[retry-policy]].\n\n"
        "The maximum payload size is 256 KiB [[limits#Limits]].\n"
    )
    report, _ = check(markdown, [evidence(), other], doc_id=DOC_ID)
    assert report.cited_documents == (
        "knowledge/evidence/limits.md",
        "knowledge/evidence/retry-policy.md",
    )


# ---------------------------------------------------------------------------
# The closed vocabulary
# ---------------------------------------------------------------------------


def test_citable_names_lists_the_document_and_every_heading() -> None:
    assert citable_names([evidence()]) == (
        "[[retry-policy]]",
        "[[retry-policy#Retry Policy]]",
        "[[retry-policy#Backoff]]",
    )


def test_every_citable_name_actually_passes_the_contract() -> None:
    """The prompt's promise, checked: nothing it offers is refused.

    A closed vocabulary that contained an unusable entry would produce a model
    that obeys the instruction and fails the contract, which is the worst of both.
    """
    document = evidence()
    for name in citable_names([document]):
        markdown = f"Deliveries are retried five times, in total {name}.\n"
        report, _ = check(markdown, [document], doc_id=DOC_ID)
        assert report.violations == (), name


# ---------------------------------------------------------------------------
# Degenerate input
# ---------------------------------------------------------------------------


def test_text_that_is_not_markdown_we_can_parse_is_refused_as_ungrounded() -> None:
    with pytest.raises(UngroundedError):
        check("---\nnot: [valid\n---\n\nbody\n", [evidence()], doc_id=DOC_ID)


def test_a_document_with_no_claims_scores_one_but_still_needs_a_citation() -> None:
    report = reviewed("Short.\n")
    assert report.claims == 0
    assert report.coverage == 1.0
    with pytest.raises(UngroundedError, match="cites nothing"):
        check("Short.\n", [evidence()], doc_id=DOC_ID)


# ---------------------------------------------------------------------------
# Rule 2 — no citation too coarse to check (roadmap 5.15)
# ---------------------------------------------------------------------------

LONG_TEXT = """\
# Anchor stability

## 1 - user

Do citations survive a file being renamed?

## 2 - assistant

Yes. A citation keys on doc_id, not on the path.

## 3 - user

And if the heading is renamed?

## 4 - assistant

The anchor dies and the fetch returns ANCHOR_GONE with the nearest ancestor.
"""


def sectioned(name: str = "conversation") -> EvidenceDocument:
    """Evidence that admits only section-level citations, minus its title heading."""
    document = evidence(name=name, text=LONG_TEXT)
    return replace(
        document,
        headings=tuple(item for item in document.headings if item != "Anchor stability"),
        cite_sections_only=True,
    )


def test_a_whole_document_citation_into_such_evidence_is_refused() -> None:
    document = sectioned()
    markdown = "# Notes\n\nCitations survive a rename of the file [[conversation]].\n"
    report = reviewed(markdown, document)

    assert report.whole_document_citations == ("conversation",)
    assert report.citations == ()
    assert any("too long to check" in item for item in report.violations)
    with pytest.raises(UngroundedError, match="whole document"):
        check(markdown, [document], doc_id=DOC_ID)


def test_the_refusal_names_the_sections_the_claim_could_have_cited() -> None:
    """The violation is quoted back to the model, so it has to carry the repair."""
    report = reviewed(
        "# Notes\n\nCitations survive a rename of the file [[conversation]].\n", sectioned()
    )

    (violation,) = [item for item in report.violations if item.startswith("[[")]
    assert "2 - assistant" in violation and "4 - assistant" in violation


def test_a_section_citation_into_the_same_evidence_is_accepted() -> None:
    document = sectioned()
    markdown = (
        "# Notes\n\nA citation keys on the document id, not the path "
        "[[conversation#2 - assistant]].\n"
    )
    report, _ = check(markdown, [document], doc_id=DOC_ID)

    assert report.whole_document_citations == ()
    assert report.coverage == 1.0
    assert report.citations == ("knowledge/evidence/conversation.md#2 - assistant",)


def test_the_title_heading_is_no_longer_citable_once_the_evidence_drops_it() -> None:
    """The second spelling of the same coarse citation: the title heading's own
    section is the whole document, so narrowing `headings` has to close it."""
    markdown = (
        "# Notes\n\nCitations survive a rename of the file [[conversation#Anchor stability]].\n"
    )
    with pytest.raises(UngroundedError, match="do not exist"):
        check(markdown, [sectioned()], doc_id=DOC_ID)


def test_a_coarse_citation_is_not_reported_as_a_fabricated_one() -> None:
    """Three failures, three sentences: the document exists, so `do not exist`
    would send the reader — and the repair round-trip — after the wrong problem."""
    markdown = "# Notes\n\nCitations survive a rename of the file [[conversation]].\n"
    with pytest.raises(UngroundedError) as raised:
        check(markdown, [sectioned()], doc_id=DOC_ID)

    assert "do not exist" not in str(raised.value)
    assert "cites nothing" not in str(raised.value)


def test_a_document_that_only_cites_the_whole_conversation_is_not_called_empty() -> None:
    markdown = "# Notes\n\nCitations survive a rename of the file [[conversation]].\n"
    with pytest.raises(UngroundedError, match="section-level"):
        check(markdown, [sectioned()], doc_id=DOC_ID)


def test_the_coarse_form_is_not_offered_in_the_citable_vocabulary() -> None:
    names = citable_names([sectioned()])

    assert "[[conversation]]" not in names
    assert "[[conversation#2 - assistant]]" in names
    assert "[[conversation#Anchor stability]]" not in names


def test_ordinary_evidence_is_unaffected_and_still_citable_whole() -> None:
    """The flag is off by default, so every document the evidence lane projects
    keeps the behaviour it had before this rule existed."""
    document = evidence()
    assert document.cite_sections_only is False
    assert "[[retry-policy]]" in citable_names([document])

    report, _ = check(
        "# Notes\n\nWebhook deliveries are retried five times over [[retry-policy]].\n",
        [document],
        doc_id=DOC_ID,
    )
    assert report.whole_document_citations == ()
    assert report.coverage == 1.0


def test_every_citable_name_of_section_only_evidence_passes_the_contract() -> None:
    """The pairing this rule rests on: what is offered is exactly what is accepted."""
    document = sectioned()
    for name in citable_names([document]):
        markdown = f"# Notes\n\nA claim long enough to need a citation {name}.\n"
        report, _ = check(markdown, [document], doc_id=DOC_ID)
        assert report.violations == (), name
