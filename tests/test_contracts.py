# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The compatibility suite for the five stable contracts (roadmap 6.1, ADR-0114).

Architecture §10 names five things v1 may not change casually; spec 05 §5 asks that
they *"get compatibility tests in CI — a PR cannot silently break them"*. This file
is those tests. Each contract is projected to a canonical JSON document
(:mod:`mycelium.contracts`) and compared, section by section, with a committed
golden under `tests/fixtures/contracts/`.

A failure here is one of two things. Either a stable contract changed without
anyone meaning it to, which is the defect the suite exists to catch. Or it changed
on purpose — in which case `python tools/update_contract_goldens.py` re-blesses the
golden and the diff goes into the PR beside the RFC and the migration note the
change needs (`docs/compatibility.md`). Never edit a golden by hand.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from mycelium.build import build as run_build
from mycelium.chunking import estimate_tokens
from mycelium.contracts import (
    CONTRACTS,
    compare,
    contract,
    golden_name,
    project,
    read_golden,
    schema_shape,
)
from mycelium.embedding import PROVIDER_NONE, EmbedderUnavailableError, build_embedder
from mycelium.embedding.onnx import PROVIDER as LOCAL_ONNX
from mycelium.mcp import ErrorCode, McpToolError
from mycelium.mcp.errors import ERROR_FIELDS, error_payload_schema
from mycelium.mcp.schemas import OUTPUT_SCHEMAS
from mycelium.mcp.tools import (
    TOOL_SCHEMAS,
    handle_explain,
    handle_fetch,
    handle_neighbors,
    handle_search,
)
from mycelium.sdk.identity import parse_citation_uri
from mycelium.sdk.types import KirDocument, SnapshotManifest

GOLDENS = Path(__file__).parent / "fixtures" / "contracts"
HISTORY = GOLDENS / "history"

REBLESS = (
    "If this change is intended, it is a change to a stable contract: it needs an RFC "
    "(spec 06 §4) and a migration note in CHANGELOG.md, and "
    "`python tools/update_contract_goldens.py` re-blesses the golden so the diff is in the "
    "PR. If the shape is incompatible, bump the contract's version token first - the golden "
    "file is named after it. If it is not intended, a stable contract just changed silently, "
    "which is what this test exists to stop (docs/compatibility.md)."
)


# ---------------------------------------------------------------------------
# The gate: five projections, five goldens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [item.name for item in CONTRACTS])
def test_the_contract_matches_its_golden(name: str) -> None:
    """The whole of the compatibility gate for one contract, in one comparison."""
    observed = project(name)
    expected = read_golden(GOLDENS / golden_name(name))
    moved = compare(expected, observed)
    assert not moved, f"{name}: {', '.join(moved)} moved. {REBLESS}"


def test_the_goldens_on_disk_are_exactly_the_five_at_their_current_tokens() -> None:
    """A golden for a token no contract carries is a stale claim, and a missing one is
    a contract with no gate. Both fail here rather than passing vacuously."""
    present = {path.name for path in GOLDENS.glob("*.json")}
    assert present == {golden_name(item.name) for item in CONTRACTS}


def test_a_versioned_golden_is_named_for_its_token() -> None:
    """The file name is the version: an incompatible change bumps the token and
    renames the file, so the bump is in the diff and the old shape in history."""
    assert golden_name("kir") == "kir.v0.json"
    assert golden_name("manifest") == "manifest.v0.json"
    assert golden_name("plugin-api") == "plugin-api.v0.json"
    # Identity and the tool surface have no token by nature (docs/compatibility.md).
    assert golden_name("identity") == "identity.json"
    assert golden_name("mcp-tools") == "mcp-tools.json"
    for item in CONTRACTS:
        assert read_golden(GOLDENS / golden_name(item.name))["version"] == item.token()


