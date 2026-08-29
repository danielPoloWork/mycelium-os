# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Frontmatter contract (roadmap 2.4): the closed field set is read, everything else
is preserved untouched, identity is never guessed, and a human's typo never stops a build."""

from datetime import date

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from mycelium.markdown.frontmatter import (
    FIELD_OWNERS,
    Frontmatter,
    FrontmatterError,
    parse_frontmatter,
    split_frontmatter,
)
from mycelium.sdk.types import ProvenanceOrigin, SourceTrust

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"

FULL = f"""---
mycelium_id: {DOC_ID}
title: Architecture
aliases: [Arch, "The Architecture"]
tags: [architecture, event-bus]
collection: core-docs
origin: synthesized
source: "https://docs.python.org/3/"
source_trust: high
generated_by: anthropic/claude-sonnet-5
verified_by: daniel
verified_at: 2026-07-31
grounding: 0.97
---

# Body
"""


def test_full_contract_round_trip() -> None:
    result = parse_frontmatter(FULL)
    fm = result.frontmatter
    assert fm.mycelium_id == DOC_ID
    assert fm.title == "Architecture"
    assert fm.aliases == ("Arch", "The Architecture")
    assert fm.tags == ("architecture", "event-bus")
    assert fm.collection == "core-docs"
    assert fm.origin is ProvenanceOrigin.SYNTHESIZED
    assert fm.source == "https://docs.python.org/3/"
    assert fm.source_trust is SourceTrust.HIGH
    assert fm.generated_by == "anthropic/claude-sonnet-5"
    assert fm.verified_by == "daniel"
    assert fm.verified_at == date(2026, 7, 31)
    assert fm.grounding == 0.97
    assert fm.properties == {}
    assert result.warnings == ()
    assert result.body.strip() == "# Body"


def test_field_owners_covers_exactly_the_contract() -> None:
    """The ownership table and the model must not drift apart (spec 03 §3)."""
    contract = set(Frontmatter.model_fields) - {"properties"}
    assert contract == set(FIELD_OWNERS)
    # Three tool writers and the human; no `status` field exists at all (D-021).
    assert set(FIELD_OWNERS.values()) == {
        "mycelium build",
        "mycelium ingest",
        "mycelium verify",
        "mycelium promote",
        "human",
    }
    assert "status" not in FIELD_OWNERS


def test_absent_frontmatter_is_not_invented() -> None:
    result = parse_frontmatter("# Just a document\n")
    assert result.frontmatter == Frontmatter()
    assert result.body == "# Just a document\n"
    assert result.body_line_offset == 0


def test_non_contract_keys_are_preserved_verbatim() -> None:
    result = parse_frontmatter("---\ncssclass: wide\ndataview: {x: 1}\npublish: true\n---\nbody\n")
    assert result.frontmatter.properties == {
        "cssclass": "wide",
        "dataview": {"x": 1},
        "publish": True,
    }
    assert result.warnings == ()


@pytest.mark.parametrize(
    ("text", "offset", "body"),
    [
        ("---\na: 1\n---\nbody", 3, "body"),
        ("---\n---\nbody", 2, "body"),
        ("no frontmatter", 0, "no frontmatter"),
        # A horizontal rule mid-document is not a frontmatter fence.
        ("intro\n\n---\n\nmore", 0, "intro\n\n---\n\nmore"),
        # An unterminated fence is body, not a parse error.
        ("---\na: 1\nbody", 0, "---\na: 1\nbody"),
    ],
)
def test_split_frontmatter_boundaries(text: str, offset: int, body: str) -> None:
    _, split_body, split_offset = split_frontmatter(text)
    assert (split_offset, split_body) == (offset, body)


def test_body_line_offset_locates_the_first_body_line() -> None:
    result = parse_frontmatter(FULL)
    body_lines = FULL.split("\n")
    first_body_line = result.body.split("\n")[1]
    assert body_lines[result.body_line_offset + 1] == first_body_line


# ---------------------------------------------------------------------------
# Identity is never guessed; everything else degrades to a warning.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["not-a-ulid", "8" * 26, "", "01J1ZC8Q4R6XKQ3F0V9T8B2M7"])
def test_malformed_identity_raises(value: str) -> None:
    with pytest.raises(FrontmatterError, match="mycelium_id"):
        parse_frontmatter(f"---\nmycelium_id: {value}\n---\nbody")


