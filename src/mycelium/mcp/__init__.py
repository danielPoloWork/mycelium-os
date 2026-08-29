# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The MCP server — the second and last public surface of v1 (D-011).

- :mod:`mycelium.mcp.tools` — `mycelium_search` and `mycelium_fetch` (spec 05 §3).
- :mod:`mycelium.mcp.server` — the stdio JSON-RPC transport.
- :mod:`mycelium.mcp.errors` — the closed error taxonomy.

Read-only by construction: v1 exposes no mutating tool, and every response says
in words that its content is data rather than instructions (D-017).
"""

from mycelium.mcp.errors import ErrorCode, McpToolError
from mycelium.mcp.server import SUPPORTED_PROTOCOL_VERSIONS, serve_stdio
from mycelium.mcp.tools import NOTICE, TOOL_SCHEMAS, handle_fetch, handle_search

__all__ = [
    "NOTICE",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "TOOL_SCHEMAS",
    "ErrorCode",
    "McpToolError",
    "handle_fetch",
    "handle_search",
    "serve_stdio",
]
