# 2026-09-10 — a module, and what it could not reach (roadmap 5.5)

- **Session scope:** roadmap 5.5 — the first contrib module, `chats` (spec doc 08), built on
  the D-023 extension points, which is also the item that tests them before the 1.0 freeze.
- **PR:** #104 (`feat/first-contrib-module-chats`). Follows #103 (5.4), merged as `e9eddce`.
- **Milestone 5:** 5.5 done; 5.13, 5.14, 5.15 and 5.16 filed. 5.6, 5.7 and 5.9–5.12 remain.
- **ADR:** [ADR-0077](../../../adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md).

## The item is two deliverables, and the second one is the point

Doc 08 §2 says so in as many words: *"if the D-023 extension points can't support this module
cleanly, they get fixed before the 1.0 API freeze. That is half the reason this module exists
in the roadmap at all."* Its sixth acceptance gate is that half — zero core patches, and any
core change that is needed is an API fix.

So the first thing to establish was what actually existed. Spec 05 §4.1.1 lists four generic
mechanisms and D-025 promises `[modules] enabled = ["chats"]`. **None of the four was
implemented.** The whole extension surface was the `mycelium.plugins` entry-point group for
parsers and connectors, and `ModulesConfig` carried a validator whose only job was to refuse
every name that could be written in it:

```python
msg = f"[modules] enabled lists {list(self.enabled)}, but no modules exist yet ..."
```

"Built exclusively on the public D-023 extension points" therefore could not be satisfied by
*using* them. Read carefully, the gate asks for something else: build the ones a real module
needs, and report on the ones it does not.

## One of four, and the three refusals are the finding

The module needs a **CLI subcommand** — six of them, under `mycelium chats`. It declares **no
MCP tools**, by doc 08 §2's own decision: a transcript is indexed like any document, so
`mycelium_search` and `mycelium_fetch` already serve it, and D-011 counts every tool as a
permanent liability. And it does its writing at *authoring* time, so there is nothing for a
**pipeline stage** or a **lifecycle hook** to observe.

Building the other three anyway was the tempting move and would have been the wrong one: three
contracts frozen at 1.0 against no consumer. That is the same refusal 5.1 made for the
`Extractor` protocol, for the same reason — an API designed from a sample of zero is an API the
first real user contradicts. `Module` is shaped so `stages()`, `hooks()` and `tools()` arrive
additively, as optional methods a later reader checks for.

## The API fix: a module could not have a setting

`mycelium.toml` is loaded strictly (ADR-0014) and refuses every section spec 05 §2 does not
print. So `[chats]` was a `ConfigError`, and the first module could not be configured at all —
no default project, no timezone, no retention window.

The fix is generic rather than a section named after one module: a table whose name is an
*installed module id* belongs to that module. The core carries it and hands it over; the module
validates it with a schema of its own. That split is the whole point — a field added to
`[chats]` is not a core release. What the core still enforces is what only it can see: the id
must be installed, the table may not shadow a section spec 05 §2 defines, and it participates
in `config_digest` under ADR-0014's own rule.

## Two bugs found by running it, not by reading it

**Mounting at import time created a cycle, and hid it.** The first implementation mounted
module sub-apps at the bottom of `cli/app.py`. A module's CLI reuses the core's output
conventions (ADR-0010), so importing the module imports `mycelium.cli` — and when `app.py`
mounted modules during its own import, that import re-entered a module which was still
half-initialised, the entry point raised `AttributeError`, and the command *vanished*. The
`except Exception: continue` I had written for "a broken wheel must not break the CLI" swallowed
the evidence.

It depended on import order, so it worked in five hand checks:

```
=== order A: app first      chats mounted: True
=== order B: output first    chats mounted: True
=== order C: doctor first    chats mounted: True
```

and failed under pytest, where a test module imported `mycelium_chats` before anything imported
the CLI. `mount(app)` is called from `main()` now, and it **returns its failures** instead of
hiding them.

**Quoting a message does not contain it.** The projection puts each message inside an Obsidian
callout, and I had written down that this made the document's structure the projection's alone.
A test disagreed:

```
headings = ['A conversation', '1 · user', 'Not a section', '2 · assistant']
```

CommonMark allows block structure inside a blockquote. `> ## X` is a heading; worse, `> ---`
under a line of text is a *setext* underline, and the heading it creates swallowed the callout
whole. Either one opens a section the projection never authored, so a pasted `## Decision`
would become a citable anchor of its own and the chunking unit would silently stop being the
message.

The fix was already written down, elsewhere: the evidence lane's projector *"emits text, never
assertions"* — a source saying `see [[secrets]]` projects the words and not the link (threat
model B11). A heading is an assertion about structure. So the projector escapes the two line
shapes with a backslash, and CommonMark reads it away:

| input | headings | indexed text |
|---|---|---|
| `> ## Not a section` | `Not a section` appears | — |
| `> \## Not a section` | none | `## Not a section` |

