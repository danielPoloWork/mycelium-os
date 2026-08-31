# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The authored-Markdown frontmatter contract (spec 03 §3).

Frontmatter is the *only* machine-read metadata in an authored document, and its
field set is closed: eleven keys with named owners. Everything else a vault
carries — Obsidian plugin properties, Dataview fields, personal conventions — is
preserved as opaque `properties` and never machine-interpreted (D-022).

Ownership is the anti-drift rule (spec 03 §3): exactly three tool writers, and
humans own the rest.

===================  ==========================================================
Owner                Fields
===================  ==========================================================
``mycelium build``   ``mycelium_id``
``mycelium ingest``  ``origin``, ``source``, ``source_trust``, ``generated_by``
``mycelium verify``  ``verified_by``, ``verified_at``, ``grounding``
human                ``title``, ``aliases``, ``tags``, ``collection``
===================  ==========================================================

There is deliberately **no** ``status:`` field: verification status is carried by
the folder alone (D-021), so a file move can never disagree with a stale field.

Parsing is deliberately lopsided about failure. A malformed ``mycelium_id``, or
unreadable YAML in a block that *declares itself* frontmatter, raises — identity
must never be guessed, and a document whose frontmatter cannot be read is a
quarantine case (spec 02 §11), not a document to compile with invented metadata.
Every other malformed value warns and is dropped, because a human's typo in
``tags`` must not stop the build. A document that merely opens with a thematic
break is not frontmatter at all: see :func:`_opens_a_mapping`.
"""

import re
from datetime import date, datetime, time
from math import isfinite
from typing import Final, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from mycelium.sdk.identity import IdentityError, decode_ulid
from mycelium.sdk.types import ProvenanceOrigin, SourceTrust, Ulid

__all__ = [
    "DELIMITER",
    "FIELD_OWNERS",
    "Frontmatter",
    "FrontmatterError",
    "FrontmatterResult",
    "parse_frontmatter",
    "split_frontmatter",
]

DELIMITER: Final = "---"
_BOM: Final = "﻿"

_MAPPING_KEY: Final = re.compile(r"(?:'[^']+'|\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_.-]*)\s*:(\s|$)")
"""What a frontmatter block's first line looks like: a YAML key, quoted or not.

The quoted form is not exotic — YAML 1.1 reads `on`, `off`, `yes`, and `no` as
booleans, so PyYAML *emits* them quoted, and an Obsidian vault with an `off:`
property round-trips through a quoted key. Requiring a bare identifier read
that document's frontmatter as a thematic break and indexed its metadata as
prose (BUG-0011).
"""

FIELD_OWNERS: Final[dict[str, str]] = {
    "mycelium_id": "mycelium build",
    "origin": "mycelium ingest",
    "source": "mycelium ingest",
    "source_trust": "mycelium ingest",
    "generated_by": "mycelium ingest",
    "verified_by": "mycelium verify",
    "verified_at": "mycelium promote",
    "grounding": "mycelium verify",
    "title": "human",
    "aliases": "human",
    "tags": "human",
    "collection": "human",
}
"""Who is allowed to write each contract field (spec 03 §3, anti-drift rule)."""


class FrontmatterError(ValueError):
    """Frontmatter could not be read, or carries an unusable identity."""


class Frontmatter(BaseModel):
    """The parsed frontmatter contract of one authored document.

    Absent fields are ``None`` (or empty), never invented. `properties` holds every
    key outside the contract, verbatim, so a round-trip through Mycelium OS never
    silently drops a vault's own metadata.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mycelium_id: Ulid | None = None
    title: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    collection: str | None = None
    origin: ProvenanceOrigin | None = None
    source: str | None = None
    source_trust: SourceTrust | None = None
    generated_by: str | None = None
    verified_by: str | None = None
    verified_at: date | None = None
    grounding: float | None = Field(default=None, ge=0.0, le=1.0)
    properties: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Non-contract keys, preserved verbatim and never machine-read.",
    )

    @model_validator(mode="after")
    def _reject_contract_keys_in_properties(self) -> Self:
        overlap = FIELD_OWNERS.keys() & self.properties.keys()
        if overlap:
            msg = f"contract fields must not be repeated in properties: {sorted(overlap)}"
            raise ValueError(msg)
        return self


