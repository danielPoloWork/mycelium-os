# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The five stable contracts, projected to what the compatibility suite compares.

Architecture §10 names five things v1 may not change casually — identity rules,
the KIR schema, the snapshot manifest schema, the MCP tool contracts and the plugin
protocols — and spec 05 §5 asked for *"compatibility tests in CI from Phase 1 — a
PR cannot silently break them"*. Until roadmap 6.1 nothing held any of the five
to a committed statement of its shape: gate G6 pins a whole build and is
re-blessed at every intended compiler change, the MCP tests pin the four tool
*names*, and the schema tests pin the version *tags*. A field could join the
manifest, a Protocol member could change its signature, or a slug rule could move
every anchor in every corpus, and the only test that noticed would be one whose
re-bless is routine.

This module is the statement. Each contract has a **projection**: a pure function
from the code as it is to a canonical JSON document of the facts a consumer can
observe, and nothing else. A golden copy of each projection is committed under
``tests/fixtures/contracts/`` and `tests/test_contracts.py` compares the two; a
difference is a contract change, and the diff is the review artifact
(ADR-0114). Like :mod:`mycelium.determinism`, the module is shared by the gate and
by the re-bless tool (`tools/update_contract_goldens.py`), so a golden can never
be produced by different code than the code that checks it.

**Shape, not prose.** A projection of a JSON Schema strips ``description``,
``title``, ``examples`` and ``$comment`` (:func:`schema_shape`), because a
docstring edit is not a contract change and a gate that fires on one selects for
being ignored (ADR-0053). Everything that decides what a consumer may send or
must accept — types, required keys, enums, patterns, bounds, defaults — is kept.

**One golden per contract, named for its version token where the contract has
one.** ``kir.v0.json`` and ``manifest.v0.json`` carry the record's
``schema_version``; ``plugin-api.v0.json`` carries
:data:`~mycelium.sdk.protocols.MYCELIUM_API_VERSION`. Identity and the MCP tools
have no token, by nature rather than by omission: a citation URI in an agent's
transcript carries no version and must resolve in every later release, so the
identity rules are append-only for good, and the tool surface is versioned by the
package that serves it.
"""

import dataclasses
import inspect
import json
import math
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Final, TypeAliasType, Union, get_args, get_origin

from pydantic import ValidationError

from mycelium.ingest.registry import ENTRY_POINT_GROUP
from mycelium.mcp.errors import ERROR_FIELDS, ErrorCode, error_payload_schema
from mycelium.mcp.schemas import NOTICE
from mycelium.mcp.server import SUPPORTED_PROTOCOL_VERSIONS
from mycelium.mcp.tools import TOOL_SCHEMAS
from mycelium.modules import MODULE_ENTRY_POINT_GROUP
from mycelium.sdk import identity, protocols
from mycelium.sdk import types as record_types
from mycelium.sdk.identity import (
    CITATION_SCHEME,
    DIGEST_LENGTH,
    EMPTY_SLUG,
    MIN_DIGEST_LENGTH,
    ULID_ALPHABET,
)
from mycelium.sdk.protocols import (
    MYCELIUM_API_VERSION,
    Blob,
    Connector,
    EvidenceDocument,
    Module,
    Parser,
    PluginMeta,
    Synthesis,
    SynthesisContext,
    Synthesizer,
)
from mycelium.sdk.schema import (
    RECORD_MODELS,
    SNAPSHOT_ARTIFACT_CLASSES,
    constraint_pattern,
    record_json_schema,
    record_schema_version,
)
from mycelium.sdk.types import (
    Anchor,
    JudgedAnchor,
    KirDocument,
    KirNode,
    NodeKind,
    OpaqueDisposition,
    Sha256Digest,
    SnapshotManifest,
    Ulid,
)

__all__ = [
    "CONTRACTS",
    "Contract",
    "compare",
    "contract",
    "golden_name",
    "project",
    "read_golden",
    "schema_shape",
    "write_golden",
]


@dataclass(frozen=True, slots=True)
class Contract:
    """One stable contract: where the spec fixes it, and how it is projected."""

    name: str
    """The golden's stem: ``identity``, ``kir``, ``manifest``, ``mcp-tools``, ``plugin-api``."""

    authority: str
    """The spec section that makes this a contract (architecture §10's list)."""

    projection: Callable[[], dict[str, Any]]
    """The facts a consumer can observe, as a JSON-ready mapping of named sections."""

    token: Callable[[], str | None]
    """The contract's version token, or ``None`` where it has none by nature."""


