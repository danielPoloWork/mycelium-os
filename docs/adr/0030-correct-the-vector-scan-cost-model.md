# ADR-0030: Correct the vector scan's cost model — the budget was met, and the benchmark was wrong

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §1
- **Related:** [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) (corrected),
  [ADR-0028](0028-keep-the-vector-scan-exact.md) (premise corrected, decision upheld);
  [BUG-0015](../bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md); roadmap 3.16

## Context

Roadmap 3.16 asked one question: an int8 first pass with an exact rescore returns the exact
top-50 (recall 1.000, measured) but is slower under numpy, so would `onnxruntime`'s quantised
kernel — already an optional dependency here — win back the 47 ms it needs to?

Measuring it answered a different question first. The `MatMulInteger` kernel does what it was
supposed to: **26 ms against numpy's widening 123 ms** over 10^5 vectors. But the baseline it
had to beat would not sit still. Timing the plain float32 scan one query per *process* gave
~31 ms, where the committed benchmark reported 73–78 ms.

The difference is the benchmark. `timed()` called its subject repeatedly inside one process,
and each call built a fresh `np.memmap` of the same 154 MB file. Printing every iteration
instead of the median shows it immediately:

```text
rounds=1:  32.3
rounds=2:  31.4  71.2
rounds=3:  29.9  70.9  70.5
rounds=5:  32.4  72.8  75.1  74.2  73.2
```

The first query in a process costs ~31 ms; every later one that re-maps the file costs ~71.
No code path re-maps: a store maps its pack once per handle (ADR-0026), so a CLI invocation
maps once and exits, and a server maps once and re-uses it. The harness measured a third
pattern that exists only in harnesses, and called it "cold". Recorded as
[BUG-0015](../bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md).

## Decision

**The cost model is corrected, and the gap ADR-0026 recorded does not exist.** Measured one
query per fresh process at the reference profile (10^5 chunks, 154 MB):

| pattern | cost | against the 60 ms budget |
|---|---:|---|
| fresh process, one query (a CLI invocation) | **~31 ms** | **within** |
| long-lived handle, per query (the MCP server) | ~1 ms | far within |
| re-map per query in one process | ~71 ms | *no code path does this* |

**Two ADRs are corrected, and neither decision changes.**

ADR-0026 said the first query in a fresh process was ~70 ms and 17 % over budget, and filed
roadmap 3.14 to close the gap. There is no gap. Everything else in ADR-0026 stands: the
packed matrix took 10 000 chunks from 92.97 ms to 2.88 ms, and its fresh-process figure at
that size (23.42 ms) was measured with a subprocess and is correct.

ADR-0028 refused an approximate index against a premise that was wrong, and the refusal gets
*stronger* rather than weaker. On the corrected numbers a partial scan of 25 % of the rows
saves 6 ms — 25 ms against 31 — and costs between a quarter and two thirds of the true top-50.
An index that buys 6 ms for a third of the answer is easier to refuse than one that buys 40.

**Roadmap 3.16 is closed as unnecessary, on its own evidence.** The quantised kernel works —
26 ms against numpy's 123 — but there is nothing to win: it must beat 31 ms, not 78, and a
fresh `InferenceSession` costs **44 ms** before the first multiply. In a fresh process the
whole path measures ~357 ms against ~32 ms for the scan it would replace. In a long-lived
process the session amortises, but that process already answers in ~1 ms from a held mapping.
The kernel is faster than numpy at the one thing numpy does badly, and slower than not needing
it.

## Alternatives Considered

- **Keep the old numbers and ship the kernel anyway**, since 26 ms beats 78. Rejected: 78 was
  never real. Shipping against a number the harness invented is how a project acquires a
  dependency it cannot justify later.
- **Treat 71 ms as the number to beat**, on the grounds that some future code might re-map per
  query. Rejected: that is optimising for a bug, and if such a path appeared the fix would be
  to hold the mapping, which the store already does.
- **Amend ADR-0026 and ADR-0028 in place.** Rejected: an ADR records what was decided and on
  what evidence, and quietly rewriting the evidence removes the only trace that a measurement
  can be wrong. They carry pointers here instead.
- **Fix the harness and say nothing**, since no shipped behaviour changed. Rejected: two ADRs,
  a roadmap item and a docstring in `src/` carried the wrong number. Silence would leave the
  next reader to re-derive it.

## Consequences

- **The candidate-generation budget is met across the v1 envelope**, in both patterns real
  code has. Spec 04 §1 needed no gap noted against it, and the roadmap no longer carries one.
- **`tools/measure_vector_index.py` times one query per child process.** The helper that
  computes a median over in-process repetitions was the defect, and medians are exactly what
  hides it — the finding is only visible when every iteration is printed.
- **"Cold" is not a measurement.** Cold disk, cold page cache and cold process are three
  different things; this project means *cold process*, and the tool now says so where it
  measures it.
- **The `onnxruntime` kernel measurement is kept even though it ships nothing**: 26 ms against
  123 for the same arithmetic is worth knowing if the corpus envelope ever moves past 10^5,
  which is where D-002 stops and a different conversation begins.
- No product code changes. The docstring in `search_vectors` is corrected for the second time
  in three items, which is its own small lesson about numbers embedded in prose.

## References

- Spec 04 §1 (candidate-generation budget); D-002 (corpus envelope)
- [BUG-0015](../bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md) — the harness defect
- `tools/measure_vector_index.py` — both tables, now measured per process