class FrontmatterResult(BaseModel):
    """A parsed frontmatter block plus the body it was stripped from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    frontmatter: Frontmatter
    body: str
    body_line_offset: int = Field(
        ge=0, description="Source lines consumed by the frontmatter block, for src locators."
    )
    warnings: tuple[str, ...] = ()


def split_frontmatter(text: str) -> tuple[str | None, str, int]:
    """Split `text` into ``(yaml_block, body, body_line_offset)``.

    A frontmatter block is a ``---`` fence on the very first line, closed by the
    next ``---`` on its own line. Anything else — including a horizontal rule in
    the first line of prose — is body. Returns ``None`` for the block when the
    document has no frontmatter.

    A leading byte-order mark is skipped before that test. Windows editors emit
    UTF-8 with a BOM routinely, and without this the fence is not at position
    zero, so the whole block — identity included — compiles as prose
    ([BUG-0008](../../../docs/bugs/2026/08/BUG-0008-bom-hides-frontmatter.md)).
    The BOM is not returned with the body: it carries no content and
    `normalize_text` strips it from every digest anyway.
    """
    text = text.removeprefix(_BOM)
    if not text.startswith(DELIMITER):
        return None, text, 0
    lines = text.split("\n")
    if lines[0].strip() != DELIMITER:
        return None, text, 0
    for index in range(1, len(lines)):
        if lines[index].strip() == DELIMITER:
            block = "\n".join(lines[1:index])
            return block, "\n".join(lines[index + 1 :]), index + 1
    # An unterminated fence is not frontmatter; the document is all body.
    return None, text, 0


def _opens_a_mapping(block: str) -> bool:
    """Does this fenced block declare itself frontmatter?

    A document may legitimately open with a thematic break, so ``---`` alone
    proves nothing: ``---`` / ``> quote`` / ``---`` is a blockquote between two
    rules, and ``>`` happens to open a YAML block scalar. The discriminator is the
    first non-empty line — real frontmatter starts with a plain ``key:`` — and it
    is checked *before* YAML is parsed, so Markdown is never diagnosed as broken
    YAML (ADR-0006). An empty block is empty frontmatter.
    """
    for line in block.split("\n"):
        if line.strip():
            return _MAPPING_KEY.match(line) is not None
    return True


def _as_string_tuple(value: object, key: str, warnings: list[str]) -> tuple[str, ...]:
    """Coerce a scalar-or-list property into a tuple of strings, warning on junk."""
    if value is None:
        return ()
    items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, bool):
            # PyYAML reads YAML 1.1, where bare `no`/`on`/`y` are booleans. The
            # author's spelling is gone by the time we see it, so the value is
            # dropped with a warning that names the fix (ADR-0006).
            warnings.append(
                f"frontmatter '{key}': {item} came from an unquoted YAML boolean "
                "(no/yes/on/off); quote it to keep it as text"
            )
        elif isinstance(item, int | float):
            result.append(str(item))
        else:
            warnings.append(f"frontmatter '{key}': ignored non-scalar entry {item!r}")
    return tuple(result)


def _as_string(value: object, key: str, warnings: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        warnings.append(
            f"frontmatter '{key}': {value} came from an unquoted YAML boolean "
            "(no/yes/on/off); quote it to keep it as text"
        )
        return None
    if isinstance(value, int | float | date):
        return str(value)
    warnings.append(f"frontmatter '{key}': expected text, ignored {type(value).__name__}")
    return None


def _as_enum[E: (ProvenanceOrigin, SourceTrust)](
    value: object, key: str, enum: type[E], warnings: list[str]
) -> E | None:
    if value is None:
        return None
    try:
        return enum(str(value))
    except ValueError:
        allowed = ", ".join(member.value for member in enum)
        warnings.append(f"frontmatter '{key}': {value!r} is not one of ({allowed}); ignored")
        return None


def _as_date(value: object, key: str, warnings: list[str]) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        warnings.append(f"frontmatter '{key}': {value!r} is not an ISO date; ignored")
        return None


def _as_grounding(value: object, key: str, warnings: list[str]) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        warnings.append(f"frontmatter '{key}': {value!r} is not a number; ignored")
        return None
    if not 0.0 <= score <= 1.0:
        warnings.append(f"frontmatter '{key}': {score} is outside 0.0-1.0; ignored")
        return None
    return score


def _as_mycelium_id(value: object, *, present: bool) -> str | None:
    """Validate the pinned document identity — the one field that may not be guessed.

    A key that is present but empty is an author error, not an absent identity:
    minting a fresh ULID there would give one document two identities.
    """
    if value is None:
        if present:
            msg = "frontmatter 'mycelium_id' is present but empty; remove it or restore the ULID"
            raise FrontmatterError(msg)
        return None
    candidate = str(value)
    try:
        decode_ulid(candidate)
    except IdentityError as exc:
        msg = (
            f"frontmatter 'mycelium_id' is not a ULID: {candidate!r}. Identity is never "
            "re-minted for a document that claims one; fix or remove the field."
        )
        raise FrontmatterError(msg) from exc
    return candidate


_UNREPRESENTABLE: Final = object()
"""Sentinel for a property value no JSON document could carry."""


def _as_json_value(value: object) -> object:
    """Coerce a YAML value into something a JSON record can hold.

    Dates are the case that matters. YAML reads an unquoted `2026-08-29` as a
    `datetime.date`, and pydantic's `JsonValue` rejects it — so a property as
    ordinary as Obsidian's `created:` raised a validation error, the build
    quarantined the whole document, and its content left the index entirely.
    This project's own bug ledger disappeared from its own corpus that way
    (BUG-0012).

    Dates, times, and timestamps become their ISO 8601 spelling, which is what
    the author wrote before YAML typed it. Anything else with no JSON form is
    dropped with a warning, because D-022 promises to *preserve* a vault's
    properties, not to interpret them — and preserving nothing is still better
    than losing the document that carried them.
    """
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else _UNREPRESENTABLE
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, list | tuple):
        items = [_as_json_value(item) for item in value]
        return _UNREPRESENTABLE if any(item is _UNREPRESENTABLE for item in items) else items
    if isinstance(value, dict):
        pairs = {str(key): _as_json_value(item) for key, item in value.items()}
        return (
            _UNREPRESENTABLE if any(item is _UNREPRESENTABLE for item in pairs.values()) else pairs
        )
    return _UNREPRESENTABLE


def parse_frontmatter(text: str) -> FrontmatterResult:
    """Parse a document's frontmatter block and return it with the remaining body."""
    block, body, offset = split_frontmatter(text)
    if block is None:
        return FrontmatterResult(frontmatter=Frontmatter(), body=body, body_line_offset=offset)
    if not _opens_a_mapping(block):
        # Markdown between two thematic breaks, not a frontmatter block.
        return FrontmatterResult(frontmatter=Frontmatter(), body=text, body_line_offset=0)

    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        msg = f"frontmatter is not valid YAML: {exc}"
        raise FrontmatterError(msg) from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        # A fence whose contents are a scalar or a sequence is not frontmatter at
        # all: `---` / prose / `---` is two thematic breaks around a paragraph, and
        # CommonMark's reading is the right one. Compile it as body.
        return FrontmatterResult(frontmatter=Frontmatter(), body=text, body_line_offset=0)

    fields: dict[str, object] = {str(key): value for key, value in loaded.items()}
    warnings: list[str] = []
    properties: dict[str, JsonValue] = {}
    for key, value in fields.items():
        if key in FIELD_OWNERS:
            continue
        coerced = _as_json_value(value)
        if coerced is _UNREPRESENTABLE:
            warnings.append(f"{key}: dropped, the value has no JSON representation")
            continue
        properties[key] = coerced  # type: ignore[assignment]

    frontmatter = Frontmatter(
        mycelium_id=_as_mycelium_id(fields.get("mycelium_id"), present="mycelium_id" in fields),
        title=_as_string(fields.get("title"), "title", warnings),
        aliases=_as_string_tuple(fields.get("aliases"), "aliases", warnings),
        tags=_as_string_tuple(fields.get("tags"), "tags", warnings),
        collection=_as_string(fields.get("collection"), "collection", warnings),
        origin=_as_enum(fields.get("origin"), "origin", ProvenanceOrigin, warnings),
        source=_as_string(fields.get("source"), "source", warnings),
        source_trust=_as_enum(fields.get("source_trust"), "source_trust", SourceTrust, warnings),
        generated_by=_as_string(fields.get("generated_by"), "generated_by", warnings),
        verified_by=_as_string(fields.get("verified_by"), "verified_by", warnings),
        verified_at=_as_date(fields.get("verified_at"), "verified_at", warnings),
        grounding=_as_grounding(fields.get("grounding"), "grounding", warnings),
        properties=properties,
    )
    return FrontmatterResult(
        frontmatter=frontmatter,
        body=body,
        body_line_offset=offset,
        warnings=tuple(warnings),
    )
