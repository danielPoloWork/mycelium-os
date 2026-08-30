---
id: BUG-0009
title: the MCP server writes its protocol stream in the console code page, corrupting any non-ASCII response
status: fixed
severity: high
reporter: internal
discovered: 2026-08-30
affected-versions: "0.2.0 and unreleased (introduced by PR #22, roadmap 2.9)"
fixed-in: "0.3.0"
---

# BUG-0009: the MCP server writes its protocol stream in the console code page, corrupting any non-ASCII response

## Summary

`python -m mycelium.mcp` wrote JSON-RPC frames to `sys.stdout` without configuring its
encoding. On Windows that is the console's legacy code page, so any non-ASCII character in
a response was emitted as cp1252 bytes on a stream the MCP specification defines as UTF-8.
The client's decoder then fails on the frame — `UnicodeDecodeError: 'utf-8' codec can't
decode byte 0x97` — and, because the failure happens inside its read loop, the pending
request never resolves: **the session hangs rather than erroring**.

The corpus this product exists to serve is explicitly multilingual (D-028), so the trigger
is not exotic: any Japanese, Italian, or typographically-punctuated passage returned by
`mycelium_search` would do it.

## Environment

- **Affected versions:** since PR #22 (roadmap 2.9) added the server. Present in v0.2.0.
- **Toolchain / platform:** Windows, where `sys.stdout` defaults to the active code page
  (cp1252 here). POSIX systems default to UTF-8 and are unaffected.
- **Configuration:** none — the behaviour was unconditional on the affected platform.

## Reproduction

Found while adding two tools at roadmap 3.4, whose descriptions contain an em dash:

```text
initialize: ok
list_tools: FAILED TimeoutError
--- server stderr ---
  | UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 2633: invalid start byte
```

Byte `0x97` is cp1252's em dash. The same failure is reachable from content alone: a
document containing `日本語` returned through `mycelium_search` produces an unencodable
character on the same stream.

## Expected vs. actual

- **Expected:** the protocol stream is UTF-8 whatever the console is, exactly as
  [ADR-0010](../../../adr/0010-adopt-cli-output-conventions.md) already requires of the CLI:
  *"UTF-8 with `errors='replace'` degrades an unrepresentable glyph instead of the process"*.
- **Actual:** the entry point inherited the console code page, so a non-ASCII byte either
  corrupted the frame (a decodable-but-wrong byte) or raised `UnicodeEncodeError` inside the
  server.

## Root cause

`mycelium serve` goes through `mycelium.cli.main`, which calls `configure_streams()` — the
fix ADR-0010 introduced after roadmap 2.8's crash. `python -m mycelium.mcp` is a *second*
entry point to the same server and never called it. The gap was invisible because every
existing tool description was ASCII, and because the in-process tests drive `serve_stdio`
with a `StringIO`, which has no encoding at all: the only path that exercises the real
stream is the subprocess conformance test, and until an em dash appeared in a description
there was nothing on it to break.

That is the same shape as the bug ADR-0010 was written for, and the same shape as
[BUG-0008](BUG-0008-bom-hides-frontmatter.md): behaviour that only the real binary, on the
real platform, with real bytes, can expose.

## Impact

High. An agent on Windows would lose its session — not with an error it could report, but
with a hang — the first time a retrieved passage contained a non-ASCII character. For a
product whose two public surfaces are the CLI and MCP (D-011), and whose corpus is
deliberately multilingual (D-028), that is a failure of the primary integration on a
supported platform.

## Fix / workaround

`mycelium/mcp/__main__.py` calls `configure_streams()` before serving, so both entry points
reconfigure stdout and stderr to UTF-8 with `errors="replace"`. Two regression tests hold
it: the subprocess conformance test now exchanges tool calls whose descriptions contain
non-ASCII characters, and a unit test asserts that a `tools/list` frame round-trips through
UTF-8.

Workaround before the fix: invoke the server as `mycelium serve` rather than
`python -m mycelium.mcp`, or set `PYTHONIOENCODING=utf-8`.

## References

- Fixing PR: #34 (roadmap 3.4 — found when two new tools' descriptions carried em dashes)
- Introduced by: #22 (roadmap 2.9)
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [ADR-0010](../../../adr/0010-adopt-cli-output-conventions.md) (the same rule, for
  the CLI), [ADR-0011](../../../adr/0011-implement-mcp-stdio-in-repo.md) (why conformance is
  proved with the reference client over a real subprocess — which is what caught this),
  D-011, D-028
