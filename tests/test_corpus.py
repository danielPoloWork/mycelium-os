# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What counts as a document (roadmap 3.7, ADR-0021).

One rule, read by discovery and by watch mode, because they had the same rule
written twice and agreement by coincidence is not agreement. The tests are about
the four things it decides: dot-directories, the tool's own output, the authored
tree, and the operator's exclusions.
"""

from pathlib import Path, PurePosixPath

import pytest

from mycelium.build import build
from mycelium.config import MyceliumConfig, ProjectConfig
from mycelium.corpus import CorpusScope, discover
from mycelium.store import SqliteStore
from mycelium.watch import is_relevant, watched_paths


def repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return root


def test_dot_directories_are_never_entered(tmp_path: Path) -> None:
    root = repo(tmp_path, {"a.md": "# A\n", ".mycelium/b.md": "# B\n", ".git/c.md": "# C\n"})
    assert [p.name for p in discover(root)] == ["a.md"]


def test_the_tools_own_output_is_never_indexed(tmp_path: Path) -> None:
    """BUG-0010: `export --with-markdown` writes copies of the corpus into
    `export/`, and indexing them duplicates every document — under the same
    pinned identity, so the guard quarantines them and every later build reports
    a warning for a file the operator never wrote."""
    root = repo(tmp_path, {"a.md": "# A\n", "export/01ABC/markdown/a.md": "# A\n"})
    assert [p.name for p in discover(root)] == ["a.md"]
    assert is_relevant(root / "export" / "01ABC" / "markdown" / "a.md", root) is False


def test_an_authored_tree_narrows_the_corpus(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/a.md": "# A\n", "elsewhere/b.md": "# B\n"})
    assert [p.name for p in discover(root, CorpusScope())] == ["a.md"]


def test_a_dot_knowledge_dir_means_the_repository_itself(tmp_path: Path) -> None:
    """`knowledge_dir = "."` is what a documentation repository says when its docs
    live at the root; read as a directory name it would compile nothing."""
    root = repo(tmp_path, {"a.md": "# A\n", "docs/b.md": "# B\n"})
    scope = CorpusScope(knowledge_dir=".")
    assert sorted(p.name for p in discover(root, scope)) == ["a.md", "b.md"]


@pytest.mark.parametrize(
    ("pattern", "excluded"),
    [
        ("tests", "tests/fixtures/x.md"),
        ("docs/journal", "docs/journal/2026/x.md"),
        ("**/fixtures", "docs/fixtures/x.md"),
        ("*.draft.md", "notes.draft.md"),
    ],
)
def test_exclude_patterns_match_paths_ancestors_and_names(
    tmp_path: Path, pattern: str, excluded: str
) -> None:
    root = repo(tmp_path, {"keep.md": "# Keep\n", excluded: "# Drop\n"})
    scope = CorpusScope(knowledge_dir=".", exclude=(pattern,))
    assert [p.name for p in discover(root, scope)] == ["keep.md"]


def test_a_star_stays_within_one_path_segment(tmp_path: Path) -> None:
    """The `fnmatch` surprise this avoids: there `docs/*.md` also matches `docs/a/b.md`."""
    scope = CorpusScope(exclude=("docs/*.md",))
    assert scope.excluded(PurePosixPath("docs/top.md")) is True
    assert scope.excluded(PurePosixPath("docs/deep/nested.md")) is False
    assert CorpusScope(exclude=("docs/**",)).excluded(PurePosixPath("docs/deep/nested.md")) is True


def test_a_pattern_also_matches_a_bare_file_name(tmp_path: Path) -> None:
    """Which is what makes `*.draft.md` work wherever the file sits — and what
    makes `*.md` exclude everything, since that is what it literally says."""
    assert CorpusScope(exclude=("*.draft.md",)).excluded(PurePosixPath("deep/a.draft.md")) is True
    assert CorpusScope(exclude=("*.md",)).excluded(PurePosixPath("deep/nested.md")) is True


def test_discovery_and_watch_agree(tmp_path: Path) -> None:
    """The reason this module exists: two answers to one question must be one answer."""
    root = repo(
        tmp_path,
        {
            "a.md": "# A\n",
            "tests/fixtures/b.md": "# B\n",
            "export/x/markdown/a.md": "# A\n",
            ".mycelium/c.md": "# C\n",
        },
    )
    scope = CorpusScope(knowledge_dir=".", exclude=("tests",))
    discovered = {p.resolve() for p in discover(root, scope)}
    watched = {p.resolve() for p in watched_paths(root, scope)}
    assert discovered == watched
    for path in (root / "tests/fixtures/b.md", root / "export/x/markdown/a.md"):
        assert is_relevant(path, root, scope) is False


def test_an_excluded_document_is_not_compiled(tmp_path: Path) -> None:
    """BUG-0007, end to end: fixtures in the tree must not become corpus."""
    root = repo(tmp_path, {"guide.md": "# Guide\n\nReal.\n", "tests/fixture.md": "# F\n\nFake.\n"})
    config = MyceliumConfig(project=ProjectConfig(knowledge_dir=".", exclude=("tests",)))

    build(root, config=config)

    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path("guide.md") is not None
        assert store.get_document_by_path("tests/fixture.md") is None
        assert not store.search_chunks("Fake")


def test_an_absolute_exclude_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="relative"):
        ProjectConfig(exclude=("/etc",))
