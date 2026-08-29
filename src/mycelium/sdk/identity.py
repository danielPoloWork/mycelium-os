# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Identity library — canonical hashing, ULIDs, and anchors (spec 03 §§1-2).

The identity rules are one of the five contracts that freeze at 1.0 (architecture
§10), so this module is deliberately small, total, and free of hidden state: every
function is pure except the ULID factory, whose only impurity (clock, entropy) is
injectable.

Two kinds of identity, never conflated (spec 03 §1):

- **Logical identity** — ULIDs for entities (documents, snapshots, entities) and
  anchors for chunks. Survives edits; sortable; assigned once.
- **Content identity** — SHA-256 digests over *normalized* bytes. Changes on every
  edit; drives dirty detection, build keys, and embedding reuse.

Normalization is what makes digests stable: text is NFC, LF-terminated and
trailing-whitespace-free before hashing; JSON is serialized in canonical form
(sorted keys, no insignificant whitespace, integral floats as integers). Two
inputs that differ only in line endings, Unicode composition, or key order
therefore produce the same digest — the precondition for byte-identical rebuilds
(G6).

Producers (including plugins) build identities through this module rather than by
string formatting, so the grammars stay in one place; :mod:`mycelium.sdk.types`
validates the same shapes at the record boundary.
"""

import json
import math
import secrets
import threading
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Final, Self

from mycelium.sdk.types import Anchor, Sha256Digest, Ulid

__all__ = [
    "AnchorParts",
    "CITATION_SCHEME",
    "CitationUri",
    "EMPTY_SLUG",
    "IdentityError",
    "ULID_ALPHABET",
    "UlidFactory",
    "anchor",
    "canonical_json",
    "citation_uri",
    "decode_ulid",
    "digest_bytes",
    "digest_json",
    "digest_text",
    "doc_ref",
    "edge_id",
    "encode_ulid",
    "entity_ref",
    "heading_slug",
    "new_ulid",
    "normalize_text",
    "parse_anchor",
    "parse_citation_uri",
    "symbol_id",
    "ulid_timestamp",
]


class IdentityError(ValueError):
    """Malformed input to an identity constructor or parser.

    A ``ValueError`` subclass: identity failures are argument failures, and the
    CLI's usage exit code (2) already covers them without a bespoke hierarchy.
    """


# ---------------------------------------------------------------------------
# Normalization and canonical hashing (spec 03 §1)
# ---------------------------------------------------------------------------

_BOM: Final = "﻿"


def normalize_text(text: str) -> str:
    """Return `text` in the form the project hashes and stores.

    UTF-8 NFC, LF line endings, no trailing whitespace on any line, no trailing
    blank lines, and no leading byte-order mark. Leading blank lines are content
    and are preserved. The function is idempotent — ``normalize_text`` of an
    already-normalized string returns it unchanged (property-tested).
    """
    text = text.removeprefix(_BOM)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).rstrip("\n")


def _canonical(value: object) -> object:
    """Recursively rewrite `value` into the JSON shape spec 03 §1 canonicalizes to."""
    # bool before int: bool is an int subclass and must stay true/false.
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = f"non-finite number is not representable in JSON: {value!r}"
            raise IdentityError(msg)
        # "integers only where integral": 2.0 and 2 must not produce two digests.
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        items: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                msg = f"JSON object keys must be strings, got {type(key).__name__}"
                raise IdentityError(msg)
            items[key] = _canonical(item)
        return items
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    msg = f"value of type {type(value).__name__} is not JSON-representable"
    raise IdentityError(msg)


def canonical_json(value: object) -> str:
    """Serialize `value` in canonical JSON form (spec 03 §1).

    Sorted keys, no insignificant whitespace, non-ASCII kept verbatim (the bytes
    are UTF-8), integral floats emitted as integers, non-finite numbers rejected.
    Strings are *not* NFC-normalized here: §1 scopes that rule to text hashing,
    and silently rewriting payload strings would make the digest disagree with
    the data a consumer reads back (ADR-0005).
    """
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_bytes(data: bytes) -> Sha256Digest:
    """Digest raw bytes verbatim — the CAS rule for acquired originals (tier 1)."""
    return f"sha256:{sha256(data).hexdigest()}"


def digest_text(text: str) -> Sha256Digest:
    """Digest text after normalization: the document/chunk content-identity rule."""
    return digest_bytes(normalize_text(text).encode("utf-8"))


def digest_json(value: object) -> Sha256Digest:
    """Digest a JSON-representable value through its canonical form.

    Key order and integral-float spelling are therefore irrelevant to the result
    — the property build keys and edge ids depend on.
    """
    return digest_bytes(canonical_json(value).encode("utf-8"))


# ---------------------------------------------------------------------------
# ULIDs (spec 03 §2)
# ---------------------------------------------------------------------------

ULID_ALPHABET: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford base32 — no I, L, O, or U, so ids survive being read aloud."""

