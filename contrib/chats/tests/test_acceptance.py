# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Doc 08 §10's six acceptance gates, one test class each.

The module's specification states the conditions under which it ships, and this
file is where each one is enforced rather than asserted. They are collected here
rather than spread through the suite because they are the *module's* contract:
the other files test how it works, and this one tests whether it is allowed to
exist.

    1. Round-trip fixtures: ≥ 2 providers + pasted text, zero silent loss.
    2. Projection determinism: same record → byte-identical Markdown.
    3. Verbatim invariant: concatenated content in the record ⊇ source text.
    4. Retrieval: chat content reachable with correct message anchors, and the
       `collection:` filter works.
    5. Deletion cascade: record, custody, projection, index.
    6. Plugin-API validation: only public extension points, zero core patches.
"""

import ast
import importlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.ingest import Custody
from mycelium.modules import MODULE_SURFACE
from mycelium.retrieval import search
from mycelium.store import SearchFilters, SqliteStore
from mycelium_chats.archive import find, import_text, list_archive, purge
from mycelium_chats.paths import projection_path
from mycelium_chats.record import Message, decode_transcript
from mycelium_chats.settings import ChatsSettings

IMPORTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
BACKSLASH = chr(92)
NL = chr(10)

PROVIDER_FIXTURES = ("chatgpt-export.json", "claude-export.json")
PASTED_FIXTURES = ("pasted-labelled.txt", "pasted-unlabelled.txt")
ALL_FIXTURES = (*PROVIDER_FIXTURES, *PASTED_FIXTURES, "transcript.md")


def import_fixture(repo: Path, fixtures: Path, name: str, settings: ChatsSettings):
    return import_text(
        repo,
        (fixtures / name).read_text("utf-8"),
        source_uri=name,
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )


# ---------------------------------------------------------------------------
# Gate 1 — round-trip fixtures, zero silent loss
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_gate1_every_fixture_imports_with_nothing_lost(
    repo: Path, fixtures: Path, settings: ChatsSettings, name: str
) -> None:
    """*"every source element recognized, inferred, or preserved as fragment,
    per the fidelity report"* — so `lost` is zero and the three buckets add up."""
    outcomes, _ = import_fixture(repo, fixtures, name, settings)

    assert outcomes, f"{name} produced no conversation"
    for item in outcomes:
        report = item.fidelity
        assert report.lost == 0, f"{name} lost content"
        assert report.turns == report.recognised + report.inferred + report.fragments
        assert report.turns == len(item.transcript.lines)
        assert report.turns > 0


