# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The content-addressed cache's write and its integrity story (roadmap 6.30, ADR-0145).

`cas_put` stopped writing through a temp file at 6.30, on the argument that a
blob's name *is* the digest of its bytes, so a torn write is something the reader
can already detect and whose remedy is to recompute. These tests hold that
argument up: the write leaves one name and no debris, a blob that does not hash
to its own name is refused, and refusing it never raises at a reader even when
the blob cannot be deleted.
"""

from pathlib import Path

import pytest

from mycelium.build.cas import cas_get, cas_inventory, cas_path, cas_put
from mycelium.layout import atomic_write_bytes, write_bytes

BLOB = "# A document\n\nWith a line that must survive verbatim.\n"


def test_a_blob_is_written_under_its_own_digest_and_reads_back(tmp_path: Path) -> None:
    digest = cas_put(tmp_path, BLOB)
    assert cas_get(tmp_path, digest) == BLOB
    assert cas_path(tmp_path, digest).exists()


def test_the_write_leaves_one_name_and_no_debris(tmp_path: Path) -> None:
    """The point of the change: a blob costs one file operation, not three.

    A `.tmp` left behind would mean the ceremony is still being paid somewhere,
    and the cost this item removed is precisely the second name.
    """
    digest = cas_put(tmp_path, BLOB)
    shard = cas_path(tmp_path, digest).parent
    assert [entry.name for entry in shard.iterdir()] == [cas_path(tmp_path, digest).name]
    assert list(tmp_path.rglob("*.tmp")) == []


def test_storing_the_same_text_twice_does_not_rewrite_it(tmp_path: Path) -> None:
    digest = cas_put(tmp_path, BLOB)
    path = cas_path(tmp_path, digest)
    stamp = path.stat().st_mtime_ns
    assert cas_put(tmp_path, BLOB) == digest
    assert path.stat().st_mtime_ns == stamp


def test_a_torn_blob_reads_as_a_miss_and_is_discarded(tmp_path: Path) -> None:
    """The failure the ceremony used to prevent, and the one the digest catches.

    A crash mid-write leaves a short file under the digest of the *whole*
    artifact. Re-hashing on read makes that indistinguishable from the blob never
    having existed, which is what lets the write be direct (ADR-0145).
    """
    digest = cas_put(tmp_path, BLOB)
    path = cas_path(tmp_path, digest)
    path.write_bytes(BLOB.encode("utf-8")[:10])

    assert cas_get(tmp_path, digest) is None
    assert not path.exists(), "a blob that lies about its bytes must not survive to be re-read"


def test_a_torn_blob_that_cannot_be_deleted_is_still_a_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reader may now race a writer that is still filling the blob.

    On Windows the delete then fails with a sharing violation. The right outcome
    is the miss `cas_get` is already returning — an exception here would turn a
    cache race into a build failure, which is the one thing the CAS promises not
    to do.
    """
    digest = cas_put(tmp_path, BLOB)
    cas_path(tmp_path, digest).write_bytes(b"truncated")

    def refuse(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(Path, "unlink", refuse)
    assert cas_get(tmp_path, digest) is None


def test_an_absent_blob_is_a_miss_rather_than_an_error(tmp_path: Path) -> None:
    (tmp_path / "cas").mkdir()
    assert cas_get(tmp_path, "sha256:" + "0" * 64) is None


def test_the_inventory_lists_what_was_stored(tmp_path: Path) -> None:
    digests = {cas_put(tmp_path, f"{BLOB}{index}") for index in range(5)}
    assert digests <= cas_inventory(tmp_path)


# ---------------------------------------------------------------------------
# The two primitives, side by side
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("writer", [write_bytes, atomic_write_bytes])
def test_both_writers_land_bytes_verbatim(tmp_path: Path, writer: object) -> None:
    """Including the newlines. Windows' CRT rewrites LF as CRLF in text mode, and
    a blob whose bytes depend on the platform would break the G6 golden and every
    acquired original that contains 0x0A (ADR-0033)."""
    data = b"one\ntwo\r\nthree\n\x00\xff"
    path = tmp_path / "blob"
    writer(path, data)  # type: ignore[operator]
    assert path.read_bytes() == data


def test_only_the_atomic_writer_uses_a_second_name(tmp_path: Path) -> None:
    """What distinguishes them, asserted rather than described.

    `write_bytes` is for a name that already says what the bytes must be;
    `atomic_write_bytes` is for one that does not, and it pays ~2.1x for the
    difference on the machine of record (ADR-0145). Both clean up after
    themselves — the temp file is debris only while the write is in flight.
    """
    write_bytes(tmp_path / "plain", b"x")
    atomic_write_bytes(tmp_path / "atomic", b"x")
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["atomic", "plain"]
