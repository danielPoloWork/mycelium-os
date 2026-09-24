# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The reference profile generates the corpus it names (roadmap 7.6, BUG-0034, BUG-0035).

Two defects let the generator write a corpus other than the one its manifest and its
docstring claimed: a source directory that did not exist was skipped in silence, and a
harvested heading could become a title YAML refuses, so the build quarantined the
document and the corpus compiled short of its stated size. Both are refusals now, and
this file pins them - and pins that every source the profile names is really there.
"""

import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import benchmark_reference_profile as profile  # noqa: E402 - the tool is not a package

from mycelium.markdown import parse_markdown  # noqa: E402

A_BLOCK = (
    "The compiler reads every document, splits it at its headings and writes one chunk "
    "per section, so a query can cite the passage rather than the file."
)


def test_every_source_the_profile_names_holds_documents() -> None:
    """The list is a claim about this repository, and a path in it that does not exist
    is BUG-0034 again."""
    for relative in profile.SOURCE_CORPORA:
        directory = ROOT / relative
        assert directory.is_dir(), relative
        assert any(directory.rglob("*.md")), relative


def test_a_missing_source_is_refused_not_skipped(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("# A\n\n" + A_BLOCK + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as refused:
        profile.harvest(tmp_path, sources=(Path("docs"), Path("nowhere/knowledge")))
    assert "nowhere/knowledge" in str(refused.value)


@pytest.mark.parametrize(
    "heading",
    [
        "`<word>` is how documentation writes a placeholder",
        '"Quantified at 1.0" now means Milestone 7',
        "Install: the short way",
        "a heading with a # in it",
        "- not a list item",
        "Größenordnung and 設計",
    ],
)
def test_a_hostile_heading_becomes_a_title_the_adapter_accepts(heading: str) -> None:
    """Every one of these is a real shape a harvested heading can take; the first two
    are the ones that quarantined 2 of roadmap 7.4's thousand documents."""
    prose = profile.Prose(blocks=(A_BLOCK,), headings=(heading,))
    text = profile._document(random.Random(7), prose, 42)

    parsed = parse_markdown(text)

    assert parsed.frontmatter.title == f"{heading} (42)"
    assert not parsed.warnings


def test_a_run_that_compiled_short_is_refused() -> None:
    short = SimpleNamespace(
        manifest=SimpleNamespace(counts=SimpleNamespace(documents=998)),
        stats=SimpleNamespace(quarantined=2),
    )
    with pytest.raises(SystemExit) as refused:
        profile.compiled_all(short, 1000)
    assert "998" in str(refused.value) and "2 quarantined" in str(refused.value)

    whole = SimpleNamespace(
        manifest=SimpleNamespace(counts=SimpleNamespace(documents=1000)),
        stats=SimpleNamespace(quarantined=0),
    )
    profile.compiled_all(whole, 1000)
