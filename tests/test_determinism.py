# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Gate G6 — byte-identical rebuild (roadmap 2.10, spec 04 §7).

The product's differentiating claim is that compilation is deterministic: the same
sources produce the same artifacts, so a build key means something and a cached
artifact can be trusted. This file is where that claim is enforced rather than
asserted, against a committed corpus and a committed golden observation.

A failure here is either a real regression or an intended compiler change. For the
second, `python tools/update_determinism_golden.py` re-blesses the golden and the
resulting diff is the change — reviewed in the PR, not absorbed silently.
"""

import shutil
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.determinism import (
    DeterminismObservation,
    observe_build,
    pin_mtimes,
    read_golden,
)

pytestmark = pytest.mark.determinism

CORPUS = Path(__file__).parent / "fixtures" / "determinism"
GOLDEN = CORPUS / "golden.json"

REBLESS = (
    "If this change is intended, run `python tools/update_determinism_golden.py` "
    "and put the golden diff in the PR. If it is not, the compiler lost determinism."
)


def workspace(tmp_path: Path, name: str = "corpus") -> Path:
    """A private copy of the fixture corpus — the committed files are never built."""
    root = tmp_path / name
    shutil.copytree(CORPUS / "knowledge", root / "knowledge")
    return root


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_compiled_output_matches_the_golden(tmp_path: Path) -> None:
    """The whole of gate G6, in one comparison."""
    observed = observe_build(workspace(tmp_path)).as_dict()
    expected = read_golden(GOLDEN)

    # Compare section by section: a failing gate should say *what* moved.
    assert observed["counts"] == expected["counts"], REBLESS
    assert observed["config_digest"] == expected["config_digest"], REBLESS
    assert observed["schema_versions"] == expected["schema_versions"], REBLESS
    assert observed["warnings"] == expected["warnings"], REBLESS
    assert observed["documents"] == expected["documents"], REBLESS
    assert observed["chunks"] == expected["chunks"], REBLESS
    assert observed["artifact_digests"] == expected["artifact_digests"], REBLESS


def test_rebuilding_the_same_workspace_changes_nothing(tmp_path: Path) -> None:
    """The literal claim: rebuild without touching sources, get the same artifacts."""
    root = workspace(tmp_path)
    first = observe_build(root)
    second = observe_build(root)
    assert first == second


def test_two_independent_workspaces_agree(tmp_path: Path) -> None:
    """Determinism is a property of the sources, not of a particular directory."""
    here = observe_build(workspace(tmp_path, "here"))
    there = observe_build(workspace(tmp_path, "there"))
    assert here == there


def test_a_build_never_modifies_the_corpus(tmp_path: Path) -> None:
    """Every fixture pins its identity, so the build has nothing to write back."""
    root = workspace(tmp_path)
    before = {
        path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.md"))
    }
    result = build(root)
    after = {
        path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.md"))
    }
    assert result.pinned == ()
    assert before == after
    assert result.manifest.counts.quarantined == 0, result.manifest.warnings


# ---------------------------------------------------------------------------
# What the gate deliberately does not claim
# ---------------------------------------------------------------------------


def test_volatile_manifest_fields_really_do_vary(tmp_path: Path) -> None:
    """The exclusions are honest, not convenient.

    `snapshot_id`, `created_at` and `timings_ms` differ between two correct builds
    by design, which is exactly why the observation omits them (ADR-0012). If they
    ever stopped varying, the exclusion would be dead weight worth removing.
    """
    root = workspace(tmp_path)
    first = build(root).manifest
    second = build(root).manifest

    assert first.snapshot_id != second.snapshot_id  # a fresh ULID per publish
    assert second.parent_id == first.snapshot_id  # and the chain records it
    assert first != second  # so the manifests are not equal, and never will be
    assert first.artifact_digests == second.artifact_digests  # what *is* claimed


def test_mtime_is_an_input_and_the_gate_pins_it(tmp_path: Path) -> None:
    """A fresh checkout has fresh mtimes; without pinning, records would differ.

    Documented rather than hidden: mtime becomes `created_at`/`updated_at` on every
    document record (ADR-0009), so the golden would otherwise encode the moment the
    repository was cloned.
    """
    root = workspace(tmp_path)
    pinned = observe_build(root, pin=True)

    for path in sorted(root.rglob("*.md")):
        path.touch()  # simulate a fresh checkout: same bytes, new timestamps
    unpinned = observe_build(root, pin=False)

    assert unpinned.chunks == pinned.chunks  # content is unaffected
    assert unpinned.documents != pinned.documents  # timestamps are not
    assert unpinned.artifact_digests["chunks"] == pinned.artifact_digests["chunks"]
    assert unpinned.artifact_digests["documents"] != pinned.artifact_digests["documents"]


# ---------------------------------------------------------------------------
# The corpus is the gate's real strength
# ---------------------------------------------------------------------------


def test_the_corpus_still_covers_the_profile() -> None:
    """A golden test is only as good as what it compiles.

    This pins the corpus's *coverage*, so a future edit cannot quietly weaken the
    gate by removing the cases that make it interesting.
    """
    golden = read_golden(GOLDEN)
    chunks = golden["chunks"]
    documents = golden["documents"]
    anchors = [str(chunk["anchor"]) for chunk in chunks]

    assert len(documents) == 6
    # All three kinds, and since packing became the default (ADR-0047) `code` is
    # only reachable through a section whose *only* content is a block — the
    # constraint ADR-0007 argued and packing preserves. The corpus carries one on
    # purpose: without it the flip would have quietly narrowed this gate's
    # coverage to two kinds, which is exactly what this assertion is here to stop.
    assert {str(chunk["kind"]) for chunk in chunks} == {"prose", "table", "code"}
    solitary = [c for c in chunks if str(c["kind"]) == "code"]
    assert len(solitary) == 1
    assert str(solitary[0]["anchor"]).endswith("#worked-example/0")
    assert {str(doc["verification_status"]) for doc in documents} == {
        "verified",
        "candidate",
        "evidence",
    }
    assert {str(doc["trust_class"]) for doc in documents} == {"authored", "ingested"}

    # Sibling headings that slug alike are numbered, not collided.
    assert any(anchor.endswith("#event-bus/0") for anchor in anchors)
    assert any(anchor.endswith("#event-bus-2/0") for anchor in anchors)
    # A nested heading path.
    assert any("#event-bus/delivery/" in anchor for anchor in anchors)
    # A section past the token ceiling, split at a paragraph boundary.
    split = [anchor for anchor in anchors if "#why-a-section-splits/" in anchor]
    assert len(split) >= 2
    # Non-Latin scripts survive slugging (D-028).
    assert any(any(ord(char) > 0x2FFF for char in anchor) for anchor in anchors)


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("knowledge/verified/architecture.md", "\nAn added paragraph.\n"),
        ("knowledge/verified/retries.md", "\n## An Added Section\n\nWith content.\n"),
    ],
)
def test_the_gate_detects_a_changed_corpus(tmp_path: Path, target: str, mutation: str) -> None:
    """A gate that cannot fail is decoration.

    Two shapes of change — added prose, and an added section — must both move the
    observation away from the golden.
    """
    root = workspace(tmp_path)
    path = root / target
    path.write_text(path.read_text(encoding="utf-8") + mutation, encoding="utf-8")

    observed = observe_build(root).as_dict()
    expected = read_golden(GOLDEN)
    assert observed["chunks"] != expected["chunks"]
    assert observed["artifact_digests"] != expected["artifact_digests"]


def test_the_golden_is_stored_reviewably() -> None:
    """A golden nobody can read in a diff is a hash, not a gate."""
    raw = GOLDEN.read_bytes()
    assert b"\r" not in raw  # LF only, so the diff is the same on every platform
    assert raw.endswith(b"\n")
    text = raw.decode("utf-8")
    assert '"anchor"' in text  # per-chunk detail, not one opaque digest
    assert "\\u" not in text  # non-Latin text is readable, not escaped


def test_observation_is_comparable_and_serialisable(tmp_path: Path) -> None:
    observation = observe_build(workspace(tmp_path))
    assert isinstance(observation, DeterminismObservation)
    assert observation.as_dict()["chunks"] == list(observation.chunks)
    with pytest.raises(AttributeError):
        observation.counts = {}  # type: ignore[misc]  # frozen: an observation is evidence


def test_pin_mtimes_is_idempotent(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    pin_mtimes(root)
    stamps = {path: path.stat().st_mtime for path in sorted(root.rglob("*.md"))}
    pin_mtimes(root)
    assert {path: path.stat().st_mtime for path in sorted(root.rglob("*.md"))} == stamps
