# ADR-0077: Give a module an entry point, a section and a command — and report what it could not reach

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec doc 08, spec 05 §4
- **Related:** [ADR-0014](0014-adopt-partial-strict-configuration.md) (the strict loader this
  amends), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (pinned plugin
  resolution, borrowed wholesale), [ADR-0010](0010-adopt-cli-output-conventions.md) (the CLI
  conventions a module inherits), [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md)
  (tier-1 custody, and why deleting evidence is explicit),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) (the evidence lane this
  projection mirrors), [ADR-0046](0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md)
  (derived identity), [ADR-0007](0007-adopt-structure-first-chunking.md) (the chunker whose
  atomicity set is narrower than the spec's), [ADR-0060](0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md)
  (the property-test budget a contrib suite may not reload); spec 02 §5, spec 03 §§1, 3, 3.1,
  spec 05 §§2, 4.1, 4.1.1, 4.2, 4.3, 5, spec doc 08 (all), spec 06 Phase 3; D-004, D-012,
  D-017, D-020, D-021, D-023, D-025, D-026, D-027; roadmap 5.5, 5.13–5.16

## Context

Spec doc 08 states why the `chats` module exists, and only half of it is the feature:

> **Module discipline:** optional, activatable, and deliberately built as a real plugin —
> if the D-023 extension points can't support this module cleanly, they get fixed *before*
> the 1.0 API freeze. That is half the reason this module exists in the roadmap at all.

So this item had two deliverables: a working archive of chat transcripts, and an honest
report on the extension points it was built on. Its sixth acceptance gate is the second one
— *"the module uses only public D-023 mechanisms — zero core patches. Any needed core change
is an API fix, made before the 1.0 freeze."*

**What existed before this item.** Spec 05 §4.1.1 lists four generic mechanisms — pipeline
stages, lifecycle hooks, CLI subcommands, opt-in MCP tools — and D-025 promises
`[modules] enabled = ["chats"]`. **None of the four was implemented.** The whole extension
surface was the `mycelium.plugins` entry-point group for parsers and connectors (ADR-0032),
and `ModulesConfig` carried a validator whose only job was to refuse every name:

```python
msg = f"[modules] enabled lists {list(self.enabled)}, but no modules exist yet ..."
```

So "built exclusively on the public D-023 extension points" could not be satisfied by using
them. It had to be satisfied by *building* the ones a real module needs and reporting on the
ones it does not — which is exactly what the gate asks, read carefully.

## Decision

### The module mechanism: one entry-point group, one protocol, one command surface

**A module registers in `mycelium.modules`, a second entry-point group.** D-027 fixes a
two-level taxonomy — engine extensions are *plugins*, packaged activatable capabilities are
*modules* — and the two levels get two groups. A parser is asked *can you read this media
type*; a module is asked nothing at all until an operator names it, and sharing one group
would make `[modules] enabled = ["docling"]` a sentence the loader had to refuse at a level
below the one that could explain it.

**`Module` is a Protocol in `mycelium.sdk.protocols` with two members** — `meta` and
`commands()` — joining the four contracts already there. It requires **one** of D-023's four
mechanisms, and the omission is the finding rather than a gap: see *What one module needed*
below. Typer appears in the signature because spec 05 §4.1.1 names it, imported only for type
checking.

**Resolution is pinned, exactly as ADR-0032 pinned parsers.** A name in `[modules] enabled`
that no installed distribution provides is a `ConfigError` naming what to install and saying
that a module is a package rather than a setting. A duplicate is refused. The check reads
installed *metadata* and imports nothing, so a valid configuration costs no module import.

**Enabling is per repository; installing is per machine.** `mycelium chats` exists because
the distribution is installed, and every command in it refuses to act on a repository whose
`[modules] enabled` does not name it, printing the TOML to paste. An installed-and-not-enabled
module is therefore normal, and `mycelium doctor` reports it as **ok** while saying which is
which — a warning there would fire forever on every repository that owns one module and not
another, which is how a health report teaches people to skip it.

### The API fix: a module may own the section named after it

`mycelium.toml` is loaded strictly (ADR-0014) and refused every section spec 05 §2 does not
print. So `[chats]` was a `ConfigError`, and **the first real module could not have a
setting** — no default project, no timezone, no retention window. This is the core change
gate 6 anticipates, and it is made generically rather than for one module:

**A table whose name is an installed module id belongs to that module.** The core carries it
in `MyceliumConfig.module_config`, hands it over through `module_settings(id)`, and does not
look inside. The module validates it with a model of its own, inheriting the strictness but
not the schema — so a field added to `[chats]` is not a core release, which is the whole point
of the split. Three things the core still enforces, because only it can see them: the id must
be installed, the table may not shadow a section spec 05 §2 defines (or an installed package
could change what a query returns), and the table participates in `config_digest` under
ADR-0014's own rule that a build recorded under a config carrying a setting must not silently
match one that did not.

### The module: two files per conversation, and four invariants

A conversation becomes a canonical `chats/<project>/<year>/<month>/<date>-<slug>-<ulid6>.chat.jsonl`
record and a Markdown projection under `knowledge/evidence/chats/` that the ordinary compiler
indexes — doc 08 §§4–7, and the same one-canonical-form-one-derived-view doctrine the evidence
lane uses (D-020). Five readers: the ChatGPT and Claude exports, a Markdown transcript, a
pasted conversation, and any JSON through a configured field mapping.

Four decisions inside it are worth recording because each was taken against an obvious
alternative:

**Identity is derived, not minted** (ADR-0046's mechanism). `conv_id` is a ULID derived from
the original's content digest and the provider's conversation id, and `imported_at` is
custody's `first_seen` rather than this run's clock — so importing the same export twice
produces byte-identical files and no diff. Minting, or taking `now`, would have made a nightly
re-export a way to accumulate duplicates and rewrite committed tier-2 files.

**An unlabelled paste invents no speakers.** Doc 08 §6 permits inferring *structure*; it does
not permit inventing a *speaker*. A paste with turn labels is segmented and every message is
marked `inferred`, because a label is prose a web page rendered rather than a field a machine
wrote. A paste without labels becomes **one** fragment. The obvious heuristic — alternate
`user`/`assistant` by paragraph — was rejected: the record is the archive and the projection
makes it citable, so a fabricated attribution is a false statement about who said what.

**A ChatGPT export's abandoned edit branches are kept.** Its turns are a node tree, and a
regenerated turn leaves its predecessor in the file; the linearisation walks `current_node`'s
parent chain, which is the conversation the user last saw. Nodes the walk never visits are
preserved as `fragment` lines with a warning, because doc 08 §6 keeps unparseable residue and
an abandoned branch is residue a naive reader loses in silence.

**A secret is redacted where it spreads and kept where it is evidence.** The header records
the rules that matched, the projection is redacted unconditionally — it is the copy that
reaches Git and the index — and the record keeps the original unless `[chats] redact_in_record`
says otherwise, because the record is the archive and the original is already in custody. The
same asymmetry ADR-0037 made for ingestion.

### The projection: a heading per message, and content that cannot escape it

Doc 08 §7 wants the **chunking unit to be the message**. Spec 03 §3.1 says a callout is an
"atomic chunk like a table", which would deliver exactly that — and the chunker implements
atomicity for tables and code blocks only (ADR-0007's `_ATOMIC_KINDS`), so consecutive
callouts pack together as prose and one chunk would hold several turns. Patching the core was
not available (gate 6) and would not have been right anyway: making callouts atomic moves every
chunk boundary in every corpus that has one. **So the projection opens each message with its
own heading**, which the chunker already treats as a section boundary: one message, one
section, one chunk, and the anchor is a message anchor — `…#12-assistant/0`. The
spec-versus-code divergence is filed rather than absorbed (roadmap 5.13).

The content sits inside a callout, and **quoting alone turned out to be insufficient** — a
test found that, not a reader. CommonMark allows block structure inside a blockquote: `> ## X`
is a heading, and `> ---` under a line of text makes a setext heading that swallowed the
callout whole. Either one opens a section the projection did not author. So the projector
escapes those two line shapes with a backslash, which is the evidence lane's own rule rather
than a new one: its projector *"emits text, never assertions"* — a source saying
`see [[secrets]]` projects the words and not the link (threat model B11). A heading is an
assertion about the document's structure, and an ingested conversation does not get to make
one. CommonMark reads `\##` back as a literal `##`, so the rendered view and the indexed text
both carry the original characters and only the block meaning is gone.

**The projection reads no `[chunking]` setting**, deliberately: gate 2 asks for "same record →
byte-identical Markdown", and a projection that varied with the chunker's budget would make
that promise relative to a configuration and would rewrite committed tier-2 files when
somebody tuned it.

### Mounting happens in `main()`, and the failure is reported

The first implementation mounted module sub-apps at import time, at the bottom of
`mycelium/cli/app.py`. **That created a cycle and hid it.** A module's CLI reuses the core's
output conventions (ADR-0010), so importing the module imports `mycelium.cli` — and when
`app.py` mounted modules during its own import, that import re-entered a module which was
still half-initialised, the entry point raised `AttributeError`, and the command silently
vanished. It depended on import order, so it worked in five hand checks and failed under
pytest.

Both halves are fixed. `mycelium.modules.mount(app)` is called by `main()`, once the command
tree exists, and it is idempotent. And it **returns its failures** instead of swallowing them:
`main()` prints them to stderr and `doctor` reports a module that cannot load as a failing
check. A broken third-party wheel still must not make `mycelium build` unusable — so it does
not raise — but swallowing it is what turned a cycle into a mystery.

### `contrib/chats/` is a distribution of its own, in a uv workspace

Spec 05 §4.3 and doc 08 §2 both say `contrib/chats/`; AGENTS.md §5 makes `src/mycelium/` the
normative tree. Both are honoured by making the module **a second distribution** —
`contrib/chats/src/mycelium_chats/`, its own `pyproject.toml`, a uv workspace member — because
§5 governs the shape of *a* Python distribution and this repository now holds two, each in
src-layout. Putting the module inside `src/mycelium/` was rejected for the reason the item
exists: a module that can import its host's internals is a plugin-API validation that cannot
fail. As a separate distribution it is held to the published surface exactly as a third party
would be, and the gate below is what checks that.

## Alternatives Considered

- **Build all four D-023 mechanisms now.** Rejected, and this is the load-bearing refusal: the
  first real module needs one of them, so three would be frozen at 1.0 against no consumer.
  That is the same reasoning that deferred the `Extractor` Protocol at roadmap 5.1 (ADR-0073) —
  a contract designed from a sample of zero is a contract the first real user contradicts.
  `Module` is shaped so `stages()`, `hooks()` and `tools()` arrive additively.
- **Let the module read `mycelium.toml` itself** instead of teaching the loader about module
  sections. Rejected: two readers of one file, two error vocabularies, and a module could then
  read `[retrieval]` too.
- **Validate `[chats]` in the core** with a section model like the others. Rejected: it puts a
  module's field set inside the core's contract, so every module release becomes a core
  release — the coupling a module exists to avoid.
- **A `mycelium.sdk.ingestion` façade** re-exporting custody, secret scanning and the output
  helpers, so a module imports only `mycelium.sdk`. Tempting, and deferred rather than
  refused: it is the API design decision, and designing it from one module is the mistake the
  first alternative describes. Filed as roadmap 5.14 with the list of couplings below, which is
  the input that decision needs.
- **Make callouts atomic in the chunker** so doc 08 §7's chunking unit needs no workaround.
  Rejected here on two counts: gate 6 forbids the core patch, and the change moves every chunk
  boundary in every corpus containing a callout — a G6 re-bless and three baseline re-blesses,
  which is its own measured PR (roadmap 5.13), not a paragraph in this one.
- **Escape nothing and accept the split.** Rejected: a message containing a Markdown heading
  is common — people paste documentation into chats — and the failure is invisible, producing
  anchors derived from what somebody pasted.
- **Alternate `user`/`assistant` by paragraph in an unlabelled paste**, then let a human fix
  it. Rejected above: it fabricates attribution into a citable artifact.
- **Mint `conv_id`** from a clock, and dedupe by scanning the archive. Rejected: derived
  identity makes the import idempotent with no scan at all, and ADR-0046's warning about
  derived ids — that they move when their *name* moves — does not apply to a content digest.
- **Register the chat readers as `Parser` plugins**, using the existing group. Rejected
  because it is not true: a `Parser` maps bytes to KIR, and a chat export maps to a chat
  record. Declaring them as parsers would mean either lying about the output type or compiling
  `.chat.jsonl` directly, which doc 08 §7 rules out by making the projection the indexed
  artifact. The readers are a protocol internal to the module, and the observation for the
  freeze is that spec 05 §4.1's protocol set has no seat for a format reader whose output is
  not KIR.
- **Reuse `FidelityReport`** for the import report, since spec 02 §5 requires one of every
  source. Rejected because the record cannot express it: it requires a `kir_digest` and counts
  KIR nodes, and a chat import has no KIR until the compiler later parses the projection. So
  the module defines `mycelium/chat-fidelity/v0` with recognised / inferred / fragment / lost
  counts, and the finding is that "every source emits a fidelity report" is a doctrine the
  core's *record* only fits for a parser producing KIR.
- **Leaving the module's suite outside `testpaths`**, so its `conftest.py` could not collide
  with the core's. Rejected: spec 05 §4.3 keeps contrib in-repo precisely so a core change that
  breaks a module fails the *core's* own suite, and a suite CI does not run does not do that. The
  collision was real — pytest's default import mode imports a `conftest.py` under its bare
  basename, so the second one claimed the name and `tests/test_hypothesis_profile.py`, which does
  `import conftest` to assert the property-test profile (ADR-0060), read the wrong module and
  failed three times. The fix is one `__init__.py` in the module's test directory, which gives its
  conftest a package-qualified name and leaves the bare `conftest` to the core. No core test
  changed, and no other basename this suite adds can collide either.
- **A hypothesis property test for the verbatim invariant**, as doc 08 §10's gate 3 words it.
  Rejected in that exact form: the property-test budget and its profile are declared once in
  the core suite (ADR-0060) and `settings.load_profile` is global state, so a profile loaded
  from a contrib conftest would change the whole session's settings. The invariant is asserted
  against a stated adversarial corpus instead — block structure, nested quotes, whitespace,
  escapes, non-ASCII, and the setext underline that actually broke it.
- **Frontmatter keys for `provider`, `project` and `started_at`**, as doc 08 §7 lists them.
  Not taken: spec 03 §3 closes the machine-read field set deliberately, and adding to it is
  roadmap 5.10's decision rather than this item's. They are written as non-contract
  `properties` — preserved verbatim, never machine-interpreted, visible as Obsidian properties,
  which is what §7 wants them for — and `collection: chats/<project>` is the contract field
  that actually serves retrieval.

## Consequences

### What one module needed, of what the plugin API offers

The report gate 6 exists to produce. Of spec 05 §4.1.1's four mechanisms:

| Mechanism | Used | Why |
|---|---|---|
| CLI subcommands | **yes** | Six commands under `mycelium chats`; the module's whole operator surface |
| MCP tools | **no, by design** | Doc 08 §2: transcripts are indexed like any document, so `mycelium_search` and `mycelium_fetch` already serve them, and D-011 counts every tool as a permanent liability |
| Pipeline stages | **no** | Import is an authoring action that writes tiers 1–2; nothing it does belongs inside a build. The one candidate — synthesis distillation (doc 08 §7) — needs a provider and is filed as roadmap 5.15 |
| Lifecycle hooks | **no** | Same reason: no build-time work to observe |

So **one of four**, and three contracts are not being frozen against nothing.

### What the module had to reach for outside the plugin API

Also the report, and the more useful half. The module imports these, and only these:

| Import | What for | Is it the plugin API? |
|---|---|---|
| `mycelium.sdk.types` | `Record`, `Ulid`, `Sha256Digest`, `UtcDatetime`, `CustodyKind` | **yes** (spec 05 §4.1) |
| `mycelium.sdk.identity` | `derived_ulid`, `digest_bytes`, `heading_slug`, `canonical_json` | **yes** |
| `mycelium.sdk.protocols` | `Module`, `PluginMeta`, `MYCELIUM_API_VERSION` | **yes** |
| `mycelium.config` | reading its own `[chats]` table | no — a component |
| `mycelium.modules` | refusing to run where it is not enabled | no — a component |
| `mycelium.ingest` | `Custody`, `scan_text`, `redact_text`, `EVIDENCE_DIRNAME` | no — a component |
| `mycelium.chunking` | the token estimator, so `--budget-tokens` means one thing | no — a component |
| `mycelium.cli.output` | ADR-0010's exit codes, JSON rule and colour policy | no — a component |

Five of the eight are components with a curated `__all__`, not the surface spec 02 §10 freezes
at 1.0. **A module that must take input into custody, scan it for secrets, report fidelity and
print like the core therefore depends today on things the freeze does not cover** — and every
future module will reimplement them, badly, or depend on them too. That is the finding, filed
as roadmap 5.14; designing the façade here would repeat the mistake this ADR's first refusal
describes.

One concrete instance was fixed in passing, because it was a one-line omission rather than a
design question: `redact_text` and `Finding` existed in `mycelium.ingest.secrets` and were not
re-exported by `mycelium.ingest`, so the module could not redact without reaching into a
submodule. They are exported now.

### Gate 6 is a test, not a claim

"Zero core patches" is not checkable by reading a diff — a module could reach into an internal
and the diff would look clean. So the table above **is** the test:
`contrib/chats/tests/test_acceptance.py` parses every module source, collects every
`mycelium.*` import, and fails on any name outside the allowlist or any private attribute.
Adding a line to that set is the reviewable event the gate exists to force. Two more checks
run beside it: the core contains no reference to `mycelium_chats` (the stronger direction), and
the module is discovered and mounted through the entry-point group rather than by anything the
core hard-codes.

### Everything else this changed

- **Store schema, manifest, retrieval, graph: unchanged.** A record is `.chat.jsonl` and
  `discover()` globs `*.md`, so no core change was needed to keep records out of the corpus;
  the projection is ordinary Markdown and is indexed, chunked, cited and searched like any
  other document. Chat content is reachable with message-level anchors and filterable with
  `--collection chats/<project>`, both tested.
- **Gate G6's golden moves one line** — `config_digest`, because `MyceliumConfig` gained the
  `module_config` field. Every document, chunk, symbol, entity and edge in the golden is
  byte-identical.
- **`mycelium doctor` gains a `modules` check**, and this repository's own report now carries
  it (installed, not enabled here).
- **`contrib/` joins the gate ladder**: `ruff format`, `ruff check` and `mypy --strict` read it,
  its tests are in `testpaths`, and `tools/verify.py` derives `code` for a change under it —
  with `tests/test_verify_ladder.py` still checking that CI and the local ladder agree
  (ADR-0059). 156 module tests and 23 core module tests.
- **The `mycelium-os` sdist excludes `contrib/`**, so one archive does not carry two
  distributions.
- **Known limits, on the record.** A message larger than the chunker's ceiling stays one chunk
  rather than splitting at paragraph boundaries as doc 08 §7's last clause suggests, because a
  callout is one block and a block is never split (ADR-0007) — filed as roadmap 5.13 with the
  callout-atomicity question it belongs to. An archive path's date follows `[chats] timezone`,
  whose default is the importing machine's, so two machines importing a *pasted* conversation
  file it under different dates; pinning the setting fixes it, and a provider export carrying
  its own timestamps is machine-independent either way (tested). `chats list` reads every
  record to count messages, which is fine at archive scale and wants an index when it is not.

## References

- Spec: `.draft-specs/08-module-chats.md` (the whole module, and §10's six gates);
  `.draft-specs/05-interfaces-and-plugins.md` §§2 (the config file), 4.1 (the protocols), 4.1.1
  (the four mechanisms), 4.2 (pinned resolution), 4.3 (stability tiers), 5 (compatibility);
  `.draft-specs/03-data-model.md` §§1 (conventions), 3 (the frontmatter contract), 3.1 (the
  profile, and the callout claim); `.draft-specs/02-architecture.md` §§3–5 (the authority
  model, the DAG, the failure taxonomy).
- Decision log: D-004 (tiers), D-012 (a plugin is installed code), D-017 (untrusted input,
  no network), D-020/D-021 (the two lanes and folder-encoded status), D-023 (the four
  mechanisms), D-025 (`chats` is the first module), D-026 (one identifier), D-027 ("skill" is
  reserved; plugins and modules are the taxonomy).
- Re-runnable: `mycelium chats import contrib/chats/tests/fixtures/chatgpt-export.json
  --project research --root <repo>`, then `mycelium build <repo>` and
  `mycelium search "webhook retries" --root <repo>`.
- Tests: `contrib/chats/tests/` (readers, archive, projection, formats, and the six gates);
  `tests/test_modules.py` (discovery, activation, module config, mounting).
