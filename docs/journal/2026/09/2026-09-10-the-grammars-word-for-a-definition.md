# 2026-09-10 — the grammar's word for a definition (roadmap 5.1)

- **Session scope:** roadmap 5.1 — symbol extraction: tree-sitter for code fences, definition
  syntax for documentation (spec 03 §§2, 6; spec 06 Phase 3). The first Milestone 5 feature.
- **PR:** #100 (`feat/symbol-extraction`). Follows #99, merged as `fcce984`.
- **Milestone 5:** 5.1 done; 5.9 filed (the retrieval leg, measured on the `symbol` slice).
- **ADR:** [ADR-0073](../../../adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md).

## Three questions, measured before they were answered

The spec gives the stage five words — *"tree-sitter (code) or definition syntax (docs)"* — and
the table, the record, the manifest count and the export file had all been waiting empty since
Milestone 2. What the words leave open is what a *definition* is in nine languages, what
*definition syntax* means in Markdown, and what documentation fences actually contain.

**Definitions.** Every grammar the tree-sitter organisation publishes ships `tags.scm`, the query
GitHub's code navigation runs to answer "where is this defined", and the Python wheels expose it as
`TAGS_QUERY`. Probed against a sample per language: nine of ten wheels carry one (C# does not, so
C# is out rather than written for), and TypeScript's covers only what TypeScript adds — the
JavaScript query compiles unchanged against the TypeScript grammar and supplies classes and
functions, which is how upstream uses them too. Taking the grammar's word is the D-007 stance:
this project adapts engines, it does not write parsers, and a home-grown notion of "definition"
in Ruby would diverge from every other tool's without anyone here able to review it.

**Definition syntax.** Markdown has one construct with that name, and across the three
evaluation corpora — 128 documents of ours, 81 of uv's, and the ingested twin — there are zero.
Reference pages put the thing in the heading instead: `## uv.lock`, `### .python-version`,
``## `pip check` ``. Five such code-span headings in uv, three bare identifiers, one in ours. And
KIR does not carry backticks (ADR-0006 flattens inline code to text), so a rule on headings has to
be a rule on text. The rule is spec 04 §2's own: a heading whose whole text is an identifier-like
token — underscore, dot, path separator, `::`, camel hump, or `()` — defines `sym:doc:<name>`.
Definition lists are supported anyway, recognised in the paragraph's text where markdown-it
already puts them, with no plugin and no new node kind in a closed vocabulary.

**Fences.** Ours: 82 `text`, 25 `bash`, 4 `python`. uv: 390 `console`, 150 `toml`, 30 `python`,
26 `yaml`, 26 `dockerfile`. Documentation shows far more than it defines, and the Python fences
are mostly assignments and calls.

## Two rules the fixture wrote

Both came from running the extractor on the determinism corpus and reading the golden, not from
design. The first golden had `CONSTANT.CONSTANT` and `Inner.method.method`: definitions were keyed
by byte span, and a Python `expression_statement` covers exactly the bytes of the `assignment`
inside it, so every module-level assignment became its own enclosing scope. Keyed by node identity
now. The same golden had `policy_t.policy` from C's `typedef struct policy {…} policy_t` — a
struct nested syntactically inside a type definition — so a `type`, `constant` or `macro` no
longer encloses anything.

The second rule is a judgment. Python's tags query captures *every* module-level assignment as a
`definition.constant`, so the fixture's `retry_policy = RetryPolicy(...)` and
`snapshot = build(root)` became symbols — the example glue the stage must not manufacture symbols
from. A `constant` is kept only when its name is SCREAMING_CASE, the one signal available and the
one every style guide gives. On the fixture that is eleven symbols against eight, and the three
removed are exactly the glue.

## The seam, cut again

Extraction is per document and cached in `doc_state` beside the links; resolution is global and
runs on every build — ADR-0018's arrangement, for the same reason: a symbol is one row and two
documents may define it, so which row changed is not a per-document question. `defined_in` is the
first site in path order as `path#L<line>`, the line a reader opens; `doc_refs` is every defining
chunk. Removing the first definer hands `defined_in` to the next without recompiling it, and that
is a test. Rollback re-resolves from the restored state and is held to the manifest's `symbols`
digest, unless the snapshot predates the digest, in which case it restores.

The grammars are an extra — `mycelium-os[symbols]`, nine wheels, all `abi3` on every platform in
the matrix — because the runtime closure is four packages by design and every capability past the
authored lane has shipped that way with a stated degradation. A fence whose grammar is absent is a
gap; a document with a gap compiles; the snapshot is `degraded: symbols` with a reason that counts
documents and names languages and the extra. The grammar versions sit in the environment digest,
so installing the extra dirties every document — the parse and chunk caches still serve, and
that is a test too. Gate G6 now covers symbols and therefore requires the grammars: it refuses to
run without them rather than compare a degraded snapshot against a golden blessed with them.

## What it yields, honestly

This repository's documentation: **3** symbols, all headings (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`), no code. The uv documentation: **14** — seven terms (`uv.lock`, `pyproject.toml`,
`.python-version`, `.venv`, and three product names the camel-case signal reads as terms:
`PyPI`, `WinGet`, `MacPorts`), five Python functions, a Rust module and its method. The fixture:
8, across `doc`, `python` and `rust`. Resolution over the whole uv corpus measures 0 ms in the
manifest timings; the extraction hides inside `compile`.

Documentation fences mostly *use*. The table earns its keep on a corpus that documents an API with
definitions in fences, which is the shape the spec wrote it for — and nothing reads the table at
query time yet. That is 5.9, filed with the cases it will be judged on and the honest expectation
that on these two corpora the move is small or zero.

## What was not done, and why it is written down

No retrieval leg: a new rank list is a tuning change, subject to G2's currency, G3's baselines and
the frozen-set rule, and it deserves its own PR. No `Extractor` Protocol: the spec shape returns
links, symbols and entities together, and freezing it around the first of the three would be
deciding 5.2 and 5.4 by accident. No `defines` edges: 5.2 can derive them from the references this
item already keeps. No KIR marker for code-span headings: of uv's five, the identifier rule reads
four, and a contract change for `pip check` is not worth it today.

One environment note for whoever reads this on the maintainer's machine: `uv sync` removed the
hand-installed `typst` (declared nowhere by design, per the `pyproject.toml` comment) and it was
reinstalled at the same version before the session ended.

## Lesson

A tags query is the grammar author's opinion of what a definition is, and it is the only opinion
worth shipping — but it is written for source files, not documentation fences, and the two
differ in exactly one way: a fence's module-level assignments are almost never definitions. The
fixture found that in the first golden; no amount of reading the query would have.
