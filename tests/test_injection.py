# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Injection resistance as a tested property (spec 04 §6, D-017; roadmap 3.7, then 6.3).

Spec 04 §6 states the doctrine in three parts, and only the first is a promise about
*words*: retrieved content is data; it is returned inside a typed field, never
concatenated into tool descriptions or system-level fields; and Mycelium itself
executes nothing it finds in a document.

The judged `injection` slice checks that the doctrine is *findable*. That is not the
same as resisting attack, so this file checks the property directly against the
**injection corpus** under `tests/fixtures/injection/` — twenty-three authored
documents, each carrying one attack class, declared in `attacks.json` with the payload
it carries, the word a query finds it by, the fields the payload may legitimately
appear in, and whether the build indexes or quarantines it. The corpus is a fixture
and not part of the judged evaluation corpus (ADR-0119): an attack document in the
documentation corpus moves every retrieval number for no gain, and nDCG cannot say
"returned verbatim".

What the suite asserts, per document: the payload comes back **verbatim** and **only**
inside the fields the inventory allows; the response envelope is ours whatever the
document says; a channel a reader cannot see is not indexed; a document that would cost
the build unbounded time is quarantined by name; and identity, status and the graph are
facts about the corpus that no document can forge. Two residuals are declared rather
than discovered — text a renderer would hide, and a credential in an *authored* file —
and a test pins that list, so a third is a decision.
"""

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from mycelium.build import build
from mycelium.build.publish import read_current
from mycelium.ingest import Registry, ingest_source
from mycelium.mcp.errors import ErrorCode, McpToolError
from mycelium.mcp.tools import NOTICE, handle_fetch, handle_neighbors, handle_search
from mycelium.sdk.identity import parse_citation_uri
from mycelium.sdk.types import EdgeStatus, SnapshotManifest, VerificationStatus
from mycelium.store import STORE_DIRNAME, SqliteStore

pytestmark = [
    pytest.mark.boundary("B6"),
    pytest.mark.boundary("B4"),
    pytest.mark.boundary("B11"),
]
"""The threat-model boundaries these tests hold (docs/security/threat-model.md §4)."""

CORPUS = Path(__file__).parent / "fixtures" / "injection"
INVENTORY: list[dict[str, Any]] = json.loads((CORPUS / "attacks.json").read_text(encoding="utf-8"))[
    "documents"
]
BY_ATTACK = {
    entry["attack"] if entry["attack"] != "duplicate-identity" else entry["marker"]: entry
    for entry in INVENTORY
}

BUILD_BUDGET_S = 30.0
"""The whole corpus, compiled, with its three refusals. Generous by an order of
magnitude: the point is that a refusal stays a refusal rather than a stall."""

SERVED = [entry for entry in INVENTORY if entry["served"]]
NOT_SERVED = [entry for entry in INVENTORY if not entry["served"] and entry["outcome"] == "indexed"]
QUARANTINED = [entry for entry in INVENTORY if entry["outcome"] == "quarantined"]

DOC_ID = "01J1ZD8Q4R6XKQ3F0V9T8B2M7N"
SHARED_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
"""The identity two corpus documents both pin (`make_corpus.py`)."""


@dataclass(frozen=True, slots=True)
class Built:
    root: Path
    manifest: SnapshotManifest
    elapsed_s: float


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Built:
    """A private copy of the corpus, compiled once — the committed files are never built."""
    root = tmp_path_factory.mktemp("injection-corpus")
    shutil.copytree(CORPUS / "knowledge", root / "knowledge")
    started = time.perf_counter()
    result = build(root)
    return Built(root=root, manifest=result.manifest, elapsed_s=time.perf_counter() - started)


def _flatten(value: Any) -> str:
    """Every string inside a JSON-ready value, joined, with no escaping in the way."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten(item)}" for key, item in value.items())
    if isinstance(value, list | tuple):
        return " ".join(_flatten(item) for item in value)
    return "" if value is None else str(value)