# ---------------------------------------------------------------------------
# JSON Schema shape
# ---------------------------------------------------------------------------

_PROSE: Final = frozenset({"description", "title", "examples", "$comment"})
"""Schema keywords that describe a schema to a reader and constrain nothing."""

_SCHEMA_MAPS: Final = frozenset(
    {"properties", "$defs", "definitions", "patternProperties", "dependentSchemas"}
)
"""Keywords whose value maps *names* to schemas — a property named ``title`` lives
under one of these, and is a property, not prose."""


def schema_shape(schema: dict[str, Any]) -> dict[str, Any]:
    """A JSON Schema with its prose removed and every constraint kept.

    ``description``, ``title``, ``examples`` and ``$comment`` go, recursively, at
    every level that is a schema. The values of ``properties`` and its siblings
    are treated as maps whose keys are names, so a property that happens to be
    called ``title`` survives with its own schema intact.
    """

    def _shape(node: Any, *, names: bool) -> Any:
        if isinstance(node, dict):
            if names:
                return {key: _shape(value, names=False) for key, value in node.items()}
            return {
                key: _shape(value, names=key in _SCHEMA_MAPS)
                for key, value in node.items()
                if key not in _PROSE
            }
        if isinstance(node, list):
            return [_shape(item, names=False) for item in node]
        return node

    shaped: dict[str, Any] = _shape(schema, names=False)
    return shaped


# ---------------------------------------------------------------------------
# 1. Identity rules (spec 03 §2)
# ---------------------------------------------------------------------------

_ULID_A: Final = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
_ULID_DERIVED: Final = "0000000000FF1H2KXKN39Z50MN"
"""``derived_ulid("knowledge/architecture.md")`` — a literal, so the vector that
asks :func:`~mycelium.sdk.identity.is_derived_ulid` about it does not depend on
the vector that mints it."""
_DIGEST_A: Final = "sha256:" + "6f2a" * 16

_IDENTITY_FUNCTIONS: Final[Mapping[str, Callable[..., object]]] = {
    name: getattr(identity, name)
    for name in (
        "normalize_text",
        "canonical_json",
        "digest_bytes",
        "digest_text",
        "digest_json",
        "encode_ulid",
        "decode_ulid",
        "ulid_timestamp",
        "derived_ulid",
        "is_derived_ulid",
        "heading_slug",
        "anchor",
        "parse_anchor",
        "citation_uri",
        "parse_citation_uri",
        "doc_ref",
        "symbol_id",
        "entity_ref",
        "edge_id",
    )
}

