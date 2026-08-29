# 2026-08-30 — CLI skeleton (roadmap 2.8)

- **Session scope:** roadmap item 2.8 — CLI skeleton (typer): `init`, `build`, `search`,
  `show`, `doctor`, with `--json` (spec 05 §1).
- **PR:** #21 (`feat/cli-skeleton`), one item, one PR. Follows #20 (2.7), merged.

## What got done

- `src/mycelium/cli/` — `app.py` (the five commands), `doctor.py` (diagnostics as records,
  so they are testable without a CLI runner), `output.py` (exit codes, JSON emission,
  colour policy, stream encoding).
- Installed as the `mycelium` console script; new runtime dependency `typer`.
- Every search hit carries a `mycelium://…?lines=a-b` citation URI — the first time the
  public reference format from spec 03 §2 reaches a user.
- `doctor` carries the check **ADR-0009 promised**: `meta[current_snapshot]` vs `CURRENT`,
  the commit-to-swap window, reported as a failure with its remedy. Its test drives the
  store into that state deliberately.
- ADR-0010 records the conventions; README gained a quickstart (the CLI is now the public
  surface, so the front door has to show it).
- Tests: 327 passing (+32).

## What the first real run caught

Running `mycelium doctor` in a scratch repo crashed with `UnicodeEncodeError`: the `→` in
"CURRENT → <id>" is unprintable on a Windows console's legacy code page, and the em dash in
the build summary had already been rendering as `?`. Two fixes, both needed:

- **CLI chrome is now ASCII** (`->`, `|`, `...`) so it cannot fail on any console;
- **`main()` reconfigures stdout/stderr to UTF-8 with `errors="replace"`**, so *content* —
  a Japanese heading, a CJK document title — prints rather than killing the process. A
  knowledge tool for a multilingual corpus (D-028) that cannot print its own documents is
  broken; verified by building and searching a Japanese document on this Windows console.

The unit tests would never have caught this: `CliRunner` captures to a UTF-8 buffer. It
took running the actual binary in a real terminal.

## A gap filed rather than papered over

`mycelium init` scaffolds `mycelium.toml` because spec 05 §1 says it does — but **nothing
reads it**, and no roadmap item owned configuration loading. Rather than quietly shipping
an inert file, or expanding 2.8 to build a config subsystem, the generated file carries a
header saying so and **roadmap item 2.14** now exists (per AGENTS.md §10: out-of-scope work
is filed in the same PR).

## Where the project stands

- Milestone 2: 2.1–2.8 ✅ · 2.9–2.14 open. A user can now `init`, `build`, `search`, `show`
  and `doctor` a repository end to end from the terminal.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (327 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #21 to merge, then start **2.9** — the MCP server (stdio): `mycelium_search`
  + `mycelium_fetch`, typed errors, and the data-not-instructions notice (spec 05 §4),
  route standard/medium. It is the second and last public surface of v1 (D-011).
- Most of what it needs exists: read-only store access, citation URIs, and the
  `_missing_anchor_help` logic in the CLI is the prose form of the typed `ANCHOR_GONE`
  the MCP contract requires — with the nearest *surviving ancestor*, which the CLI
  approximates by listing siblings.
- `Chunk.tokens` is an estimate (ADR-0007): `budget_tokens` packing in `mycelium_search`
  must measure with the caller's own tokenizer, not trust the field.
