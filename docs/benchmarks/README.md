# Benchmarks

Reproducible performance measurements for `mycelium-os`. Any performance claim in the
spec, README, or a PR must be backed by a benchmark here and by code under
`tests/bench/`. Numbers without a reproducible method
are not evidence.

## Methodology

- **Harness:** `Hatch (PEP 517/518, pyproject.toml)` builds the bench target; run with `pytest tests/bench --benchmark-only`.
- **Environment:** record the machine (CPU, RAM, OS), the toolchain version, and the build
  configuration (release/optimized) with every result — a number without its environment is
  not comparable.
- **Discipline:** warm up, run multiple iterations, report a central tendency **and** spread
  (e.g. median + p99), and pin the commit SHA the run was taken at.
- **Regression gate:** the CI `benchmark` job runs the suite; a result is a regression only
  against a recorded baseline on comparable hardware (note when CI hardware is too noisy to
  gate and the run is informational).

### Two rules added at roadmap 6.4 (ADR-0120)

- **A report cites a run manifest, and the manifest is committed beside it.** Spec 04 §7.5:
  *"a report without a manifest is exploratory and cannot satisfy a gate."* Manifests live in
  [`manifests/`](manifests/); `tools/consistency_lint.py`'s `benchmarks` check refuses a
  report that cites none, a citation that resolves to nothing, and a manifest no report
  cites. What is *inside* a manifest is checked by
  `python tools/benchmark_reference_profile.py --check`.
- **Record what a file open costs on the machine.** Every build figure here is dominated by
  it, and it is not a property of the compiler: on the machine of record a warm read of a
  4 KB Markdown file costs ~1.3 ms, about a hundred times an unencumbered SSD, because a
  real-time malware scanner sits in the open path. Without that constant a reader cannot
  tell a compiler cost from a machine cost, and the incremental-build numbers are mostly the
  second. The reference-profile tool measures it over the corpus it is about to build and
  writes it into the manifest as a measurement like any other.

### The reference profile

Three budgets — cold build (spec 01 §8), incremental rebuild (NFR-3), and end-to-end search
(NFR-2, spec 04 §1) — are stated against a **reference profile** of 10⁵ chunks on local
hardware. That corpus is too large to commit, so it is *generated*:

```bash
python tools/benchmark_reference_profile.py --out <scratch-dir> \
    --manifest docs/benchmarks/manifests/<date>-reference-profile.json
```

Same seed, same corpus, on any machine. The prose is harvested from two corpora this
repository already holds — the vendored uv documentation and its own `docs/` — so the term
distribution is real documentation rather than random words; what it cannot reproduce is a
real vault's link structure, and the report states that limit beside the numbers. Each
manifest names the sources under `corpus.sources`: until roadmap 7.6 the first path did not
exist and was skipped in silence, so every corpus generated before it came from `docs/`
alone (BUG-0034), and the two series are not the same corpus. For a published run pass
`--harvest-root` a clean export of the commit (`git archive <sha> docs
eval/corpora/uv-docs/docs`), so nothing outside that commit — the report being written, an
untracked note — enters the corpus.

## Results

One report per measured scenario, from [`template.md`](template.md). Keep the index newest-first.

