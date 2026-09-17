---
id: BUG-0030
title: a JSON file nested past the recursion limit crashes `mycelium chats import` instead of being refused
status: fixed
severity: low
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.5.0,<0.6.0"
fixed-in: 0.6.0
---

# BUG-0030: a JSON file nested past the recursion limit crashes `mycelium chats import` instead of being refused

## Summary

Handing `mycelium chats import` a file of a hundred thousand `[` characters makes the
command die with a `RecursionError` traceback. Every reader wraps `json.loads` in
`except ValueError`, and a `RecursionError` is not one, so neither the sniffing that
chooses a reader nor the reader's own `read` reports the input as unreadable.

## Environment

- **Affected versions:** every release with the `chats` module (roadmap 5.5, v0.5.0) up
  to but not including 0.6.0
- **Toolchain / platform:** any; CPython's default recursion limit
- **Configuration:** `[modules] enabled = ["chats"]`; with or without `--provider`

## Reproduction

Found by the 6.3 security review; pinned by `contrib/chats/tests/test_hostile_input.py`.

```text
>>> from mycelium_chats.readers import reader_for
>>> reader_for("[" * 100_000, provider=None, source_uri="x", mapping={})
RecursionError: maximum recursion depth exceeded
```

## Expected vs. actual

- **Expected:** a `ReaderError` — the typed, per-input refusal the import reports and
  moves past when several files were named (spec 02 §5's quarantine-not-abort rule,
  applied to an authoring command).
- **Actual:** an uncaught `RecursionError` out of the command.

## Root cause

`json.loads` raises `RecursionError` for input nested deeper than the interpreter
allows, and the five readers, the segmenter's reply parser and the registry's sniff loop
all catch `ValueError` only.

## Impact

A crash of one authoring command on one hostile file, with a traceback instead of a
message; nothing is written. Low.

## Fix / workaround

Fixed at roadmap 6.3 (ADR-0119): every `json.loads` in the readers and the segmenter
treats `RecursionError` as it treats `ValueError` — a typed refusal for `read`, a `False`
for a sniff — and `pasted` declines to claim bracket soup as a conversation. Workaround
before 0.6.0: pin `--provider pasted`, which does not parse the file as JSON.

## References

- Fixing PR: the roadmap 6.3 pull request (`feat/security-review-pass`)
- `CHANGELOG` entry: `[Unreleased]` → *Security*
- Related: ADR-0119; `docs/security/audit-2026-09-17-review-pass.md` finding F9;
  BUG-0029 (the same exception class escaping the other lane)
