# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The archive: identity, custody, secrets, fidelity, retention, deletion.

The claims under test:

**Identity is derived and an import is idempotent** — the same export twice is
the same files and no diff, because `conv_id` comes from the original's digest
and `imported_at` comes from custody's `first_seen`.

**The original is kept**, so the archive is re-derivable (invariant 5).

**A secret is redacted where it spreads and kept where it is evidence.**

**Retention excludes from the vault without deleting the archive**, and
deletion cascades exactly as far as it is told to.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.ingest import Custody
from mycelium.sdk.identity import digest_bytes, is_derived_ulid
from mycelium.sdk.types import CustodyKind
from mycelium_chats.archive import (
    find,
    import_text,
    list_archive,
    load_record,
    purge,
    record_path_of,
)
from mycelium_chats.paths import projection_path
from mycelium_chats.settings import ChatsSettings

IMPORTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def do_import(repo: Path, text: str, settings: ChatsSettings, **kwargs: object):
    return import_text(
        repo,
        text,
        source_uri=str(kwargs.pop("source_uri", "export.json")),
        project=str(kwargs.pop("project", "research")),
        settings=settings,
        knowledge_dir="knowledge",
        now=kwargs.pop("now", IMPORTED),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Identity and idempotence
# ---------------------------------------------------------------------------


def test_the_archive_path_is_the_one_the_spec_draws(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    (only,) = outcomes
    parts = only.record_path.parts

    # chats/<project>/<year>/<month>/<date>-<slug>-<ulid6>.chat.jsonl (doc 08 §5)
    assert parts[:4] == ("chats", "research", "2026", "07")
    assert parts[4].startswith("2026-07-31-anchor-stability-")
    assert parts[4].endswith(".chat.jsonl")
    assert (
        parts[4]
        .removesuffix(".chat.jsonl")
        .endswith(only.transcript.conversation.conv_id[-6:].lower())
    )


def test_identity_is_derived_from_the_original_rather_than_minted(
    repo: Path, fixtures: Path, settings
) -> None:
    """ADR-0046's mechanism: reproducible without being recorded."""
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    assert is_derived_ulid(outcomes[0].transcript.conversation.conv_id)


def test_importing_the_same_export_twice_changes_nothing(
    repo: Path, fixtures: Path, settings
) -> None:
    """The property that makes a nightly re-export a safe habit."""
    text = (fixtures / "chatgpt-export.json").read_text("utf-8")
    first, _ = do_import(repo, text, settings)
    before = {item.record_path: (repo / item.record_path).read_text("utf-8") for item in first}

    # A later clock, deliberately: `imported_at` must come from custody, not now.
    second, _ = do_import(repo, text, settings, now=datetime(2027, 1, 1, tzinfo=UTC))

    assert [item.written for item in second] == [False, False]
    assert [item.record_path for item in second] == [item.record_path for item in first]
    for item in second:
        assert (repo / item.record_path).read_text("utf-8") == before[item.record_path]


def test_a_changed_export_lands_beside_its_predecessor(
    repo: Path, fixtures: Path, settings
) -> None:
    """Different bytes are a different conversation: the digest is in the id."""
    text = (fixtures / "claude-export.json").read_text("utf-8")
    first, _ = do_import(repo, text, settings)
    edited = text.replace("Rotate that token", "Rotate that credential")
    second, _ = do_import(repo, edited, settings)

    assert first[0].record_path != second[0].record_path
    assert (repo / first[0].record_path).exists()
    assert (repo / second[0].record_path).exists()


def test_two_conversations_in_one_export_get_their_own_identities(
    repo: Path, fixtures: Path, settings
) -> None:
    outcomes, _ = do_import(repo, (fixtures / "chatgpt-export.json").read_text("utf-8"), settings)
    ids = {item.transcript.conversation.conv_id for item in outcomes}

    assert len(outcomes) == 2
    assert len(ids) == 2


def test_the_record_round_trips_through_its_own_encoding(
    repo: Path, fixtures: Path, settings
) -> None:
    outcomes, _ = do_import(repo, (fixtures / "transcript.md").read_text("utf-8"), settings)
    written = load_record(repo / outcomes[0].record_path)

    assert written == outcomes[0].transcript
    assert written.conversation.schema_version == "mycelium/chat/v0"
    # Line 1 is the header, and every line after it is a message or a fragment.
    lines = (repo / outcomes[0].record_path).read_text("utf-8").splitlines()
    assert json.loads(lines[0])["kind"] == "conversation"
    assert {json.loads(line)["kind"] for line in lines[1:]} <= {"message", "fragment"}


# ---------------------------------------------------------------------------
# Custody (invariant 5)
# ---------------------------------------------------------------------------


def test_the_original_input_is_kept_under_its_own_digest(
    repo: Path, fixtures: Path, settings
) -> None:
    text = (fixtures / "claude-export.json").read_text("utf-8")
    outcomes, _ = do_import(repo, text, settings)
    digest = outcomes[0].transcript.conversation.source_digest

    assert digest == digest_bytes(text.encode("utf-8"))
    custody = Custody(repo / ".mycelium")
    assert custody.get(digest) == text.encode("utf-8")
    record = custody.record(digest)
    assert record is not None
    assert record.kind is CustodyKind.ORIGINAL
    assert record.connector == "chats/claude"


def test_every_import_files_a_fidelity_report_in_custody(
    repo: Path, fixtures: Path, settings
) -> None:
    outcomes, _ = do_import(repo, (fixtures / "chatgpt-export.json").read_text("utf-8"), settings)
    reports = [
        record
        for record in Custody(repo / ".mycelium").records()
        if record.kind is CustodyKind.FIDELITY
    ]
    assert len(reports) == len(outcomes)


def test_the_fidelity_report_accounts_for_every_turn(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "chatgpt-export.json").read_text("utf-8"), settings)
    report = outcomes[0].fidelity

    assert report.turns == report.recognised + report.inferred + report.fragments
    assert report.turns == len(outcomes[0].transcript.lines)
    assert report.lost == 0
    assert report.reader == "chatgpt"
    # The abandoned branch is the fragment, so this import is not "complete".
    assert report.fragments == 1
    assert not report.complete


def test_a_clean_provider_import_is_complete(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    assert outcomes[0].fidelity.complete


# ---------------------------------------------------------------------------
# Secrets (doc 08 §6)
# ---------------------------------------------------------------------------


def test_a_secret_is_flagged_and_redacted_in_the_projection_not_the_record(
    repo: Path, fixtures: Path, settings
) -> None:
    """Doc 08 §6's asymmetry: the projection reaches Git and the index, the
    record is the archive, and the original is already in custody."""
    outcomes, notes = do_import(
        repo, (fixtures / "claude-export.json").read_text("utf-8"), settings
    )
    conversation = outcomes[0].transcript.conversation
    record = (repo / outcomes[0].record_path).read_text("utf-8")
    projection = (repo / outcomes[0].projection_path).read_text("utf-8")

    assert conversation.secrets, "the fixture carries a token-shaped string"
    assert "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" in record
    assert "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" not in projection
    assert any("secret-pattern match" in note for note in notes)
    assert "redacted here" in projection


def test_redact_in_record_rewrites_the_record_too(repo: Path, fixtures: Path) -> None:
    strict = ChatsSettings(timezone="UTC", redact_in_record=True)
    outcomes, _ = do_import(
        repo, (Path(__file__).parent / "fixtures" / "claude-export.json").read_text("utf-8"), strict
    )
    record = (repo / outcomes[0].record_path).read_text("utf-8")

    assert "ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" not in record
    # And the original is still whole in custody: that is the point of keeping it.
    digest = outcomes[0].transcript.conversation.source_digest
    kept = Custody(repo / ".mycelium").get(digest)
    assert kept is not None and b"ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" in kept


# ---------------------------------------------------------------------------
# Retention (doc 08 §8)
# ---------------------------------------------------------------------------


def test_retention_keeps_the_archive_and_withholds_the_projection(
    repo: Path, fixtures: Path
) -> None:
    windowed = ChatsSettings(timezone="UTC", retention_months=1)
    outcomes, notes = do_import(
        repo,
        (fixtures / "claude-export.json").read_text("utf-8"),
        windowed,
        now=datetime(2027, 1, 1, tzinfo=UTC),
    )
    (only,) = outcomes

    assert (repo / only.record_path).exists(), "the archive is kept"
    assert only.projection_path is None
    assert any("retention_months" in note for note in notes)
    assert not (repo / projection_path(only.record_path, "knowledge")).exists()


def test_a_conversation_inside_the_window_is_projected(repo: Path, fixtures: Path) -> None:
    windowed = ChatsSettings(timezone="UTC", retention_months=24)
    outcomes, _ = do_import(
        repo,
        (fixtures / "claude-export.json").read_text("utf-8"),
        windowed,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert outcomes[0].projection_path is not None


# ---------------------------------------------------------------------------
# Listing and lookup
# ---------------------------------------------------------------------------


def test_the_listing_is_newest_first_and_filters_by_project(
    repo: Path, fixtures: Path, settings
) -> None:
    do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    do_import(
        repo,
        (fixtures / "transcript.md").read_text("utf-8"),
        settings,
        source_uri="transcript.md",
        project="notes",
    )
    everything = list_archive(repo)
    only_notes = list_archive(repo, project="notes")

    assert len(everything) == 2
    stamps = [
        entry.conversation.started_at or entry.conversation.imported_at for entry in everything
    ]
    assert stamps == sorted(stamps, reverse=True)
    assert [entry.conversation.project for entry in only_notes] == ["notes"]


def test_a_conversation_is_found_by_an_id_prefix(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    conv_id = outcomes[0].transcript.conversation.conv_id

    assert find(repo, conv_id) is not None
    assert find(repo, conv_id[:8]) is not None
    assert find(repo, "ZZZZZZ") is None


def test_a_conversation_is_found_by_the_handle_the_listing_prints(
    repo: Path, fixtures: Path, settings
) -> None:
    """The bug running the CLI found: `chats list` prints the last six characters
    as the handle, and identity is *derived*, so every id begins with ten zeros
    and a prefix match distinguished nothing."""
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    conv_id = outcomes[0].transcript.conversation.conv_id
    handle = conv_id[-6:]

    assert handle.lower() in outcomes[0].record_path.name, "the filename carries it too"
    found = find(repo, handle.lower())
    assert found is not None
    assert found.conversation.conv_id == conv_id


def test_an_empty_lookup_matches_nothing(repo: Path) -> None:
    assert find(repo, "   ") is None


def test_an_ambiguous_prefix_is_refused_rather_than_resolved(
    repo: Path, fixtures: Path, settings
) -> None:
    do_import(repo, (fixtures / "chatgpt-export.json").read_text("utf-8"), settings)
    with pytest.raises(ValueError, match="more than one conversation"):
        find(repo, "0")  # every derived ULID starts with ten zeros


def test_the_listing_survives_a_damaged_record(repo: Path, fixtures: Path, settings) -> None:
    """A listing is not the place a corrupt file stops the world."""
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    (repo / outcomes[0].record_path).write_text("not jsonl at all\n", encoding="utf-8")
    assert list_archive(repo) == ()


# ---------------------------------------------------------------------------
# Deletion (doc 08 §8)
# ---------------------------------------------------------------------------


def test_deletion_removes_the_record_and_the_projection_and_keeps_the_evidence(
    repo: Path, fixtures: Path, settings
) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    entry = find(repo, outcomes[0].transcript.conversation.conv_id)
    assert entry is not None
    digest = entry.conversation.source_digest

    removed = purge(repo, entry, knowledge_dir="knowledge")

    assert set(removed) == {entry.record_path, projection_path(entry.record_path, "knowledge")}
    assert not (repo / entry.record_path).exists()
    assert not (repo / outcomes[0].projection_path).exists()
    # ADR-0033: deleting evidence is an explicit act, never a side effect.
    assert Custody(repo / ".mycelium").get(digest) is not None
    assert list_archive(repo) == ()


def test_purge_also_removes_the_archived_original(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    entry = find(repo, outcomes[0].transcript.conversation.conv_id)
    assert entry is not None
    digest = entry.conversation.source_digest

    purge(repo, entry, knowledge_dir="knowledge", purge_custody=True)

    assert Custody(repo / ".mycelium").get(digest) is None


def test_deletion_prunes_the_dated_directories_it_emptied(
    repo: Path, fixtures: Path, settings
) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    entry = find(repo, outcomes[0].transcript.conversation.conv_id)
    assert entry is not None

    purge(repo, entry, knowledge_dir="knowledge")

    assert not (repo / "chats" / "research" / "2026" / "07").exists()
    assert not (repo / "chats" / "research").exists()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def test_the_configured_timezone_decides_the_paths_date(repo: Path, fixtures: Path) -> None:
    """Doc 08 §5's rule, and the reason `[chats] timezone` exists: the record's
    timestamps stay UTC, and only the filing date moves."""
    text = (fixtures / "claude-export.json").read_text("utf-8")
    utc, _ = do_import(repo, text, ChatsSettings(timezone="UTC"))
    conversation = utc[0].transcript.conversation

    behind = record_path_of(conversation, ChatsSettings(timezone="-11:00"))
    ahead = record_path_of(conversation, ChatsSettings(timezone="+13:00"))

    # 2026-07-31T09:02Z is the 30th at -11:00 and the 31st at +13:00.
    assert "2026-07-30" in behind.name
    assert "2026-07-31" in ahead.name
    assert conversation.started_at is not None
    assert conversation.started_at.isoformat().endswith("+00:00")


def test_the_projection_mirrors_the_records_path(repo: Path, fixtures: Path, settings) -> None:
    outcomes, _ = do_import(repo, (fixtures / "claude-export.json").read_text("utf-8"), settings)
    (only,) = outcomes

    assert only.projection_path is not None
    assert only.projection_path.parts[:4] == ("knowledge", "evidence", "chats", "research")
    assert only.projection_path.stem == only.record_path.name.removesuffix(".chat.jsonl")
