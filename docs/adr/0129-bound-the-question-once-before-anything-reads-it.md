# ADR-0129: Bound the question once, before anything reads it

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§1–2, D-017
- **Related:** [ADR-0119](0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-may-cost-to-read.md)
  (the review that found this, and the sibling bound on what a *document* may cost to read),
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (why the tool's input schema is not where a bound goes),
  [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) (the fingerprint this adds a
  field to), [ADR-0057](0057-drop-the-function-words-and-score-the-seam-that-ships.md) (the
  other rule that decides which of a question's words are searched on),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md) and
  [ADR-0094](0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md)
  (the symbol leg, whose tokenizer the bound must not disturb),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) (the vector leg's
  precondition); spec 04 §§1–2, spec 05 §3; threat model B6, register
  [F11](../security/audit-2026-09-17-review-pass.md); roadmap 6.3, 6.17

## Context

Every cost on the serving path is bounded except one. `k` is capped at 50 by the tool schema,
`budget_tokens` bounds the answer and returns a typed `BUDGET_EXCEEDED` when even one result
will not fit, the embedder truncates at its model's sequence length, each leg has a candidate
budget, and since ADR-0119 a *document* has a ceiling on what it may cost to read. The
**question** had none.

The 6.3 security review measured what that costs (register F11): twenty thousand terms held
the single-threaded stdio server for 57 s. Filed as roadmap 6.17 rather than fixed there,
because a change to which terms are ranked on is a retrieval change and belongs under the
evaluation gates, not inside a security PR.

Re-measured at 6.17, on the corpus of record and through the whole `search` path rather than
the lexical primitive alone, it is worse than the review found and the realistic case is the
expensive one:

| pasted as the query | before | after |
|---|---|---|
| `docs/compatibility.md` (9.1 KB, 1 074 terms) | 5 146 ms | 94 ms |
| `AGENTS.md` (27.8 KB, 3 182 terms) | 25 230 ms | 98 ms |
| `README.md` (62.4 KB, 7 384 terms) | **146 528 ms** | 94 ms |

Two things in that table matter more than the ratio. The first is that **nothing hostile is
involved**: an agent pasting a document as its query is ordinary use, and this repository's
own README is the document. The second is the shape of the "after" column — 94 ms for 9 KB and
for 62 KB alike. Unbounded, the server's cost was a function of what a caller pasted; bounded,
it is a function of what the corpus holds, which is the property a serving budget needs before
any number in it means anything.

The cost is **linear in the term count at 3–4 ms a term** on the largest corpus here, with a
knee at the top end (4.2 ms/term at twenty thousand against 3.3 at five thousand). F11 called
it superlinear and that is right at the extreme, but the load-bearing fact is simpler: it was
unbounded, and linear without a bound is enough.

Where the cost sits, at 62 KB: 130 s in the lexical leg, 7 s in the symbol leg — which ships
**on** by default since roadmap 5.25 and composes one candidate id per identifier-like token
per language, then re-ranks the survivors with BM25 over the same enormous expression. The
vector leg is already bounded (its tokenizer truncates) and the planner's scans are linear and
trivial. So a bound placed at the lexical leg alone would have left the second-largest cost
where it was.

## Decision

**The question is bounded once, before the plan and before any leg reads it.**
`mycelium.retrieval.bound_query` reads the first `MAX_QUERY_TERMS` terms and reports how many
it declined to read; `search` calls it on entry, and everything downstream — the plan, the
lexical leg, the symbol leg's id composition and its BM25 re-rank, the foothold probe, the term
report — sees the question the server agreed to read. A leg added later is bounded by
construction, which is the property the alternatives below do not have.

**`MAX_QUERY_TERMS` is 64, and the number is the measurement.** The longest query anything in
this project measures itself on is **nine terms** — one agent task — across six judged sets and
the agent-task suite, with a median of three to four. Sixty-four is seven times that maximum,
so no question this project can observe reaches it. It is also where a bound still binds: at 64
terms the lexical leg costs ~210 ms on the largest corpus here, against ~110 ms at 32 and
~470 ms at 128 — the worst case stays within the same order as a normal question rather than
within the same order as a document. Both halves are needed: a bound no question reaches is
useless if it does not bound, and a bound that binds tightly is a defect if a real question
reaches it.

**It truncates and says so; it does not refuse.** The realistic long query is an agent pasting
a document, and the first sixty-four terms of a document are a usable question — the answer to
the bounded query is exactly the answer to its first terms, and a test pins that. `explain`
carries the note, naming how many terms went unread, beside the function-word note that already
reports the other rule about which words are searched on.

**The bound joins `retrieval_identity()`.** It decides a ranking for every query above it by
deciding which terms are ranked on at all, which is the criterion that function states of
itself: *"a new ranking parameter belongs in this dict in the same commit that introduces it."*
No judged query comes near the bound, so the re-recorded gate-G2 verdict moves only its
fingerprint — and that the four `uv` and `uv-ingested` numbers reproduce byte-identically is
itself the evidence that the bound touched nothing judged.

**The evidence the bound was chosen on is kept as a test.** `test_no_query_this_project_measures_itself_on_reaches_the_bound`
walks all six judged sets and the agent tasks and fails if any question ever grows long enough
to be cut — because on that day the cut is a scoring change, and it should be named as one
before a gate reports it as a regression.

## Alternatives Considered

- **Cap inside `fts_query`** — the item's own first suggestion, and the narrowest-looking
  place. Rejected on what else that function does: it builds the expression the *index* is
  written with (`_stemmed` tokenizes with the same expression), so a bound there is a bound on
  indexing, which would silently truncate long documents at build time. It is also below the
  seam that can report anything: `explain` speaks of the question, and the store does not know
  it is answering one.
- **Cap in the planner** — the item's other suggestion. The planner decides *routing*, and the
  bound is about *cost*; putting it there would make every future reader ask why the router
  truncates. `search` is where the question is prepared and where the existing preparation rule
  (function words, ADR-0057) already lives and already reports.
- **Cap `query_terms` alone** — the smallest change that fixes the headline number. Rejected
  because it bounds the lexical leg and nothing else: the symbol leg tokenizes the raw query
  itself (`_QUERY_TOKEN`, which keeps `uv.lock` whole where the lexical counter sees two
  terms), and 7 s of the 146 s was there. Bounding the question instead of one leg's reading of
  it is what makes the property hold for legs nobody has written yet.
- **Reject an over-long query with `INVALID_ARGUMENT`.** Cleaner to specify, and wrong twice.
  It breaks the ordinary case — an agent pasting a document gets an error where a good answer
  was available — and it would mean narrowing `mycelium_search`'s input schema with a
  `maxLength`, which is one of the five frozen contracts (ADR-0114): tightening an input is an
  incompatible change needing an RFC, spent on making the product worse.
- **Deduplicate the surface terms instead of bounding them.** The surface side of
  `expanded_query` does *not* deduplicate while the stem side does, so a pasted document
  contributes one `OR` arm per **occurrence** — measured at 2.2x to 3.7x redundancy on real
  documents, and a 98.9 KB `MATCH` expression for a 62 KB README. Deduplicating would have cut
  the cost by that factor and bounded nothing: the cost would still grow without limit in the
  distinct words pasted. It is a real asymmetry and a possible ranking change — two of 155
  measured queries repeat a term, both agent tasks — so it is **filed as roadmap 6.26** to be
  measured on its own, not folded in here where its effect could not be told apart from the
  bound's.
- **Bound bytes rather than terms.** A single 100 KB word is one posting list and costs
  nothing; sixty-four short words cost sixty-four lookups. The cost is per term, so the bound
  is per term, and a test pins that a long word is not truncated.
- **Make it configurable** (`[retrieval] max_query_terms`). Rejected for now: a setting in
  `mycelium.toml` enters `config_digest` and the G6 golden, and a knob whose only honest
  setting is "the measured one" is a knob that invites a wrong one. It becomes a setting when
  somebody has a question longer than sixty-four terms, which is the trigger to reopen this.

## Consequences

- **The server's cost is a function of the corpus rather than of the caller's paste**, which is
  the precondition for every latency budget in spec 04 §1 meaning anything. It does not by
  itself make NFR-2's 150 ms p95 — 6.18, 6.19 and 6.24 own that, and 6.4 measured it missed —
  but it removes the term under which no budget could have held.
- **Threat model B6's denial-of-service row closes**, and register F11 moves from *open, filed*
  to fixed, naming this item. The residual is stated there: a bounded query still costs what
  sixty-four terms cost, so a client issuing them in a tight loop can still occupy a
  single-threaded server — which is a rate question and not a query question, and a local
  single-user client can only stall itself.
- **`retrieval_identity()` moves, and `eval/g2-verdict.json` is re-recorded in this PR**
  (ADR-0068). All four `uv` and `uv-ingested` set numbers reproduce **byte-identically**, which
  is how a fingerprint move is told apart from a ranking move.
- **The bound is provably inert on every judged query**, because every judged query is at most
  nine terms and a test asserts it. `ours/*` *does* move in the re-record — its lexical mean on
  `dev` goes 0.5029 → 0.4705 — and that is this pull request's own ADR, journal entry and README
  prose joining a corpus this repository hosts, which is what `DATED_CORPORA` exists to report
  rather than gate (ADR-0053). Saying "no score moves" without that distinction would blur a
  corpus effect into a retrieval one, which is the confusion the dev/release split and the
  reported/gated split both exist to prevent.
- **A new roadmap item, 6.26**, carries the surface/stem deduplication asymmetry this work
  uncovered.
- **A limitation, stated.** The bound is on terms the server reads, not on what a caller may
  send: a 190 KB question is still transported, JSON-parsed and scanned once to find the
  sixty-fourth term. That scan is linear and costs milliseconds against the 146 s it replaces,
  and bounding the transport is the MCP framing's business rather than retrieval's.
- **A second limitation, and it is a deliberate consistency rather than an oversight.** A
  caller who does not ask for `explain` is not told that the question was cut. The note goes
  where every other fact about the query path already goes — the function words that were
  dropped, the vector leg withheld for want of lexical evidence, hybrid disabled by
  configuration — and none of those is surfaced without `explain` either. Making this one the
  exception would mean adding a top-level field to `mycelium_search`'s response, whose output
  schema is closed and frozen (ADR-0114), so it would be an RFC spent on making one note
  louder than its siblings. If that surfacing is ever wanted it should be wanted for all of
  them at once, which is a different decision from this one.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §§1–2 (the pipeline and its latency
  budgets), `.draft-specs/05-interfaces-and-plugins.md` §3 (the tool surface the bound is
  reported through).
- Security: `docs/security/threat-model.md` B6; `docs/security/audit-2026-09-17-review-pass.md`
  F11.
- Re-runnable: `uv run pytest tests/test_retrieval.py -q -k bound`,
  `uv run pytest tests/bench/test_retrieval_bench.py -q`, and
  `python -c "from mycelium.retrieval import bound_query; print(bound_query(open('README.md',encoding='utf-8').read())[1])"`.
