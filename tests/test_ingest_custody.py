# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Tier-1 custody (roadmap 4.2): the acquired original is kept verbatim, kept idempotently,
kept honest about what it holds — and, above all, **kept**: the garbage collector that owns
the rest of `.mycelium/` must never be able to reach it."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.build.cas import CAS_DIRNAME, CUSTODY_DIRNAME, cas_put
from mycelium.build.snapshots import collect_garbage
from mycelium.ingest.custody import Custody, custody_root
from mycelium.ingest.errors import CustodyError
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob
from mycelium.sdk.types import CustodyKind

ORIGINAL = b"%PDF-1.4\nsome acquired bytes\n\r\n"
STAMP = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def custody(tmp_path: Path) -> Custody:
    return Custody(tmp_path / ".mycelium")


def test_bytes_are_stored_verbatim(custody: Custody) -> None:
    record = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    # Verbatim, mixed line endings included: normalising an acquired original
    # would break the one claim custody exists to support.
    assert custody.get(record.digest) == ORIGINAL
    assert record.digest == digest_bytes(ORIGINAL)
    assert record.size == len(ORIGINAL)


def test_storing_the_same_bytes_twice_is_idempotent(custody: Custody) -> None:
    first = custody.put(
        ORIGINAL,
        kind=CustodyKind.ORIGINAL,
        media_type="application/pdf",
        source_uri="file:///a.pdf",
        now=STAMP,
    )
    second = custody.put(
        ORIGINAL,
        kind=CustodyKind.ORIGINAL,
        media_type="application/pdf",
        source_uri="file:///a.pdf",
    )
    assert second == first, "a second acquisition must not move first_seen"


def test_first_seen_never_moves(custody: Custody) -> None:
    first = custody.put(
        ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf", now=STAMP
    )
    later = custody.put(
        ORIGINAL,
        kind=CustodyKind.ORIGINAL,
        media_type="application/pdf",
        now=datetime(2027, 1, 1, tzinfo=UTC),
    )
    # A refreshed timestamp would change the document record built from it, and
    # invalidate an incremental rebuild for a document that did not change.
    assert later.first_seen == first.first_seen == STAMP


def test_the_same_bytes_from_two_places_records_both_sources_sorted(custody: Custody) -> None:
    custody.put(
        ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf", source_uri="file:///b"
    )
    record = custody.put(
        ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf", source_uri="file:///a"
    )
    # Sorted, not arrival-ordered: content addressing means two machines can meet
    # the same bytes in a different order, and a record that differed on that
    # would make custody itself irreproducible.
    assert record.sources == ("file:///a", "file:///b")


def test_a_contradicting_write_is_a_bug_not_a_merge(custody: Custody) -> None:
    custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    with pytest.raises(CustodyError, match="already has kind"):
        custody.put(ORIGINAL, kind=CustodyKind.KIR, media_type="application/json")


def test_a_kir_blob_records_what_it_was_compiled_from(custody: Custody) -> None:
    original = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    kir = custody.put(
        b'{"nodes": []}',
        kind=CustodyKind.KIR,
        media_type="application/json",
        derived_from=original.digest,
    )
    linked = custody.link_kir(original.digest, kir.digest)
    assert kir.derived_from == original.digest
    assert linked.kir_digest == kir.digest
    assert custody.link_kir(original.digest, kir.digest) == linked, "linking is idempotent"


def test_linking_a_kir_to_an_unknown_original_is_refused(custody: Custody) -> None:
    with pytest.raises(CustodyError, match="must be stored first"):
        custody.link_kir(digest_bytes(b"absent"), digest_bytes(b"kir"))


def test_a_corrupt_blob_reads_as_missing_and_is_not_deleted(custody: Custody) -> None:
    record = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    custody.blob_path(record.digest).write_bytes(b"tampered")

    assert custody.get(record.digest) is None
    # Unlike a cache blob, evidence that went bad is a finding, not litter: the
    # file stays so `mycelium doctor` can report it and an operator can look.
    assert custody.blob_path(record.digest).is_file()
    integrity = custody.verify()
    assert integrity.corrupt == (record.digest,)
    assert not integrity.healthy