@pytest.mark.parametrize(
    "block",
    [
        "---\ntitle: [unclosed\n---\nbody",  # declares itself frontmatter, then breaks
        '---\ntitle: "unterminated\n---\nbody',
        "---\ntitle: x\n  bad_indent: y\n---\nbody",
    ],
)
def test_unreadable_frontmatter_raises(block: str) -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter(block)


@pytest.mark.parametrize(
    "text",
    [
        "---\n- a list\n- not a mapping\n---\nbody",
        "---\n\njust prose between rules\n\n---\n",
        "---\n> quote\n---\n",  # `>` opens a YAML block scalar, but this is a blockquote
        "---\n# Heading\n---\n",
        "---\n: :\n---\n",
    ],
)
def test_a_fence_around_markdown_is_body_not_frontmatter(text: str) -> None:
    """`---` / Markdown / `---` is two thematic breaks; CommonMark's reading wins.

    The discriminator runs before YAML does, so Markdown is never reported as
    broken YAML — which is what a document opening with a thematic break would
    otherwise produce (ADR-0006).
    """
    result = parse_frontmatter(text)
    assert result.frontmatter == Frontmatter()
    assert result.body == text
    assert result.body_line_offset == 0


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        ("origin: invented", "origin"),
        ("source_trust: quite-high", "source_trust"),
        ("verified_at: last tuesday", "verified_at"),
        ("grounding: 1.5", "grounding"),
        ("grounding: high", "grounding"),
        ("tags: [{nested: map}]", "tags"),
        ("title: [a, list]", "title"),
    ],
)
def test_malformed_soft_fields_warn_and_drop(block: str, expected: str) -> None:
    result = parse_frontmatter(f"---\n{block}\n---\nbody")
    assert any(expected in warning for warning in result.warnings), result.warnings
    assert getattr(result.frontmatter, expected) in (None, ())


def test_yaml_11_booleans_are_reported_not_silently_mangled() -> None:
    """`tags: [no]` is a boolean in YAML 1.1; the author's spelling is unrecoverable."""
    result = parse_frontmatter("---\ntags: [no, ok]\ntitle: yes\n---\nbody")
    assert result.frontmatter.tags == ("ok",)
    assert result.frontmatter.title is None
    assert len(result.warnings) == 2
    assert all("quote it" in warning for warning in result.warnings)


def test_scalar_shorthand_and_numeric_tags() -> None:
    result = parse_frontmatter("---\ntags: architecture\naliases: 2026\n---\nbody")
    assert result.frontmatter.tags == ("architecture",)
    assert result.frontmatter.aliases == ("2026",)
    assert result.warnings == ()


def test_contract_fields_cannot_hide_in_properties() -> None:
    with pytest.raises(ValueError, match="must not be repeated"):
        Frontmatter(properties={"title": "sneaky"})


# U+0085 (NEL) is excluded because PyYAML cannot round-trip it: `safe_dump` writes it
# as a literal line break and `safe_load` reads that back as a space. The asymmetry is
# the library's, not the contract's — the same YAML 1.1 heritage ADR-0006 records for
# unquoted booleans — so the property states what is actually guaranteed rather than
# failing on a character no vault contains.
_yaml_safe_text = st.text(alphabet=st.characters(blacklist_characters="\x85"), max_size=20)


@given(
    title=_yaml_safe_text.filter(lambda s: s.strip() == s and s != ""),
    tags=st.lists(st.from_regex(r"\A[a-z][a-z0-9-]{0,12}\Z", fullmatch=True), max_size=4),
    properties=st.dictionaries(
        st.from_regex(r"\A[a-z_]{1,10}\Z", fullmatch=True).filter(
            lambda key: key not in FIELD_OWNERS
        ),
        _yaml_safe_text | st.integers() | st.booleans(),
        max_size=3,
    ),
)
def test_any_yaml_written_frontmatter_round_trips(
    title: str, tags: list[str], properties: dict[str, object]
) -> None:
    """Whatever a YAML writer emits, the contract reads back — text, tags, and all
    the vault's own properties, unchanged."""
    block = yaml.safe_dump({"title": title, "tags": tags, **properties}, allow_unicode=True)
    result = parse_frontmatter(f"---\n{block}---\nbody\n")
    assert result.frontmatter.title == title
    assert result.frontmatter.tags == tuple(tags)
    assert result.frontmatter.properties == properties