def test_the_goldens_are_stored_reviewably() -> None:
    """A golden nobody can read in a diff is a hash, not a gate."""
    for path in GOLDENS.glob("*.json"):
        raw = path.read_bytes()
        assert b"\r" not in raw, path.name  # LF only, so the diff is the same everywhere
        assert raw.endswith(b"\n"), path.name
        text = raw.decode("utf-8")
        assert "\\u" not in text, path.name  # non-Latin text is readable, not escaped
        document = json.loads(text)
        assert text == json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_an_unknown_contract_is_refused_by_name() -> None:
    with pytest.raises(KeyError, match="identity, kir, manifest, mcp-tools, plugin-api"):
        contract("cli")


# ---------------------------------------------------------------------------
# The projection's own rules
# ---------------------------------------------------------------------------


def test_schema_shape_strips_prose_and_keeps_a_property_named_title() -> None:
    """A docstring edit must not be a contract event; a property called `title` is
    not a docstring."""
    schema = {
        "title": "Doc",
        "description": "prose",
        "$comment": "prose",
        "properties": {
            "title": {"type": "string", "description": "the title", "examples": ["x"]},
            "description": {"type": "string"},
        },
        "required": ["title"],
        "$defs": {"Kind": {"title": "Kind", "enum": ["a", "b"]}},
    }
    assert schema_shape(schema) == {
        "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
        "required": ["title"],
        "$defs": {"Kind": {"enum": ["a", "b"]}},
    }


def test_compare_names_the_sections_that_moved() -> None:
    before = {"contract": "kir", "schema": {"a": 1}, "node_kinds": ["x"]}
    after = {"contract": "kir", "schema": {"a": 2}, "node_kinds": ["x"], "extra": True}
    assert compare(before, after) == ("extra", "schema")
    assert compare(before, before) == ()


def test_identity_vectors_record_refusals_as_well_as_values() -> None:
    """What the grammar refuses is as much the contract as what it accepts."""
    vectors = project("identity")["vectors"]
    functions = {vector["function"] for vector in vectors}
    assert {"heading_slug", "citation_uri", "parse_citation_uri", "edge_id"} <= functions
    assert any("raises" in vector for vector in vectors)
    assert all(("output" in vector) != ("raises" in vector) for vector in vectors)


def test_the_kind_field_table_is_asked_of_the_record_not_read_from_it() -> None:
    """Spot checks of the behavioural table: a heading must carry a level and may
    carry nothing else; a paragraph carries no kind-specific field; `opaque` takes
    the four ADR-0034 gave it."""
    table = project("kir")["kind_fields"]
    assert table["heading"] == {"required": ["level"], "optional": []}
    assert table["paragraph"] == {"required": [], "optional": []}
    assert table["opaque"] == {
        "required": [],
        "optional": ["variant", "media_type", "blob", "note"],
    }


# ---------------------------------------------------------------------------
# Readers still accept what earlier releases wrote
# ---------------------------------------------------------------------------


def _preserved(fixture: Any, current: Any) -> bool:
    """Every value the fixture carries is still there after a round trip.

    Subset rather than equality: a reader that gained a defaulted field dumps one
    more key, and that is an additive change the promise allows. Losing or
    changing a key the fixture carried is what it forbids.
    """
    if isinstance(fixture, dict):
        return isinstance(current, dict) and all(
            key in current and _preserved(value, current[key]) for key, value in fixture.items()
        )
    if isinstance(fixture, list):
        return (
            isinstance(current, list)
            and len(fixture) == len(current)
            and all(_preserved(a, b) for a, b in zip(fixture, current, strict=True))
        )
    return bool(fixture == current)


def test_a_manifest_written_by_v0_5_0_still_loads() -> None:
    """Spec 05 §5: a newer Mycelium OS may refuse an older snapshot only by saying so.
    Within one token it does not refuse at all - the record written at the freeze
    loads, and nothing it said is lost."""
    text = (HISTORY / "v0.5.0" / "manifest.json").read_text(encoding="utf-8")
    manifest = SnapshotManifest.model_validate_json(text)
    assert manifest.schema_version == "mycelium/manifest/v0"
    assert _preserved(json.loads(text), manifest.model_dump(mode="json"))