The rendered view and the indexed text carry the original characters; only the block-level
meaning is gone. The record keeps the true bytes regardless.

## Two findings filed rather than fixed

**A callout is not an atomic chunk, and spec 03 §3.1 says it is.** The profile promises
*"atomic chunks like tables"*; `_ATOMIC_KINDS` covers tables and code blocks only. Doc 08 §7
wants the *message* to be the chunking unit, and the obvious rendering — one callout per message
— would have packed several turns into one chunk. The projection opens each message with its own
heading instead, which the chunker already bounds: one message, one section, one chunk, and an
anchor like `#12-assistant/0`. Closing the divergence moves every boundary in every corpus with a
callout, so it is 5.13's own measured PR rather than a paragraph in this one.

**A fidelity report cannot describe a source that produces no KIR.** Spec 02 §5 requires one of
every source, and `FidelityReport` requires a `kir_digest` and counts KIR nodes. A chat import
has no KIR until the compiler later parses the projection. So the module defines its own
`mycelium/chat-fidelity/v0` with recognised / inferred / fragment / lost counts, and the doctrine
turns out to be stated more universally than the record supports.

## And the coupling nobody had written down

The module imports three SDK modules — `sdk.types`, `sdk.identity`, `sdk.protocols` — and five
*components*: `config`, `modules`, `ingest`, `chunking`, `cli.output`. Spec 02 §10 freezes five
contracts at 1.0 and none of those components is among them. So a module that must take input
into custody, scan it for secrets, report fidelity and print like the core depends today on
surfaces that may move, and the next module will either reimplement them badly or depend on them
too.

I deliberately did not design the façade. Doing it here would repeat the mistake the three
refusals above avoid: one consumer is not a sample. It is filed as 5.14 with the list, which is
the input that decision needs. One instance was fixed in passing because it was an omission
rather than a question — `redact_text` existed in `mycelium.ingest.secrets` and was not
re-exported, so the module could not redact without reaching into a submodule.

## Gate 6 is a test

"Zero core patches" cannot be checked by reading a diff: a module could reach into an internal
and the diff would look clean. So the allowlist above *is* the test. `test_acceptance.py` parses
every module source, collects every `mycelium.*` import, and fails on any name outside the set
or any private attribute. Two more checks run beside it: the core contains no reference to
`mycelium_chats`, and the module is discovered through the entry-point group rather than by
anything the core hard-codes.

Adding a line to that allowlist is now a reviewable event, which is exactly what the gate is for.

## What the module does

Five readers. ChatGPT's export stores turns as a *node tree*, so the reader walks
`current_node`'s parent chain — the conversation the user last saw — and keeps the nodes that
walk never visits as fragments, because a regenerated turn leaves its predecessor in the file and
a naive reader loses it in silence. Claude's two body shapes, a Markdown transcript, a pasted
conversation, and any JSON through `[chats.mapping]`.

Two decisions inside it are worth repeating. Identity is *derived* from the original's content
digest and `imported_at` comes from custody's `first_seen`, so importing the same export twice
produces byte-identical files and no diff — a nightly re-export is a safe habit rather than a way
to accumulate duplicates. And an unlabelled paste gets **no invented speakers**: the obvious
heuristic is to alternate `user`/`assistant` by paragraph, and it is wrong often enough that a
record built from it is a record nobody can cite. It is kept as one fragment instead, with the
cost stated and lifted by 5.16 when a model can propose boundaries.

## And one the full suite found that neither suite alone could

Adding the module's tests to `testpaths` broke three tests in
`tests/test_hypothesis_profile.py` with `module 'conftest' has no attribute
'DEADLINE_MS'`. pytest's default import mode imports a `conftest.py` under its bare
basename, so two directories holding one meant the second claimed the name — and that file
does `import conftest` to assert the property-test profile the core declares (ADR-0060).

The fix is one `__init__.py` in the module's test directory: pytest then imports its conftest
under a package-qualified name and the bare `conftest` stays the core's. No core test changed.
Worth recording because the failure is invisible to either suite run alone, and because the
first instinct — take the module's tests out of `testpaths` — would have removed the reason
spec 05 §4.3 keeps contrib in-repo at all.

## One thing that was not a product problem

A single archive test took 114 seconds with a 0.05-second body. It turned out to be pytest
pruning 32,805 leftover files from six earlier `pytest-of-Polo` directories on this machine.
Deleting them took the same suite to 4.9 seconds. Worth writing down only because the shape —
"a trivial test is inexplicably slow" — is much more often environmental than it looks, and I
spent a round measuring regexes and imports before checking the temp directory.

## Lesson

A specification that says a module exists to validate an API is asking for a *report*, not just
a feature — and the report's most valuable lines are the mechanisms that went unused and the
couplings that had no name. Both are invisible to anyone reading the finished module, which is
why the allowlist had to become a test rather than a paragraph.