def _results_for(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    return [result for result in payload["results"] if result["path"] == path]


# ---------------------------------------------------------------------------
# The corpus is whole, and the build treats it as declared
# ---------------------------------------------------------------------------


def test_the_corpus_is_complete() -> None:
    """Every file is declared and every declaration has a file — the rule the hostile
    ingestion suite applies, because a fixture nobody declared is a fixture nobody checks."""
    on_disk = {path.relative_to(CORPUS).as_posix() for path in CORPUS.rglob("*.md")}
    declared = {entry["path"] for entry in INVENTORY}
    assert on_disk == declared
    for entry in INVENTORY:
        assert set(entry) >= {
            "attack",
            "vector",
            "marker",
            "payload",
            "served",
            "fields",
            "outcome",
        }
        text = (CORPUS / entry["path"]).read_text(encoding="utf-8")
        assert entry["payload"] in text, entry["attack"]
    markers = [entry["marker"] for entry in INVENTORY]
    assert len(set(markers)) == len(markers)


def test_the_build_finishes_inside_the_budget_and_refuses_exactly_the_declared(
    built: Built,
) -> None:
    """Three documents exist to cost the build unbounded time — an alias bomb, an
    emphasis run, a duplicate identity — and each is refused by name, quickly."""
    assert built.elapsed_s < BUILD_BUDGET_S, built.elapsed_s
    assert built.manifest.counts.quarantined == len(QUARANTINED)
    assert built.manifest.counts.documents == len(INVENTORY) - len(QUARANTINED)
    for entry in QUARANTINED:
        assert any(entry["path"] in warning for warning in built.manifest.warnings), entry["path"]
    # Typed refusals: the reason names the contract that refused, never the interpreter.
    assert not any("RecursionError" in warning for warning in built.manifest.warnings)


def test_a_refused_document_is_absent_from_the_store(built: Built) -> None:
    with SqliteStore.open(built.root, read_only=True) as store:
        for entry in QUARANTINED:
            assert store.get_document_by_path(entry["path"]) is None, entry["path"]


# ---------------------------------------------------------------------------
# Served payloads: verbatim, typed, labelled — and nowhere else
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", SERVED, ids=[entry["attack"] for entry in SERVED])
def test_a_served_payload_is_returned_verbatim_and_only_inside_its_typed_fields(
    built: Built, entry: dict[str, Any]
) -> None:
    payload = handle_search(built.root, {"query": entry["marker"]})
    assert payload["notice"] == NOTICE
    mine = _results_for(payload, entry["path"])
    assert mine, f"{entry['attack']}: the corpus is indexed, so the query must find it"
    allowed = set(entry["fields"])
    assert any(
        entry["payload"] in _flatten([result[field] for field in allowed]) for result in mine
    ), f"{entry['attack']}: the payload must come back verbatim, inside {sorted(allowed)}"
    for result in payload["results"]:
        for key, value in result.items():
            if key in allowed or key in {"uri", "path"}:
                continue
            assert entry["payload"] not in _flatten(value), (
                f"{entry['attack']}: leaked into {key!r}"
            )
    envelope = {key: value for key, value in payload.items() if key != "results"}
    assert entry["payload"] not in _flatten(envelope), (
        f"{entry['attack']}: leaked into the envelope"
    )


@pytest.mark.parametrize("entry", SERVED[:4], ids=[entry["attack"] for entry in SERVED[:4]])
def test_fetch_serves_the_attack_with_the_lane_it_came_from(
    built: Built, entry: dict[str, Any]
) -> None:
    """Quoting the attack is correct: the agent asked what the corpus says. What the
    agent is also told is where it came from, so it can weigh it."""
    uri = str(
        _results_for(handle_search(built.root, {"query": entry["marker"]}), entry["path"])[0]["uri"]
    )
    fetched = handle_fetch(built.root, {"uri": uri})
    assert fetched["notice"] == NOTICE
    assert fetched["trust_class"] == "authored"
    assert fetched["verification_status"] == "candidate"
    assert entry["payload"] in _flatten([item["text"] for item in fetched["content"]])


@pytest.mark.parametrize("entry", NOT_SERVED, ids=[entry["attack"] for entry in NOT_SERVED])
def test_a_channel_a_reader_cannot_see_is_not_indexed(built: Built, entry: dict[str, Any]) -> None:
    """An HTML comment, a link's title attribute, a frontmatter claim, a pinned id:
    none of them is prose, so none of them is evidence a query can surface."""
    with SqliteStore.open(built.root, read_only=True) as store:
        document = store.get_document_by_path(entry["path"])
        assert document is not None, entry["path"]
        for chunk in store.chunks_of(document.doc_id):
            assert entry["payload"] not in chunk.text, entry["attack"]
    payload = handle_search(built.root, {"query": entry["marker"]})
    assert entry["payload"] not in _flatten(payload), entry["attack"]


# ---------------------------------------------------------------------------
# The envelope, identity, status and the graph are ours
# ---------------------------------------------------------------------------


def test_the_envelope_is_ours_whatever_the_document_says(built: Built) -> None:
    """A document that imitates the response — a notice, a snapshot id, an isError flag —
    is quoted inside `text`; the envelope around it is minted by the server."""
    entry = BY_ATTACK["envelope-spoof"]
    payload = handle_search(built.root, {"query": entry["marker"]})
    assert payload["notice"] == NOTICE
    assert payload["snapshot_id"] == read_current(built.root / STORE_DIRNAME)
    assert "isError" not in payload
    assert set(payload) == {"snapshot_id", "results", "truncated", "omitted", "notice"}
    assert entry["payload"] in _flatten(
        [result["text"] for result in _results_for(payload, entry["path"])]
    )


def test_a_citation_written_into_content_is_text_and_not_a_citation(built: Built) -> None:
    """A `mycelium://` URI in a document names nothing this snapshot holds, and every URI
    the server returns is minted from a document that exists."""
    entry = BY_ATTACK["fake-citation"]
    with pytest.raises(McpToolError) as caught:
        handle_fetch(built.root, {"uri": entry["payload"]})
    assert caught.value.code is ErrorCode.NOT_FOUND
    payload = handle_search(built.root, {"query": entry["marker"]})
    with SqliteStore.open(built.root, read_only=True) as store:
        for result in payload["results"]:
            assert store.get_document(parse_citation_uri(str(result["uri"])).doc_id) is not None


def test_a_duplicate_identity_is_refused_not_merged(built: Built) -> None:
    """Two documents pinning one `mycelium_id`: the first claim in path order wins and
    the second is quarantined by name, so a citation into the id has one referent."""
    first, second = BY_ATTACK["meerkat"], BY_ATTACK["numbat"]
    with SqliteStore.open(built.root, read_only=True) as store:
        kept = store.get_document_by_path(first["path"])
        assert kept is not None and kept.doc_id == SHARED_ID
        assert store.get_document_by_path(second["path"]) is None
    assert any(
        second["path"] in warning and "duplicate mycelium_id" in warning
        for warning in built.manifest.warnings
    )


def test_a_reference_outside_the_tree_is_text_never_a_read(built: Built) -> None:
    """Embeds, wikilinks and links pointing outside the corpus, or at URL schemes, are
    returned as the words they are; nothing is opened, nothing outside the tree is a
    document, and the graph reaches no node for them."""
    entry = BY_ATTACK["reference-outside-the-tree"]
    payload = handle_search(built.root, {"query": entry["marker"]})
    text = _flatten([result["text"] for result in _results_for(payload, entry["path"])])
    assert entry["payload"] in text
    assert "javascript:alert(1)" in text
    for forbidden in ("root:", "[fonts]", "[extensions]"):
        assert forbidden not in _flatten(payload), forbidden
    for result in payload["results"]:
        assert str(result["path"]).startswith("knowledge/")
    neighbours = handle_neighbors(built.root, {"uri": entry["path"]})
    for neighbour in neighbours["neighbors"]:
        assert str(neighbour["ref"]).startswith(("doc:knowledge/", "sym:", "ent:")), neighbour[
            "ref"
        ]
    with SqliteStore.open(built.root, read_only=True) as store:
        for doc_id in store.document_ids():
            document = store.get_document(doc_id)
            assert document is not None and document.path.startswith("knowledge/")


def test_a_forged_symbol_is_a_fact_about_its_document_and_never_an_authored_one(
    built: Built,
) -> None:
    """A fence defining `mycelium_search` yields a symbol — that is what the document
    says — whose definition site is that document and whose edges are `extracted`."""
    entry = BY_ATTACK["symbol-forgery"]
    symbol_id = "sym:python:mycelium_search"
    with SqliteStore.open(built.root, read_only=True) as store:
        symbol = store.get_symbol(symbol_id)
        assert symbol is not None
        assert entry["path"] in symbol.defined_in
        touching = [edge for edge in store.all_edges() if symbol_id in (edge.from_, edge.to)]
        assert touching
        assert {edge.status for edge in touching} == {EdgeStatus.EXTRACTED}
    neighbours = handle_neighbors(built.root, {"uri": symbol_id})
    assert neighbours["neighbors"]
    assert {neighbour["status"] for neighbour in neighbours["neighbors"]} == {"extracted"}


def test_status_comes_from_the_folder_not_from_the_text_or_the_frontmatter(built: Built) -> None:
    """A frontmatter-shaped block in the body is Markdown; a `verified_by` in real
    frontmatter is a claim; the folder is the status (D-021)."""
    with SqliteStore.open(built.root, read_only=True) as store:
        for key in ("status-forgery-in-body", "status-forgery-in-frontmatter"):
            document = store.get_document_by_path(BY_ATTACK[key]["path"])
            assert document is not None, key
            assert document.verification_status is VerificationStatus.CANDIDATE, key
    body = BY_ATTACK["status-forgery-in-body"]
    payload = handle_search(built.root, {"query": body["marker"]})
    assert body["payload"] in _flatten(
        [result["text"] for result in _results_for(payload, body["path"])]
    )


# ---------------------------------------------------------------------------
# The ingested copy, and the residuals
# ---------------------------------------------------------------------------


def test_an_ingested_copy_is_redacted_where_the_authored_one_is_served(tmp_path: Path) -> None:
    """The residual the inventory declares for a credential in *authored* prose has its
    other half here: the same document taken through the evidence lane is scanned,
    flagged and redacted before it is projected (ADR-0037)."""
    entry = BY_ATTACK["credential-in-authored-prose"]
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[CORPUS])
    result = ingest_source(
        tmp_path / ".mycelium", registry, str(CORPUS / entry["path"]), doc_id=DOC_ID
    )
    assert result.secret_flags == ("github-token",)
    assert "[redacted: github-token]" in result.projection.text
    assert entry["payload"] not in result.projection.text
    assert all(entry["payload"] not in (node.text or "") for node in result.kir.nodes)


def test_the_residuals_are_declared_not_discovered() -> None:
    """Exactly two documents are served in a way the review chose to accept rather than
    close, and each says why. A third residual is a decision, not a diff."""
    residuals = {entry["attack"]: entry["residual"] for entry in INVENTORY if entry["residual"]}
    assert set(residuals) == {"hidden-html-block", "credential-in-authored-prose"}
    for reason in residuals.values():
        assert len(reason) > 60
