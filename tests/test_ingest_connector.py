# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The file connector (roadmap 4.1): acquisition is bounded by declared roots, by size, and
by an extension the project actually ingests — and the digest is over the bytes verbatim."""

import os
from pathlib import Path

import pytest

from mycelium.ingest.connectors.file import FileConnector
from mycelium.ingest.errors import ConnectorError, SourceTooLargeError
from mycelium.ingest.media import MARKDOWN, PDF
from mycelium.sdk.identity import digest_bytes


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "sources"
    (root / "nested").mkdir(parents=True)
    (root / "notes.md").write_bytes(b"# Notes\n")
    (root / "nested" / "deep.md").write_bytes(b"# Deep\n")
    (tmp_path / "outside.md").write_bytes(b"# Outside\n")
    return root


def test_acquire_returns_bytes_digest_and_media_type(tree: Path) -> None:
    blob = FileConnector([tree]).acquire(str(tree / "notes.md"))
    assert blob.data == b"# Notes\n"
    assert blob.digest == digest_bytes(b"# Notes\n")
    assert blob.media_type == MARKDOWN
    assert blob.source_uri == "file:notes.md"
    assert blob.size == 8
    assert blob.warnings == ()


def test_an_acquired_uri_is_relative_so_a_committed_document_travels(tree: Path) -> None:
    """BUG-0017. This URI ends up in a projected document's frontmatter, and that
    document is committed — so an absolute path would put one machine's directory
    layout into everyone else's checkout."""
    blob = FileConnector([tree]).acquire(str(tree / "nested" / "deep.md"))
    assert blob.source_uri == "file:nested/deep.md"
    assert str(tree) not in blob.source_uri


def test_the_uri_is_written_against_base_not_against_the_widest_root(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    sources = repository / "sources"
    sources.mkdir(parents=True)
    (sources / "brief.md").write_bytes(b"# Brief\n")
    # Two roots, as `mycelium ingest` declares them: the repository and its
    # sources directory. The URI is written against the first, so it names the
    # file the way the repository does.
    connector = FileConnector([repository, sources])
    assert connector.acquire("sources/brief.md").source_uri == "file:sources/brief.md"


def test_a_source_outside_base_keeps_its_absolute_uri(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    elsewhere = tmp_path / "elsewhere"
    repository.mkdir()
    elsewhere.mkdir()
    (elsewhere / "brief.md").write_bytes(b"# Brief\n")
    # Readable because it is a declared root, but not *under* the repository, so
    # a relative name would be a lie rather than a shorter truth.
    connector = FileConnector([repository, elsewhere], base=repository)
    uri = connector.acquire(str(elsewhere / "brief.md")).source_uri
    assert uri.startswith("file:///")


def test_an_acquired_uri_round_trips_back_through_the_connector(tree: Path) -> None:
    connector = FileConnector([tree])
    once = connector.acquire("nested/deep.md")
    assert connector.acquire(once.source_uri).digest == once.digest


def test_a_space_in_the_name_is_percent_encoded(tree: Path) -> None:
    (tree / "two words.md").write_bytes(b"# Two\n")
    blob = FileConnector([tree]).acquire("two words.md")
    assert blob.source_uri == "file:two%20words.md"
    assert FileConnector([tree]).acquire(blob.source_uri).digest == blob.digest


def test_a_relative_source_resolves_against_the_first_root(tree: Path) -> None:
    blob = FileConnector([tree]).acquire("nested/deep.md")
    assert blob.data == b"# Deep\n"


def test_a_file_uri_is_accepted(tree: Path) -> None:
    connector = FileConnector([tree])
    uri = (tree / "notes.md").as_uri()
    assert connector.acquire(uri).data == b"# Notes\n"


def test_a_windows_drive_letter_is_a_path_not_a_scheme(tree: Path) -> None:
    # `urlparse("D:/x")` reports the scheme "d"; a one-character scheme is a drive.
    absolute = str((tree / "notes.md").resolve())
    assert FileConnector([tree]).acquire(absolute).data == b"# Notes\n"


def test_a_remote_scheme_is_refused_by_name(tree: Path) -> None:
    with pytest.raises(ConnectorError, match="https"):
        FileConnector([tree]).acquire("https://example.com/notes.md")


def test_a_path_outside_the_roots_is_refused(tree: Path) -> None:
    with pytest.raises(ConnectorError, match="outside the declared root"):
        FileConnector([tree]).acquire(str(tree.parent / "outside.md"))


def test_dot_dot_cannot_climb_out_of_a_root(tree: Path) -> None:
    with pytest.raises(ConnectorError, match="outside the declared root"):
        FileConnector([tree]).acquire("../outside.md")


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privilege on Windows")
def test_a_symlink_pointing_out_of_a_root_is_refused(tree: Path) -> None:
    escape = tree / "escape.md"
    escape.symlink_to(tree.parent / "outside.md")
    # The check is on the *resolved real path*, so a link inside the tree that
    # points out of it is caught (spec 02 §8).
    with pytest.raises(ConnectorError, match="outside the declared root"):
        FileConnector([tree]).acquire(str(escape))


def test_a_missing_file_says_so(tree: Path) -> None:
    with pytest.raises(ConnectorError, match="cannot be resolved"):
        FileConnector([tree]).acquire("absent.md")


def test_a_directory_is_not_a_document(tree: Path) -> None:
    with pytest.raises(ConnectorError, match="not a regular file"):
        FileConnector([tree]).acquire("nested")


def test_an_unknown_extension_names_what_is_ingestible(tree: Path) -> None:
    (tree / "notes.rtf").write_bytes(b"{\\rtf1}")
    with pytest.raises(ConnectorError, match="is not one Mycelium ingests"):
        FileConnector([tree]).acquire("notes.rtf")


def test_the_size_ceiling_is_checked_before_the_read(tree: Path) -> None:
    (tree / "big.md").write_bytes(b"x" * 4096)
    with pytest.raises(SourceTooLargeError, match="above the connector's"):
        FileConnector([tree], max_bytes=1024).acquire("big.md")


def test_bytes_that_contradict_the_extension_travel_as_a_warning(tree: Path) -> None:
    (tree / "lying.md").write_bytes(b"%PDF-1.4\ntrust me\n")
    blob = FileConnector([tree]).acquire("lying.md")
    assert blob.media_type == MARKDOWN, "the extension still decides dispatch"
    assert len(blob.warnings) == 1
    assert PDF in blob.warnings[0]


def test_a_connector_needs_at_least_one_root() -> None:
    with pytest.raises(ConnectorError, match="at least one declared root"):
        FileConnector([])


def test_a_root_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConnectorError, match="does not exist"):
        FileConnector([tmp_path / "nope"])


def test_several_roots_are_all_readable(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "one.md").write_bytes(b"one")
    (second / "two.md").write_bytes(b"two")
    connector = FileConnector([first, second])
    assert connector.acquire(str(second / "two.md")).data == b"two"
    assert len(connector.roots) == 2
