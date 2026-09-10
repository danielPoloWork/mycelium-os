# ADR-0073: Take the grammar's word for what a definition is, and the heading's for what it names

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§2, 6
- **Related:** [ADR-0018](0018-build-the-graph-from-authored-links.md) (the per-document /
  global seam this reuses), [ADR-0015](0015-adopt-content-addressed-incremental-builds.md)
  (the environment digest the grammars join), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (the optional-extra-plus-degraded-snapshot precedent), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md)
  (adapt an engine, pin its version), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the
  golden this re-blesses), [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md)
  (why backticks do not reach KIR); spec 02 §§4.1, 4.3, spec 03 §§2, 3.1, 4, 6, 7, 9, spec 04 §§2, 3,
  spec 06 Phase 3; D-003, D-007, D-013, D-017; roadmap 5.1, 5.2, 5.9

## Context

The `symbols` table, the `Symbol` record, the manifest's `counts.symbols` and the export
bundle's `symbols.jsonl` have existed since Milestone 2 and have been empty since. Spec 03
§2 fixes the identity — `sym:<language>:<qualified-name>` — and names two sources in five
words: *"tree-sitter (code) or definition syntax (docs)"*. Spec 06 puts the stage in Phase 3
as *"tree-sitter for code fences/repos, definition syntax for docs"*, and document 00 explains
why it is there at all: agents ask *where is X defined* constantly, and a symbol index is the
part of that question the RAG ecosystem leaves unanswered.

Three things had to be decided before a line was written, and each was measured first.

**What is a definition?** Nine languages, nine opinions. Writing a query per language means
deciding, nine times, what counts — and being wrong in a language nobody on this project
writes. Every grammar the tree-sitter organisation publishes ships a `tags.scm`: the query
GitHub's code navigation runs to answer exactly this question, exposed by the Python wheels
as `TAGS_QUERY`. Probed on 2026-09-10 against a sample per language, nine of ten wheels carry
one; C#'s (0.23.5) does not. TypeScript's covers only what TypeScript adds — interfaces,
abstract members, signatures — and its upstream tooling runs the JavaScript query beside it
for classes and functions, which compiles unchanged against the TypeScript and TSX grammars.

**What is the documentation's definition syntax?** Markdown has one construct called a
definition: the definition list (`Term` on one line, `: definition` on the next). Measured over
the three corpora the evaluation runs on — this repository's 128 documents, the vendored uv
documentation's 81, and the ingested twin — there are **zero**. What reference documentation
does instead is put the thing in the heading: `## uv.lock`, `### .python-version`,
``## `pip check` ``. The uv corpus has five headings whose whole text is a code span and three
more that are a bare identifier; ours has one. So the syntax documentation actually uses is
*a heading that is a name*, and the profile's adapter flattens inline code to its text
(ADR-0006), so the rule cannot see the backticks anyway — it has to be a rule on the text.

**What do the fences contain?** Our corpus: 82 `text`, 25 `bash`, 4 `python`, 3 `markdown`,
2 `toml` fences. The uv corpus: 390 `console`, 150 `toml`, 30 `python`, 26 `yaml`, 26
`dockerfile`, 3 `jsx`. Documentation fences overwhelmingly *show* rather than *define* —
shell sessions, configuration, invocations — and the Python ones are mostly assignments and
calls. Whatever the stage does, it must not manufacture symbols out of example glue.

## Decision

**A code fence's definitions are what its grammar's own tags query says they are.** Each
supported language is one row in a registry — the wheel, the attribute that yields its
language, the tags queries to run — and the extractor runs those queries and reads the
`definition.*` captures. Nine grammars ship: Python, JavaScript, TypeScript and TSX, Rust, Go,
Java, C, C++, Ruby. C# joins when its wheel publishes a tags query; this project does not
write one for it. The fence's info string selects the grammar through an alias table
(`py`, `rs`, `c++`, `python title="x.py"`); a tag not in the table is a fence the build does
not read for symbols.

**Qualification is ours, and it is three hints plus a walk.** A tags query captures a name and
its node, not its nesting. The extractor walks each definition's ancestors and prepends the
names of the definitions it sits inside, joined with `.` whatever the language spells its
paths with, so `RetryPolicy.delay` is the symbol in Python, Rust, Java and JavaScript alike. Three
constructs enclose without being captured and are data on the grammar row: a Rust `impl`
block contributes its `type`, a C++ `namespace` its `name`, a Go method its receiver's type. A
name that already carries its path (`RetryPolicy::attempts` outside the class) is taken whole,
so the out-of-class definition and the in-class declaration are one symbol. A `function`
nested directly in a `class` or `interface` is a `method`, so Python agrees with the grammars
that say so themselves; every other kind is the grammar's own word. Two refinements were
found by running it, not by reasoning: definitions are keyed by node identity, not byte span —
Python's `expression_statement` and the `assignment` inside it cover the same bytes, and a span
key made every constant its own scope (`CONSTANT.CONSTANT`); and a `type`, `constant` or
`macro` encloses nothing, or C's `typedef struct policy {…} policy_t` yields `policy_t.policy`.