_ULID_DECODE: Final = {char: index for index, char in enumerate(ULID_ALPHABET)}
_ULID_LENGTH: Final = 26
_RANDOMNESS_BYTES: Final = 10
_MAX_TIMESTAMP: Final = (1 << 48) - 1
_MAX_RANDOMNESS: Final = (1 << 80) - 1
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


def encode_ulid(timestamp_ms: int, randomness: bytes) -> Ulid:
    """Encode a 48-bit millisecond timestamp and 80 bits of randomness as a ULID."""
    if not 0 <= timestamp_ms <= _MAX_TIMESTAMP:
        msg = f"ULID timestamp out of range (0..{_MAX_TIMESTAMP}): {timestamp_ms}"
        raise IdentityError(msg)
    if len(randomness) != _RANDOMNESS_BYTES:
        msg = f"ULID randomness must be {_RANDOMNESS_BYTES} bytes, got {len(randomness)}"
        raise IdentityError(msg)
    value = (timestamp_ms << 80) | int.from_bytes(randomness, "big")
    return "".join(
        ULID_ALPHABET[(value >> (5 * (_ULID_LENGTH - 1 - position))) & 0x1F]
        for position in range(_ULID_LENGTH)
    )


def decode_ulid(ulid: str) -> tuple[int, bytes]:
    """Decode a ULID into its ``(timestamp_ms, randomness)`` parts."""
    if len(ulid) != _ULID_LENGTH:
        msg = f"ULID must be {_ULID_LENGTH} characters, got {len(ulid)}"
        raise IdentityError(msg)
    value = 0
    for char in ulid:
        digit = _ULID_DECODE.get(char)
        if digit is None:
            msg = f"invalid Crockford base32 character in ULID: {char!r}"
            raise IdentityError(msg)
        value = (value << 5) | digit
    if value > (1 << 128) - 1:
        # 26 chars carry 130 bits; the two leading bits must be zero.
        msg = f"ULID overflows 128 bits: {ulid!r}"
        raise IdentityError(msg)
    return value >> 80, (value & _MAX_RANDOMNESS).to_bytes(_RANDOMNESS_BYTES, "big")


def ulid_timestamp(ulid: str) -> datetime:
    """Return the UTC instant a ULID was minted (millisecond resolution).

    Computed as an exact offset from the epoch: ``datetime.fromtimestamp`` takes a
    float (lossy past millisecond precision at these magnitudes) and raises
    ``OSError`` on Windows for far-future values. The 48-bit ULID range reaches
    beyond ``datetime.max``, so timestamps past year 9999 raise
    :class:`IdentityError` rather than a platform-dependent error.
    """
    timestamp_ms, _ = decode_ulid(ulid)
    try:
        return _EPOCH + timedelta(milliseconds=timestamp_ms)
    except OverflowError as exc:
        msg = f"ULID timestamp {timestamp_ms} is beyond the representable date range"
        raise IdentityError(msg) from exc


