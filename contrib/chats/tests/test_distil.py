# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Chat distillation (roadmap 5.15, doc 08 §7, ADR-0087).

Three claims, and the first is the one the item was filed to answer:

**A distilled conversation cites the message a claim came from.** The citable
vocabulary offered to the model is message anchors and nothing else, the two
whole-conversation spellings are both refused, and a refusal comes back with the
sections the claim could have cited so the repair round-trip can act on it.

**A distillation is an ordinary synthesized document.** Same folder, same
provenance frontmatter, same `mycelium verify` and `mycelium promote` — the
module contributes evidence and a topic and decides nothing else.

**A refusal costs the conversation nothing.** Doc 08 §7 calls distillation
optional; a conversation that cannot be distilled is still archived, projected
and searchable.

Every test runs against a scripted provider (ADR-0035): the item observed that
this needs `[synthesis]` and therefore a provider, and that the existing lane's
answer is the one to reuse.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.cli.output import ExitCode
from mycelium.synthesis import Completion, UngroundedError, WikiSynthesizer
from mycelium.synthesis.citations import citable_names
from mycelium.verification.grounding import section_text
from mycelium_chats.archive import import_text
from mycelium_chats.distil import (
    citable_evidence,
    distil_conversation,
    message_citations,
    topic_of,
    write_distillation,
)
from mycelium_chats.projection import message_heading
from mycelium_chats.settings import ChatsSettings

FIXTURE = "claude-export.json"
CONFIGURED = """[project]
name = "fixture"
knowledge_dir = "knowledge"

[modules]
enabled = ["chats"]

[chats]
timezone = "UTC"
default_project = "research"

[synthesis]
provider = "anthropic"
"""
"""The `repo` fixture's configuration plus a named provider — enough for the lane
to be *active*, which is all `[synthesis] enabled = "auto"` asks (D-020). No
provider is ever constructed in this suite; every test that reaches a model
reaches a scripted one."""
IMPORTED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
"""A fixed import clock, so a test that asserts a path is not a test about today.

Defined here rather than imported from `conftest`: this suite is a package, so a
conftest import would depend on where `pytest` was started from. `test_acceptance`
keeps its own for the same reason."""


class ScriptedProvider:
    """An LLM that answers from a list, in order — this suite's test double.

    The core has one of these too (`tests/fakes.py`) and this is deliberately not
    an import of it. A module is a distribution of its own, and one whose tests
    reach into another package's *test* helpers has a dependency nobody declared
    and nobody ships — the coupling doc 08 §10's sixth gate checks for in the
    sources. That satisfying `LlmProvider` takes a dozen lines is itself the point
    ADR-0035 made about the seam.
    """

    def __init__(self, *answers: str, model: str = "scripted-1") -> None:
        self._answers = list(answers)
        self._model = model
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return self._model

    def complete(self, *, system: str, prompt: str) -> Completion:
        self.prompts.append(prompt)
        if not self._answers:
            msg = "the scripted provider ran out of answers"
            raise AssertionError(msg)
        return Completion(text=self._answers.pop(0), model=self._model, parameters={})


def archived(repo: Path, fixtures: Path, settings: ChatsSettings, name: str = FIXTURE):
    """Import one fixture and return what a distillation needs from it."""
    outcomes, _ = import_text(
        repo,
        (fixtures / name).read_text("utf-8"),
        source_uri=name,
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED_AT,
    )
    outcome = outcomes[0]
    assert outcome.projection_path is not None
    return outcome.transcript, outcome.projection_path


def evidence_of_fixture(repo: Path, fixtures: Path, settings: ChatsSettings):
    transcript, projection = archived(repo, fixtures, settings)
    text = (repo / projection).read_text("utf-8")
    return transcript, projection, citable_evidence(transcript, projection, text)


def document(stem: str, *citations: str) -> str:
    """A candidate document whose every claim carries one of `citations`."""
    body = "\n\n".join(
        f"A claim long enough to need a citation of its own [[{stem}#{item}]]."
        for item in citations
    )
    return f"# Anchor stability\n\n{body}\n"


# ---------------------------------------------------------------------------
# What a distilled conversation may cite
# ---------------------------------------------------------------------------