def test_a_kir_document_written_by_v0_5_0_still_loads() -> None:
    """Architecture §10: connectors written for v1 keep working - and so does what
    they wrote. The fixture exercises headings, paragraphs, a table, code, callouts
    and an embed, so a field a later reader stopped accepting on any of those fails."""
    text = (HISTORY / "v0.5.0" / "kir.json").read_text(encoding="utf-8")
    document = KirDocument.model_validate_json(text)
    assert document.schema_version == "mycelium/kir/v0"
    assert {node.kind.value for node in document.nodes} >= {
        "heading",
        "paragraph",
        "table",
        "code_block",
        "callout",
        "embed",
    }
    assert _preserved(json.loads(text), document.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# The MCP output contracts hold for real payloads
# ---------------------------------------------------------------------------

DOC = """---
collection: core-docs
---

# Retry Policy

Failed deliveries retry with exponential backoff, up to five attempts.
See [[draft]] for the unreviewed notes.

## Limits

The ceiling is five attempts per webhook.
"""

CANDIDATE = """# Draft Notes

An unreviewed note about retry behaviour.
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for relative, text in {
        "knowledge/verified/retries.md": DOC,
        "knowledge/candidate/draft.md": CANDIDATE,
    }.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    run_build(tmp_path)
    return tmp_path


def _validate(tool: str, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(OUTPUT_SCHEMAS[tool]).validate(payload)


def test_every_tool_advertises_a_valid_output_schema() -> None:
    """Declared beside the input, so a client that validates results can; and a
    malformed schema is invisible until that client rejects the tool."""
    assert {tool["name"] for tool in TOOL_SCHEMAS} == set(OUTPUT_SCHEMAS)
    for tool in TOOL_SCHEMAS:
        assert tool["outputSchema"] is OUTPUT_SCHEMAS[tool["name"]]
        jsonschema.Draft202012Validator.check_schema(tool["outputSchema"])


def test_search_payloads_conform_in_every_shape_they_take(repo: Path) -> None:
    plain = handle_search(repo, {"query": "retry"})
    _validate("mycelium_search", plain)
    assert plain["results"]
    explained = handle_search(repo, {"query": "retry", "explain": True, "include_text": "snippet"})
    _validate("mycelium_search", explained)
    assert "explain" in explained
    trimmed = handle_search(repo, {"query": "retry", "k": 1, "include_text": "none"})
    _validate("mycelium_search", trimmed)
    # A budget that admits exactly the first result, so the truncated shape is real.
    assert len(plain["results"]) >= 2
    budget = estimate_tokens(str(plain["results"][0]["text"]))
    budgeted = handle_search(repo, {"query": "retry", "budget_tokens": budget})
    _validate("mycelium_search", budgeted)
    assert budgeted["truncated"] is True
    assert budgeted["omitted"]


def test_fetch_payloads_conform_including_the_stale_block(repo: Path) -> None:
    uri = str(handle_search(repo, {"query": "retry"})["results"][0]["uri"])
    for context in ("chunk", "section", "document"):
        fresh = handle_fetch(repo, {"uri": uri, "context": context})
        _validate("mycelium_fetch", fresh)
        assert fresh["stale"] is None
    # A citation whose lines no longer match is served with a stale block: the
    # block is part of the contract, so it is exercised rather than left null.
    parsed = parse_citation_uri(uri)
    assert parsed.lines is not None and parsed.digest is not None
    moved = uri.replace(f"lines={parsed.lines[0]}-{parsed.lines[1]}", "lines=900-901")
    stale = handle_fetch(repo, {"uri": moved})
    _validate("mycelium_fetch", stale)
    assert stale["stale"] is not None
    assert stale["stale"]["kind"] == "moved"
    rewritten = uri.replace(f"digest={parsed.digest}", "digest=000000000000")
    stale = handle_fetch(repo, {"uri": rewritten})
    _validate("mycelium_fetch", stale)
    assert stale["stale"]["kind"] == "rewritten"


def test_neighbors_and_explain_payloads_conform(repo: Path) -> None:
    walked = handle_neighbors(repo, {"uri": "knowledge/verified/retries.md"})
    _validate("mycelium_neighbors", walked)
    assert walked["neighbors"]
    explained = handle_explain(repo, {"query": "retry backoff nonesuchword"})
    _validate("mycelium_explain", explained)
    assert explained["terms"] and explained["candidates"]


def test_error_payloads_conform_and_carry_only_their_declared_fields(
    repo: Path, tmp_path: Path
) -> None:
    """The error result is pinned separately from the output schemas because a
    conformant client validates `structuredContent` only when `isError` is false.
    Every code the handlers raise is exercised, plus the one only the server does."""
    doc_id = parse_citation_uri(
        str(handle_search(repo, {"query": "retry"})["results"][0]["uri"])
    ).doc_id
    unbuilt = tmp_path / "unbuilt"
    unbuilt.mkdir()
    raised: list[McpToolError] = []
    for handler, arguments, root in (
        (handle_search, {"query": ""}, repo),
        (handle_search, {"query": "retry", "budget_tokens": 1}, repo),
        (handle_fetch, {"uri": f"mycelium://{doc_id}#nonesuch/0"}, repo),
        (handle_fetch, {"uri": "mycelium://01J1ZF8Q4R6XKQ3F0V9T8B2M7N#x/0"}, repo),
        (handle_search, {"query": "retry"}, unbuilt),
    ):
        with pytest.raises(McpToolError) as caught:
            handler(root, arguments)
        raised.append(caught.value)
    raised.append(McpToolError(ErrorCode.INTERNAL, "boom"))

    schema = error_payload_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    assert {error.code for error in raised} == set(ErrorCode)
    for error in raised:
        jsonschema.Draft202012Validator(schema).validate(error.payload())
        assert set(error.fields) <= set(ERROR_FIELDS.get(error.code, {}))
    gone = next(error for error in raised if error.code is ErrorCode.ANCHOR_GONE)
    assert set(gone.fields) == {"nearest", "path"}
    exceeded = next(error for error in raised if error.code is ErrorCode.BUDGET_EXCEEDED)
    assert set(exceeded.fields) == {"needed_tokens"}


def test_an_error_cannot_carry_a_field_its_code_does_not_declare() -> None:
    """The declaration is true by construction, not by convention."""
    with pytest.raises(TypeError, match="NOT_FOUND carries no field"):
        McpToolError(ErrorCode.NOT_FOUND, "x", nearest="mycelium://...")


# ---------------------------------------------------------------------------
# Decisions the freeze review took, pinned so that changing them is an act
# ---------------------------------------------------------------------------


def test_the_embedder_stays_outside_the_frozen_protocols_until_a_plugin_can_supply_one() -> None:
    """Spec 05 §4.1 lists `Embedder` among the plugin Protocols and ADR-0032 deferred
    reconciling it to the freeze. The review left it out (ADR-0114): a frozen
    protocol protects a third-party implementation across versions, and no entry
    point can supply an embedder - `[embedding] provider` resolves exactly two names.
    The day a third resolves, this test says the premise changed."""
    assert "Embedder" not in project("plugin-api")["protocols"]
    assert {LOCAL_ONNX, PROVIDER_NONE} == {"local-onnx", "none"}
    with pytest.raises(EmbedderUnavailableError, match="plugin surface"):
        build_embedder(provider="openai", model_id="text-embedding-3-small")


def test_the_frozen_protocols_are_the_four_a_plugin_can_register() -> None:
    """Connector and Parser through `mycelium.plugins`, Module through
    `mycelium.modules`, Synthesizer through `[synthesis] plugin`. Chunker, Extractor
    and Reranker are in the spec's sketch and in no code (ADR-0032, ADR-0073,
    ADR-0076): the freeze binds what exists."""
    api = project("plugin-api")
    assert set(api["protocols"]) == {"Connector", "Parser", "Synthesizer", "Module"}
    assert api["entry_point_groups"] == {
        "plugins": "mycelium.plugins",
        "modules": "mycelium.modules",
    }
    assert api["api_version"] == 0
