# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""``python -m mycelium.mcp [root]`` — the server without the CLI in the way.

`mycelium serve` is the supported entry point; this one exists because an MCP
client configuration is often a bare interpreter invocation, and because it lets
the conformance test drive the server as a real subprocess.
"""

import sys
from pathlib import Path

from mycelium.mcp.server import serve_stdio


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    root = Path(arguments[0]) if arguments else Path()
    # stdout is the protocol channel; nothing but messages may go there.
    sys.stderr.write(f"mycelium MCP server on stdio, root={root}\n")
    sys.stderr.flush()
    try:
        serve_stdio(root)
    except KeyboardInterrupt:  # pragma: no cover - a client detaching is not an error
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
