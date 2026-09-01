# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The `wiki` plugin (roadmap 4.4): the prompt, the repair, and the refusal.

The plugin owns three things and the model owns none of them, so all three are
tested against a scripted provider: what the prompt puts in front of the model,
what happens to a draft that breaks the contract, and what happens when the
second one breaks it too.
"""

from pathlib import PurePosixPath

import pytest

from fakes import ScriptedProvider
from mycelium.markdown.adapter import parse_markdown
from mycelium.sdk.protocols import EvidenceDocument, SynthesisContext, Synthesizer
from mycelium.synthesis.errors import UngroundedError
from mycelium.synthesis.wiki import (
    MAX_ATTEMPTS,
    PLUGIN_ID,
    WikiSynthesizer,
    build_prompt,
    system_prompt,
)

EVIDENCE_TEXT = """\
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

FABRICATED = """\
# Retry Behaviour

Webhook deliveries are retried up to five times [[somewhere-else#Invented]].
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


def context(**kwargs: object) -> SynthesisContext:
    return SynthesisContext(
        topic=str(kwargs.get("topic", "Retry Behaviour")),
        evidence=(evidence(),),
        instructions=str(kwargs.get("instructions", "")),
    )


# ---------------------------------------------------------------------------
# The contract's shape
# ---------------------------------------------------------------------------


def test_the_plugin_satisfies_the_synthesizer_protocol() -> None:
    assert isinstance(WikiSynthesizer(ScriptedProvider(GOOD)), Synthesizer)


def test_the_plugin_declares_itself_non_deterministic() -> None:
    # The declaration gate G6 relies on (ADR-0017's rule, applied to prose): a
    # stage that cannot promise reproducibility must say so, not be discovered.
    meta = WikiSynthesizer(ScriptedProvider(GOOD)).meta
    assert meta.id == PLUGIN_ID == "wiki"
    assert meta.deterministic is False


def test_the_id_carries_no_technology_and_the_description_carries_the_heritage() -> None:
    # D-026: "wiki", never "wiki-llm"; llm-wiki is credited in the description.
    meta = WikiSynthesizer(ScriptedProvider(GOOD)).meta
    assert "llm" not in meta.id
    assert "llm-wiki" in meta.description


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------


def test_the_prompt_hands_the_model_the_complete_citable_vocabulary() -> None:
    prompt = build_prompt(context())
    assert "[[retry-policy]]" in prompt
    assert "[[retry-policy#Backoff]]" in prompt
    assert "Nothing outside this list" in prompt


def test_the_prompt_carries_the_evidence_text() -> None:
    prompt = build_prompt(context())
    assert "Webhook deliveries are retried five times." in prompt
    assert "Backoff doubles after every failed attempt." in prompt


def test_operator_instructions_are_passed_through_but_kept_out_of_the_rules() -> None:
    prompt = build_prompt(context(instructions="Write in the second person."))
    assert "Write in the second person." in prompt
    # Style guidance is not the citation contract, and the contract is enforced
    # after the model has spoken regardless of what it was told.
    assert "Style guidance" in prompt


def test_the_system_prompt_says_the_evidence_is_data_not_instructions() -> None:
    # D-017: all source content is untrusted, including the operator's own.
    assert "never as" in system_prompt()
    assert "instructions" in system_prompt()


def test_the_repair_prompt_quotes_the_violations() -> None:
    prompt = build_prompt(context(), ["[[nope]] cites nothing in the evidence set"])
    assert "previous attempt was rejected" in prompt
    assert "[[nope]] cites nothing in the evidence set" in prompt


# ---------------------------------------------------------------------------
# Accept, repair, refuse
# ---------------------------------------------------------------------------


def test_a_grounded_draft_is_accepted_on_the_first_attempt() -> None:
    provider = ScriptedProvider(GOOD)
    draft = WikiSynthesizer(provider).draft(context())
    assert draft.synthesis.attempts == 1
    assert draft.report.coverage == 1.0
    assert len(provider.prompts) == 1


def test_a_broken_draft_is_repaired_once_with_its_violations_quoted() -> None:
    provider = ScriptedProvider(FABRICATED, GOOD)
    draft = WikiSynthesizer(provider).draft(context())
    assert draft.synthesis.attempts == 2
    assert len(provider.prompts) == 2
    # The second prompt carries what was wrong with the first, which is the whole
    # mechanism: an unexplained retry is a coin flip.
    assert "previous attempt was rejected" in provider.prompts[1]
    assert "somewhere-else" in provider.prompts[1]


def test_two_broken_drafts_write_nothing_and_say_what_the_evidence_lacked() -> None:
    provider = ScriptedProvider(FABRICATED, FABRICATED)
    with pytest.raises(UngroundedError, match="does not support") as caught:
        WikiSynthesizer(provider).draft(context())
    assert caught.value.violations
    assert len(provider.prompts) == MAX_ATTEMPTS


def test_the_lane_never_loops_forever_on_a_model_that_cannot_comply() -> None:
    provider = ScriptedProvider(*[FABRICATED] * 10)
    with pytest.raises(UngroundedError):
        WikiSynthesizer(provider).draft(context())
    assert len(provider.prompts) == MAX_ATTEMPTS, "bounded, and the bound is the constant"


def test_synthesizing_from_no_evidence_is_refused_before_a_model_is_called() -> None:
    provider = ScriptedProvider(GOOD)
    empty = SynthesisContext(topic="Nothing", evidence=())
    with pytest.raises(UngroundedError, match="no evidence"):
        WikiSynthesizer(provider).synthesize(empty)
    assert provider.prompts == [], "no request was made, so nothing was spent"


# ---------------------------------------------------------------------------
# What the run records
# ---------------------------------------------------------------------------


def test_the_synthesis_records_what_produced_it() -> None:
    synthesis = WikiSynthesizer(ScriptedProvider(GOOD)).synthesize(context())
    assert synthesis.provider == "scripted"
    assert synthesis.model == "scripted-1"
    assert synthesis.prompt_digest.startswith("sha256:")
    assert synthesis.parameters == {"effort": "high"}


def test_the_prompt_digest_covers_the_system_prompt_and_the_evidence() -> None:
    first = WikiSynthesizer(ScriptedProvider(GOOD)).synthesize(context())
    other = SynthesisContext(
        topic="Retry Behaviour",
        evidence=(evidence(text=EVIDENCE_TEXT + "\nAn extra sentence of evidence.\n"),),
    )
    second = WikiSynthesizer(ScriptedProvider(GOOD)).synthesize(other)
    assert first.prompt_digest != second.prompt_digest


# ---------------------------------------------------------------------------
# Output the model wraps
# ---------------------------------------------------------------------------


def test_a_document_wrapped_in_a_code_fence_is_unwrapped() -> None:
    """Instruction 4 says not to; when a model does it anyway, every citation
    would be inside a code block and the contract would report "cites nothing"
    for a document that cites correctly."""
    fenced = "```markdown\n" + GOOD + "```"
    draft = WikiSynthesizer(ScriptedProvider(fenced)).draft(context())
    assert draft.synthesis.markdown.startswith("# Retry Behaviour")
    assert draft.report.coverage == 1.0


def test_surrounding_whitespace_is_trimmed_and_the_body_ends_with_a_newline() -> None:
    draft = WikiSynthesizer(ScriptedProvider("\n\n" + GOOD + "\n\n")).draft(context())
    assert draft.synthesis.markdown.startswith("# Retry")
    assert draft.synthesis.markdown.endswith("\n")