class UlidFactory:
    """Mints monotonically increasing ULIDs.

    Lexicographic order equals mint order even within one millisecond: ids minted
    in the same millisecond reuse that millisecond's randomness incremented by
    one, per the ULID specification's monotonic mode. Build stages run in bounded
    parallelism, so ``new`` serializes on a lock (Monitor Object, ADR-0005) — the
    invariant is worthless if two threads can interleave a read-modify-write.

    ``clock`` and ``entropy`` are injectable so tests can pin both and assert the
    ordering rules rather than sample them.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], int] | None = None,
        entropy: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._clock = clock or self._default_clock
        self._entropy = entropy
        self._lock = threading.Lock()
        self._last_timestamp_ms = -1
        self._last_randomness = 0

    @staticmethod
    def _default_clock() -> int:
        """Wall-clock milliseconds since the Unix epoch."""
        return int(datetime.now(tz=UTC).timestamp() * 1000)

    def new(self) -> Ulid:
        """Mint the next ULID."""
        with self._lock:
            timestamp_ms = self._clock()
            if timestamp_ms < self._last_timestamp_ms:
                # A clock step backwards must not break sortability: hold the
                # last millisecond and keep incrementing within it.
                timestamp_ms = self._last_timestamp_ms
            if timestamp_ms == self._last_timestamp_ms:
                randomness = self._last_randomness + 1
                if randomness > _MAX_RANDOMNESS:
                    msg = "monotonic ULID randomness exhausted within one millisecond"
                    raise IdentityError(msg)
            else:
                randomness = int.from_bytes(self._entropy(_RANDOMNESS_BYTES), "big")
            self._last_timestamp_ms = timestamp_ms
            self._last_randomness = randomness
            return encode_ulid(timestamp_ms, randomness.to_bytes(_RANDOMNESS_BYTES, "big"))


_DEFAULT_FACTORY: Final = UlidFactory()


def new_ulid() -> Ulid:
    """Mint a ULID from the process-wide monotonic factory."""
    return _DEFAULT_FACTORY.new()


# ---------------------------------------------------------------------------
# Heading slugs and anchors (spec 03 §2)
# ---------------------------------------------------------------------------

EMPTY_SLUG: Final = "section"
"""Slug for a heading whose text carries no alphanumerics (e.g. ``## ---``)."""

_SLUG_SEPARATOR: Final = "-"


def heading_slug(heading: str) -> str:
    """Slugify heading text for use in an anchor.

    NFKC-folded, case-folded, alphanumerics kept, every other run collapsed to a
    single ``-``, no leading or trailing separator. Non-Latin scripts survive
    intact — the corpus is multilingual (D-028) and transliterating would make
    Japanese and Chinese headings collide on the empty slug. A heading with no
    alphanumerics at all slugs to :data:`EMPTY_SLUG`.
    """
    folded = unicodedata.normalize("NFKC", heading).casefold()
    slug = "".join(char if char.isalnum() else _SLUG_SEPARATOR for char in folded)
    slug = _SLUG_SEPARATOR.join(part for part in slug.split(_SLUG_SEPARATOR) if part)
    return slug or EMPTY_SLUG


@dataclass(frozen=True, slots=True)
class AnchorParts:
    """The parsed components of a chunk anchor."""

    doc_path: str
    heading_slugs: tuple[str, ...]
    ordinal: int

    def to_anchor(self) -> Anchor:
        """Rebuild the anchor string these parts came from."""
        return anchor(self.doc_path, self.heading_slugs, self.ordinal)


def _validate_slugs(heading_slugs: Sequence[str]) -> tuple[str, ...]:
    for slug in heading_slugs:
        if not slug:
            msg = "heading slug must not be empty"
            raise IdentityError(msg)
        if "#" in slug or "/" in slug:
            msg = f"heading slug must not contain '#' or '/': {slug!r}"
            raise IdentityError(msg)
    return tuple(heading_slugs)


def _validate_ordinal(ordinal: int) -> int:
    if ordinal < 0:
        msg = f"ordinal must be non-negative, got {ordinal}"
        raise IdentityError(msg)
    return ordinal


def anchor(doc_path: str, heading_slugs: Sequence[str], ordinal: int) -> Anchor:
    """Build a chunk anchor: ``<doc-path>#<heading-slug-path>/<ordinal>``.

    `heading_slugs` is the path of section slugs containing the chunk, outermost
    first, and is empty for content that precedes the first heading. The ordinal
    is the chunk's position within that section (spec 03 §2).
    """
    if not doc_path:
        msg = "document path must not be empty"
        raise IdentityError(msg)
    if "#" in doc_path:
        msg = f"document path must not contain '#': {doc_path!r}"
        raise IdentityError(msg)
    slugs = _validate_slugs(heading_slugs)
    return f"{doc_path}#{'/'.join(slugs)}/{_validate_ordinal(ordinal)}"


def _split_fragment(fragment: str, *, source: str) -> tuple[tuple[str, ...], int]:
    """Split ``<heading-slug-path>/<ordinal>`` — the ordinal is the last segment."""
    head, separator, tail = fragment.rpartition("/")
    if not separator:
        msg = f"missing '/<ordinal>' in {source!r}"
        raise IdentityError(msg)
    if not tail.isdigit() or (tail != "0" and tail.startswith("0")):
        msg = f"ordinal must be a canonical non-negative integer in {source!r}"
        raise IdentityError(msg)
    slugs = tuple(head.split("/")) if head else ()
    return _validate_slugs(slugs), int(tail)


def parse_anchor(value: str) -> AnchorParts:
    """Parse a chunk anchor, raising :class:`IdentityError` if it is malformed."""
    doc_path, separator, fragment = value.partition("#")
    if not separator or not doc_path:
        msg = f"anchor must be '<doc-path>#<heading-slug-path>/<ordinal>': {value!r}"
        raise IdentityError(msg)
    slugs, ordinal = _split_fragment(fragment, source=value)
    return AnchorParts(doc_path=doc_path, heading_slugs=slugs, ordinal=ordinal)


# ---------------------------------------------------------------------------
# Citation URIs and reference forms (spec 03 §2)
# ---------------------------------------------------------------------------

CITATION_SCHEME: Final = "mycelium://"


@dataclass(frozen=True, slots=True)
class CitationUri:
    """The parsed components of a citation URI."""

    doc_id: str
    heading_slugs: tuple[str, ...]
    ordinal: int
    lines: tuple[int, int] | None = None

    def to_uri(self) -> str:
        """Rebuild the citation URI these parts came from."""
        return citation_uri(self.doc_id, self.heading_slugs, self.ordinal, lines=self.lines)

    @classmethod
    def from_anchor(cls, parts: AnchorParts, doc_id: str) -> Self:
        """Lift a parsed anchor into a citation for `doc_id`.

        Citations key on ``doc_id``, not path, so they survive folder moves —
        including ``candidate/`` → ``verified/`` promotion (D-021).
        """
        return cls(doc_id=doc_id, heading_slugs=parts.heading_slugs, ordinal=parts.ordinal)


def _validate_ulid(value: str, *, field: str) -> str:
    try:
        decode_ulid(value)
    except IdentityError as exc:
        msg = f"{field} is not a ULID: {value!r}"
        raise IdentityError(msg) from exc
    return value


def citation_uri(
    doc_id: str,
    heading_slugs: Sequence[str],
    ordinal: int,
    *,
    lines: tuple[int, int] | None = None,
) -> str:
    """Build the public citation URI returned to agents (spec 03 §2).

    ``mycelium://<doc_id>#<heading-slug-path>/<ordinal>``, with the optional
    ``?lines=a-b`` suffix appended *after* the fragment exactly as the spec
    writes it — a deliberate departure from RFC 3986 component order, recorded
    in ADR-0005.
    """
    _validate_ulid(doc_id, field="doc_id")
    slugs = _validate_slugs(heading_slugs)
    uri = f"{CITATION_SCHEME}{doc_id}#{'/'.join(slugs)}/{_validate_ordinal(ordinal)}"
    if lines is None:
        return uri
    start, end = lines
    if start < 0 or end < start:
        msg = f"line range must be non-negative and ordered, got {lines!r}"
        raise IdentityError(msg)
    return f"{uri}?lines={start}-{end}"


def parse_citation_uri(value: str) -> CitationUri:
    """Parse a citation URI, raising :class:`IdentityError` if it is malformed."""
    if not value.startswith(CITATION_SCHEME):
        msg = f"citation URI must start with {CITATION_SCHEME!r}: {value!r}"
        raise IdentityError(msg)
    body = value.removeprefix(CITATION_SCHEME)
    body, separator, query = body.partition("?")
    lines: tuple[int, int] | None = None
    if separator:
        if not query.startswith("lines="):
            msg = f"the only supported citation query is 'lines=a-b': {value!r}"
            raise IdentityError(msg)
        start_text, dash, end_text = query.removeprefix("lines=").partition("-")
        if not dash or not start_text.isdigit() or not end_text.isdigit():
            msg = f"line range must be 'lines=<start>-<end>': {value!r}"
            raise IdentityError(msg)
        lines = (int(start_text), int(end_text))
        if lines[1] < lines[0]:
            msg = f"line range must be ordered, got {lines!r}"
            raise IdentityError(msg)
    doc_id, separator, fragment = body.partition("#")
    if not separator:
        msg = f"citation URI must carry a '#<heading-slug-path>/<ordinal>': {value!r}"
        raise IdentityError(msg)
    _validate_ulid(doc_id, field="doc_id")
    slugs, ordinal = _split_fragment(fragment, source=value)
    return CitationUri(doc_id=doc_id, heading_slugs=slugs, ordinal=ordinal, lines=lines)


def doc_ref(path: str) -> str:
    """Reference form for a document in the edge graph: ``doc:<path>``."""
    if not path:
        msg = "document path must not be empty"
        raise IdentityError(msg)
    return f"doc:{path}"


def symbol_id(language: str, qualified_name: str) -> str:
    """Symbol identity: ``sym:<language>:<qualified-name>`` (spec 03 §2)."""
    if not language or not qualified_name:
        msg = "symbol language and qualified name must both be non-empty"
        raise IdentityError(msg)
    if ":" in language:
        msg = f"symbol language must not contain ':': {language!r}"
        raise IdentityError(msg)
    return f"sym:{language.lower()}:{qualified_name}"


def entity_ref(slug: str) -> str:
    """Entity reference form: ``ent:<slug>`` (identity itself is the ULID)."""
    if not slug:
        msg = "entity slug must not be empty"
        raise IdentityError(msg)
    return f"ent:{slug}"


def edge_id(
    from_id: str, to_id: str, edge_type: str, provenance_digest: Sha256Digest
) -> Sha256Digest:
    """Edge identity: the digest of ``(from, to, type, provenance_digest)``.

    Edges are facts, not entities (spec 03 §6): the same assertion observed twice
    yields the same id, and re-deriving it is how a rebuild converges.
    """
    return digest_json([from_id, to_id, str(edge_type), provenance_digest])
