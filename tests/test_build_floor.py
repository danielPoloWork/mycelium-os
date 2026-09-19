# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The incremental floor (roadmap 6.20, ADR-0133): what an unchanged file costs a rebuild.

Until 6.20 every discovered file was read and digested on every build — *"content
truth comes from the digest, never from metadata"* — and that read was the floor
NFR-3's 2 s budget was spent on: linear in the corpus, over budget from ~250
documents on the machine of record. The floor now rests on a **stat memo**: a
document whose size and mtime match the ones recorded when its digest was last
computed keeps that digest without being read, and the digest stays the only
identity anything downstream sees. Three guards keep that honest, and each has a
test here:

- the **racy window** — a file modified within two seconds of the previous
  build's start is read regardless, because a coarse filesystem clock could give
  two different contents the same timestamp (Git's "racily clean" rule);
- **`rescan`** — the operator's way to distrust every memo once, at the cost of the
  old floor and nothing more;
- **`mycelium doctor`** — re-digests the corpus and reports a document whose bytes
  no longer match the index, which is the one case the memo cannot see.

The other two whole-corpus filesystem passes a rebuild made are pinned here too:
restorability is answered from one listing of the cache rather than two probes
per document, and an unresolved link's existence probe is asked once per
candidate path rather than once per link.
"""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mycelium.build import build
from mycelium.build.orchestrator import RACY_MTIME_WINDOW_NS
from mycelium.build.snapshots import decode_snapshot_state, encode_snapshot_state, rollback
from mycelium.cli.doctor import diagnose
from mycelium.determinism import observe_build
from mycelium.graph import CorpusIndex, LinkRef, resolve_edges
from mycelium.sdk.identity import canonical_json
from mycelium.store import SqliteStore

_IDS = {
    "architecture": "01ARZ3NDEKTSV4RRFFQ69G5FA1",
    "api": "01ARZ3NDEKTSV4RRFFQ69G5FA2",
    "notes": "01ARZ3NDEKTSV4RRFFQ69G5FA3",
    "guide": "01ARZ3NDEKTSV4RRFFQ69G5FA4",
}

CORPUS = {
    "knowledge/verified/architecture.md": (
        f"---\nmycelium_id: {_IDS['architecture']}\n---\n\n"
        "# Architecture\n\nThe event bus routes messages between agents.\n\n"
        "## Retries\n\nExponential backoff with jitter.\n"
    ),
    "knowledge/verified/api.md": (
        f"---\nmycelium_id: {_IDS['api']}\n---\n\n"
        "# API\n\nEndpoints are versioned. See [[architecture]] and [LICENSE](../../LICENSE).\n"
    ),
    "knowledge/candidate/notes.md": (
        f"---\nmycelium_id: {_IDS['notes']}\n---\n\n"
        "# Notes\n\nUnreviewed synthesis about the queue.\n"
    ),
    "knowledge/guide.md": (
        f"---\nmycelium_id: {_IDS['guide']}\n---\n\n"
        "# Guide\n\nHow to operate the system day to day.\n"
    ),
}

GUIDE = "knowledge/guide.md"
OLD_MTIME_NS = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()) * 1_000_000_000
"""Well outside the racy window of any build run by this suite."""


def repo(tmp_path: Path, name: str = "repo", *, aged: bool = True) -> Path:
    """A four-document repository; `aged` gives every file an old, stable mtime.

    Aged by default so the memo is *trusted* — a file written a millisecond before
    the build sits inside the racy window and is read regardless, which is the
    right behaviour and the wrong thing to measure here.
    """
    root = tmp_path / name
    for relative, text in CORPUS.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    (root / "LICENSE").write_text("Apache-2.0\n", encoding="utf-8")
    if aged:
        age(root)
    return root


def age(root: Path, mtime_ns: int = OLD_MTIME_NS) -> None:
    for path in root.rglob("*.md"):
        if ".mycelium" not in path.parts:
            os.utime(path, ns=(mtime_ns, mtime_ns))


def write(root: Path, relative: str, text: str, *, mtime_ns: int | None = None) -> None:
    target = root / relative
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    if mtime_ns is not None:
        os.utime(target, ns=(mtime_ns, mtime_ns))


def assert_equal_to_clean(tmp_path: Path, root: Path, name: str = "fresh") -> None:
    """The exit-gate property from `test_build_incremental`: an incrementally
    maintained store observes identically to a from-scratch build of the same tree."""
    fresh = tmp_path / name
    if fresh.exists():
        shutil.rmtree(fresh)
    # Every source file, not only the documents: `api.md` links `LICENSE`, and a
    # clean tree without it would warn where the incremental one does not.
    for path in sorted(root.rglob("*")):
        if ".mycelium" in path.parts or not path.is_file():
            continue
        target = fresh / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)  # copy2: mtime is an input (ADR-0009)
    assert observe_build(root, pin=False) == observe_build(fresh, pin=False)


def document_reads(monkeypatch: pytest.MonkeyPatch, root: Path) -> list[Path]:
    """Every `read_bytes` of a corpus document from here on — the floor, counted."""
    seen: list[Path] = []
    real = Path.read_bytes

    def counting(self: Path) -> bytes:
        if self.suffix == ".md" and root in self.parents and ".mycelium" not in self.parts:
            seen.append(self)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    return seen


def memo_of(root: Path, relative: str) -> tuple[int | None, int | None]:
    with SqliteStore.open(root, read_only=True) as store:
        state = next(state for state in store.doc_states() if state.path == relative)
    return state.source_size, state.source_mtime_ns


# ---------------------------------------------------------------------------
# The memo: an unchanged file is not read
# ---------------------------------------------------------------------------


def test_an_unchanged_document_is_not_read_on_the_next_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    build(root)
    reads = document_reads(monkeypatch, root)

    result = build(root)

    assert reads == []
    assert result.stats.reused == 4
    assert result.stats.rebuilt == 0


def test_the_memo_records_what_the_digest_was_computed_over(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    size, mtime_ns = memo_of(root, GUIDE)
    stat = (root / GUIDE).stat()
    assert size == stat.st_size
    assert mtime_ns == stat.st_mtime_ns


def test_an_edit_that_changes_size_or_mtime_is_read_and_rebuilt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    build(root)
    write(root, GUIDE, CORPUS[GUIDE] + "\nA new paragraph.\n", mtime_ns=OLD_MTIME_NS + 1)
    reads = document_reads(monkeypatch, root)

    result = build(root)

    assert [path.name for path in reads] == ["guide.md"]
    assert result.stats.rebuilt == 1
    assert result.stats.reused == 3
    assert_equal_to_clean(tmp_path, root)


def test_touching_a_file_is_still_a_rebuild_of_its_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same bytes, new mtime: the memo misses, the file is read, the digest agrees,
    and the document is still dirty — mtime is an input (ADR-0009). Nothing the
    memo does may change what a touch means."""
    root = repo(tmp_path)
    build(root)
    os.utime(root / GUIDE, ns=(OLD_MTIME_NS + 10**9, OLD_MTIME_NS + 10**9))
    reads = document_reads(monkeypatch, root)

    result = build(root)

    assert [path.name for path in reads] == ["guide.md"]
    assert result.stats.rebuilt == 1
    assert result.stats.parse_hits == 1  # the content did not change; the cache had it
    assert_equal_to_clean(tmp_path, root)


def test_a_clean_build_reads_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--clean` distrusts every cache, and the memo is one of them."""
    root = repo(tmp_path)
    build(root)
    reads = document_reads(monkeypatch, root)
    build(root, clean=True)
    assert len(reads) == 4


# ---------------------------------------------------------------------------
# The racy window: a same-size edit right after a build is still seen
# ---------------------------------------------------------------------------


def test_a_same_size_edit_inside_the_racy_window_is_read_and_seen(tmp_path: Path) -> None:
    """The case the memo alone cannot tell apart: the same size, the very same
    mtime — which a coarse filesystem clock can produce for an edit made within
    its tick of the previous read. A file whose mtime is that recent is read
    regardless of the memo, so the edit is found."""
    root = repo(tmp_path, aged=False)  # fresh mtimes: inside the window
    build(root)
    _size, recorded = memo_of(root, GUIDE)
    assert recorded is not None
    # Same length, different words, and the mtime put back to what the memo holds.
    write(root, GUIDE, CORPUS[GUIDE].replace("day to day", "day by day"), mtime_ns=recorded)
    assert (root / GUIDE).stat().st_mtime_ns == recorded

    result = build(root)

    assert result.stats.rebuilt == 1
    assert_equal_to_clean(tmp_path, root)


def test_the_racy_window_is_two_seconds() -> None:
    """Stated because it is a claim about filesystems, not about this code: FAT
    keeps mtimes to two seconds, and nothing in common use is coarser."""
    assert RACY_MTIME_WINDOW_NS == 2_000_000_000


# ---------------------------------------------------------------------------
# The blind spot, named, and the two ways out of it
# ---------------------------------------------------------------------------


def test_a_same_size_edit_under_a_restored_old_mtime_is_the_documented_blind_spot(
    tmp_path: Path,
) -> None:
    """Same size, same mtime, outside the racy window: the memo is trusted and the
    edit is not seen. This is the trade the floor was raised on, and the test
    exists so that changing it is an act rather than a surprise. The remedies are
    the two tests that follow."""
    root = repo(tmp_path)
    build(root)
    write(root, GUIDE, CORPUS[GUIDE].replace("day to day", "day by day"), mtime_ns=OLD_MTIME_NS)

    result = build(root)

    assert result.stats.rebuilt == 0


def test_rescan_reads_every_file_and_finds_what_the_memo_missed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    build(root)
    write(root, GUIDE, CORPUS[GUIDE].replace("day to day", "day by day"), mtime_ns=OLD_MTIME_NS)
    build(root)  # trusts the memo, misses the edit
    reads = document_reads(monkeypatch, root)

    result = build(root, rescan=True)

    assert len(reads) == 4
    assert result.stats.rebuilt == 1
    assert result.stats.parsed == 1  # new bytes: a real parse
    assert result.stats.reused == 3  # and nothing else recompiled: the caches stand
    assert_equal_to_clean(tmp_path, root)


def test_rescan_on_an_unchanged_corpus_changes_nothing_but_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    first = build(root)
    reads = document_reads(monkeypatch, root)

    result = build(root, rescan=True)

    assert len(reads) == 4
    assert result.stats.reused == 4
    assert result.manifest.artifact_digests == first.manifest.artifact_digests


def test_doctor_reports_a_document_whose_bytes_no_longer_match_the_index(
    tmp_path: Path,
) -> None:
    """The detector for the one case the memo cannot see: `doctor` pays the old
    floor on demand, re-digesting every document, and names the drift and the
    remedy."""
    root = repo(tmp_path)
    build(root)
    checks = {check.name: check for check in diagnose(root)}
    assert checks["index"].status == "ok"

    write(root, GUIDE, CORPUS[GUIDE].replace("day to day", "day by day"), mtime_ns=OLD_MTIME_NS)
    build(root)  # the blind spot
    checks = {check.name: check for check in diagnose(root)}

    assert checks["index"].status == "warn"
    assert GUIDE in checks["index"].detail
    assert "--rescan" in checks["index"].detail


def test_doctor_is_quiet_about_the_index_before_a_build(tmp_path: Path) -> None:
    root = repo(tmp_path)
    assert "index" not in {check.name for check in diagnose(root)}


# ---------------------------------------------------------------------------
# Rollback: the memo travels with the snapshot's state, without a clock
# ---------------------------------------------------------------------------


def test_a_rolled_back_snapshot_keeps_the_memo_and_the_next_build_reads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    first = build(root)
    write(root, GUIDE, CORPUS[GUIDE] + "\nDrift.\n", mtime_ns=OLD_MTIME_NS + 1)
    build(root)
    rollback(root, first.manifest.snapshot_id)
    write(root, GUIDE, CORPUS[GUIDE], mtime_ns=OLD_MTIME_NS)  # the tree as it was
    reads = document_reads(monkeypatch, root)

    result = build(root)

    assert reads == []
    assert result.stats.reused == 4
    assert result.manifest.artifact_digests == first.manifest.artifact_digests


def test_the_state_blob_is_still_canonical_json(tmp_path: Path) -> None:
    """The blob is written with the C encoder for speed (roadmap 6.20); it must be
    byte-for-byte what the identity library's canonical form would have written,
    or two builds of one corpus could stop addressing one blob."""
    root = repo(tmp_path)
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        states = store.doc_states()
    encoded = encode_snapshot_state(states)
    assert encoded == canonical_json(json.loads(encoded))
    assert decode_snapshot_state(encoded) == tuple(sorted(states, key=lambda s: s.path))


# ---------------------------------------------------------------------------
# The other two per-document filesystem passes
# ---------------------------------------------------------------------------


def test_a_rebuild_does_not_probe_the_cache_once_per_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restorability used to cost two `exists()` per live document on every build.
    It is answered from one listing of the cache now, so the probes into it no
    longer scale with the corpus: the one that remains is the snapshot state
    blob's own write asking whether its blob already exists — once per build, for
    four documents or four thousand."""
    root = repo(tmp_path)
    build(root)
    probes: list[Path] = []
    real = Path.exists

    def counting(self: Path) -> bool:
        if "cas" in self.parts and ".mycelium" in self.parts:
            probes.append(self)
        return real(self)

    monkeypatch.setattr(Path, "exists", counting)
    build(root)
    assert len(probes) <= 1, probes


def test_a_cleared_cache_is_still_reported_as_not_restorable(tmp_path: Path) -> None:
    """The listing must say the same thing the probes did (ADR-0016's promise)."""
    root = repo(tmp_path)
    build(root)
    shutil.rmtree(root / ".mycelium" / "cas")
    write(root, GUIDE, CORPUS[GUIDE] + "\nDrift.\n", mtime_ns=OLD_MTIME_NS + 1)
    manifest = build(root).manifest
    assert "snapshot_state" in manifest.degraded


def test_an_unresolved_link_lists_each_candidate_directory_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fifty documents linking the same missing target used to ask the filesystem
    a hundred times. The probe lists a directory once for the whole resolution and
    answers every question about it from the listing, so fifty links cost two
    listings: `docs/`, where the link sits, and the root."""
    root = tmp_path / "graph"
    (root / "docs").mkdir(parents=True)
    listed: list[str] = []
    real = os.scandir

    def counting(path: Any = ".") -> Any:
        listed.append(os.path.normpath(str(path)))
        return real(path)

    links = {
        f"docs/d{index}.md": [LinkRef(kind="wikilink", target="nowhere", fragment="", anchor="")]
        for index in range(50)
    }
    index = CorpusIndex.build(links)
    monkeypatch.setattr(os, "scandir", counting)
    _edges, warnings = resolve_edges(links, index, root=root)

    assert len(warnings) == 50  # every link is still reported as unresolved
    assert len(listed) == len(set(listed)) <= 2  # `docs/` and the root, each once
    (existing_root,) = [tmp_path / "graph"]
    (existing_root / "nowhere").write_text("a file, not a document", encoding="utf-8")
    _edges, warnings = resolve_edges(links, CorpusIndex.build(links), root=root)
    assert warnings == ()  # the target exists at the root: a non-document, not a broken link
