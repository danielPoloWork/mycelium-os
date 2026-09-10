# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Import hot path (roadmap 5.5).

An import is an authoring action, not a build stage, so it sits under no gate's
budget — these are a baseline, and no performance claim is made. What they exist
for is the shape of the cost: reading an export is regex and dictionary work,
and the writes are what a filesystem charges for.

Kept in the module's own suite so a promoted repository takes them with it
(spec 05 §4.3).
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium_chats.archive import import_text
from mycelium_chats.paths import archive_path, projection_path
from mycelium_chats.projection import project_transcript
from mycelium_chats.readers import ImportContext, reader_for
from mycelium_chats.record import Transcript, decode_transcript, encode_transcript
from mycelium_chats.settings import ChatsSettings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
"""One directory up: the benchmarks live in `bench/` and share the suite's
fixtures rather than keeping a second copy of an export to drift from."""
IMPORTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
SETTINGS = ChatsSettings(timezone="UTC")


@pytest.fixture(scope="module")
def export() -> str:
    return (FIXTURES / "chatgpt-export.json").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def transcript(export: str) -> Transcript:
    """One archived conversation, without touching a filesystem to get it."""
    reader = reader_for(export, provider=None, source_uri="chatgpt-export.json")
    result = reader.read(export, ImportContext(project="research"))
    from mycelium_chats.record import Conversation, participants_of, renumber

    lines = tuple(renumber(result.conversations[0].lines))
    conversation = Conversation(
        conv_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        title=result.conversations[0].title,
        project="research",
        provider="chatgpt",
        imported_at=IMPORTED,
        source_digest="sha256:" + "ab" * 32,
        participants=participants_of(lines),
    )
    lines = tuple(line.model_copy(update={"conv_id": conversation.conv_id}) for line in lines)
    return Transcript(conversation=conversation, lines=lines)


def test_read_a_chatgpt_export(benchmark: BenchmarkFixture, export: str) -> None:
    reader = reader_for(export, provider=None, source_uri="chatgpt-export.json")
    context = ImportContext(project="research")
    benchmark(reader.read, export, context)


def test_project_a_conversation(benchmark: BenchmarkFixture, transcript: Transcript) -> None:
    record = archive_path(
        project="research",
        title=transcript.conversation.title,
        conv_id=transcript.conversation.conv_id,
        dated=IMPORTED,
        zone=UTC,
    )
    projection = projection_path(record, "knowledge")
    benchmark(project_transcript, transcript, record, projection=projection)


def test_round_trip_a_record(benchmark: BenchmarkFixture, transcript: Transcript) -> None:
    text = encode_transcript(transcript)
    benchmark(decode_transcript, text)


def test_import_end_to_end(benchmark: BenchmarkFixture, export: str, tmp_path: Path) -> None:
    """The whole authoring action, filesystem included — the number an operator
    actually waits for."""
    root = tmp_path / "repo"
    (root / "knowledge").mkdir(parents=True)

    def run() -> None:
        import_text(
            root,
            export,
            source_uri="chatgpt-export.json",
            project="research",
            settings=SETTINGS,
            knowledge_dir="knowledge",
            now=IMPORTED,
        )

    benchmark(run)
