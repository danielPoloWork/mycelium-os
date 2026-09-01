# 2026-09-01 — keeping the original (roadmap 4.2)

- **Session scope:** roadmap 4.2 — CAS custody of originals, KIR v0 hardened on hostile
  fixtures, the opaque-node escape hatch (spec 02 §§3-5 and §8, D-004/D-005/D-017).
- **PR:** #52 (`feat/cas-custody-and-hostile-fixtures`). Follows #51 (4.1), merged as
  `dfce101`.
- **Milestone 4:** 4.1 and 4.2 done; 4.3–4.9 open.

## The CAS was already there, and it was the wrong lifecycle

4.1 acquired bytes and threw them away. Storing them looked like a two-line change — a CAS
exists, its docstring even says *"ingestion (milestone 4) shares this module instead of
growing a second CAS"* — until you read what the rest of that docstring promises:

> Nothing in the published snapshot references the CAS — it is purely reuse, so deleting the
> whole directory costs one clean rebuild and nothing else (D-005).

`mycelium gc` believes that. It computes a live set from retained snapshots and cache rows
and deletes every blob outside it. Put an acquired PDF in there and the first `gc` deletes
the evidence a citation quotes.

The fix is not clever, but the reasoning is the item: **tier 1 shares the CAS's address
space and must not share its lifecycle.** Architecture §4 puts tier 1 "under
`.mycelium/cas`", so custody is a named subtree the sweep skips by name — and
`CUSTODY_DIRNAME` lives in `build/cas.py`, beside the layout it excepts, so the module that
deletes blobs and the module that writes them read the same rule from the same place. The
tempting alternative — add custody digests to the live set — fails on a detail worth
writing down: the live set is computed from the SQLite store, and the store is tier 3.
Delete it, which is a supported and documented thing to do, and every original becomes
unreferenced. **Tier 1 cannot be pinned by tier 3.** The custody record therefore lives
beside its blob on disk, not in the store, for the same reason.

The load-bearing test is the one that would have caught the original mistake: build a
repository, put an original in custody next to a collectable cache blob, run
`gc(keep=0, cache_max_age_days=0)` — the most aggressive sweep the command offers — and
assert the cache blob is gone and the evidence is not.

## The hostile fixtures found two real defects, which is what they are for

I generated the suite before writing any guard, ran it through the four engines, and got
numbers rather than opinions:

| depth | docling | pandoc |
|---|---|---|
| 200 | 0.6 s | 0.13 s |
| 1 000 | 7.3 s | **`RecursionError`** |
| 5 000 | 45.3 s | `RecursionError` |
| 50 000 | **no return in 300 s** | `RecursionError` |

Two defects, both shipped in 4.1:

1. **docling's cost is superlinear in structure**, and the connector's 64 MiB ceiling
   bounds bytes. A 550 KB file was a denial of service on the build.
2. **`RecursionError` escaped `parse()`** — `json.loads` raises it, nothing was catching it,
   so a hostile document crashed ingestion rather than being quarantined by it. The typed
   error taxonomy 4.1 was so careful about had a hole straight through it.

The answer is to bound *shape*, in layers, before any engine runs: an archive's own
directory is read for a bomb (51 KB declaring 50 MB), markup is scanned in one linear pass
for nesting depth, and the shared `KirBuilder` caps node count and text — so a new adapter
inherits the last defence without knowing it exists. Everything in the suite now fails in
under 0.1 s. The real fixtures all pass every guard, which is asserted, because a guard that
refuses honest documents is worse than no guard.

I considered a wall-clock timeout on the parse instead. It catches more, and I refused it as
the primary defence: an in-process timeout in CPython cannot reliably interrupt a C
extension, the threshold is a guess about machine speed, and a document that succeeds on a
laptop and fails in CI is worse than one refused everywhere for a stated reason.

## Custody before compilation

`ingest_source` stores the original *before* it decides whether the document is worth
parsing. That costs a write for a file that turns out to be hostile. It buys the thing 4.6
will need: a quarantined file whose bytes were never kept cannot be re-examined, and
re-examining them is the whole reason to quarantine rather than drop. Every hostile fixture
has a test asserting its bytes are in custody after its refusal.

## The escape hatch was completed by removing something

4.1's pandoc adapter set an opaque node's `blob` to `digest_bytes(payload)` — a digest of
bytes it never stored. I had even written a test asserting `blob is not None` and called it
"addressable, not merely counted". It was a dangling pointer with a confident docstring.

The fix is smaller than the mistake: where the payload is literal source text it is kept as
the node's `text`, which is what ADR-0006 already does with raw HTML in authored Markdown,
and `blob` is reserved for a payload that is genuinely in custody. Storing opaque payloads
properly would need a sink threaded through the `Parser` protocol, and widening a contract
that froze one PR ago, for a field with no consumer, is a decision to make when 4.3's
fidelity reports actually need extracted images.

## What I did not name

`safety.py` has no row in the patterns catalogue. "Guard" is not in the canonical taxonomy;
*Guarded Suspension* is a concurrency pattern about blocking, and nothing here blocks;
*Specification* composes predicates as objects, and these are four fixed checks with no
composition and no caller that wants any. Both are recorded under **Rejected** with the
reason, because §8 forbids force-fitting and the next reader will ask the same question.
The honest description is "four functions that raise".

## What this deliberately does not do

No evidence projection or fidelity reports (4.3), no secret scan and no decision about what
happens to a failed document (4.6), no `mycelium ingest` command. `ingest_source` raises a
typed error and leaves the choice to its caller — which is what lets 4.6 quarantine, a test
assert, and a future build stage record.
