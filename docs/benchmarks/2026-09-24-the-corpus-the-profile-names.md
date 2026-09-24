# Benchmark Report: the corpus the profile names, before and after roadmap 7.6

- **Date:** 2026-09-24
- **Version / commit:** v0.6.0 @ `df43af8` — the compiler is the same in both runs; only
  `tools/benchmark_reference_profile.py`'s generator differs (before: `df43af8` as
  committed; after: the 7.6 change, harvesting from `git archive df43af8 docs
  eval/corpora/uv-docs/docs`)
- **Environment:** Windows 11 (10.0.26200), Intel family 6 model 151, 20 logical CPUs,
  31.7 GiB; CPython 3.12.10. A real-time scanner sits in the file path: a warm read of one
  small Markdown file costs 1.29–1.45 ms here (calibration rows in both manifests). The two
  runs were taken back to back on an otherwise idle machine.
- **Command:** `python tools/benchmark_reference_profile.py --out <scratch> --scales 250,1000
  --no-reference --manifest <path>.json`, the after run with `--harvest-root <export>`
- **Manifests:**
  [`manifests/2026-09-24-the-corpus-the-profile-names-before.json`](manifests/2026-09-24-the-corpus-the-profile-names-before.json),
  [`manifests/2026-09-24-the-corpus-the-profile-names.json`](manifests/2026-09-24-the-corpus-the-profile-names.json)

## Scenario

Roadmap 7.6 fixed two defects in the generator every reference-profile number is taken over
([BUG-0034](../bugs/2026/09/BUG-0034-the-reference-profile-harvests-one-of-the-two-corpora-it-names.md),
[BUG-0035](../bugs/2026/09/BUG-0035-a-generated-reference-title-can-be-yaml-the-parser-refuses.md)).
It harvested prose from one corpus while naming two, because the second path never existed
and a missing source was skipped in silence; and it wrote a harvested heading into
frontmatter with only its colon escaped, so a heading YAML refuses as a plain scalar
quarantined its document and the corpus compiled short of the size it named.

Both fixes change every corpus the generator writes afterwards, so the item asked for the
before and the after at the same commit, published, so that the series in this directory
says where its corpus changed rather than drifting under a constant. This report is that
discontinuity. It is **not** a claim that the compiler got faster or slower: the compiler did
not change, and a cold build is one sample per scale here.

## Results

The same seed (20260917), the same compiler, the same machine, the same hour.

**What the generator produced**

| | before | after |
|---|---:|---:|
| sources harvested | `docs/` (the uv path skipped, unreported) | `docs/` + `eval/corpora/uv-docs/docs` |
| blocks / headings harvested | 5 998 / 2 494 | 8 767 / 3 046 |
| words harvested | 369 368 | 433 710 |
| 250 generated → compiled | **249** (one quarantined) | 250 |
| 1 000 generated → compiled | 1 000 | 1 000 |
| chunks at 250 / 1 000 | 1 253 / 4 966 | 1 243 / 4 877 |

**What the compiler measured over it** (p95 unless stated; cold build is one sample)

| Measurement | before, 250 | after, 250 | before, 1 000 | after, 1 000 |
|---|---:|---:|---:|---:|
| cold build (one sample) | 20.4 s | 18.0 s | 67.2 s | 70.9 s |
| no-op rebuild, 20 builds | 803 ms | 590 ms | 1 455 ms | 1 505 ms |
| one-document edit, 20 edits | 850 ms | 572 ms | 1 390 ms | 1 714 ms |
| `search`, warm store | 26.3 ms | 30.7 ms | 98.2 ms | 74.2 ms |
| `mycelium_search`, end to end | 43.4 ms | 54.1 ms | 101.5 ms | 86.9 ms |
| file open, warm (calibration) | 1.45 ms | 1.29 ms | 1.33 ms | 1.39 ms |

## Interpretation

**1. The series breaks here, and the manifests say so.** Every manifest in this directory
carries `corpus.sources`; the ones before this report list `eval/corpora/uv-docs/knowledge`,
a path that never existed, and were generated from this repository's `docs/` alone. From
this report on the list reads `eval/corpora/uv-docs/docs`, and the corpus is what the
docstring always said it was. A number from one side of the break is not the same corpus as
a number from the other, at any seed.

**2. No published reference-profile run had compiled the size it named.** Reading every
manifest's `scales[].documents` while preparing this report: the 2026-09-17 profile — whose
text says the cold-build budget was measured *"at exactly the stated size"* — compiled
**998** of 1 000; the 2026-09-19 floor report **998, 2 493 and 4 988**; the 2026-09-20
precondition report **249, 999, 2 498 and 4 989**; and the before run here **249** of 250.
Spec 01 §8's budget is stated at 1 000 documents, and it had never been measured at 1 000.
The shortfall is two tenths of a percent and moves no conclusion those reports drew, but a
report that names a size it did not compile is the thing `compiled_all` now refuses, and
the after run is the first at 1 000 that is 1 000.

**3. The differences in the second table are the corpus, not the compiler.** With one cold
sample per scale and a ±8 % noise floor on this machine (roadmap 6.30 measured it), a
250-document build 2.4 s faster and a 1 000-document one 3.7 s slower are two corpora of
different composition, not a trend. The one row worth a sentence is warm search at 1 000
documents, 98 → 74 ms p95: the after corpus draws from a larger pool of blocks, so a term's
matching set is a smaller fraction of it, which the 2026-09-17 report predicted when it
called the generated vocabulary *closed*. It is one run, and it is reported, not claimed.

**4. What this does not do.** It does not re-take any earlier report's number: those stand
as measurements of the corpus their manifest records, at the commit it names. It does not
re-baseline the 10⁵-chunk query profile, which `--query-scale` writes from the same
harvested blocks and is therefore also a different corpus after this change — the next run
that needs that number takes it fresh, and this report is the reason its manifest will not
match the last one's. And it does not re-run roadmap 7.4's cache-ceiling measurement, whose
comparisons are all inside one run.

## Reproduce

```bash
mkdir export && git archive df43af8 docs eval/corpora/uv-docs/docs | tar -x -C export
git rev-parse df43af8 > export/COMMIT
# after: the generator as of roadmap 7.6
python tools/benchmark_reference_profile.py --out <scratch> --scales 250,1000 \
    --no-reference --harvest-root export --manifest after.json
# before: the generator at df43af8, from a worktree of that commit
git worktree add --detach before df43af8 && cd before && uv sync --all-extras --dev --frozen
python tools/benchmark_reference_profile.py --out <scratch> --scales 250,1000 \
    --no-reference --manifest before.json
```

The before run harvests its own worktree's `docs/`, which at `df43af8` is the export's
`docs/`; it cannot take `--harvest-root`, because that flag arrived with the fix.
