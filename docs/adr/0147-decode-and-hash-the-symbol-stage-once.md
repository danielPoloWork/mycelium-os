# ADR-0147: Decode and hash the symbol stage once

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 03 §6
- **Date:** 2026-09-21
- **Related:**
  [ADR-0133](0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md)
  (roadmap 6.20, which profiled the no-op floor and named this item),
  [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md) (why the
  symbol stage derives `defines`/`references` edges at all, and why edges must exist
  before `put_edges` writes them),
  [ADR-0018](0018-build-the-graph-from-authored-links.md) (resolution is global — every
  document is re-read on every build, the property this item's fix has to preserve),
  [ADR-0145](0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md)
  and
  [ADR-0146](0146-memoise-the-stemmer-bounded-against-a-measured-vocabulary.md) (roadmap
  6.30/6.31, this item's siblings from the same profile — one plain economy each,
  measured and shipped); D-011 (a knob nobody has evidence for is a liability);
  spec 03 §6; roadmap 6.19, 6.20, 6.32

## Context

Roadmap 6.19 profiled a 1 000-document cold build; once the write ceremony (6.30) and
the quadratic it replaced (6.19 itself) were accounted for, roadmap 6.20 turned the same
lens on the **no-op incremental floor** — a rebuild in which nothing changed, still
costing **~1.36 s** because the graph and the symbol table are resolved and republished
wholesale on every build, not diffed (ADR-0018: adding one document can settle what an
untouched one's reference means). Of that floor, the `symbols` stage cost **235 ms**, and
the profile attributed it to two plain kinds of waste rather than to any algorithm:

1. **Decoding more than once.** `resolve_symbols` and `symbol_edges` are always called
   back to back — a use becomes an edge only when the corpus defines what it names, so
   the symbol table must exist before the edges over it do (ADR-0074) — and each
   independently decoded every document's `symbols` and `symbol_uses` from `doc_state`'s
   stored JSON. Three decodes of `symbols` and two of `symbol_uses` per rebuild, where
   one of each does the same work. The generated prose in this repository's own fences
   names on the order of twenty thousand uses, so decoding is not free arithmetic.
2. **Hashing an edge's identity twice.** `symbol_edges` builds a `dict[Sha256Digest,
   Edge]` to key and deduplicate the edges it derives — computing each one's identity in
   the process — and then discards that key when it returns the plain edge list.
   `SqliteStore.put_edges` receives the edges without it and derives the identity again
   from scratch, including a `canonical_json(provenance)` call that duplicates one
   already spent computing the same edge's identity moments earlier.

Neither is an algorithmic problem the way 6.19's quadratic was: both are literally
redoing arithmetic whose first answer was still in scope. The item sized this `S · route:
fast / low` on exactly that basis, and asked for measurement before deciding how far to
take it — content-proportional work looks large on a corpus dense with code and small on
a vault of prose.

## Decision

**Decode each state once and thread the result through both passes; stop
double-serializing an edge's provenance when writing it.** Two contained fixes, no change
to what is published.

### Decode once

`mycelium.symbols.resolve` gains a private `_Facts` record — a document's `symbols` and
`symbol_uses`, decoded exactly once — and `_facts_of(states)` builds one per state.
`resolve_symbols` and `symbol_edges` become thin wrappers around private
`_resolve_symbols`/`_symbol_edges` implementations that take `_Facts` instead of decoding
raw `SymbolState`s themselves; **`resolve_symbols_and_edges(states, namespace)`** is the
new entry point that calls `_facts_of` once and hands the same facts to both passes. It
is what the build orchestrator and `mycelium rollback`'s restore now call — the two, and
only two, production call sites. `resolve_symbols` and `symbol_edges` stay public and
independently callable — and independently decoding — for a caller, or a test, that only
needs one of the two; `tests/test_typed_edges.py` pins that the combined function's
output equals the old two-call pattern's, and that it halves the `decode_symbols` call
count on a mixed corpus.

### Hash once

`SqliteStore.put_edges` serialized an edge's provenance to canonical JSON twice per edge
— once inside `digest_json(provenance)` to derive the id, once explicitly for the storage
column — walking the same small object twice for no reason a caller could observe. It now
serializes once (`provenance_json = canonical_json(provenance)`) and derives the digest
from those same bytes (`digest_bytes(provenance_json.encode("utf-8"))`), which is
provably the same value `digest_json(provenance)` would have produced — `digest_json` is
defined as exactly that composition — so the id written is byte-identical, not merely
compatible.

This is deliberately **not** the more invasive version the item floats as an aside — "the
store's `put_edges` could accept the identity its caller already computed" — which would
mean changing `Store.put_edges`'s signature (a swappable-backend protocol, spec 02 §10)
and `merge_edges`'s return type, cascading through both real call sites and every test
that compares `merge_edges`'s output against a plain edge tuple. That is a real second
economy — an edge's identity is still computed three times across `symbol_edges`,
`merge_edges` and `put_edges` — but it is a different-shaped change than "S / fast /
low" asks for, and is left for a future item if the remaining cost is ever worth it.

## Measured

Both arms alternated on an idle machine (the discipline ADR-0145/0146 established), at
1 000 documents, reading the compiler's own per-stage timings out of the manifest for
**"incremental rebuild, nothing edited (the floor)"** — the no-op case 6.20 measured,
where nothing needs re-parsing and the whole cost is resolution:

| | before | after | |
|---|---:|---:|---|
| `symbols` stage, p50 | 250 ms | **188 ms** | **−24.8 %** |
| whole no-op floor, p50 | 1 918.9 ms | **1 676.2 ms** | **−12.6 %** |

A repeated **before** run (250 ms → 218 ms on the unpatched code, run-to-run) puts this
machine's noise on the `symbols` stage bucket at roughly 13 %, so −24.8 % is a real
reduction and not entirely the noise floor, though on one alternated pair it is not a
wide margin either — `tests/bench/test_symbol_resolution_bench.py` is the number to trust
for a small, low-variance regression check, and this end-to-end reading is context for
what it costs where the item was found.

**The `put_edges` fix does not show up in the `symbols` bucket, and that is itself worth
recording.** `put_edges` runs after `timer.lap("symbols")`, so its cost — including the
`canonical_json` call this item removes — falls into the gap between the last named stage
and the manifest's own `total`: **~190–200 ms on every run measured, before and after**,
unaccounted for by any stage name. That gap is a pre-existing instrumentation blind spot,
not something this item introduces or was asked to close, and it is the reason the
`put_edges` half of this fix is verified by `tests/bench/test_symbol_resolution_bench.py`
and by the byte-for-byte equivalence argument in *Decision* rather than by a stage-level
timing that cannot see it.

## Consequences

**Nothing about what is published moves.** The symbol table and the edge set are the same
records in the same order; `tests/test_typed_edges.py` and `tests/test_symbols.py` pass
unchanged, and no baseline, golden or gate is touched — the item said so in advance, and
the tests confirm it rather than merely repeat the claim.

**`tests/bench/test_symbol_resolution_bench.py`** is the reproducible perf claim AGENTS.md
§10 asks for. It compares the two coexisting code paths directly — the old two-call
pattern against `resolve_symbols_and_edges` — on a synthetic corpus with cross-document
uses, and separately benchmarks `put_edges` on a batch of edges as the floor a future
regression would be measured against.

**What is left.** The double- and triple-hashing across `symbol_edges` → `merge_edges` →
`put_edges` is real and unresolved; so is the rest of 6.19's list beyond the symbol stage.
Neither is this item's to close.