**A `constant` is kept only when its name says it is one.** Python's query tags every
module-level assignment as `definition.constant`, `policy = build_policy()` included. In a
documentation fence that is example glue; `MAX_ATTEMPTS = 5` is a definition. SCREAMING_CASE
is the one signal available and the one every style guide gives, so the capture is honoured
exactly then. Measured on the fixture corpus: this rule is the difference between eight
symbols and eleven, and the three it removes are `retry_policy`, `snapshot` and `policy`.

**Documentation defines a term two ways, both read from KIR text.** A paragraph whose lines
are term lines followed by lines opening with `: ` is a definition list, recognised in the
paragraph's text with no parser plugin and no new node kind in spec 03 §4's closed
vocabulary. A heading defines the term its text *is*: one token, less a leading section
number and a trailing colon, carrying at least one of spec 04 §2's identifier signals — an
underscore, a dot, a path separator, a `::`, a camel-case hump, a trailing `()`. `## Retries`
is a title; `## RetryPolicy`, `## uv.lock`, `## 3.3 mycelium_neighbors` define
`sym:doc:RetryPolicy`, `sym:doc:uv.lock`, `sym:doc:mycelium_neighbors`. Every documentation
symbol is language `doc`, kind `term`.

**Extraction is per document and cached; resolution is global and runs every build** — the
seam ADR-0018 cut for links, cut again. `extract_symbols` reads one document's KIR and
chunks and yields references (language, qualified name, kind, source line, chunk anchor) that
`doc_state` keeps beside the links. `resolve_symbols` folds every document's references, in
path order, into one `Symbol` per id: `defined_in` is the first site — `<path>#L<line>`,
the Markdown line a reader opens — and `doc_refs` is every chunk that defines it. A symbol is
one row and two documents may define it, so which row changed is not a per-document question;
the table is republished whole, the manifest carries `artifact_digests.symbols`, and rollback
re-resolves from the restored state and refuses a restore that does not reproduce the digest
(a snapshot published before this ADR has no digest to be held to, and restores).

**The grammars are an optional extra, and their absence is a degraded snapshot.** Nine
compiled wheels are a real price to charge someone who wants lexical search over Markdown, and
the documentation syntax needs none of them, so `mycelium-os[symbols]` follows `embeddings`,
`ingest` and `synthesis`. A fence whose grammar is not installed is a *gap*; a document with a
gap compiles; the snapshot is `degraded: ["symbols"]` with a reason that counts the documents,
names the languages and names the extra — counted from the documents, so a corpus without code
fences is never degraded by a wheel it does not need. Which grammars are installed, at which
versions, joins the build environment digest: installing the extra dirties every document
(the parse and chunk caches still serve), and a grammar release moves the key without anyone
bumping a constant. Gate G6 covers the symbols and therefore requires the grammars: the
observation refuses to run without them rather than compare a degraded snapshot against a
golden blessed with them.

**Two things this ADR deliberately does not do.** It adds no symbol leg to retrieval: spec
04 §3's *"exact lookup in `symbols` for identifier-like tokens"* is a ranking change, subject
to gate G2's currency, gate G3's baselines and the frozen-set rule, and it deserves its own
measured PR — filed as roadmap 5.9, to be judged on the `symbol` slice. And it adds no
`Extractor` Protocol to the SDK: spec 05 §4.1 sketches one returning links, symbols *and*
entities, and its shape is a decision to make once the second of those exists (5.2) rather
than to freeze around the first.

## Alternatives Considered

- **Write our own tree-sitter queries per language.** Full control over what counts, and
  uniform kinds. Rejected: it is the decision D-007 says this project does not make — what a
  definition is in Ruby or C++ is the grammar author's call, the tags query is the industry's
  shared answer, and a home-grown query would diverge from every other tool's "go to
  definition" in ways nobody here could review.
- **A single language-pack wheel instead of nine grammar wheels.** One dependency, many
  languages. Rejected: it pins every grammar's version at once, so a build key that needs nine
  would move for a hundred and fifty it never reads, and the evidence above says documentation
  corpora use a handful. Not measured, because the versioning argument decides it alone.
- **Make the grammars a hard dependency.** No degraded state to explain. Rejected: the
  runtime closure is four packages by design (D-013/D-017), and every capability beyond the
  authored lane has shipped as an extra with a stated degradation — the symbol table follows
  the precedent rather than becoming the first exception.
- **Regular expressions over fence text.** No wheels at all. Rejected: `class` inside a
  string, a docstring or a comment is not a definition, and the false positives would be
  found by a user rather than a test. Parsing research is not this project's (D-007).
