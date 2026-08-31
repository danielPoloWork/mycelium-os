# 2026-08-31 — measuring the kernel, and finding the baseline was wrong (roadmap 3.16)

- **Session scope:** roadmap 3.16 — would a quantised kernel win back the 47 ms an int8 first
  pass needs? ADR-0028 had identified the algorithm and named the blocker as a dependency.
- **PR:** #46 (`feat/quantised-kernel`). Follows #45 (3.15), merged as `66fde7b`.
- **Milestone 3:** 3.1–3.16 done; 3.17 and 3.18 open.

## The kernel works. That turned out not to be the question.

`onnxruntime`'s `MatMulInteger` multiplies int8 in place: **26 ms** over 10^5 vectors, against
numpy's 123 ms for the same arithmetic with a widening copy. Exactly the 3× ADR-0028
predicted.

Then the baseline refused to sit still. Timing the plain float32 scan one query per *process*
gave ~31 ms. The committed benchmark said 73–78.

## Printing every iteration instead of the median

```text
rounds=1:  32.3
rounds=2:  31.4  71.2
rounds=3:  29.9  70.9  70.5
rounds=5:  32.4  72.8  75.1  74.2  73.2
```

The first query in a process costs ~31 ms. Every later one costs ~71 — because the harness
built a fresh `np.memmap` of the same 154 MB file each time. **No code path re-maps**: a store
maps its pack once per handle, so a CLI invocation maps once and exits and a server maps once
and re-uses it. The harness measured a third pattern that exists only in harnesses and labelled
it "cold".

The median is what hid it. Ten samples, nine of them the artifact, and the number that came out
looked stable and careful.

## What it costs to have been wrong

The gap ADR-0026 recorded at 10^5 — "17 % over budget" — does not exist. Roadmap 3.14 was filed
to close it and spent an item's worth of measurement refusing an index for a budget that was
already met. That refusal survives and gets *stronger*: on the corrected numbers a partial scan
saves 6 ms rather than 40, for the same third-to-two-thirds of the answer. Easier to refuse, for
worse reasons than I had.

And 3.16 dissolves: the kernel must beat 31 ms, not 78, and a fresh `InferenceSession` costs
44 ms before the first multiply. End to end in a fresh process it is ~357 ms against ~32 for the
scan it would replace. Faster than numpy at the thing numpy does badly; slower than not needing
it.

## What I am taking from this

**"Cold" is not a measurement.** Cold disk, cold page cache and cold process are three different
numbers. I used one word for all three across three items and never defined it, which is exactly
how the wrong one gets reported.

**A median over in-process repetitions is the wrong shape for anything that maps a large file.**
It is the right shape for arithmetic, and that is why it was reached for without thinking.

**The correction is louder than the original claim.** Two ADRs carry pointers, the bug is in the
ledger as BUG-0015, and the `search_vectors` docstring is corrected for the second time in three
items — which is its own small argument against embedding numbers in prose next to the code they
describe.

The measurement of the kernel is kept even though nothing ships from it. If the corpus envelope
ever moves past D-002's 10^5, 26 against 123 is worth having already measured.
