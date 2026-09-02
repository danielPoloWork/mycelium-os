# 2026-09-02 — the suspect was wrong, and the real one was the ruled-out line (roadmap 4.16)

- **Session scope:** roadmap 4.16 / [BUG-0018](../../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)
  — make the carried ingested judgements reproduce from their own generator.
- **PR:** #63 (`fix/reproducible-ingested-carry`). Follows #62 (4.12), merged as `08a0fb6`.
- **Milestone 4:** 4.1–4.7, 4.9–4.12, 4.16 done; 4.8, 4.13–4.15, 4.17, 4.18 open.

## Confirm before fixing, and the confirmation refused the hypothesis

4.16's own text said to confirm the cause against the pre-4.11 chunker *before* fixing
anything. That instruction paid for itself immediately: the hypothesis was wrong.

Chunking both corpora with `chunking.py` at `d8a842b` and at `HEAD`, with `pack_atomic` at
its shipped default, gives **identical output** — 2244 chunks across `uv-docs`, 2073 across
`uv-docs-ingested`, and *zero* documents differing in anchor, text or kind. Reading the diff
says the same thing: with packing off, `ChunkKind.PROSE` → `_kind_of(pending)` cannot change
anything, because `pending` only ever holds prose units on that path. ADR-0042's claim that
the default did not move is exactly true, and BUG-0018 accused it wrongly.

Which left nothing. The generator was unchanged since the commit that wrote the sets, both
corpora's documents were unchanged, `config.py` had only gained a defaulted field. Same
inputs, same code, different output.

## The cause was the line the record used to rule it out

BUG-0018 said: *"What is ruled out: stale local state. `build_ingested_cases.py` builds both
corpora itself before reading them."* Both halves of that sentence are true and the conclusion
does not follow — because **`build()` is incremental**. It recompiles what `doc_state` says is
dirty, and a chunking *policy* that arrived from outside `mycelium.toml` leaves nothing dirty
to notice.

Roadmap 4.11's measurement session had built `uv-docs` with `pack_atomic` forced on from code.
That store is gitignored and disposable, so it is invisible in every way a reviewer looks —
and it survived. The carry then read **packed** judged text (568 chunks where the corpus has
2244) and scored it against the twin's unpacked chunks. Coverage collapsed, and four anchors
sitting within 0.02 of the floor went under.

Deleting both `.mycelium` directories and re-running reproduces the committed sets exactly.
That is the confirmation, and it took one command once the right question was asked.

**The generalisation is the part worth keeping**: a generator that derives a committed
artifact from an *incremental* build inherits whatever the local store happens to hold, and
records the machine rather than the corpus. I had written "stale local state is ruled out"
because the tool calls `build()` — as though calling a build were the same as controlling one.

## The fix, in three parts

1. **Both builds are clean.** One keyword, and the artifact becomes a function of the
   committed corpora and nothing else. `build_uv_docs_cases.py` gets it too — it also
   compiles its corpus in place, so it had the same exposure and nobody had noticed.
2. **`--check` regenerates and compares**, wired into `ingest / lanes` beside
   `build_ingested_corpus.py --check`. The corpus check proves the *documents* still match
   their sources; this proves the *judgements* still derive from them. **Proved to fail**
   before being trusted: mutating one recorded coverage value makes it name the file and
   refuse.
3. **The carry leaves a receipt.** `eval/carry.json` records every mapped anchor's twin and
   its coverage. The tool always printed those numbers; printing is not committing, and the
   coverage of a *surviving* anchor is what moves first when a derivation drifts. Three
   anchors legitimately map between 0.42 and 0.49 against a 0.50 floor — a cliff a reviewer
   should be able to see rather than discover.

`MIN_COVERAGE` stays at 0.5. It is a floor below which "the same passage" stops being a
defensible claim, not a dial, and widening it so marginal anchors survive would be fitting the
threshold to the data — the same move ADR-0031 refused three times for ranking.

This also lands the **u-1016 re-carry** that 4.12 had to defer: its source judgment became a
section anchor, whose text is the whole six-chunk section, which covers 0.42 of the twin's
best chunk — below the floor, so the anchor drops and the case survives on its `http.md`
anchor. Mechanical, and now visible in the receipt.

## What this says about the last three sessions

Every one of them ended by stripping `mycelium_id` out of documents a build had pinned, and
this one found that the same in-place builds were also *reading* state they did not control.
Roadmap **4.14** — let a build compile without writing to the tree — is the fix for the first
half; the second half is fixed here. They are the same root: measurement that mutates and
inherits the thing it measures.
