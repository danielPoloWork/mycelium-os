# 2026-09-12 — a command is what the corpus shows and names (roadmap 5.23)

- **Session scope:** roadmap 5.23 — a command is what the uv corpus documents, and nothing
  made it a symbol. Decide the source before the retrieval; expect the ablation to be allowed to
  say no again (spec 03 §2, spec 04 §§2-3; ADR-0062/0065/0073/0080/0091).
- **PR:** #121 (`feat/command-symbols`). Follows #120, merged as `6abf7e1`.
- **Milestone 5:** 5.23 done; 5.25 filed (project code spans, so the ingested twin names what
  its source named).
- **ADR:** [ADR-0094](../../../adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md).

## The oracle came first, and it changed the question

The item was filed expecting a no, and the memory from 5.11 says what to do with a lost
ablation that prompts "measure it differently": build the oracle arm before the heuristic. So
before any source existed, a *perfect* symbol table — sites equal to the judged anchors — was
scored under both readings of the leg on all six sets. Under add-only it moves the slice
**+0.0 % on five sets**: every judged chunk already sits inside the lexical leg's fifty
candidates, so a leg that only adds has nothing to add, whatever the source. Under promote it
lifts the slice 22.8 % to 115.9 %. Twenty minutes, and the item's question was no longer "what
source" but "whether a real source's sites behave like the judged anchors under promotion".

## The source was in the corpus, in two halves

Reading the uv docs for how they write commands: 509 prompt lines, 176 distinct multi-word
invocation prefixes, 121 multi-word phrases in backticks. The two lists disagree almost
everywhere and agree exactly where it matters. Demonstrated *and* named: **45 phrases, and they
are the CLI's command list** — `uv add`, `uv lock`, `uv pip install`, `uv python pin`, `uv tool
install`, `gh auth login`, `docker run`. Demonstrated and never named: `uv add httpx`, `uv init
example-bare`, `aws lambda create-function` — arguments. Named and never demonstrated:
`uv cache prune`, `pip check` — mentions. Every one of the eight judged commands is in the
intersection. No rule over a single prompt line can separate `uv add requests` from `uv tool
install`; the corpus's prose does it for free, in backticks.

Which is where the compiler had been in the way. ADR-0006 flattens inline code into node text,
and the backticks — the one syntax documentation uses to name a command without its arguments —
were gone before any stage could read them. `KirNode.spans` now carries them beside the
unchanged text, from the Markdown adapter and from pandoc's `Code` inlines. `PARSE_STAGE_VERSION`
is 2; documents, chunks and digests are byte-identical, because the text was annotated, not
changed.

## Three things the measurement fixed on the way

**Prefixes.** A demonstration offers every prefix of its run so the corpus can decide which is
the command, and the first lookup asked for every prefix of the query too. Measured: `uv python
pin` promoted the 272 sites of `uv` and `uv python` and lost its judged section outright
(0.3962 → 0.0000). Keeping only the most specific command the corpus *held* fixed uv and broke
the twin, which lacks `uv python pin` (projection drops the spans) and answered with
`uv python` — ADR-0080's tail-matching refusal from the other end. The lookup is exact now, and
nothing shorter.

**Casefolding.** The first shape test casefolded the query, which turned `SqliteStore` into a
shell word and every identifier into a command. Read as written; a command is lowercase.

**The criterion for a default.** The runner used to say "earns on at least one set". Promotion
for `cli` earns on both dev sets and moves nothing on either release set, and under the old
criterion that would have flipped a retrieval default on four dev cases. ADR-0070 set the
standard — a ranking change earns its default on the sets it was not developed against — and
the runner now says so: earned on release with no regression anywhere, *proposable* on dev
only, lost otherwise.

## What the ablation said

Add-only: **byte-identical on every set**, exactly as the oracle predicted. Promote everything:
earns on both dev sets, loses 1.1 % and 2.7 % overall on the release sets through `u-1001`,
whose `PyPI` sites are a listing — ADR-0080's finding, unchanged. Promote `cli` only: **+7.7 %**
on uv/dev's slice (`u-0017`, `uv venv`) and **+16.2 %** on the twin's (`uv build`, `uv init`),
overall +1.3 % and +2.5 %, no regression anywhere, and **every case identical on both release
sets and on our own corpus**. Proposable, not earned. `SYMBOL_PROMOTE_LANGUAGES = ("cli",)`
ships so an operator who turns the leg on gets the reading that does something; the leg ships
off; `--check` agrees.

The interesting number is the one that did not move. `uv tool install` has seventeen sites and
the judged section is among them, and `u-1007` is identical under promotion — because the leg's
ten BM25-ranked sites *are* the lexical leg's ranks one to ten, in the same order. A command's
sites are the chunks that contain the command as code, and BM25 already puts those first. A
second vote for each of them reorders nothing. Promotion helps where prose coincidence outranks a
site (`uv venv` against paragraphs about virtual environments) and cannot help where the judged
section is the fourth of ten sites that all run the command. The slice is a ranking problem
*inside* the documenting sections, and which of several sections that run a command is the
documentation is the editorial fact 5.19 already established no per-document stage can read.
The oracle's +22.8 % on uv/release is the size of that gap.

## What it yields

uv: 23 → 92 symbols, 69 of them commands; this repository: 3 → 45, 42 of them the `mycelium`
and `uv` commands the README and CONTRIBUTING list; the twin: 17 → 29, twelve commands,
limited by projection — filed as 5.25 with the numbers rather than fixed here, because a
projection change regenerates a corpus, its carried cases and its baselines.

## Lesson

Measure the ceiling before building the floor. The oracle turned "what mints a command" into
"can promotion carry it", and the site inspection turned "the source is weak" into "the
mechanism cannot reorder what BM25 already ordered" — two findings the ablation table alone would
have blurred into one +0.0 %.
