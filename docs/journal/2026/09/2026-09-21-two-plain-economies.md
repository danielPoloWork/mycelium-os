# 2026-09-21 — two plain economies (roadmap 6.32)

- **Session scope:** roadmap 6.32 — the symbol stage decodes every use and hashes every
  edge twice, on every rebuild; decode once and hash once, and measure on both before
  deciding how far to take it.
- **PR:** #PRNUM (`perf/decode-and-hash-the-symbol-stage-once`). Follows #181, merged as
  `0239e81`.
- **Milestone 6:** 6.32 closed. 6.33–6.37 remain open.
- **Decision it records:**
  [ADR-0147](../../../adr/0147-decode-and-hash-the-symbol-stage-once.md).

## Two functions that are always called together, decoding separately

`resolve_symbols` builds the symbol table; `symbol_edges` derives the `defines` and
`references` edges over it. Every real caller — the build orchestrator, `mycelium
rollback`'s restore, the test helper both files already had — calls them back to back,
because an edge can only point at a symbol the table already resolved (ADR-0074). Neither
function knew about the other, so each decoded every document's `symbols` and
`symbol_uses` from `doc_state`'s stored JSON on its own: three decodes of `symbols`, two
of `symbol_uses`, per rebuild.

The fix is a shared `_Facts` record — a document's `symbols` and `symbol_uses`, decoded
once — built by `_facts_of`, and a new `resolve_symbols_and_edges` entry point that calls
it once and threads the result through both passes. `resolve_symbols` and `symbol_edges`
keep decoding on their own when called alone, because a caller — or a test — that only
needs one of the two should not have to build the other to get it.

## The second economy was smaller in scope than the item's own aside

The item noted, almost in passing, that `put_edges` *"could accept the identity its
caller already computed"* — `symbol_edges` already builds a dict keyed by each edge's
identity to deduplicate, and `put_edges` recomputes the same identity from scratch when
writing it. Chasing that literally would change `Store.put_edges`'s signature — a
swappable-backend protocol (spec 02 §10) — and `merge_edges`'s return type, cascading
through both real call sites and every test that compares `merge_edges`'s output against
a plain edge tuple. That is a real, larger economy (an edge's identity is still computed
three times across `symbol_edges` → `merge_edges` → `put_edges`), and a different-shaped
change than "S · route: fast / low" asks for.

What stayed in scope: `put_edges` itself serialized an edge's provenance to canonical
JSON **twice** — once inside `digest_json(provenance)` to derive the id, once explicitly
for the storage column — walking the same small object twice for no reason a caller could
observe. Serializing once and deriving the digest from those same bytes
(`digest_bytes(provenance_json.encode("utf-8"))`) is provably the same value
`digest_json` would have produced, so the id written is byte-identical, not merely
compatible with what shipped before.

## Measuring found the fix's shadow, not just its size

Alternating before/after on an idle machine at 1 000 documents, reading the compiler's
own per-stage timings: the no-op floor's `symbols` bucket fell **250 → 188 ms (−24.8 %)**,
against a same-code repeat of 218 ms that puts this machine's noise on that one bucket
around 13 %. Real, on the small side of convincing from one pair — which is what the
benchmark comparing the two coexisting code paths directly is for going forward, rather
than a number that ages the moment the machine changes.

The whole no-op floor fell further than the `symbols` bucket alone predicts — 1 918.9 →
1 676.2 ms, −12.6 %. `put_edges` runs *after* `timer.lap("symbols")`, so the second
economy's saving does not land in that bucket at all; it falls into a gap between the
last named stage and the manifest's own total that measured **~190–200 ms on every run,
before and after** — a pre-existing instrumentation blind spot this measurement noticed
rather than one this item was asked to close. Worth naming rather than quietly working
around: a reader of the manifest's stage breakdown has been missing a fifth of the no-op
floor's own accounting the whole time.

## What shipped

Nothing published moves — `tests/test_typed_edges.py` and `tests/test_symbols.py` pass
unchanged, and two new tests in the former pin the exact claims: the combined function's
output equals the old two-call pattern's, and it halves the `decode_symbols` call count
on a mixed corpus (a definer, a resolvable use, an ambiguous one, and a document that
both defines and uses). `tests/bench/test_symbol_resolution_bench.py` is the durable
regression guard AGENTS.md §10 asks for.

The larger identity-computed-three-times economy stays open, alongside the rest of
6.19's list beyond the symbol stage. Neither is this item's to close.
