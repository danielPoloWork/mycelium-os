# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Identity library (roadmap 2.3): the spec's identity rules hold as properties —
normalization is idempotent, digests ignore representation, ULIDs sort by mint order,
and every anchor/citation round-trips through its parser."""

import unicodedata
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from mycelium.sdk.identity import (
    EMPTY_SLUG,
    ULID_ALPHABET,
    AnchorParts,
    CitationUri,
    IdentityError,
    UlidFactory,
    anchor,
    canonical_json,
    citation_uri,
    decode_ulid,
    digest_bytes,
    digest_json,
    digest_text,
    doc_ref,
    edge_id,
    encode_ulid,
    entity_ref,
    heading_slug,
    new_ulid,
    normalize_text,
    parse_anchor,
    parse_citation_uri,
    symbol_id,
    ulid_timestamp,
)
from mycelium.sdk.types import Anchor, EdgeType, Sha256Digest, Symbol, Ulid

ANCHOR_ADAPTER = TypeAdapter(Anchor)
DIGEST_ADAPTER = TypeAdapter(Sha256Digest)
ULID_ADAPTER = TypeAdapter(Ulid)

# Slugs that survive `heading_slug` unchanged, for building anchors in properties.
slug_strategy = st.from_regex(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z", fullmatch=True)
ordinal_strategy = st.integers(min_value=0, max_value=10_000)
json_strategy = st.recursive(
    st.none() | st.booleans() | st.integers(min_value=-(2**53), max_value=2**53) | st.text(),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=8,
)


# ---------------------------------------------------------------------------
# Normalization and canonical hashing (spec 03 §1)
# ---------------------------------------------------------------------------


def test_normalize_text_applies_the_spec_rules() -> None:
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"
    assert normalize_text("trailing   \nspace\t\n") == "trailing\nspace"
    assert normalize_text("﻿bom") == "bom"
    assert normalize_text("body\n\n\n") == "body"
    # NFC: "e" + combining acute collapses onto the precomposed character.
    assert normalize_text("é") == "é"
    # Leading blank lines are content, not noise.
    assert normalize_text("\n\nbody") == "\n\nbody"


@given(text=st.text(max_size=200))
def test_normalize_text_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once


@given(text=st.text(max_size=200))
def test_digest_text_ignores_line_endings_and_composition(text: str) -> None:
    decomposed = unicodedata.normalize("NFD", text)
    crlf = normalize_text(text).replace("\n", "\r\n")
    assert digest_text(decomposed) == digest_text(text)
    assert digest_text(crlf) == digest_text(text)


@given(value=json_strategy)
def test_digest_json_ignores_key_order(value: object) -> None:
    reversed_value = value
    if isinstance(value, dict):
        reversed_value = dict(reversed(list(value.items())))
    assert digest_json(reversed_value) == digest_json(value)


def test_canonical_json_form() -> None:
    assert canonical_json({"b": 1, "a": [2, 3]}) == '{"a":[2,3],"b":1}'
    # "integers only where integral": 2.0 and 2 must not produce two digests.
    assert canonical_json({"n": 2.0}) == '{"n":2}'
    assert digest_json({"n": 2.0}) == digest_json({"n": 2})
    assert canonical_json({"n": 2.5}) == '{"n":2.5}'
    # Non-ASCII is kept verbatim; the digest is over UTF-8 bytes.
    assert canonical_json({"k": "é"}) == '{"k":"é"}'
    # bool must not degrade into its int value.
    assert canonical_json([True, 1]) == "[true,1]"
    # Tuples are JSON arrays; records use tuples for immutability.
    assert canonical_json(("a", "b")) == '["a","b"]'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "int key"}, {"set"}, object()])
def test_canonical_json_rejects_unrepresentable_values(value: object) -> None:
    with pytest.raises(IdentityError):
        canonical_json(value)


def test_digests_are_valid_contract_values() -> None:
    for digest in (digest_bytes(b""), digest_text("x"), digest_json({"a": 1})):
        DIGEST_ADAPTER.validate_python(digest)
    # Known vector: SHA-256 of the empty string.
    assert digest_bytes(b"") == (
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    # Raw-byte custody (CAS) does not normalize; text hashing does.
    assert digest_bytes(b"a  \n") != digest_text("a  \n")
    assert digest_text("a  \n") == digest_bytes(b"a")


# ---------------------------------------------------------------------------
# ULIDs (spec 03 §2)
# ---------------------------------------------------------------------------


def test_ulid_encoding_boundaries() -> None:
    assert encode_ulid(0, bytes(10)) == "0" * 26
    assert encode_ulid((1 << 48) - 1, b"\xff" * 10) == "7ZZZZZZZZZZZZZZZZZZZZZZZZZ"
    # The timestamp occupies the first ten characters.
    assert encode_ulid((1 << 48) - 1, bytes(10)).startswith("7ZZZZZZZZZ")


@given(
    timestamp_ms=st.integers(min_value=0, max_value=(1 << 48) - 1),
    randomness=st.binary(min_size=10, max_size=10),
)
def test_ulid_round_trips_and_validates(timestamp_ms: int, randomness: bytes) -> None:
    ulid = encode_ulid(timestamp_ms, randomness)
    ULID_ADAPTER.validate_python(ulid)
    assert set(ulid) <= set(ULID_ALPHABET)
    assert decode_ulid(ulid) == (timestamp_ms, randomness)


@given(
    # Bounded at 9999-12-31T23:59:59.999Z: the 48-bit ULID range runs past `datetime.max`.
    timestamp_ms=st.integers(min_value=0, max_value=253_402_300_799_999),
    randomness=st.binary(min_size=10, max_size=10),
)
def test_ulid_timestamp_is_exact(timestamp_ms: int, randomness: bytes) -> None:
    minted = ulid_timestamp(encode_ulid(timestamp_ms, randomness))
    assert minted == datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=timestamp_ms)
    assert minted.tzinfo is UTC


def test_ulid_timestamp_beyond_year_9999_is_a_typed_error() -> None:
    far_future = encode_ulid((1 << 48) - 1, bytes(10))
    with pytest.raises(IdentityError, match="representable date range"):
        ulid_timestamp(far_future)


@given(
    first=st.integers(min_value=0, max_value=(1 << 48) - 1),
    second=st.integers(min_value=0, max_value=(1 << 48) - 1),
    randomness=st.binary(min_size=10, max_size=10),
)
def test_ulid_lexicographic_order_matches_time_order(
    first: int, second: int, randomness: bytes
) -> None:
    assume(first < second)
    assert encode_ulid(first, randomness) < encode_ulid(second, randomness)


@pytest.mark.parametrize(
    ("timestamp_ms", "randomness"),
    [(-1, bytes(10)), (1 << 48, bytes(10)), (0, bytes(9)), (0, bytes(11))],
)
def test_encode_ulid_rejects_out_of_range_parts(timestamp_ms: int, randomness: bytes) -> None:
    with pytest.raises(IdentityError):
        encode_ulid(timestamp_ms, randomness)


@pytest.mark.parametrize("value", ["", "0" * 25, "0" * 27, "I" * 26, "8" * 26, "0" * 25 + "u"])
def test_decode_ulid_rejects_malformed_input(value: str) -> None:
    """Both layers agree: what `decode_ulid` refuses, the record contract refuses.

    `"8" * 26` is the case that made them disagree — 26 Crockford characters can
    express 130 bits, and the record pattern accepted the 2-bit overflow until the
    identity library was written against it (ADR-0005).
    """
    with pytest.raises(IdentityError):
        decode_ulid(value)
    with pytest.raises(ValidationError):
        ULID_ADAPTER.validate_python(value)


def test_factory_is_monotonic_within_one_millisecond() -> None:
    factory = UlidFactory(clock=lambda: 1_700_000_000_000, entropy=lambda n: bytes(n))
    minted = [factory.new() for _ in range(5)]
    assert minted == sorted(minted)
    assert len(set(minted)) == len(minted)
    # Same millisecond: the randomness increments by one rather than being redrawn.
    assert [decode_ulid(u)[1] for u in minted[:2]] == [
        (0).to_bytes(10, "big"),
        (1).to_bytes(10, "big"),
    ]


def test_factory_redraws_entropy_on_a_new_millisecond() -> None:
    ticks = iter([1, 1, 2])
    factory = UlidFactory(clock=lambda: next(ticks), entropy=lambda n: b"\x07" * n)
    first, second, third = (factory.new() for _ in range(3))
    assert decode_ulid(second)[1] == (int.from_bytes(b"\x07" * 10, "big") + 1).to_bytes(10, "big")
    assert decode_ulid(third)[1] == b"\x07" * 10
    assert first < second < third


def test_factory_holds_order_when_the_clock_steps_backwards() -> None:
    ticks = iter([1_000, 999])
    factory = UlidFactory(clock=lambda: next(ticks), entropy=lambda n: bytes(n))
    first, second = factory.new(), factory.new()
    assert first < second
    assert decode_ulid(second)[0] == 1_000


def test_factory_raises_when_monotonic_randomness_is_exhausted() -> None:
    factory = UlidFactory(clock=lambda: 42, entropy=lambda n: b"\xff" * n)
    factory.new()
    with pytest.raises(IdentityError, match="randomness exhausted"):
        factory.new()


def test_new_ulid_uses_the_process_factory() -> None:
    minted = [new_ulid() for _ in range(3)]
    assert minted == sorted(minted)
    for ulid in minted:
        ULID_ADAPTER.validate_python(ulid)
    assert abs((ulid_timestamp(minted[0]) - datetime.now(tz=UTC)).total_seconds()) < 60


# ---------------------------------------------------------------------------
# Heading slugs and anchors (spec 03 §2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Event Bus", "event-bus"),
        ("  Event   Bus  ", "event-bus"),
        ("Build Keys & Caching", "build-keys-caching"),
        ("MCP/CLI", "mcp-cli"),
        ("C# and F#", "c-and-f"),
        ("Über Größe", "über-grösse"),
        ("設計", "設計"),
        ("---", EMPTY_SLUG),
        ("", EMPTY_SLUG),
    ],
)
def test_heading_slug_examples(heading: str, expected: str) -> None:
    assert heading_slug(heading) == expected


@given(heading=st.text(max_size=80))
def test_heading_slug_is_anchor_safe_and_idempotent(heading: str) -> None:
    slug = heading_slug(heading)
    assert slug
    assert "#" not in slug
    assert "/" not in slug
    assert not slug.startswith("-")
    assert not slug.endswith("-")
    assert heading_slug(slug) == slug


def test_anchor_matches_the_spec_example() -> None:
    assert anchor("architecture.md", ["event-bus"], 2) == "architecture.md#event-bus/2"
    # Content before the first heading has an empty slug path.
    assert anchor("architecture.md", [], 0) == "architecture.md#/0"


@given(
    # `codec="utf-8"` excludes lone surrogates: they are not characters a real
    # path can hold, and pydantic's Rust validator cannot encode them at all.
    doc_path=st.text(
        alphabet=st.characters(blacklist_characters="#", codec="utf-8"),
        min_size=1,
        max_size=40,
    ),
    slugs=st.lists(slug_strategy, max_size=4),
    ordinal=ordinal_strategy,
)
def test_anchor_round_trips_and_validates(doc_path: str, slugs: list[str], ordinal: int) -> None:
    value = anchor(doc_path, slugs, ordinal)
    ANCHOR_ADAPTER.validate_python(value)
    parsed = parse_anchor(value)
    assert parsed == AnchorParts(doc_path, tuple(slugs), ordinal)
    assert parsed.to_anchor() == value


def test_anchor_parses_numeric_heading_slugs_unambiguously() -> None:
    # A heading like "## 2026" slugs to digits; the ordinal is still the last segment.
    value = anchor("roadmap.md", ["2026", "12"], 3)
    assert value == "roadmap.md#2026/12/3"
    assert parse_anchor(value) == AnchorParts("roadmap.md", ("2026", "12"), 3)


@pytest.mark.parametrize(
    ("doc_path", "slugs", "ordinal"),
    [
        ("", ["a"], 0),
        ("a#b.md", ["a"], 0),
        ("a.md", [""], 0),
        ("a.md", ["a/b"], 0),
        ("a.md", ["a#b"], 0),
        ("a.md", ["a"], -1),
    ],
)
def test_anchor_rejects_malformed_parts(doc_path: str, slugs: list[str], ordinal: int) -> None:
    with pytest.raises(IdentityError):
        anchor(doc_path, slugs, ordinal)


@pytest.mark.parametrize(
    "value",
    [
        "architecture.md",
        "architecture.md#event-bus",
        "#event-bus/0",
        "architecture.md#event-bus/01",
        "architecture.md#event-bus/x",
    ],
)
def test_parse_anchor_rejects_malformed_input(value: str) -> None:
    with pytest.raises(IdentityError):
        parse_anchor(value)


# ---------------------------------------------------------------------------
# Citation URIs and reference forms (spec 03 §2)
# ---------------------------------------------------------------------------

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"


def test_citation_uri_matches_the_spec_form() -> None:
    assert citation_uri(DOC_ID, ["event-bus"], 2) == f"mycelium://{DOC_ID}#event-bus/2"
    assert (
        citation_uri(DOC_ID, ["event-bus"], 2, lines=(88, 141))
        == f"mycelium://{DOC_ID}#event-bus/2?lines=88-141"
    )


@given(
    slugs=st.lists(slug_strategy, max_size=4),
    ordinal=ordinal_strategy,
    lines=st.none() | st.tuples(st.integers(0, 500), st.integers(0, 500)).map(sorted).map(tuple),
)
def test_citation_uri_round_trips(
    slugs: list[str], ordinal: int, lines: tuple[int, int] | None
) -> None:
    uri = citation_uri(DOC_ID, slugs, ordinal, lines=lines)
    parsed = parse_citation_uri(uri)
    assert parsed == CitationUri(DOC_ID, tuple(slugs), ordinal, lines)
    assert parsed.to_uri() == uri


def test_citation_survives_a_folder_move() -> None:
    # D-021: candidate/ -> verified/ changes the path, never the citation.
    before = parse_anchor(anchor("knowledge/candidate/api.md", ["retries"], 0))
    after = parse_anchor(anchor("knowledge/verified/api.md", ["retries"], 0))
    assert CitationUri.from_anchor(before, DOC_ID) == CitationUri.from_anchor(after, DOC_ID)


@pytest.mark.parametrize(
    "value",
    [
        f"https://{DOC_ID}#a/0",
        f"mycelium://{DOC_ID}",
        "mycelium://not-a-ulid#a/0",
        f"mycelium://{DOC_ID}#a/0?pages=1-2",
        f"mycelium://{DOC_ID}#a/0?lines=5",
        f"mycelium://{DOC_ID}#a/0?lines=9-4",
    ],
)
def test_parse_citation_uri_rejects_malformed_input(value: str) -> None:
    with pytest.raises(IdentityError):
        parse_citation_uri(value)


def test_citation_uri_rejects_a_non_ulid_doc_id() -> None:
    with pytest.raises(IdentityError, match="doc_id"):
        citation_uri("architecture.md", ["a"], 0)


def test_reference_forms() -> None:
    assert doc_ref("architecture.md") == "doc:architecture.md"
    assert entity_ref("event-bus") == "ent:event-bus"
    assert symbol_id("Python", "mycelium.compiler.BuildKey") == (
        "sym:python:mycelium.compiler.BuildKey"
    )
    # The constructed symbol id satisfies the record contract it feeds.
    Symbol(
        symbol=symbol_id("python", "mycelium.compiler.BuildKey"),
        kind="class",
        defined_in="src/mycelium/compiler.py#L84",
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: doc_ref(""),
        lambda: entity_ref(""),
        lambda: symbol_id("", "x"),
        lambda: symbol_id("python", ""),
        lambda: symbol_id("py:thon", "x"),
    ],
)
def test_reference_forms_reject_empty_parts(call: object) -> None:
    with pytest.raises(IdentityError):
        call()  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Edge identity (spec 03 §2/§6)
# ---------------------------------------------------------------------------


def test_edge_id_is_content_derived_and_stable() -> None:
    provenance = digest_json({"kind": "markdown_link", "anchor": "a.md#b/1"})
    first = edge_id(doc_ref("a.md"), doc_ref("b.md"), EdgeType.LINKS_TO, provenance)
    again = edge_id(doc_ref("a.md"), doc_ref("b.md"), "links_to", provenance)
    assert first == again  # StrEnum and its value are the same fact
    DIGEST_ADAPTER.validate_python(first)


@settings(max_examples=50)
@given(
    from_id=st.text(min_size=1, max_size=20),
    to_id=st.text(min_size=1, max_size=20),
    edge_type=st.sampled_from([e.value for e in EdgeType]),
)
def test_edge_id_distinguishes_direction_and_type(from_id: str, to_id: str, edge_type: str) -> None:
    assume(from_id != to_id)
    provenance = digest_json({"kind": "markdown_link"})
    forward = edge_id(from_id, to_id, edge_type, provenance)
    backward = edge_id(to_id, from_id, edge_type, provenance)
    other_type = next(e.value for e in EdgeType if e.value != edge_type)
    assert forward != backward
    assert forward != edge_id(from_id, to_id, other_type, provenance)