_IDENTITY_VECTORS: Final[tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...]] = (
    # Normalization: BOM, CRLF, trailing whitespace, trailing blank lines, NFC.
    ("normalize_text", ("﻿alpha  \r\nbeta\t\r\n\r\n",), {}),
    ("normalize_text", ("é",), {}),
    ("normalize_text", ("\n\nlead\n",), {}),
    # Content identity: two spellings of one text digest alike.
    ("digest_text", ("hello\r\n",), {}),
    ("digest_text", ("hello\n",), {}),
    ("digest_text", ("café",), {}),
    ("digest_text", ("café",), {}),
    ("digest_bytes", (b"",), {}),
    ("digest_bytes", (b"\r\nabc\r\n",), {}),
    ("digest_json", ({"b": 1, "a": [1, 2.0, "x"]},), {}),
    ("digest_json", ({"a": [1, 2, "x"], "b": 1.0},), {}),
    ("canonical_json", ({"z": 1, "a": {"é": 2.5, "n": None, "t": True, "f": 3.0}},), {}),
    ("canonical_json", (float("inf"),), {}),
    # ULIDs: the alphabet, both range ends, the 128-bit cap, the invalid letter.
    ("encode_ulid", (0, bytes(10)), {}),
    ("encode_ulid", ((1 << 48) - 1, b"\xff" * 10), {}),
    ("encode_ulid", (1_690_000_000_000, bytes(range(10))), {}),
    ("encode_ulid", (1 << 48, bytes(10)), {}),
    ("decode_ulid", (_ULID_A,), {}),
    ("decode_ulid", ("7ZZZZZZZZZZZZZZZZZZZZZZZZZ",), {}),
    ("decode_ulid", ("8ZZZZZZZZZZZZZZZZZZZZZZZZZ",), {}),
    ("decode_ulid", ("01J1ZC8Q4R6XKQ3F0V9T8B2M7I",), {}),
    ("ulid_timestamp", (_ULID_A,), {}),
    # Derived identity: a function of the normalized name, timestamp zero.
    ("derived_ulid", ("knowledge/architecture.md",), {}),
    ("derived_ulid", ("docs/Ünicode.md",), {}),
    ("derived_ulid", ("docs/Ünicode.md",), {}),
    ("is_derived_ulid", (_ULID_DERIVED,), {}),
    ("is_derived_ulid", (_ULID_A,), {}),
    ("is_derived_ulid", ("not a ulid",), {}),
    # Slugs: fold, collapse, keep every script, name the empty case.
    ("heading_slug", ("Event Bus",), {}),
    ("heading_slug", ("  Retry Policy — v2!  ",), {}),
    ("heading_slug", ("設計",), {}),
    ("heading_slug", ("ﬁle names",), {}),
    ("heading_slug", ("---",), {}),
    ("heading_slug", ("C++ & C#",), {}),
    ("heading_slug", ("2024",), {}),
    # Anchors: the grammar, and what it refuses.
    ("anchor", ("architecture.md", ["event-bus"], 2), {}),
    ("anchor", ("docs/a.md", ["setup", "install"], 0), {}),
    ("anchor", ("readme.md", [], 3), {}),
    ("anchor", ("a#b.md", [], 0), {}),
    ("anchor", ("a.md", ["x/y"], 0), {}),
    ("anchor", ("a.md", [], -1), {}),
    ("parse_anchor", ("architecture.md#event-bus/2",), {}),
    ("parse_anchor", ("docs/a.md#2024/0",), {}),
    ("parse_anchor", ("readme.md#/3",), {}),
    ("parse_anchor", ("a.md#x/01",), {}),
    ("parse_anchor", ("nohash",), {}),
    # Citation URIs: the public form, both queries, the lenient read (ADR-0089).
    ("citation_uri", (_ULID_A, ["event-bus"], 2), {}),
    ("citation_uri", (_ULID_A, ["retries"], 0), {"lines": (88, 141)}),
    ("citation_uri", (_ULID_A, ["a", "b"], 1), {"lines": (3, 9), "digest": _DIGEST_A}),
    ("citation_uri", (_ULID_A, [], 0), {"digest": "6F2A6F2A6F2A6F2A"}),
    ("citation_uri", (_ULID_A, [], 0), {"digest": "abc"}),
    ("citation_uri", ("not-a-ulid", [], 0), {}),
    ("citation_uri", (_ULID_A, [], 0), {"lines": (9, 1)}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#event-bus/2",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#retries/0?lines=88-141",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#a/b/1?lines=3-9&digest=6f2a6f2a6f2a",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#x/1?future=yes&lines=1-2",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#x/1?digest=zz",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#x/1?digest={_DIGEST_A}",), {}),
    ("parse_citation_uri", (f"mycelium://{_ULID_A}#x/1?lines=9-1",), {}),
    ("parse_citation_uri", ("mycelium://nope#x/1",), {}),
    ("parse_citation_uri", (f"https://{_ULID_A}#x/1",), {}),
    # Reference forms and the one content-derived identity.
    ("doc_ref", ("knowledge/a.md",), {}),
    ("symbol_id", ("Python", "RetryPolicy.delay"), {}),
    ("symbol_id", ("cli", "uv tool install"), {}),
    ("entity_ref", ("event-bus",), {}),
    ("edge_id", ("doc:a.md", "doc:b.md", "links_to", _DIGEST_A), {}),
    ("edge_id", ("doc:b.md", "doc:a.md", "links_to", _DIGEST_A), {}),
)
"""Fixed inputs whose outputs *are* the identity rules, as far as a test can hold them.

Each is written to exercise one clause of spec 03 §§1-2 — a normalization step, a
grammar boundary, a refusal — so that a diff in the golden names the clause that
moved. The list grows when a rule grows (roadmap 5.17 added ``digest=``); an
existing vector's output never changes without a MAJOR release."""


def _jsonable(value: object) -> Any:
    """Render a Python value the way the golden stores it: readable and stable."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        # `inf` and `nan` are not JSON; Python's encoder writes them anyway, and a
        # golden a strict parser refuses is not a golden.
        return value if math.isfinite(value) else {"float": repr(value)}
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return repr(value)


def _identity_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    for name, args, kwargs in _IDENTITY_VECTORS:
        entry: dict[str, Any] = {"function": name, "args": _jsonable(args)}
        if kwargs:
            entry["kwargs"] = _jsonable(kwargs)
        try:
            entry["output"] = _jsonable(_IDENTITY_FUNCTIONS[name](*args, **kwargs))
        except identity.IdentityError as error:
            entry["raises"] = type(error).__name__
        vectors.append(entry)
    return vectors


def _project_identity() -> dict[str, Any]:
    return {
        "constants": {
            "CITATION_SCHEME": CITATION_SCHEME,
            "DIGEST_LENGTH": DIGEST_LENGTH,
            "MIN_DIGEST_LENGTH": MIN_DIGEST_LENGTH,
            "EMPTY_SLUG": EMPTY_SLUG,
            "ULID_ALPHABET": ULID_ALPHABET,
        },
        "patterns": {
            "Ulid": constraint_pattern(Ulid),
            "Sha256Digest": constraint_pattern(Sha256Digest),
            "Anchor": constraint_pattern(Anchor),
            "JudgedAnchor": constraint_pattern(JudgedAnchor),
        },
        "conventions": [
            'bytes arguments and outputs are written as {"hex": ...}',
            'a vector that raises records the exception type under "raises"',
            "datetimes are RFC 3339 UTC",
        ],
        "vectors": _identity_vectors(),
    }


# ---------------------------------------------------------------------------
# 2. KIR schema (spec 03 §4)
# ---------------------------------------------------------------------------

_KIND_SPECIFIC_SAMPLES: Final[Mapping[str, Any]] = {
    "level": 1,
    "lang": "python",
    "variant": "note",
    "title": "a title",
    "target": "a target",
    "media_type": "text/plain",
    "blob": _DIGEST_A,
    "note": "a note",
}
"""One acceptable value per kind-specific field, to ask the record which kinds take it."""


def _node(kind: NodeKind, **fields: Any) -> bool:
    try:
        KirNode(id="n", kind=kind, ord=0, **fields)
    except ValidationError:
        return False
    return True


def _kind_fields() -> dict[str, dict[str, list[str]]]:
    """Which optional fields each kind may carry, and which it must — asked, not read.

    The table lives in :mod:`mycelium.sdk.types` as a private constant; reading it
    would pin the constant, and what the contract promises is the *behaviour* — a
    consumer constructs a node and it is accepted or refused. So every kind is
    tried with every field, one at a time, and the answer is recorded.
    """
    table: dict[str, dict[str, list[str]]] = {}
    for kind in NodeKind:
        required = [
            name
            for name, sample in _KIND_SPECIFIC_SAMPLES.items()
            if _node(kind, **{name: sample}) and not _node(kind)
        ]
        base = {name: _KIND_SPECIFIC_SAMPLES[name] for name in required}
        allowed = [
            name
            for name, sample in _KIND_SPECIFIC_SAMPLES.items()
            if name not in required and _node(kind, **base, **{name: sample})
        ]
        table[kind.value] = {"required": required, "optional": allowed}
    return table


def _project_kir() -> dict[str, Any]:
    return {
        "schema": schema_shape(record_json_schema(KirDocument)),
        "node_kinds": [kind.value for kind in NodeKind],
        "kind_fields": _kind_fields(),
        "opaque_dispositions": [item.value for item in OpaqueDisposition],
    }


# ---------------------------------------------------------------------------
# 3. Snapshot manifest schema (spec 03 §7)
# ---------------------------------------------------------------------------


def _project_manifest() -> dict[str, Any]:
    return {
        "schema": schema_shape(record_json_schema(SnapshotManifest)),
        "artifact_classes": list(SNAPSHOT_ARTIFACT_CLASSES),
        "artifact_versions": {
            name: record_schema_version(RECORD_MODELS[name]) for name in SNAPSHOT_ARTIFACT_CLASSES
        },
    }


# ---------------------------------------------------------------------------
# 4. MCP tool contracts (spec 05 §3)
# ---------------------------------------------------------------------------


def _project_mcp_tools() -> dict[str, Any]:
    return {
        "protocol_versions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "notice": NOTICE,
        "errors": {
            "codes": [code.value for code in ErrorCode],
            "fields": {
                code.value: {name: schema_shape(field) for name, field in fields.items()}
                for code, fields in ERROR_FIELDS.items()
            },
            "payload": schema_shape(error_payload_schema()),
        },
        "tools": {
            tool["name"]: {
                "input": schema_shape(tool["inputSchema"]),
                "output": schema_shape(tool["outputSchema"]),
            }
            for tool in TOOL_SCHEMAS
        },
    }


# ---------------------------------------------------------------------------
# 5. Plugin protocols (spec 05 §4)
# ---------------------------------------------------------------------------

_PROTOCOLS: Final = (Connector, Parser, Synthesizer, Module)
_TRANSPORTS: Final = (PluginMeta, Blob, EvidenceDocument, SynthesisContext, Synthesis)


def _annotation(annotation: object) -> str:
    """Spell a type the same way on every supported Python.

    Qualified names only — ``PurePosixPath``, never ``pathlib.PurePosixPath`` —
    because a class's module is an implementation detail of the standard library
    that moved between 3.12 and 3.13, and the golden must not.
    """
    if isinstance(annotation, str):
        return annotation
    if annotation is None or annotation is type(None):
        return "None"
    if annotation is Ellipsis:
        return "..."
    if isinstance(annotation, TypeAliasType):
        return annotation.__name__
    origin = get_origin(annotation)
    if origin is not None:
        args = ", ".join(_annotation(item) for item in get_args(annotation))
        if origin is types.UnionType or origin is Union:
            return " | ".join(_annotation(item) for item in get_args(annotation))
        return f"{_annotation(origin)}[{args}]"
    if isinstance(annotation, type):
        return annotation.__qualname__
    return repr(annotation)


def _signature(function: Callable[..., object]) -> dict[str, Any]:
    signature = inspect.signature(function)
    parameters = []
    for parameter in signature.parameters.values():
        if parameter.name == "self":
            continue
        entry: dict[str, Any] = {"name": parameter.name, "kind": parameter.kind.name}
        if parameter.annotation is not inspect.Parameter.empty:
            entry["annotation"] = _annotation(parameter.annotation)
        if parameter.default is not inspect.Parameter.empty:
            entry["default"] = repr(parameter.default)
        parameters.append(entry)
    returns = signature.return_annotation
    return {
        "parameters": parameters,
        "returns": None if returns is inspect.Signature.empty else _annotation(returns),
    }


def _protocol(proto: type) -> dict[str, Any]:
    attributes = {
        name: _annotation(annotation) for name, annotation in inspect.get_annotations(proto).items()
    }
    methods = {
        name: _signature(member)
        for name, member in vars(proto).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }
    return {"attributes": attributes, "methods": methods}


def _transport(cls: type) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        entry: dict[str, Any] = {"type": _annotation(field.type)}
        if field.default_factory is not dataclasses.MISSING:
            entry["default"] = "<factory>"
        elif field.default is not dataclasses.MISSING:
            entry["default"] = repr(field.default)
        fields[field.name] = entry
    return fields


def _project_plugin_api() -> dict[str, Any]:
    return {
        "api_version": MYCELIUM_API_VERSION,
        "entry_point_groups": {"plugins": ENTRY_POINT_GROUP, "modules": MODULE_ENTRY_POINT_GROUP},
        "protocols": {proto.__name__: _protocol(proto) for proto in _PROTOCOLS},
        "transports": {cls.__name__: _transport(cls) for cls in _TRANSPORTS},
        "exports": {
            "mycelium.sdk.identity": sorted(identity.__all__),
            "mycelium.sdk.protocols": sorted(protocols.__all__),
            "mycelium.sdk.types": sorted(record_types.__all__),
        },
    }


# ---------------------------------------------------------------------------
# The register, and the golden files
# ---------------------------------------------------------------------------


def _record_token(model: type[KirDocument] | type[SnapshotManifest]) -> Callable[[], str]:
    return lambda: record_schema_version(model).rsplit("/", 1)[-1]


CONTRACTS: Final[tuple[Contract, ...]] = (
    Contract(
        name="identity",
        authority="spec 03 §2 — identity rules",
        projection=_project_identity,
        token=lambda: None,
    ),
    Contract(
        name="kir",
        authority="spec 03 §4 — KIR schema",
        projection=_project_kir,
        token=_record_token(KirDocument),
    ),
    Contract(
        name="manifest",
        authority="spec 03 §7 — snapshot manifest schema",
        projection=_project_manifest,
        token=_record_token(SnapshotManifest),
    ),
    Contract(
        name="mcp-tools",
        authority="spec 05 §3 — MCP tool contracts",
        projection=_project_mcp_tools,
        token=lambda: None,
    ),
    Contract(
        name="plugin-api",
        authority="spec 05 §4 — plugin protocols",
        projection=_project_plugin_api,
        token=lambda: f"v{MYCELIUM_API_VERSION}",
    ),
)
"""Architecture §10's five, in its order."""


def contract(name: str) -> Contract:
    """The contract called `name`, or a :class:`KeyError` naming the five."""
    for item in CONTRACTS:
        if item.name == name:
            return item
    msg = f"no contract {name!r}; the five are {', '.join(item.name for item in CONTRACTS)}"
    raise KeyError(msg)


def golden_name(name: str) -> str:
    """The golden's file name: ``<contract>.<token>.json``, or ``<contract>.json``.

    A contract with a version token is named for it, so an incompatible change —
    the kind that bumps the token — renames the file and the rename is in the
    diff, while a token-less contract's golden simply changes in place.
    """
    token = contract(name).token()
    return f"{name}.{token}.json" if token else f"{name}.json"


def project(name: str) -> dict[str, Any]:
    """The full golden document for one contract, as the code stands now."""
    item = contract(name)
    return {
        "contract": item.name,
        "authority": item.authority,
        "version": item.token(),
        **item.projection(),
    }


def write_golden(path: Path, document: Mapping[str, Any]) -> None:
    """Write a golden: sorted keys, two-space indent, LF, trailing newline — diffable."""
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_golden(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def compare(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> tuple[str, ...]:
    """The top-level sections on which two golden documents disagree, sorted.

    Section-wise rather than whole-document, so a failing gate says *what* moved
    — ``kind_fields`` and not ``kir`` — which is the difference between a
    review and a re-bless.
    """
    return tuple(
        sorted(
            section
            for section in set(expected) | set(observed)
            if expected.get(section) != observed.get(section)
        )
    )
