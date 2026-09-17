# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Hostile input at the chat-import boundary (B15; roadmap 6.3, ADR-0119).

An export is untrusted like any other source, and the failure it can produce must be
the typed, per-input kind the import reports — never a traceback out of the command.
The review found one shape that was not: a hundred thousand nested brackets is JSON
`json.loads` refuses with a `RecursionError`, which is not a `ValueError`, so every
reader's ``except ValueError`` let it through and `mycelium chats import` died on it
(BUG-0030). These tests hold the boundary closed.
"""

import time

import pytest

from mycelium_chats.readers import ImportContext, ReaderError, reader_for, reader_ids
from mycelium_chats.segment import SegmentationError, _load

pytestmark = pytest.mark.boundary("B15")
"""The threat-model boundary these tests hold (docs/security/threat-model.md §4)."""

DEEP = "[" * 100_000
"""Brackets nested past the interpreter's recursion limit, and nothing else."""

CONTEXT = ImportContext(project="research", source_uri="hostile.json")


def test_deeply_nested_json_is_refused_as_a_typed_reader_error_when_sniffed() -> None:
    """The unpinned path: every reader is asked, and none may raise anything but
    the registry's own refusal."""
    started = time.perf_counter()
    with pytest.raises(ReaderError):
        reader_for(DEEP, provider=None, source_uri="hostile.json", mapping={})
    assert time.perf_counter() - started < 5.0


@pytest.mark.parametrize("provider", ["chatgpt", "claude", "generic"])
def test_deeply_nested_json_is_refused_as_a_typed_reader_error_when_pinned(provider: str) -> None:
    """The pinned path: a reader chosen by name still has to read the bytes, and
    refuses them by name rather than by traceback."""
    reader = reader_for(
        DEEP,
        provider=provider,
        source_uri="hostile.json",
        mapping={"messages": "m", "role": "r", "content": "c"} if provider == "generic" else {},
    )
    with pytest.raises(ReaderError, match="not JSON"):
        reader.read(
            DEEP,
            ImportContext(
                project="research",
                source_uri="hostile.json",
                mapping={"messages": "m", "role": "r", "content": "c"}
                if provider == "generic"
                else {},
            ),
        )


def test_the_pasted_reader_does_not_claim_bracket_soup_as_a_conversation() -> None:
    """`pasted` accepts what is *not* JSON. Bracket soup is JSON-shaped and unreadable
    at the same time; claiming it would archive punctuation and call that success."""
    pasted = reader_for("hello there", provider="pasted", source_uri="x", mapping={})
    assert pasted.sniff(DEEP, source_uri="hostile.txt") is False


def test_the_segmenter_refuses_a_deeply_nested_provider_reply_by_name() -> None:
    """The other JSON a hostile party can hand this module: the model's reply.
    A provider that returned bracket soup gets the same typed refusal as one
    that returned prose (B10 rides on the same consent, ADR-0088)."""
    with pytest.raises(SegmentationError, match="not JSON"):
        _load(DEEP)


def test_every_reader_is_still_registered() -> None:
    """The refusals above are per reader; a reader that fell out of the registry
    would make them vacuous for it."""
    assert set(reader_ids()) >= {"chatgpt", "claude", "generic", "transcript", "pasted"}
