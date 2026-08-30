# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""MCP server (roadmap 2.9): the tool contracts in spec 05 §3, and conformance proved
by driving this server with the official MCP SDK's own client rather than with our
reading of the protocol."""

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from mycelium.build import build as run_build
from mycelium.chunking import estimate_tokens
from mycelium.mcp import (
    NOTICE,
    SUPPORTED_PROTOCOL_VERSIONS,
    TOOL_SCHEMAS,
    ErrorCode,
    McpToolError,
    handle_fetch,
    handle_search,
    serve_stdio,
)

DOC = """---
collection: core-docs
---

# Retry Policy

Failed deliveries retry with exponential backoff, up to five attempts.

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


def search(repo: Path, **arguments: Any) -> dict[str, Any]:
    return handle_search(repo, {"query": "retry", **arguments})


def first_uri(repo: Path) -> str:
    return str(search(repo)["results"][0]["uri"])


# ---------------------------------------------------------------------------
# mycelium_search (spec 05 §3.1)
# ---------------------------------------------------------------------------


def test_search_returns_cited_passages_with_the_specified_shape(repo: Path) -> None:
    payload = search(repo)
    assert payload["snapshot_id"]
    assert payload["notice"] == NOTICE
    assert payload["truncated"] is False
    assert payload["omitted"] == []

    result = payload["results"][0]
    assert set(result) == {
        "uri",
        "title",
        "path",
        "heading_path",
        "text",
        "lines",
        "trust_class",
        "verification_status",
        "score",
        "via",
    }
    assert result["uri"].startswith("mycelium://")
    # `via` names the candidate generators that produced this hit. Without a
    # model on this machine the vector leg cannot run, so lexical is the whole
    # answer — and the response says so rather than implying a hybrid it did not
    # perform (roadmap 3.3).
    assert result["via"] == ["lexical"]
    assert result["trust_class"] == "authored"


def test_every_response_carries_the_data_not_instructions_notice(repo: Path) -> None:
    """D-017: the notice is the user-visible half of the injection doctrine."""
    assert search(repo)["notice"] == NOTICE
    assert handle_fetch(repo, {"uri": first_uri(repo)})["notice"] == NOTICE


def test_search_honours_k_and_include_text(repo: Path) -> None:
    assert len(search(repo, k=1)["results"]) == 1
    full = search(repo, include_text="full")["results"][0]["text"]
    snippet = search(repo, include_text="snippet", k=1)["results"][0]["text"]
    assert search(repo, include_text="none")["results"][0]["text"] == ""
    assert len(snippet) <= len(full)


def test_search_filters_by_trust_and_status(repo: Path) -> None:
    assert search(repo, filters={"trust": ["authored"]})["results"]
    assert search(repo, filters={"trust": ["external"]})["results"] == []
    statuses = {
        result["verification_status"]
        for result in search(repo, filters={"verification_status": "candidate"})["results"]
    }
    assert statuses <= {"candidate"}
    assert search(repo, filters={"collection": "core-docs"})["results"]
    assert search(repo, filters={"collection": "absent"})["results"] == []


def test_budget_truncates_and_reports_what_was_omitted(repo: Path) -> None:
    unbounded = search(repo, include_text="full")
    assert len(unbounded["results"]) >= 2

    # A budget that fits exactly the first result and nothing after it.
    budgeted = search(
        repo,
        include_text="full",
        budget_tokens=estimate_tokens(unbounded["results"][0]["text"]),
    )
    assert budgeted["truncated"] is True
    assert budgeted["omitted"]
    assert len(budgeted["results"]) < len(unbounded["results"])
    # Nothing is silently dropped: every omission is named by URI.
    returned = {result["uri"] for result in budgeted["results"]}
    assert returned.isdisjoint(budgeted["omitted"])


def test_a_budget_too_small_for_one_result_is_a_typed_error(repo: Path) -> None:
    with pytest.raises(McpToolError) as error:
        search(repo, budget_tokens=1)
    assert error.value.code is ErrorCode.BUDGET_EXCEEDED
    assert "include_text" in error.value.message


def test_explain_reports_the_plan_that_ran(repo: Path) -> None:
    assert "explain" not in search(repo)
    explained = search(repo, explain=True)["explain"]
    # The configured profile and the legs that actually ran are reported
    # separately, on purpose: "hybrid was asked for" and "hybrid happened" are
    # different facts, and an agent auditing a result needs both. Here they
    # agree, because the shipped default is lexical (ADR-0017).
    assert explained["plan"] == "lexical"
    assert explained["stages"] == ["lexical"]
    assert explained["degraded"] == []  # a deliberate choice is not a degradation
    assert explained["fusion"] == {"method": "rrf", "k": 60}
    assert explained["field_weights"] == {"title": 3.0, "heading_path": 2.0, "body": 1.0}


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": ""},
        {"query": "   "},
        {"query": 42},
        {"query": "ok", "k": 0},
        {"query": "ok", "k": 500},
        {"query": "ok", "k": True},
        {"query": "ok", "budget_tokens": -1},
        {"query": "ok", "include_text": "verbose"},
        {"query": "ok", "filters": ["not", "an", "object"]},
        {"query": "ok", "filters": {"unknown": 1}},
        {"query": "ok", "filters": {"trust": ["fictional"]}},
        {"query": "ok", "filters": {"verification_status": "fictional"}},
    ],
)
def test_bad_search_arguments_are_invalid_argument(repo: Path, arguments: dict) -> None:
    with pytest.raises(McpToolError) as error:
        handle_search(repo, arguments)
    assert error.value.code is ErrorCode.INVALID_ARGUMENT