def test_a_record_whose_blob_is_gone_is_reported_as_orphaned(custody: Custody) -> None:
    record = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    custody.blob_path(record.digest).unlink()
    integrity = custody.verify()
    assert integrity.orphaned_records == (record.digest,)
    assert not integrity.healthy


def test_an_unreadable_record_is_an_error_not_a_shrug(custody: Custody) -> None:
    record = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    custody.record_path(record.digest).write_text("{not json", encoding="utf-8")
    with pytest.raises(CustodyError, match="not a valid custody record"):
        custody.record(record.digest)


def test_an_absent_digest_is_none(custody: Custody) -> None:
    assert custody.get(digest_bytes(b"never stored")) is None
    assert custody.record(digest_bytes(b"never stored")) is None


def test_a_malformed_digest_is_refused(custody: Custody) -> None:
    with pytest.raises(CustodyError, match="not a sha256 digest"):
        custody.get("sha256:nope")


def test_a_blob_carries_its_connector_identity(custody: Custody) -> None:
    blob = Blob.of(ORIGINAL, media_type="application/pdf", source_uri="file:///x.pdf")
    record = custody.put_blob(blob, connector="file", version="1")
    assert record.connector == "file"
    assert record.connector_version == "1"
    assert record.kind is CustodyKind.ORIGINAL
    assert record.sources == ("file:///x.pdf",)


def test_records_enumerate_the_whole_inventory(custody: Custody) -> None:
    for index in range(3):
        custody.put(f"blob {index}".encode(), kind=CustodyKind.ORIGINAL, media_type="text/plain")
    assert len(list(custody.records())) == 3
    assert len(custody.digests()) == 3


def test_an_empty_store_verifies_clean(custody: Custody) -> None:
    integrity = custody.verify()
    assert integrity.healthy
    assert integrity.blobs == 0


# ---------------------------------------------------------------------------
# The property the whole design exists for
# ---------------------------------------------------------------------------


def test_garbage_collection_never_reaches_tier_one(tmp_path: Path) -> None:
    """The load-bearing test of ADR-0033.

    `gc` sweeps every CAS blob outside the live set — that is its job, and it is
    safe because the build cache is reuse (D-005). Run it against a store holding
    an acquired original and the same rule would delete the evidence a citation
    quotes. It must walk past it, and say how much it walked past.
    """
    from mycelium.build.orchestrator import build
    from mycelium.store import STORE_DIRNAME

    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "a.md").write_text("# A\n\ntext\n", encoding="utf-8")
    build(tmp_path)

    mycelium_dir = tmp_path / STORE_DIRNAME
    custody = Custody(mycelium_dir)
    evidence = custody.put(ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf")
    # An unreferenced *cache* blob, for the control: gc must still collect that.
    collectable = cas_put(mycelium_dir, "an artifact nothing references")

    result = collect_garbage(tmp_path, keep=0, cache_max_age_days=0)

    assert custody.get(evidence.digest) == ORIGINAL, "tier-1 evidence survived"
    assert result.kept_custody_blobs == 1
    assert result.kept_custody_bytes == len(ORIGINAL)
    from mycelium.build.cas import cas_get

    assert cas_get(mycelium_dir, collectable) is None, "the cache blob was collectable"


def test_custody_lives_where_the_architecture_says_it_does(tmp_path: Path) -> None:
    mycelium_dir = tmp_path / ".mycelium"
    assert custody_root(mycelium_dir) == mycelium_dir / CAS_DIRNAME / CUSTODY_DIRNAME
    record = Custody(mycelium_dir).put(
        ORIGINAL, kind=CustodyKind.ORIGINAL, media_type="application/pdf"
    )
    blob = Custody(mycelium_dir).blob_path(record.digest)
    assert blob.is_file()
    assert CUSTODY_DIRNAME in blob.parts
