# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The threat model names its tests, and the tests name their boundary (roadmap 6.3, ADR-0119).

`docs/security/threat-model.md` declares the trust boundaries and, per boundary, the
controls that hold them. Before this item every control was a sentence, and whether a
test stood behind it was a matter of reading the test tree with the model open beside
it. Now a test file that holds a boundary says so — a module-level ``pytestmark`` carrying
the ``boundary`` marker with the boundary's id — which makes two things mechanical:
`pytest -m boundary` runs the threat-model-derived suite, and this file checks that the
derivation is whole.

Whole means: every boundary the model declares is held by at least one test file, or is
excused here by name with the reason; every marker names a boundary the model declares;
and the marker itself is registered, so a typo in one cannot pass as a marker pytest
does not know. A boundary that gains a control gains a marked test in the same PR — the
same rule AGENTS.md §7 already applies to the model's prose.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THREAT_MODEL = ROOT / "docs" / "security" / "threat-model.md"
TEST_TREES = (ROOT / "tests", ROOT / "contrib" / "chats" / "tests")

BOUNDARY_ROW = re.compile(r"^\|\s*\*\*(B\d+)\s+—\s+([^*]+?)\*\*", re.MULTILINE)
"""A declared boundary: the same shape `tools/consistency_lint.py` parses."""

MARKER = re.compile(r'pytest\.mark\.boundary\(\s*"(B\d+)"\s*\)')

UNTESTED_BY_DESIGN: dict[str, str] = {
    "B3": (
        "the vendored EADOS bundle runs by a maintainer's hand and, in CI, only through the "
        "generated consistency lint; its control is that every update arrives as a reviewable "
        "diff, which is a property of the review and not of the code"
    ),
}
"""Boundaries no test can hold, each with the reason. Adding one is a decision."""


def declared_boundaries() -> dict[str, str]:
    text = THREAT_MODEL.read_text(encoding="utf-8")
    return {match.group(1): match.group(2).strip() for match in BOUNDARY_ROW.finditer(text)}


def held_boundaries() -> dict[str, set[Path]]:
    holders: dict[str, set[Path]] = {}
    for tree in TEST_TREES:
        for path in sorted(tree.rglob("test_*.py")):
            if path.name == Path(__file__).name:
                continue  # this file talks about markers; it holds none
            for boundary in MARKER.findall(path.read_text(encoding="utf-8")):
                holders.setdefault(boundary, set()).add(path.relative_to(ROOT))
    return holders


def test_the_model_declares_boundaries_the_lint_can_parse() -> None:
    declared = declared_boundaries()
    assert len(declared) >= 15, sorted(declared)
    assert "B4" in declared and "B6" in declared and "B15" in declared


def test_every_declared_boundary_is_held_by_a_test_or_excused_by_name() -> None:
    """The derivation, checked whole: a boundary with a control and no test is a
    sentence, and a sentence is what the review found five of."""
    declared = set(declared_boundaries())
    held = set(held_boundaries())
    unheld = declared - held
    assert unheld == set(UNTESTED_BY_DESIGN), (
        f"boundaries with no marked test and no recorded excuse: "
        f"{sorted(unheld - set(UNTESTED_BY_DESIGN))}; excused but now held: "
        f"{sorted(set(UNTESTED_BY_DESIGN) & held)}"
    )


def test_every_marker_names_a_boundary_the_model_declares() -> None:
    """A marker citing a boundary the model does not declare reads as coverage of
    nothing — the same failure `check_threat_boundaries` refuses for a STRIDE row."""
    declared = set(declared_boundaries())
    for boundary, files in held_boundaries().items():
        assert boundary in declared, f"{sorted(map(str, files))} hold {boundary}, undeclared"


def test_an_excuse_names_a_declared_boundary_and_gives_a_reason() -> None:
    declared = set(declared_boundaries())
    for boundary, reason in UNTESTED_BY_DESIGN.items():
        assert boundary in declared, boundary
        assert len(reason) > 40, boundary


def test_the_marker_is_registered_so_a_typo_cannot_pass_as_one() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = project["tool"]["pytest"]["ini_options"]["markers"]
    assert any(str(marker).startswith("boundary(id)") for marker in markers), markers


def test_a_file_that_holds_a_boundary_holds_it_at_module_level_with_tests_in_it() -> None:
    """The marker is a claim about a file's tests; a file with the claim and no tests,
    or with the claim on one test only, would let `-m boundary` run less than it says."""
    for files in held_boundaries().values():
        for relative in files:
            source = (ROOT / relative).read_text(encoding="utf-8")
            assert re.search(r"^pytestmark\s*=", source, re.MULTILINE), (
                f"{relative}: not module-level"
            )
            assert re.search(r"^(?:async )?def test_", source, re.MULTILINE), (
                f"{relative}: no tests"
            )


def test_the_live_boundaries_each_have_more_than_one_holder_where_the_review_added_one() -> None:
    """The four surfaces the review measured — ingested and authored content, the
    serving edge, the evidence projection, the chat import — each hold at least two
    files, because one file is one author's reading of a boundary."""
    held = held_boundaries()
    for boundary in ("B4", "B6", "B11", "B15"):
        assert len(held.get(boundary, ())) >= 2, (
            boundary,
            sorted(map(str, held.get(boundary, ()))),
        )