def test_the_citable_vocabulary_is_message_anchors_and_nothing_else(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection, evidence = evidence_of_fixture(repo, fixtures, settings)
    names = citable_names([evidence])

    expected = {f"[[{projection.stem}#{message_heading(line)}]]" for line in transcript.lines}
    assert set(names) == expected
    assert f"[[{projection.stem}]]" not in names
    assert f"[[{projection.stem}#{transcript.conversation.title}]]" not in names


def test_the_title_heading_covers_the_whole_conversation_which_is_why_it_is_dropped(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The measurement behind the decision: the coarse citation has two spellings.

    `[[conversation]]` is the obvious one. The other is the projection's own title
    heading, whose section text is every message in the file — so dropping it from
    the citable set is not tidiness, it is the same rule applied twice.
    """
    _, projection, evidence = evidence_of_fixture(repo, fixtures, settings)
    text = (repo / projection).read_text("utf-8")
    from mycelium.synthesis import evidence_of

    unnarrowed = evidence_of(projection, text)
    title = unnarrowed.headings[0]

    assert section_text(unnarrowed.kir, title) == section_text(unnarrowed.kir, "")
    assert title not in evidence.headings


def test_a_message_citation_is_accepted_and_covers_its_claim(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection = archived(repo, fixtures, settings)
    text = document(projection.stem, "2 · assistant", "4 · assistant")
    provider = ScriptedProvider(text)

    result = distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    assert result.report.coverage == 1.0
    assert result.report.claims == 2
    assert len(message_citations(result.report.citations)) == 2
    assert all("#" in citation for citation in result.report.citations)


def test_citing_the_whole_conversation_is_refused_twice_and_writes_nothing(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection = archived(repo, fixtures, settings)
    coarse = (
        f"# Anchor stability\n\nA claim long enough to need a citation [[{projection.stem}]].\n"
    )
    provider = ScriptedProvider(coarse, coarse)

    with pytest.raises(UngroundedError) as raised:
        distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    assert "section-level" in str(raised.value)
    assert not (repo / "knowledge" / "candidate").exists()


def test_a_refusal_tells_the_model_which_messages_it_could_have_cited(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The repair round-trip is the mechanism; a violation that named no remedy
    would spend the second attempt without improving its odds."""
    transcript, projection = archived(repo, fixtures, settings)
    coarse = (
        f"# Anchor stability\n\nA claim long enough to need a citation [[{projection.stem}]].\n"
    )
    good = document(projection.stem, "2 · assistant")
    provider = ScriptedProvider(coarse, good)

    result = distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    assert result.record.attempts == 2
    repair = provider.prompts[1]
    assert "too long to check" in repair
    assert "2 · assistant" in repair


def test_the_prompt_does_not_offer_what_the_contract_refuses(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """Offering without enforcing is a suggestion; enforcing without offering is a
    trap. The evidence block used to say `cite as [[document]]` from the KIR while
    the contract read `headings` — they agreed only by coincidence (ADR-0087)."""
    transcript, projection = archived(repo, fixtures, settings)
    provider = ScriptedProvider(document(projection.stem, "2 · assistant"))

    distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    prompt = provider.prompts[0]
    assert f"cite as [[{projection.stem}]]" not in prompt
    assert f"cite as [[{projection.stem}#{transcript.conversation.title}]]" not in prompt
    assert f"[[{projection.stem}#2 · assistant]]" in prompt


# ---------------------------------------------------------------------------
# A distillation is an ordinary synthesized document
# ---------------------------------------------------------------------------


def test_the_candidate_lands_where_every_synthesized_document_lands(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection = archived(repo, fixtures, settings)
    provider = ScriptedProvider(document(projection.stem, "2 · assistant"))

    result = distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)
    written = write_distillation(repo, result)

    assert result.candidate.path.parts[:2] == ("knowledge", "candidate")
    text = written.read_text("utf-8")
    assert "origin: synthesized" in text
    assert "generated_by: scripted/scripted-1" in text
    # Its own grade is not its to write: `mycelium verify` stamps grounding.
    assert "grounding:" not in text


def test_the_run_is_recorded_in_custody_before_the_document_names_it(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection = archived(repo, fixtures, settings)
    provider = ScriptedProvider(document(projection.stem, "2 · assistant"))

    result = distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    assert result.record.provider == "scripted"
    assert result.record_digest.startswith("sha256:")
    assert result.record_digest in write_distillation(repo, result).read_text("utf-8")


def test_the_topic_is_doc_08_section_7s_own_words_and_invents_nothing(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, _ = archived(repo, fixtures, settings)

    topic = topic_of(transcript.conversation)

    assert "Decisions and outcomes" in topic
    assert transcript.conversation.title in topic


# ---------------------------------------------------------------------------
# A refusal costs the conversation nothing
# ---------------------------------------------------------------------------


def test_a_conversation_that_cannot_be_distilled_is_still_archived_and_projected(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    transcript, projection = archived(repo, fixtures, settings)
    fabricated = "# Anchor stability\n\nA claim long enough to need a citation [[invented]].\n"
    provider = ScriptedProvider(fabricated, fabricated)

    with pytest.raises(UngroundedError):
        distil_conversation(repo, WikiSynthesizer(provider), transcript, projection)

    assert (repo / projection).is_file()
    assert (repo / "chats").is_dir()


def test_distilling_twice_replaces_the_draft_rather_than_accumulating(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The core lane's rule, inherited: two runs on one subject are two drafts of
    one document, and the superseded one is in Git."""
    transcript, projection = archived(repo, fixtures, settings)

    first = ScriptedProvider(document(projection.stem, "2 · assistant"))
    write_distillation(
        repo, distil_conversation(repo, WikiSynthesizer(first), transcript, projection)
    )
    second = ScriptedProvider(document(projection.stem, "2 · assistant", "4 · assistant"))
    write_distillation(
        repo, distil_conversation(repo, WikiSynthesizer(second), transcript, projection)
    )

    candidates = sorted((repo / "knowledge" / "candidate").glob("*.md"))
    assert len(candidates) == 1
    assert "4 · assistant" in candidates[0].read_text("utf-8")


def test_message_citations_counts_distinct_messages_not_citations() -> None:
    """What the CLI reports: eight claims citing one message is a summary of one
    turn, and an operator should see that before promoting it."""
    assert message_citations(("a.md#1 · user", "a.md#1 · user", "a.md#2 · assistant")) == (
        "a.md#1 · user",
        "a.md#2 · assistant",
    )
    assert message_citations(("a.md",)) == ()


# ---------------------------------------------------------------------------
# The command (doc 08 §9's shape, ADR-0010's conventions)
# ---------------------------------------------------------------------------


def run(*args: str):  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from mycelium_chats.cli import app

    return CliRunner().invoke(app, list(args))


def test_distil_without_a_provider_is_a_usage_error_that_says_what_to_configure(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The repository's `mycelium.toml` names no `[synthesis] provider`, which is
    every default install (D-013): no key, no call, and a sentence saying so."""
    transcript, _ = archived(repo, fixtures, settings)

    result = run("distil", transcript.conversation.conv_id, "--root", str(repo))

    assert result.exit_code == ExitCode.USAGE
    assert "[synthesis]" in result.output
    assert "archived, projected" in result.output


def test_distil_refuses_a_conversation_it_cannot_find(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """With the lane configured, an unknown id is the failure reported.

    The repository is given a provider first, because the two refusals are
    ordered and the order is a decision: a repository that cannot distil at all
    is told so before an argument is looked at, or an operator whose real problem
    is `[synthesis]` goes hunting for a conversation id instead.
    """
    with (repo / "mycelium.toml").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(CONFIGURED)
    archived(repo, fixtures, settings)

    result = run("distil", "01ARZ3NDEKTSV4RRFFQ69G5FAV", "--root", str(repo))

    assert result.exit_code == ExitCode.FAILED
    assert "no archived conversation matches" in result.output


def test_the_module_must_be_enabled_before_it_will_distil(
    tmp_path: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """Every command in this module refuses a repository that has not named it —
    enablement is checked before anything is read (roadmap 5.5)."""
    root = tmp_path / "bare"
    (root / "knowledge").mkdir(parents=True)
    (root / "mycelium.toml").write_text('[project]\nname = "bare"\n', encoding="utf-8")

    result = run("distil", "01ARZ3NDEKTSV4RRFFQ69G5FAV", "--root", str(root))

    assert result.exit_code == ExitCode.USAGE
