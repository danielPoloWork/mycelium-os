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

Same seed, same corpus, on any machine. The prose is harvested from the corpora this
repository already vendors, so the term distribution is real documentation rather than
random words; what it cannot reproduce is a real vault's link structure, and the report
states that limit beside the numbers.

## Results

One report per measured scenario, from [`template.md`](template.md). Keep the index newest-first.

| Date | Scenario | Version | Headline result | Report |
|------|----------|---------|-----------------|--------|
| 2026-09-18 | The incumbent reads a window: the agent-task comparison with the grep loop's read bounded, and the band it buys evidence along | v0.5.0 | The incumbent gained **13 tasks** and shed two-thirds of its cost. Our lead on evidence is **+2 tasks**, not +15, and the context ratio **5.7×**, not 33× — so the verdict gate's first condition no longer passes | [2026-09-18-the-incumbent-reads-a-window.md](2026-09-18-the-incumbent-reads-a-window.md) |
| 2026-09-18 | The hybrid path at the reference profile: the vector leg and the whole hybrid query at 10⁵ chunks | v0.5.0 | The vector leg is **inside** its 60 ms budget (43.2 ms fresh, 12.1 ms warm) — and the per-query precondition guarding it costs **129.9 ms**, three times the leg | [2026-09-18-the-hybrid-path-at-the-reference-profile.md](2026-09-18-the-hybrid-path-at-the-reference-profile.md) |
| 2026-09-17 | The reference profile: the three stated performance budgets, measured at the conditions they are stated for | v0.5.0 | All three missed. `mycelium_search` misses its 150 ms p95 **at every corpus size**, by a constant ~250 ms spent re-reading configuration before retrieval starts | [2026-09-17-reference-profile.md](2026-09-17-reference-profile.md) |
