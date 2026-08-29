# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The MCP error taxonomy (spec 05 §3, RFC-0001 error model).

Six codes, closed. They are returned as *tool results* marked ``isError``, not as
JSON-RPC protocol errors: a query that finds nothing, an anchor that has moved, a
budget that is too small — these are answers about the corpus, and an agent should
be able to read and act on them. A JSON-RPC error means the *call* was
unintelligible, which is a different thing and stays reserved for protocol faults.
"""

from enum import StrEnum
from typing import Any

__all__ = ["ErrorCode", "McpToolError"]


class ErrorCode(StrEnum):
    """The v1 error vocabulary — extensible only by RFC, like every other contract."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    ANCHOR_GONE = "ANCHOR_GONE"
    SNAPSHOT_UNAVAILABLE = "SNAPSHOT_UNAVAILABLE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    INTERNAL = "INTERNAL"


class McpToolError(Exception):
    """A typed failure to be rendered as an error tool result."""

    def __init__(self, code: ErrorCode, message: str, **fields: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields

    def payload(self) -> dict[str, Any]:
        """The structured body an agent receives."""
        return {"error": {"code": self.code.value, "message": self.message, **self.fields}}