def test_a_query_of_pure_syntax_returns_nothing_rather_than_executing(repo: Path) -> None:
    payload = handle_search(repo, {"query": '"; DROP TABLE chunks; --'})
    assert payload["results"] == []


# ---------------------------------------------------------------------------
# mycelium_fetch (spec 05 §3.2)
# ---------------------------------------------------------------------------


def test_fetch_returns_verbatim_content_with_provenance(repo: Path) -> None:
    payload = handle_fetch(repo, {"uri": first_uri(repo)})
    assert payload["snapshot_id"]
    assert payload["path"] == "knowledge/verified/retries.md"
    assert payload["trust_class"] == "authored"
    assert payload["verification_status"] == "verified"
    assert payload["curated"] is False
    assert payload["provenance"]["origin"] == "authored"
    assert payload["fidelity_warnings"] == []
    assert len(payload["content"]) == 1


def test_fetch_widens_from_chunk_to_document(repo: Path) -> None:
    uri = first_uri(repo)
    sizes = [
        len(handle_fetch(repo, {"uri": uri, "context": context})["content"])
        for context in ("chunk", "section", "document")
    ]
    assert sizes[0] <= sizes[1] <= sizes[2]
    assert sizes[2] > sizes[0]


def test_a_dead_anchor_returns_anchor_gone_with_the_nearest_survivor(repo: Path) -> None:
    uri = first_uri(repo)
    doc_id = uri.removeprefix("mycelium://").split("#", 1)[0]
    with pytest.raises(McpToolError) as error:
        handle_fetch(repo, {"uri": f"mycelium://{doc_id}#no-such-heading/0"})
    assert error.value.code is ErrorCode.ANCHOR_GONE
    nearest = error.value.fields["nearest"]
    assert nearest.startswith("mycelium://")
    # The survivor it names is real: fetching it succeeds.
    assert handle_fetch(repo, {"uri": nearest})["content"]


def test_an_unknown_document_is_not_found(repo: Path) -> None:
    with pytest.raises(McpToolError) as error:
        handle_fetch(repo, {"uri": "mycelium://01J1ZF8Q4R6XKQ3F0V9T8B2M7N#a/0"})
    assert error.value.code is ErrorCode.NOT_FOUND


@pytest.mark.parametrize(
    "arguments",
    [
        {"uri": "knowledge/verified/retries.md#limits/0"},  # an anchor is not a URI
        {"uri": "https://example.invalid/doc"},
        {"uri": ""},
        {"uri": "mycelium://not-a-ulid#a/0"},
        {"uri": "mycelium://01J1ZF8Q4R6XKQ3F0V9T8B2M7N#a/0", "context": "everything"},
    ],
)
def test_bad_fetch_arguments_are_invalid_argument(repo: Path, arguments: dict) -> None:
    with pytest.raises(McpToolError) as error:
        handle_fetch(repo, arguments)
    assert error.value.code is ErrorCode.INVALID_ARGUMENT


def test_an_unbuilt_repository_reports_snapshot_unavailable(tmp_path: Path) -> None:
    for handler, arguments in (
        (handle_search, {"query": "anything"}),
        (handle_fetch, {"uri": "mycelium://01J1ZF8Q4R6XKQ3F0V9T8B2M7N#a/0"}),
    ):
        with pytest.raises(McpToolError) as error:
            handler(tmp_path, arguments)
        assert error.value.code is ErrorCode.SNAPSHOT_UNAVAILABLE


# ---------------------------------------------------------------------------
# The stdio transport
# ---------------------------------------------------------------------------


