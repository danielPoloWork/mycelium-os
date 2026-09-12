# ADR-0094: Mint a command the corpus both demonstrates and names, and report what promotion can and cannot reorder

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §2, spec 04 §§2-3
- **Related:** [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  (the symbol table and its two sources), [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the leg, its bar, the refusal of tail matching, the shared identifier rule),
  [ADR-0091](0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md)
  (naming sites are not documenting sites, and 5.23's filing), [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (a leg adds and never promotes — the rule this makes one measured exception to),
  [ADR-0083](0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md)
  (the oracle arm, and the planner this amends), [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md)
  / [ADR-0065](0065-one-section-cannot-document-two-commands.md) (what a `symbol` judgment
  names), [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) (the flattening
  KIR's new field undoes), [ADR-0070](0070-raise-the-leaf-heading-weight-now-that-a-dev-set-can-see-it.md)
  (a ranking change earns its default on held-out sets), [ADR-0057](0057-strip-the-function-words-the-harness-already-stripped.md)
  (the stopword list, which now lives with the planner); spec 02 §4.1, spec 03 §§2, 4, 6, spec
  04 §§2-3, §7.1; D-007, D-010; roadmap 5.1, 5.9, 5.19, 5.23, 5.25

## Context

Roadmap 5.23 was filed from 5.19 with a diagnosis and an open question. The diagnosis: sixteen
of the nineteen judged `symbol` case-instances ask for a multi-word command — `uv tool install`,
`uv lock --check`, `uv python pin` — spec 04 §2's identifier test rejects every one on
whitespace alone, and the pages that document them head their sections *Installing tools* and
*Checking the lockfile*, never with the command. A command is what that corpus documents, and
spec 03 §2's identity has no language for one. The question: what mints `sym:cli:uv tool
install`, whether the planner must learn a multi-word lookup, and whether that is spec 04 §2 as
written or an amendment. The item said to decide the source before the retrieval and to expect
the ablation to be allowed to say no again.

Three measurements were taken before the source was chosen, and they decided most of it.

**The oracle, first.** A perfect symbol table — one whose sites are the judged anchors
themselves — was scored under both readings of the leg on all six sets, before a line of the
source existed, because a lost ablation that prompts "measure it differently" wants its upper
bound known first (ADR-0083). Under *add-only* the slice moves **+0.0 % on five sets** and
+2.4 % on the sixth: every judged chunk already sits inside the lexical leg's fifty
candidates, so there is nothing for a leg that only adds to add — **no source can clear the bar
under the shipped reading**. Under *promote* the same table lifts the slice **+22.8 % to
+115.9 %**. So the source could matter only through promotion, and the question became whether
a real source's sites behave like the judged anchors.

**How the corpora write commands.** Across the uv documentation's 81 pages: 509 prompt lines in
388 `console` fences, 176 distinct multi-word invocation prefixes, and 121 multi-word phrases
written as inline code. The intersection — demonstrated at a prompt *and* named as code — holds
**45 phrases, and they are the CLI's command list**: `uv add`, `uv build`, `uv cache clean`,
`uv export`, `uv init`, `uv lock`, `uv pip install`, `uv python pin`, `uv self update`,
`uv sync`, `uv tool install`, `uv venv`, `gh auth login`, `docker run`, `pip install`… The 131
demonstrated and never named are arguments and one-offs (`uv add httpx`, `uv init
example-bare`, `aws lambda create-function`); the named and never demonstrated are things the
corpus talks about but does not show (`uv cache prune`, `pip check`, `uv tool update-shell`).
Every one of the eight judged commands is in the intersection. This repository's own
documentation writes its commands in promptless `bash` fences — the README's command list —
and names them as code; the intersection there is `mycelium build`, `mycelium search`,
`mycelium doctor` and their siblings.

**What one document cannot know.** `$ uv add requests` and `$ uv tool install ruff` have the
same shape, and no rule over one line separates a subcommand from an argument. Branching
statistics over a trie of invocations were considered and cannot either: `ruff` is one of
many children of `uv tool install` exactly as `lock` is one of many children of `uv`. The
information is in the corpus's *prose*, where authors name a command without its arguments
in backticks nearly every time — and KIR had flattened those backticks into text since
ADR-0006, so the one signal a command source needs was the one signal the compiler had erased.

## Decision

**A command is a symbol when the corpus both demonstrates it at a prompt and names it as
code.** Language `cli`, kind `command`, identity `sym:cli:uv tool install` with the words as a
shell reads them. Neither half mints alone: a demonstration without a naming is an argument or
a one-off, a naming without a demonstration is a mention. Both halves are *syntax*, read where
they are written, in `mycelium.symbols.shell`:

- **A prompt line** in a fence is a demonstration: `$ `, `% `, `> `, `PS …> ` or `❯ ` at the
  start of a line in a `console`, `shell-session`, `bash`/`sh`/`shell`/`zsh`/`fish`, `text` or
  untagged fence. A `bash`-family fence with no prompt in it is a script, and each of its lines
  that is not a comment, an assignment or a continuation is an invocation. A fence in another
  language contributes nothing whatever it holds. The line is tokenised the way a shell does
  (`shlex`), its leading run of *shell words* — lowercase, letter first, letters, digits and
  hyphens — is the command run, bounded at five words, and **every prefix of the run is
  offered** (`uv`, `uv tool`, `uv tool install`, `uv tool install ruff`): which prefix is the
  command is the corpus's call, not the line's.
- **A code span** is a naming, and KIR now carries them. `KirNode.spans` holds a node's inline
  code spans, in order, beside its unchanged flattened text — a common-core field like `text`
  itself, filled by the Markdown adapter for headings, paragraphs, list items, table cells and
  callout bodies, and by the pandoc adapter for `Code` inlines. The span's own command run and
  its prefixes are the phrases it names. A **heading that is a run of shell words** (`## pip
  check`, the convention of a CLI reference page) names a command the same way.
- **Resolution keeps the intersection.** Demonstrations travel in a document's `symbols`,
  namings in its `symbol_uses`; over the corpus, a `cli` symbol is minted when some document
  names it, its `defined_in` is the first demonstration in path order — the Markdown line of the
  prompt — and its `doc_refs` are every chunk that demonstrates *or names* it, because a section
  that names a command in prose is where the corpus documents it as often as one that runs it
  (`uv python pin` is demonstrated once, on the index page, and documented where it is named).
  A document that names a command without running it gets one `references` edge to it; one
  that runs it gets `defines`.

**The planner gains a `command` rule, and it is an amendment to spec 04 §2, stated as one.**
The spec's signals for an exact lookup are orthographic — CamelCase, snake_case, a dotted path,
a quoted phrase — and a command has none of them. Its quoted form is covered as written:
`"uv tool install"` routes through the identifier rule and the lookup reads the phrase. The bare
form is the amendment: a **command-shaped query** — a leading run of shell words followed by
nothing but flags and arguments, at most five words, **with no function word in it** — is looked
up whole in the `cli` language. The absence of function words is what separates `uv tool
install` from `how do i install`, and the list is the one the lexical leg already strips
(ADR-0057), which now lives with the planner and is re-exported by retrieval so the two cannot
drift. A sentence that contains a command unquoted is routed nowhere, on purpose: the
alternative reports `how do` as a command phrase in every plan and finds nothing.

**The lookup is exact, and never by a prefix.** A query about `uv python pin` asks for
`sym:cli:uv python pin` and nothing shorter. The prefix fallback was built and measured wrong
twice over: with the parent's sites kept, `uv python pin` promoted the 272 sites of `uv` and
`uv python` and lost its judged section entirely (0.3962 → 0.0000); with only the most specific
*held* command kept, the ingested twin — which lacks `uv python pin` because projection drops
code spans — answered with `uv python` and lost it again (→ 0.0413). That is ADR-0080's
tail-matching refusal read from the other end: the parent is a different thing from the one
asked about.

**Promotion for `cli` is the shipped reading of the leg, and the leg still ships off.** ADR-0075's
rule — a leg adds and never promotes — is the reason ADR-0080's leg was inert; this ADR makes one
measured exception, by language, and states why the language is the right unit: a command's
sites are the sections that run it or name it as code, a `doc` term's sites are headings that
spell a filename (ADR-0091), and the two readings cost differently on the same sets — promoting
everything costs 1.1 % overall on both release sets through `u-1001`, promoting commands costs
nothing anywhere. `SYMBOL_PROMOTE_LANGUAGES = ("cli",)` is a named constant in the retrieval
fingerprint. The measurement on all six sets, at the shipped constants:

| set | lexical | add-only | promote (all) | promote `cli` | `symbol` slice, promote `cli` |
|---|---:|---:|---:|---:|---|
| ours/dev | 0.4995 | 0.4995 | 0.4995 | 0.4995 | no command queries |
| ours/release | 0.5214 | 0.5214 | 0.5214 | 0.5214 | no command queries |
| uv/dev | 0.6143 | 0.6143 | 0.6279 | **0.6224** | **+7.7 %** (`u-0017` 0.4587 → 0.6201) |
| uv/release | 0.6109 | 0.6109 | 0.6039 (−1.1 %) | 0.6109 | +0.0 %, every case identical |
| uv-ingested/dev | 0.5616 | 0.5616 | 0.5811 | **0.5758** | **+16.2 %** (`u-0016` 0.7453 → 0.9049, `u-0018` 0.2128 → 0.3374) |
| uv-ingested/release | 0.6018 | 0.6018 | 0.5858 (−2.7 %) | 0.6018 | +0.0 %, every case identical |

Add-only is **byte-identical on every set**, which is the oracle's prediction reproduced. Promote
for `cli` clears the bar (≥ +3 % on the slice, no overall regression) on both dev sets and moves
nothing on either release set or on this repository. **That is proposable, not earned.** A
default flip needs the bar on a held-out set — ADR-0070's precedent, now written into the
runner's verdict: earned on release with no regression anywhere, proposable on dev only, lost
otherwise — and `tools/measure_symbol_leg.py --check` holds the shipped flag to that verdict.
An operator who sets `[retrieval] symbol_lookup = true` gets the reading that does something.

**And the finding the item asked for.** Why does a source whose sites include every judged
section for `uv tool install` move `u-1007` by nothing? Because a command's sites are the
chunks that contain the command as an invocation or a code span, and the lexical leg already
ranks those chunks first — *in the same order*. Read for `uv tool install`, the leg's ten
BM25-ranked sites are the lexical leg's ranks 1 to 10, exactly; a second vote for each of them
changes no position. Promotion helps where prose coincidence outranks a site — `uv venv` against
paragraphs about virtual environments — and cannot help where the judged section is the fourth
of ten sites that all run the command. **The `symbol` slice is a ranking problem inside the set
of documenting sections, not a reach problem**, and which of several sections that run a command
is *the* documentation is the editorial fact ADR-0091 established no per-document stage can
read. The oracle's +22.8 % on uv/release is the size of that gap, and no membership signal can
close it.

## Alternatives Considered

- **Console sessions alone, without the naming.** Every prefix of every invocation becomes a
  symbol: 176 on uv, `uv add requests` and `uv init example-bare` among them. Rejected on the
  measurement above — the intersection is the command list and the union is the argument list.
- **Namings alone, without the demonstration.** Every backticked phrase becomes a symbol: `pip
  check`, `uv cache prune`, and on this repository the commands of a tool it discusses but does
  not document (`uv tool install`, 25 times, in ADRs about the uv corpus). Rejected: a mention is
  mining, and the corpus would define commands it never shows.
- **A trie of invocations, branching statistics deciding the boundary.** Rejected before it was
  built: `ruff` under `uv tool install` and `lock` under `uv` are both one child of many, and
  a threshold that separated them on uv would be a number fitted to uv.
- **Confirm the boundary from flattened prose, without a KIR change.** Tempting, since it needs
  no contract change. Rejected: without the backticks, *"run uv tool install ruff to…"* names
  `uv tool install ruff` as readily as `uv tool install`, and the prose that would confirm a
  phrase cannot be separated from the fences that already contain it in chunk text.
- **Read the reference page's headings only** (`### uv tool install`). The convention exists and
  is read — a shell-word heading names a command — but the vendored uv corpus carries no CLI
  reference (ADR-0062), so on its own it mints nothing here. Kept as one naming syntax among
  three rather than the source.
- **Look up every window of a question as a command.** Rejected: it reports `how do` as a
  command phrase in every plan, costs a store round-trip on every query, and finds nothing; the
  bare command-shaped query and the quoted phrase are what a user types when they mean a command.
- **Casefold the query before the shape test.** Rejected on the first test: `SqliteStore`
  becomes a shell word and every identifier becomes a command.
- **Fall back to the most specific command the corpus holds.** Built, measured, removed — twice,
  as recorded above.
- **Ship the leg on, on the strength of two dev sets.** The runner's old criterion — the bar on
  any set — would have said yes. Rejected for the standard ADR-0070 set: a ranking change earns
  its default on the sets it was not developed against, and here those are byte-identical. The
  criterion is now written into the runner, so the next arm meets it rather than the old one.
- **Promote every language, since the dev sets like it.** Rejected on the release sets: −1.1 %
  and −2.7 % overall, both through `u-1001`, whose `PyPI` sites are an installation-methods
  listing (ADR-0080's finding, unchanged).
- **Judge new `symbol` cases the source can serve.** Rejected outright, as at ADR-0080: writing
  cases a feature can win is fitting the benchmark to the product (D-010).
- **Project code spans in the same change**, so the ingested twin names what its source named.
  Deferred to roadmap 5.25 with the numbers: the twin mints 12 commands to uv's 69 because
  projection emits flattened text, and re-carrying the spans is a projection change with its own
  regenerated corpus, carried cases and baselines (the shape 5.18 and 5.22 took).

## Consequences

- **The table holds commands.** uv: 23 → **92** symbols, 69 of them `cli`, and the 69 read as
  the CLI: the `uv` tree to depth three, `uvx`, `gh auth login`, `docker run`, `pip install`,
  plus the shell utilities the pages name and run (`curl`, `chmod`, `source`) and five named
  invocations (`uv tool install ruff`, `uvx ruff`, `uv tool upgrade black`). This repository:
  3 → **45**, 42 of them the `mycelium` and `uv` commands its README and CONTRIBUTING list. The
  ingested twin: 17 → **29**, 12 `cli`, limited by projection (5.25).
- **Every judged command is reachable.** All eight judged `cli` queries resolve through the
  `command` rule to a symbol the uv corpus holds; the three identifier queries and every
  question route as before, asserted case by case in `tests/test_symbols_commands.py`.
- **KIR gains `spans` and `PARSE_STAGE_VERSION` becomes 2**, so every document reparses once
  through the caches; the documents, chunks and their digests are byte-identical — the text was
  never changed, only annotated. `EXTRACT_STAGE_VERSION` becomes 7. Store schema unchanged.
- **Gate G6's golden gains the source.** `api.md` gains a section that demonstrates
  `mycelium build --no-pin` at a prompt and names `mycelium build` as code; the golden gains
  `sym:cli:mycelium` and `sym:cli:mycelium build`, their `defines` edges, and the coverage test
  pins the `cli` language and the `command` kind by name.
- **`retrieval_identity()` moves** — `promote_languages` and `command_words` join the symbol
  constants, and the stopword list's owner changed without its membership changing — so gate
  G2's verdict is re-recorded in this change, with the four vendored numbers reproducing
  byte-identically and only `ours/*` moving, by corpus growth (ADR-0053).
- **No baseline moves.** The shipped configuration ranks identically on every judged set, so
  gate G3 has nothing to re-bless and `tools/check_frozen_release_sets.py` has no conjunction to
  refuse.
- **Threat model: no new boundary.** A prompt line is fence text already inside B14's bounds,
  read by a regular expression and `shlex` with no grammar and no dependency; a code span is
  text the adapter already held.
- **Known limits, on the record.** A PowerShell cmdlet (`Get-ChildItem`) is not a shell word
  and is not read. A command named only inside a sentence, unquoted, is not looked up. The
  program of every command is itself a symbol (`uv`, 250 sites), true and bulky. A section that
  documents a command without running or naming it as code is invisible to the source, and the
  section that *is* the documentation among several that run the command is invisible to any
  source — the finding above.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (identity), §4 (KIR's additive fields), §6 (the
  record); `.draft-specs/04-retrieval-and-evaluation.md` §2 (the rule table this amends), §3
  (the leg), §7.1 (the `symbol` slice); `.draft-specs/02-architecture.md` §4.1.
- Decision log: D-007 (adapt, never write a parser), D-010 (measure before believing; fix the
  product, not the benchmark).
- Re-runnable: `python tools/measure_symbol_leg.py` (add-only), `--promote`,
  `--promote-languages cli`, `--oracle`, `--coverage`; the corpus measurements in the Context
  were taken over `eval/corpora/uv-docs/docs` and this repository's Markdown.
- Tests: `tests/test_symbols_commands.py`; the leg in `tests/test_symbol_leg.py`; the planner in
  `tests/test_planner.py`; gate G6 in `tests/test_determinism.py`.