- **Index every module-level assignment, as the Python tags query does.** Rejected on the
  fixture: it turns `snapshot = build(root, clean=True)` into `sym:python:snapshot`, which is
  the example glue the stage must not manufacture symbols from.
- **Definition lists through a markdown-it plugin and a new KIR kind.** Rejected: spec 03 §4's
  node vocabulary is closed, Obsidian renders no definition lists, and the count across three
  corpora is zero. The syntax is recognised where it already lands — in a paragraph's text.
- **Mark code-span headings in KIR** (`variant="code"` on a heading) so ``## `pip check` ``
  defines a term. Deferred, not rejected: it is a KIR contract change, and of the five
  code-span headings in the uv corpus the identifier rule already reads four; `pip check` is
  two words and the only one it misses.
- **Key definitions by byte span.** The first implementation. Replaced after the fixture
  produced `CONSTANT.CONSTANT` and `Inner.method.method`: a parent node can cover exactly its
  child's bytes.
- **Emit `defines` edges now.** The vocabulary has the type (spec 03 §6). Deferred to 5.2 with
  the other typed edges; until then `doc_refs` carries the relation, and 5.2 can derive the
  edge from the same references without a second extraction.

## Consequences

- **Measured yields, stated rather than implied.** This repository's documentation: 3
  symbols, all terms (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md` as headings), no code — its four
  Python fences assign and call. The uv documentation: 14 symbols — 7 terms (`uv.lock`,
  `pyproject.toml`, `.python-version`, `.venv`, `PyPI`, `WinGet`, `MacPorts`), 5 Python
  functions and a Rust module with one method, two of them defined in more than one document.
  The determinism fixture: 8, across `doc`, `python` and `rust`. Documentation fences mostly
  *use*; the table earns its keep on corpora that document an API with definitions in fences,
  which is the shape the spec wrote it for, and 5.9 will measure what it does to retrieval.
- **Gate G6's golden gains a document and a section.** `knowledge/verified/api.md` joins the
  fixture with a Python fence, a Rust fence, a definition list and a heading term, so the gate
  covers every source; `counts.symbols` 0 → 8, `artifact_digests.symbols` becomes real,
  `schema_versions` gains `symbol`, and the observation records every symbol so a grammar
  release that changes a capture fails by name. Every other document and chunk in the golden
  is byte-identical.
- **Store schema unchanged.** `doc_state.graph_json` gains `symbols` and `symbol_gaps` keys
  that older rows decode as empty; the environment digest changed, so the first build after
  upgrading recompiles every document through the caches and fills the table.
- **The manifest and the bundle now say what they always claimed.** `counts.symbols`,
  `artifact_digests.symbols`, `schema_versions.symbol`, and a `symbols.jsonl` with records in
  it. `mycelium build` reports edges and symbols; `mycelium doctor` gains a `symbols` check
  naming each grammar it can load and the extra when it cannot.
- **A grammar upgrade is a compiler change** and shows up as one: gate G6 goes red, the
  re-blessed golden's `symbols` section is the diff, and the PR body carries it.
- **Threat model:** boundary B14 — in-process grammar parsing of untrusted fence bytes —
  bounded by a byte ceiling, error-tolerant by construction, and a per-fence warning rather
  than a per-document quarantine.
- **Known limits, on the record.** Kinds are the grammar's words and differ by language: a
  Rust `fn` inside a `mod` is a `method` because Rust's tags query says so. The camel-case
  signal reads product names as terms (`PyPI`, `WinGet`). A multi-word code-span heading
  defines nothing. A `constant` in lowercase is dropped. Each is a one-line rule with a
  measured reason, and each is cheaper to revisit with a case than to guess at now.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (identity), §6 (the record), §7 (the manifest),
  §9 (the bundle); `.draft-specs/02-architecture.md` §4.1 (the `extract` stage), §4.3
  (degraded snapshots); `.draft-specs/04-retrieval-and-evaluation.md` §2 (identifier-like
  tokens), §3 (the symbol leg, deferred); `.draft-specs/06-roadmap-and-governance.md` Phase 3.
- Decision log: D-003 (Python only), D-007 (adapt engines, never write parsers), D-013/D-017
  (zero network, small closure).
- Grammars: the `tree-sitter-*` wheels published by the tree-sitter organisation, each
  shipping `queries/tags.scm`; the binding `tree-sitter ≥ 0.25` (`QueryCursor`).
- Re-runnable: `mycelium build --no-pin` on `eval/corpora/uv-docs`, then `mycelium export`
  and read `records/symbols.jsonl`.
- Tests: `tests/test_symbols.py`; gate G6 in `tests/test_determinism.py` with
  `tests/fixtures/determinism/golden.json`.