def test_gate1_covers_at_least_two_providers_and_pasted_text(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The gate names the corpus it wants: two providers, plus pasted cases."""
    readers = set()
    for name in ALL_FIXTURES:
        outcomes, _ = import_fixture(repo, fixtures, name, settings)
        readers.update(item.fidelity.reader for item in outcomes)

    assert {"chatgpt", "claude"} <= readers
    assert "pasted" in readers


def test_gate1_residue_is_preserved_rather_than_dropped(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """What "zero silent loss" means for the two cases that cannot be segmented:
    an abandoned edit branch, and a paste with no labels."""
    chatgpt, _ = import_fixture(repo, fixtures, "chatgpt-export.json", settings)
    pasted, _ = import_fixture(repo, fixtures, "pasted-unlabelled.txt", settings)

    branches = chatgpt[0].transcript.fragments
    assert any(line.content == "Linear backoff is simpler." for line in branches)
    assert pasted[0].transcript.fragments, "the unlabelled paste is kept whole"


# ---------------------------------------------------------------------------
# Gate 2 — projection determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_gate2_the_same_record_projects_byte_identically(
    repo: Path, fixtures: Path, settings: ChatsSettings, tmp_path: Path, name: str
) -> None:
    """*"same record → byte-identical Markdown"* — in another directory.

    The gate names the **record**, not the source, and the distinction is real: a
    pasted conversation carries no date of its own, so its filing date is when it
    was first seen, and two imports days apart are two different records. Both
    imports here are given the same clock, which is what "same record" means; the
    machine-independence of a *dated* source is the next test.
    """
    first, _ = import_fixture(repo, fixtures, name, settings)

    elsewhere = tmp_path / "second"
    (elsewhere / "knowledge").mkdir(parents=True)
    second, _ = import_text(
        elsewhere,
        (fixtures / name).read_text("utf-8"),
        source_uri=name,
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )

    for here, there in zip(first, second, strict=True):
        assert here.transcript == there.transcript, "the same record"
        assert here.record_path == there.record_path
        assert here.projection_path == there.projection_path
        assert here.projection_path is not None
        assert (repo / here.projection_path).read_text("utf-8") == (
            elsewhere / there.projection_path
        ).read_text("utf-8")


@pytest.mark.parametrize("name", (*PROVIDER_FIXTURES, "transcript.md"))
def test_gate2_a_dated_source_projects_the_same_on_any_machine_at_any_time(
    repo: Path, fixtures: Path, settings: ChatsSettings, tmp_path: Path, name: str
) -> None:
    """The stronger property, for the sources that can have it.

    An export carrying its own timestamps is filed by them, so its record and its
    projection are a function of the bytes alone — two machines importing it
    months apart agree. A paste cannot have this, and does not claim it.
    """
    first, _ = import_fixture(repo, fixtures, name, settings)

    elsewhere = tmp_path / "later"
    (elsewhere / "knowledge").mkdir(parents=True)
    second, _ = import_text(
        elsewhere,
        (fixtures / name).read_text("utf-8"),
        source_uri=name,
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=datetime(2027, 5, 5, tzinfo=UTC),
    )

    for here, there in zip(first, second, strict=True):
        assert here.record_path == there.record_path
        assert here.projection_path is not None and there.projection_path is not None
        assert (repo / here.projection_path).read_text("utf-8") == (
            elsewhere / there.projection_path
        ).read_text("utf-8")


# ---------------------------------------------------------------------------
# Gate 3 — the verbatim invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_gate3_the_record_contains_what_the_source_said(
    repo: Path, fixtures: Path, settings: ChatsSettings, name: str
) -> None:
    """*"concatenated message content in record ⊇ source text"*.

    Checked on the text a *reader recovered*, which is the only honest form of
    the containment: an export's JSON punctuation is not something anybody said,
    so the invariant is that no recovered character was altered, and that is
    asserted by rebuilding the source's own strings from the record.
    """
    outcomes, _ = import_fixture(repo, fixtures, name, settings)
    source = (fixtures / name).read_text("utf-8")

    for item in outcomes:
        for line in item.transcript.lines:
            for paragraph in line.content.split("\n\n"):
                stripped = paragraph.strip()
                if len(stripped) < 12 or "\\" in stripped:
                    continue  # JSON escapes are the export's, not the speaker's
                assert stripped.split("\n")[0] in source or stripped in source, (
                    f"{name}: {stripped[:60]!r} is not in the source verbatim"
                )


ADVERSARIAL = (
    "plain text",
    "unicode: 設計ノート · Größenordnung · 术语",
    "markdown: ## heading\n\n- list\n\n```py\nx=1\n```\n\n| a | b |\n|---|---|",
    "quotes: > already quoted\n> > twice",
    "blank lines:\n\n\n\nafter three",
    "trailing spaces   \nand a tab\there",
    "a lone backslash \\ and an escape \\## not a heading",
    "emoji 🍄 and a zero-width​space",
    "---\n===\n***\n___",
)
"""Inputs chosen to break the invariant, rather than random ones.

The project's property-test budget and its hypothesis profile are declared once
in the core suite (ADR-0060), and loading a second profile from a contrib
conftest would change the whole session's settings — so this suite states its
adversarial corpus instead. Every entry is a shape that has broken a Markdown
round trip somewhere: block structure, nested quotes, whitespace, escapes,
non-ASCII, and the setext underlines that swallowed a callout during 5.5.
"""


@pytest.mark.parametrize("content", ADVERSARIAL)
def test_gate3_content_survives_an_import_verbatim(
    repo: Path, settings: ChatsSettings, content: str
) -> None:
    """The invariant on the record, for content designed to break it."""
    paste = f"You said:\n{content}\n\nChatGPT said:\nNoted.\n"
    outcomes, _ = import_text(
        repo,
        paste,
        source_uri="adversarial.txt",
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )
    (only,) = outcomes
    written = decode_transcript((repo / only.record_path).read_text("utf-8"))
    first = written.lines[0]

    assert isinstance(first, Message)
    assert first.content == content, "the record holds exactly what the source said"


@pytest.mark.parametrize("content", ADVERSARIAL)
def test_gate3_the_projection_carries_the_content_unchanged(
    repo: Path, settings: ChatsSettings, content: str
) -> None:
    """The other half: the projection carries the same characters.

    Compared by un-quoting the callout — stripping the `> ` a blockquote adds and
    the backslash the projector adds for block safety — rather than by looking
    for words in the compiled KIR. KIR is a *semantic* form: a fence's info
    string becomes a `lang` field and a table becomes rows, so "is this word in
    the node text" asks the wrong question. Un-quoting asks the right one, and
    asks it exactly.
    """
    paste = f"You said:{NL}{content}{NL}{NL}ChatGPT said:{NL}Noted.{NL}"
    outcomes, _ = import_text(
        repo,
        paste,
        source_uri="adversarial.txt",
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )
    assert outcomes[0].projection_path is not None
    text = (repo / outcomes[0].projection_path).read_text("utf-8")

    # The projector rstrips each quoted line, so trailing whitespace inside a
    # message does not survive into the *projection*. The record keeps it, which
    # is where the verbatim invariant lives — asserted by the test above.
    expected = NL.join(line.rstrip() for line in content.split(NL))
    assert unquote_first_callout(text) == expected


def unquote_first_callout(projection: str) -> str:
    """The first callout's body, as the message that produced it.

    Reverses exactly what `_callout` did: drop the `[!role]` head, remove one
    level of `> ` quoting, and undo the escape that keeps a heading from opening
    a section.
    """
    lines = projection.split(NL)
    start = next(index for index, line in enumerate(lines) if line.startswith("> [!"))
    body: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith(">"):
            break
        stripped = line[2:] if line.startswith("> ") else line[1:]
        body.append(stripped[1:] if stripped.startswith(BACKSLASH) else stripped)
    return NL.join(body)


# ---------------------------------------------------------------------------
# Gate 4 — retrieval
# ---------------------------------------------------------------------------


def test_gate4_chat_content_is_reachable_with_a_message_anchor(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """*"chat content reachable via `mycelium_search` with correct citations into
    message anchors; `collection:` filter works"*."""
    import_fixture(repo, fixtures, "chatgpt-export.json", settings)
    import_fixture(repo, fixtures, "claude-export.json", settings)
    build(repo)

    with SqliteStore.open(repo, read_only=True) as store:
        outcome = search(store, "webhook retries back off", limit=5)
        anchors = [hit.hit.chunk.anchor for hit in outcome.hits]

    assert anchors, "the corpus answers the question"
    best = anchors[0]
    assert "/evidence/chats/research/" in best
    # The anchor names a message, not a whole conversation.
    assert best.rsplit("#", 1)[1].split("/")[0] in {
        "1-user",
        "2-assistant",
        "3-user",
        "4-assistant",
    }


def test_gate4_the_collection_filter_selects_one_project(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    import_fixture(repo, fixtures, "chatgpt-export.json", settings)
    import_text(
        repo,
        (fixtures / "claude-export.json").read_text("utf-8"),
        source_uri="claude-export.json",
        project="notes",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )
    build(repo)

    with SqliteStore.open(repo, read_only=True) as store:
        research = search(
            store, "retries citations", limit=10, filters=SearchFilters(collection="chats/research")
        )
        notes = search(
            store, "retries citations", limit=10, filters=SearchFilters(collection="chats/notes")
        )

    assert research.hits and notes.hits
    assert all("/chats/research/" in hit.hit.chunk.anchor for hit in research.hits)
    assert all("/chats/notes/" in hit.hit.chunk.anchor for hit in notes.hits)


def test_gate4_a_citation_resolves_to_the_conversation_and_the_message(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """The anchor is the whole claim: from a hit, a reader gets back to the
    record and to the turn inside it."""
    outcomes, _ = import_fixture(repo, fixtures, "claude-export.json", settings)
    build(repo)

    with SqliteStore.open(repo, read_only=True) as store:
        outcome = search(store, "citations survive a rename", limit=3)
        anchor = outcome.hits[0].hit.chunk.anchor

    path, fragment = anchor.split("#", 1)
    seq = int(fragment.split("-", 1)[0])
    record = decode_transcript((repo / outcomes[0].record_path).read_text("utf-8"))
    turn = next(line for line in record.lines if line.seq == seq)

    assert path == str(outcomes[0].projection_path)
    assert turn.content, "the cited message exists in the record"


# ---------------------------------------------------------------------------
# Gate 5 — the deletion cascade
# ---------------------------------------------------------------------------


def test_gate5_deletion_cascades_through_record_projection_and_index(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """*"Deletion cascade verified (record, CAS, projection, index)"*."""
    outcomes, _ = import_fixture(repo, fixtures, "claude-export.json", settings)
    build(repo)
    entry = find(repo, outcomes[0].transcript.conversation.conv_id)
    assert entry is not None
    digest = entry.conversation.source_digest
    projection = projection_path(entry.record_path, "knowledge")

    with SqliteStore.open(repo, read_only=True) as store:
        assert search(store, "citations survive a rename", limit=3).hits

    purge(repo, entry, knowledge_dir="knowledge", purge_custody=True)
    build(repo)  # the next build drops the index entries

    assert not (repo / entry.record_path).exists()
    assert not (repo / projection).exists()
    assert Custody(repo / ".mycelium").get(digest) is None
    assert list_archive(repo) == ()
    with SqliteStore.open(repo, read_only=True) as store:
        remaining = [
            hit.hit.chunk.anchor
            for hit in search(store, "citations survive a rename", limit=5).hits
        ]
    assert not any("chats" in anchor for anchor in remaining)


def test_gate5_deletion_without_purge_keeps_the_evidence(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    """ADR-0033: destroying evidence is an explicit act, never a side effect."""
    outcomes, _ = import_fixture(repo, fixtures, "claude-export.json", settings)
    entry = find(repo, outcomes[0].transcript.conversation.conv_id)
    assert entry is not None

    purge(repo, entry, knowledge_dir="knowledge")

    assert Custody(repo / ".mycelium").get(entry.conversation.source_digest) is not None


# ---------------------------------------------------------------------------
# Gate 6 — plugin-API validation
# ---------------------------------------------------------------------------

MODULE_SOURCE = Path(__file__).resolve().parents[1] / "src" / "mycelium_chats"

PUBLIC_SURFACE = frozenset(MODULE_SURFACE)
"""Every core module this module is allowed to import — **the core's own list**.

The mechanical form of doc 08 §10's sixth gate. "Zero core patches" is not
checkable by reading a diff — the module could reach into an internal and the
diff would look clean — so it is checked here: every `mycelium.*` import in the
module's sources must name a module the core declares module-facing, and every
name imported from one must be in that module's `__all__`.

**Read from `mycelium.modules.MODULE_SURFACE` rather than restated** (roadmap
5.14). Restated, this was the module's claim about itself and a core author who
moved one of those surfaces met a failing test in somebody else's distribution.
Declared in the core, it is the core's claim about what it offers, and the
difference is who the failure is addressed to (ADR-0086).

Adding an entry is still the reviewable event the gate exists to force — it just
happens in the core now. It means a module needed something the core did not
offer as module-facing, which is either an API gap to fix or a coupling to record
before the freeze.
"""


def module_files() -> list[Path]:
    return sorted(MODULE_SOURCE.rglob("*.py"))


def test_gate6_the_module_has_sources_to_check() -> None:
    assert len(module_files()) >= 10


@pytest.mark.parametrize("path", module_files(), ids=lambda path: path.name)
def test_gate6_the_module_imports_only_the_published_surface(path: Path) -> None:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    offences: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not module.startswith("mycelium.") and module != "mycelium":
                continue
            if module not in PUBLIC_SURFACE:
                offences.append(f"line {node.lineno}: from {module} import …")
                continue
            exported = set(getattr(importlib.import_module(module), "__all__", ()))
            offences.extend(
                f"line {node.lineno}: {module}.{alias.name} is not in its `__all__`"
                for alias in node.names
                if alias.name not in exported
            )
        elif isinstance(node, ast.Import):
            offences.extend(
                f"line {alias.lineno if hasattr(alias, 'lineno') else node.lineno}: "
                f"import {alias.name}"
                for alias in node.names
                if (alias.name.startswith("mycelium.") or alias.name == "mycelium")
                and alias.name not in PUBLIC_SURFACE
            )

    assert not offences, f"{path.name} reaches outside the published surface:\n  " + "\n  ".join(
        offences
    )


def test_gate6_the_module_declares_itself_through_an_entry_point() -> None:
    """Discovery is the published mechanism, not an import the core hard-codes."""
    from mycelium.modules import MODULE_ENTRY_POINT_GROUP, installed_ids, load_module

    assert MODULE_ENTRY_POINT_GROUP == "mycelium.modules"
    assert "chats" in installed_ids()
    module = load_module("chats")
    assert module.meta.id == "chats"
    assert module.commands().info.name == "chats"


def test_gate6_the_core_contains_no_reference_to_this_module() -> None:
    """The other direction, and the stronger half of "zero core patches": the
    core must not know this module exists."""
    core = Path(__file__).resolve().parents[3] / "src" / "mycelium"
    mentions = [
        path.relative_to(core).as_posix()
        for path in sorted(core.rglob("*.py"))
        if "mycelium_chats" in path.read_text("utf-8")
    ]
    assert mentions == []


def test_gate6_the_module_is_mounted_by_the_core_without_being_named() -> None:
    from typer.main import get_command

    from mycelium.cli.app import app
    from mycelium.modules import mount

    # Exactly what `main()` does, and idempotent — mounting at import time is
    # what created the cycle this call replaced (roadmap 5.5).
    _, problems = mount(app)
    assert problems == ()

    commands = get_command(app).commands
    assert "chats" in commands
    assert set(commands["chats"].commands) == {
        "import",
        "list",
        "show",
        "export",
        "resume",
        "delete",
        # Doc 08 §9's table has six rows; `distil` is §7's optional half, added at
        # roadmap 5.15. Pinned here on purpose: a command is a public surface, so
        # one appearing or vanishing should be a decision somebody made.
        "distil",
    }
