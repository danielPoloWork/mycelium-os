# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The MCP error taxonomy (spec 05 §3, RFC-0001 error model).

Six codes, closed. They are returned as *tool results* marked ``isError``, not as
JSON-RPC protocol errors: a query that finds nothing, an anchor that has moved, a
budget that is too small — these are answers about the corpus, and an agent should
be able to read and act on them. A JSON-RPC error means the *call* was
unintelligible, which is a different thing and stays reserved for protocol faults.

**The fields an error may carry are declared, per code** (:data:`ERROR_FIELDS`,
roadmap 6.1). ``ANCHOR_GONE`` hands back the nearest surviving ancestor and
``BUDGET_EXCEEDED`` says how many tokens one result would have needed; until the
contract freeze those two facts existed only as keyword arguments at two call
sites, which is a contract nobody can read and a compatibility suite cannot pin.
The constructor refuses a field the code does not declare, so the declaration is
true by construction rather than by convention (ADR-0114).
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

__all__ = ["ERROR_FIELDS", "ErrorCode", "McpToolError", "error_payload_schema"]


class ErrorCode(StrEnum):
    """The v1 error vocabulary — extensible only by RFC, like every other contract."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    ANCHOR_GONE = "ANCHOR_GONE"
    SNAPSHOT_UNAVAILABLE = "SNAPSHOT_UNAVAILABLE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    INTERNAL = "INTERNAL"


ERROR_FIELDS: Final[Mapping[ErrorCode, Mapping[str, dict[str, Any]]]] = {
    ErrorCode.ANCHOR_GONE: {
        "nearest": {
            "type": ["string", "null"],
            "description": (
                "The closest surviving anchor above the dead one, as a mycelium:// URI, "
                "so an agent that followed a stale citation has somewhere real to continue "
                "from; null when the document has no chunks left at all."
            ),
        },
        "path": {"type": "string", "description": "The document the dead anchor was in."},
    },
    ErrorCode.BUDGET_EXCEEDED: {
        "needed_tokens": {
            "type": "integer",
            "minimum": 0,
            "description": "What the first result alone would have cost, approximately.",
        },
    },
}
"""What each code may carry beside ``code`` and ``message``, as JSON Schema.

Codes absent from this map carry nothing extra. Adding a field here is a change to
the MCP tool contract — the compatibility golden pins this map — and is therefore
the reviewable event, while a keyword argument at a call site is not.
"""


def error_payload_schema() -> dict[str, Any]:
    """The JSON Schema of every error tool result's ``structuredContent``.

    One shape for all six codes: ``{"error": {"code", "message", ...}}``, with the
    per-code extras of :data:`ERROR_FIELDS` as optional properties. Which extras a
    given code actually carries is the map itself; the schema says only what any
    error may look like, which is what a client that validates results needs.
    """
    extras: dict[str, Any] = {}
    for fields in ERROR_FIELDS.values():
        extras.update(fields)
    return {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "enum": [code.value for code in ErrorCode]},
                    "message": {"type": "string"},
                    **extras,
                },
                "required": ["code", "message"],
                "additionalProperties": False,
            }
        },
        "required": ["error"],
        "additionalProperties": False,
    }


class McpToolError(Exception):
    """A typed failure to be rendered as an error tool result."""

    def __init__(self, code: ErrorCode, message: str, **fields: Any) -> None:
        declared = ERROR_FIELDS.get(code, {})
        undeclared = sorted(set(fields) - set(declared))
        if undeclared:
            msg = (
                f"{code.value} carries no field {undeclared!r}; the error contract declares "
                f"{sorted(declared) or 'nothing'} for it (mycelium.mcp.errors.ERROR_FIELDS)"
            )
            raise TypeError(msg)
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields

    def payload(self) -> dict[str, Any]:
        """The structured body an agent receives."""
        return {"error": {"code": self.code.value, "message": self.message, **self.fields}}