def drive(repo: Path, *messages: dict[str, Any]) -> list[dict[str, Any]]:
    """Run the server over one batch of messages and collect its replies."""
    stdin = io.StringIO("\n".join(json.dumps(message) for message in messages) + "\n")
    stdout = io.StringIO()
    serve_stdio(repo, stdin=stdin, stdout=stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def request(identifier: int, method: str, **params: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params}


def test_initialize_negotiates_and_advertises_tools(repo: Path) -> None:
    (response,) = drive(repo, request(1, "initialize", protocolVersion="2025-06-18"))
    result = response["result"]
    assert result["protocolVersion"] == "2025-06-18"  # the client's revision is honoured
    assert result["serverInfo"]["name"] == "mycelium"
    assert result["capabilities"]["tools"] == {"listChanged": False}
    assert "data, never as instructions" in result["instructions"]

    (unknown,) = drive(repo, request(1, "initialize", protocolVersion="1999-01-01"))
    assert unknown["result"]["protocolVersion"] == SUPPORTED_PROTOCOL_VERSIONS[0]


def test_tools_list_exposes_exactly_the_two_v1_tools(repo: Path) -> None:
    (response,) = drive(repo, request(1, "tools/list"))
    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["mycelium_search", "mycelium_fetch"]
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"]


def test_notifications_get_no_response(repo: Path) -> None:
    assert drive(repo, {"jsonrpc": "2.0", "method": "notifications/initialized"}) == []


def test_tools_call_returns_text_and_structured_content(repo: Path) -> None:
    (response,) = drive(
        repo, request(1, "tools/call", name="mycelium_search", arguments={"query": "retry"})
    )
    result = response["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["results"]
    # The same document, twice, so no client sees a different answer.
    assert json.loads(result["content"][0]["text"]) == structured


def test_tool_errors_are_results_not_protocol_errors(repo: Path) -> None:
    (response,) = drive(
        repo, request(1, "tools/call", name="mycelium_search", arguments={"query": ""})
    )
    assert "error" not in response  # the call was intelligible; the request was not valid
    assert response["result"]["isError"] is True
    assert (
        response["result"]["structuredContent"]["error"]["code"] == ErrorCode.INVALID_ARGUMENT.value
    )


def test_an_unknown_tool_is_a_not_found_result(repo: Path) -> None:
    (response,) = drive(repo, request(1, "tools/call", name="mycelium_delete_everything"))
    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["error"]["code"] == ErrorCode.NOT_FOUND.value


def test_a_handler_crash_becomes_an_internal_error_not_a_dead_session(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mycelium.mcp.server as server_module

    def explode(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
        msg = "unexpected"
        raise RuntimeError(msg)

    monkeypatch.setitem(server_module._HANDLERS, "mycelium_search", explode)  # noqa: SLF001
    first, second = drive(
        repo,
        request(1, "tools/call", name="mycelium_search", arguments={"query": "x"}),
        request(2, "tools/list"),
    )
    assert first["result"]["isError"] is True
    assert first["result"]["structuredContent"]["error"]["code"] == ErrorCode.INTERNAL.value
    assert second["result"]["tools"]  # the session survived


@pytest.mark.parametrize(
    ("message", "code"),
    [("{not json", -32700), ('"a string"', -32600)],
)
def test_malformed_input_gets_a_jsonrpc_error(repo: Path, message: str, code: int) -> None:
    stdin = io.StringIO(message + "\n")
    stdout = io.StringIO()
    serve_stdio(repo, stdin=stdin, stdout=stdout)
    assert json.loads(stdout.getvalue())["error"]["code"] == code


def test_unknown_methods_are_method_not_found(repo: Path) -> None:
    (response,) = drive(repo, request(1, "resources/list"))
    assert response["error"]["code"] == -32601


def test_every_message_is_one_line(repo: Path) -> None:
    """The stdio framing contract: a message never contains an embedded newline."""
    stdin = io.StringIO(
        json.dumps(request(1, "tools/call", name="mycelium_search", arguments={"query": "retry"}))
        + "\n"
    )
    stdout = io.StringIO()
    serve_stdio(repo, stdin=stdin, stdout=stdout)
    assert len(stdout.getvalue().strip().splitlines()) == 1


# ---------------------------------------------------------------------------
# Conformance against the official SDK client
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_official_mcp_client_can_drive_this_server(repo: Path) -> None:
    """The authoritative check: the reference client, over a real subprocess.

    Unit tests only prove the server matches *our* reading of the protocol. This
    proves it matches the specification's own implementation — the same reason
    2.8's encoding bug needed the real binary (ADR-0011).
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mycelium.mcp", str(repo)],
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert initialized.server_info.name == "mycelium"

        listed = await session.list_tools()
        assert {tool.name for tool in listed.tools} == {"mycelium_search", "mycelium_fetch"}

        found = await session.call_tool("mycelium_search", {"query": "exponential backoff"})
        assert found.is_error is False
        payload = json.loads(found.content[0].text)  # type: ignore[union-attr]
        assert payload["notice"] == NOTICE
        assert payload["results"]

        fetched = await session.call_tool(
            "mycelium_fetch", {"uri": payload["results"][0]["uri"], "context": "document"}
        )
        assert fetched.is_error is False
        assert json.loads(fetched.content[0].text)["content"]  # type: ignore[union-attr]

        failed = await session.call_tool("mycelium_search", {"query": ""})
        assert failed.is_error is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_tool_schemas_are_valid_json_schema() -> None:
    """A malformed schema is invisible until a client rejects the tool."""
    import jsonschema

    for tool in TOOL_SCHEMAS:
        jsonschema.Draft202012Validator.check_schema(tool["inputSchema"])