| Date | Scenario | Version | Headline result | Report |
|------|----------|---------|-----------------|--------|
| 2026-09-25 | A restored checkout rebuilds nothing: the cache-ceiling arms after roadmap 7.7 took the timestamps out of the Document record | v0.6.0 + 7.7 | A fresh checkout with another's `.mycelium/` builds in **5.4 s** at 1 000 documents where it took 40.1 s, with **0 documents rebuilt**; the remaining 3 s over the mtime control is the memo re-reading every file once | [2026-09-25-a-restored-checkout-rebuilds-nothing.md](2026-09-25-a-restored-checkout-rebuilds-nothing.md) |
| 2026-09-24 | The corpus the profile names: the generated curve before and after roadmap 7.6, same commit, same seed | v0.6.0 | The series breaks here — every earlier manifest was harvested from `docs/` alone, and **no published run had compiled the size it named** (998 of 1 000, 249 of 250); the after run is the first at 1 000 that is 1 000. The compiler did not change, and the table says so | [2026-09-24-the-corpus-the-profile-names.md](2026-09-24-the-corpus-the-profile-names.md) |
| 2026-09-23 | The ceiling a remote cache could buy: fresh checkouts built with nothing, every stage artifact, and a whole `.mycelium/` in the cache, at 250 and 1 000 documents | v0.6.0 | The ideal remote cache takes **35 %** off a thousand-document cold build, **9 ms a document** of it computation, and one that keeps its hits here is **20 s slower** than building; the same checkout given its cache's mtimes rebuilds **nothing**, in 1.6 s | [2026-09-23-the-ceiling-a-remote-cache-could-buy.md](2026-09-23-the-ceiling-a-remote-cache-could-buy.md) |
| 2026-09-20 | The budget we could not spend: the agent-task band with our own constant swept beside the incumbent's two | v0.5.0 | At 16 000 tokens **19/22, 22/22 and 21/22** where the arm saturated at ten results before — and a caller at the tool's *default* `k` saturates too | [2026-09-20-the-budget-we-could-not-spend.md](2026-09-20-the-budget-we-could-not-spend.md) |
| 2026-09-20 | The precondition that counted: the hybrid yes/no `search` asks per query, before and after roadmap 6.27 | v0.5.0 | **91.0 ms p50 to 0.013 ms** at 10⁵ vectors — the aggregate read every row to answer a yes/no, and it was **8.2× the vector leg it guards** | [2026-09-20-the-precondition-that-counted.md](2026-09-20-the-precondition-that-counted.md) |
| 2026-09-19 | The agent-task suite on a corpus we did not write: the comparison on `uv-docs`, on its ingested twin, and on this repository at the same commit | v0.5.0 | On documentation nobody here wrote the lead is **+5 tasks** (18/22 against 13/22) at **6.7×** the context, where our own corpus gives +1 — the verdict gate's first condition passes on one corpus and fails on the other, and which corpus it is read on is now the question | [2026-09-19-the-suite-on-a-corpus-we-did-not-write.md](2026-09-19-the-suite-on-a-corpus-we-did-not-write.md) |
| 2026-09-19 | The incremental floor, before and after roadmap 6.20: every whole-corpus pass a rebuild makes, and the rebuild against corpus size | v0.5.0 | A no-op rebuild of 1 000 documents **5.1 s → 1.6 s** and a single-document edit **5.8 s → 1.7 s**. The read of every file the item named was **54 %** of the floor; three filesystem probes nobody had named were another third; nothing left in a rebuild opens a document. Taken on a contended machine, and the report says so first | [2026-09-19-the-floor-was-the-whole-corpus.md](2026-09-19-the-floor-was-the-whole-corpus.md) |
| 2026-09-19 | The quadratic in the lexical index removed, and a profile of what the cold build spends its time on now | v0.5.0 | Cold build **193.5 s to 91.7 s** at 1 000 documents, and cost per document **flat** (93 ms at 250, 92 at 1 000) where it grew before. What remains is not algorithmic: **~79 s of it is 2 995 content-addressed blob writes** | [2026-09-19-the-quadratic-in-the-lexical-index.md](2026-09-19-the-quadratic-in-the-lexical-index.md) |
| 2026-09-18 | The incumbent reads a window: the agent-task comparison with the grep loop's read bounded, and the band it buys evidence along | v0.5.0 | The incumbent gained **13 tasks** and shed two-thirds of its cost. Our lead on evidence is **+2 tasks**, not +15, and the context ratio **5.7×**, not 33× — so the verdict gate's first condition no longer passes | [2026-09-18-the-incumbent-reads-a-window.md](2026-09-18-the-incumbent-reads-a-window.md) |
| 2026-09-18 | The hybrid path at the reference profile: the vector leg and the whole hybrid query at 10⁵ chunks | v0.5.0 | The vector leg is **inside** its 60 ms budget (43.2 ms fresh, 12.1 ms warm) — and the per-query precondition guarding it costs **129.9 ms**, three times the leg | [2026-09-18-the-hybrid-path-at-the-reference-profile.md](2026-09-18-the-hybrid-path-at-the-reference-profile.md) |
| 2026-09-17 | The reference profile: the three stated performance budgets, measured at the conditions they are stated for | v0.5.0 | All three missed. `mycelium_search` misses its 150 ms p95 **at every corpus size**, by a constant ~250 ms spent re-reading configuration before retrieval starts | [2026-09-17-reference-profile.md](2026-09-17-reference-profile.md) |
