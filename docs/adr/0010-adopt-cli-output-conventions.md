# ADR-0010: CLI output conventions — one JSON document on stdout, ASCII chrome, UTF-8 content

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 05 §1
- **Related:** [ADR-0009](0009-adopt-build-publication-semantics.md) (the doctor check it
  promised), [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md); spec 05 §1
  (CLI table and conventions), §2 (`mycelium.toml`); D-011, D-017, D-021, D-028;
  roadmap 2.8

## Context

The CLI is one of v1's two public surfaces (D-011), so every flag is a permanent
compatibility liability and the conventions are as load-bearing as the commands. Spec 05 §1
states four: exit codes 0/1/2, `--json` on every read command, no interactive prompts in
non-TTY contexts, `NO_COLOR` honoured. What it leaves open is what those mean in practice —
in particular what `--json` promises about *stdout as a whole*, and what happens when the
content being printed is not representable in the terminal's encoding, which for a corpus
that is explicitly multilingual (D-028) is not a hypothetical.

The spec's table also lists sixteen commands. This item is a *skeleton*: five of them.

## Decision

**Five commands now** — `init`, `build`, `search`, `show`, `doctor` — and the rest arrive
with the features behind them (`ingest` at milestone 4, `snapshots`/`rollback` at 3.2,
`serve` at 2.9). A command that exists but does nothing is worse than one that does not
exist yet: it becomes a compatibility liability before it has earned one.

**`--json` means stdout holds exactly one JSON document and nothing else.** Progress,
warnings, and errors go to stderr always — so `mycelium search --json … | jq` never needs
filtering, and a failed command's stdout is empty rather than half a document. This is
tested per command, not assumed.

**Exit codes are a contract, and quarantine is not failure.** `0` ok, `1` the operation
failed, `2` the invocation was wrong (click supplies `2` for parse errors; `show --context
galaxy` raises it deliberately). A build that quarantines a document still exits `0` with
warnings on stderr — the build succeeded, and the taxonomy (ADR-0009) says per-document
failures are not build failures. `doctor` exits `1` only on a `fail` check; `warn` (nothing
built yet, a build in progress) stays `0`, so a fresh `init` does not fail CI.

**The CLI's own chrome is ASCII; content is UTF-8 with a fallback.** A Windows console
still defaults to a legacy code page, where printing `→` raises `UnicodeEncodeError` and
takes the command down — which the first manual run of `doctor` did. Two fixes, both
needed: our chrome uses `->`, `|`, `...` so it cannot fail anywhere, and `main()`
reconfigures stdout/stderr to UTF-8 with `errors="replace"` so a Japanese heading prints
(and, at worst, degrades a glyph rather than killing the process).

**Colour is opt-out and never assumed**: off when `NO_COLOR` is set to *any* value
(per no-color.org), off when the stream is not a TTY, off under `--json`.

**No prompts anywhere.** Not "no prompts when non-interactive" — none at all. `init` is
idempotent instead of asking about overwrites; it never rewrites an edited
`mycelium.toml` and appends to `.gitignore` rather than replacing it. The CI-safety
requirement is met by construction rather than by TTY detection.

**`show` accepts both a `mycelium://` URI and a bare anchor**, and resolving a URI means
asking the store where that `doc_id` lives *now* — which is exactly why citations key on
identity rather than path (D-021), and is covered by a test that promotes a document from
`candidate/` to `verified/` and re-resolves the same URI. A dead anchor gets prose naming
the surviving anchors of that document; the typed `ANCHOR_GONE` with its nearest ancestor
is an MCP contract (2.9), and the CLI gives the same information in the register a human
reads.

**`init` scaffolds `mycelium.toml` that nothing reads yet.** The spec says `init` writes
it, so it does — with a comment saying configuration loading is roadmap item 2.14 and edits
take effect when that lands. A file that silently ignores its contents is a trap; a file
that says so is documentation.

## Alternatives Considered

- **Stub the full sixteen-command table** with "not implemented" errors — discoverable,
  spec-shaped. Rejected: it advertises a surface that does not exist, and every stub is a
  name and a flag set frozen before the feature designed them.
- **`--json` as a formatting flag** (JSON where a value would print, prose alongside).
  Rejected: it makes stdout unparseable in exactly the situation the flag exists for.
- **`--format=json|text|yaml`** — more general. Rejected: the spec says `--json`, one more
  format is one more compatibility liability, and YAML has no consumer.
- **Colour via `click`'s automatic TTY detection alone** — less code. Rejected: it does
  not honour `NO_COLOR`, which the spec requires; the explicit check is four lines and
  testable.
- **ASCII-only output including content** — cannot fail on any console. Rejected: it would
  mangle the corpus itself, and a knowledge tool that cannot print its own Japanese
  documents is broken (D-028).
- **Failing loudly on unencodable output** instead of `errors="replace"` — surfaces the
  terminal's limitation honestly. Rejected: the user cannot act on it mid-pipe, and losing
  a glyph beats losing the answer.
- **`doctor` exiting non-zero on warnings** — stricter CI signal. Rejected: `init` then
  `doctor` would fail on a correct fresh repository, training users to ignore the exit code.

## Consequences

- The `doctor` check ADR-0009 promised now exists: `meta[current_snapshot]` versus
  `CURRENT`, reported as `fail` with the remedy (`mycelium build`). Its test drives the
  store into that state deliberately rather than waiting for a real crash.
- `diagnose()` returns records, not text, so the checks are unit-testable and `--json`
  is a rendering choice rather than a second implementation.
- Every search hit carries a `mycelium://…?lines=a-b` citation URI — the first place the
  public reference format from spec 03 §2 reaches a user.
- The CLI holds the store **read-only**, so `search`, `show`, and `doctor` are safe to run
  during a build (spec 02 §7); only `build` takes the writer lock.
- `mycelium.toml` exists but is inert until 2.14. Recorded in the roadmap, in the file's
  own header, and here — three places, because an inert config file is the kind of thing
  that quietly stays inert.
- Adding a command later is cheap; changing one of these conventions is not. That
  asymmetry is why the skeleton is five commands and four rules rather than sixteen
  commands and none.

## References

- Spec: `.draft-specs/05-interfaces-and-plugins.md` §1 (CLI), §2 (configuration) ·
  `.draft-specs/02-architecture.md` §7 (concurrent readers)
- Decision log: D-011 (CLI + MCP only), D-017 (untrusted input), D-021 (citations key on
  `doc_id`), D-028 (multilingual corpus)
- [no-color.org](https://no-color.org/) — the `NO_COLOR` convention
