# Benchmark Report: the ceiling a remote cache could buy

- **Date:** 2026-09-23
- **Version / commit:** v0.6.0 @ `9b8d8cc` — the compiler measured is that commit's; the
  instrument is `tools/measure_cache_ceiling.py` as committed with roadmap 7.4, which changes
  nothing under `src/`
- **Environment:** Windows 11 (10.0.26200), Intel family 6 model 151, 20 logical CPUs,
  31.7 GiB; CPython 3.12.10. A real-time scanner sits in the file path: a warm read of one small
  Markdown file costs **1.24 ms** p50 here (the calibration row below), about a hundred times an
  unencumbered SSD. Background load ≈ 10 % CPU (two IDEs and a media player) throughout.
- **Command:** `python tools/measure_cache_ceiling.py --out <scratch> --scales 250,1000
  --rounds 3 --harvest-root <git archive 9b8d8cc docs>
  --manifest docs/benchmarks/manifests/2026-09-23-the-ceiling-a-remote-cache-could-buy.json`
- **Manifest:** [`manifests/2026-09-23-the-ceiling-a-remote-cache-could-buy.json`](manifests/2026-09-23-the-ceiling-a-remote-cache-could-buy.json)

## Scenario

Roadmap 7.1 is a remote build cache, deferred by spec 06 §3 until *"≥ 1 team dogfooding with
measured duplicate-build pain"* — a condition nothing could measure. This is the measurement:
the most any cache could take off a build, taken before anybody designs one
([ADR-0154](../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)).

A cache can change exactly one kind of build. After the first build every rebuild is
incremental — a thousand-document no-op in 1.6 s since roadmap 6.20 — so what a cache prices is
a **cold build**, and within it only the two stages the compiler caches, parse and chunk.
Every arm therefore builds a **fresh checkout**: the corpus copied to a new path with every file
written anew, as `git clone` and `actions/checkout` produce. Only `.mycelium/` differs:

| Arm | What `.mycelium/` holds before the build | What it stands for |
|---|---|---|
| **cold** | nothing | every clone and CI runner, today |
| **seeded** | every parse and chunk artifact, with the index row naming it | a remote cache that answers instantly — the ceiling |
| **restored** | another checkout's whole `.mycelium/` | caching the directory in CI, today |
| **restored-mtimes** | the same, with each document given the mtime the cached checkout had | a directory cache over a checkout whose mtimes are deterministic |

Two preparations are timed apart from the builds they precede, because a real cache pays them:
**seeding** — each blob re-hashed and written, each row inserted, the local half of a fetch —
and **restoring**, the directory copied in. And the computation a cache miss runs (parse, chunk,
encode, hash) is timed **in memory** against what a hit runs instead (re-hash, decode), with no
file touched, so the part of a saving that is the compiler's can be told from the part that is
this filesystem's.

The corpus is the reference profile's generator at seed 20260923 (250 documents) and 20260924
(1 000), harvesting prose from `docs/` exported clean at `9b8d8cc` so no uncommitted file could
enter it. Two limits of that generator surfaced while preparing the run and are recorded rather
than fixed here, because fixing them changes every corpus it generates: it harvests **one** of
the two corpora it names ([BUG-0034](../bugs/2026/09/BUG-0034-the-reference-profile-harvests-one-of-the-two-corpora-it-names.md)),
and two of the thousand generated titles are YAML the parser refuses, so that corpus compiles
**998** documents ([BUG-0035](../bugs/2026/09/BUG-0035-a-generated-reference-title-can-be-yaml-the-parser-refuses.md)).
Every arm builds the same 998, so no comparison below is affected.

## Results

Three rounds per scale, the arms rotated one place per round. Every seeded and restored build hit
the cache for **every** document it compiled, and every build published `chunks`, `edges` and
`symbols` digests identical to the source build's.

**250 documents (1 264 chunks)**

| Arm | p50 | min – max | Rebuilt | Parse / chunk hits |
|---|---:|---:|---:|---:|
| cold | 15.53 s | 15.52 – 16.57 s | 250 | 0 / 0 |
| seeded | 7.37 s | 7.34 – 7.74 s | 250 | 250 / 250 |
| restored | 7.68 s | 7.63 – 8.02 s | 250 | 250 / 250 |
| restored-mtimes | **0.59 s** | 0.56 – 0.69 s | **0** | — |
| *seeding, before seeded* | 7.96 s | 7.63 – 8.02 s | | 500 rows |
| *restoring, before either restored arm* | 12.65 s | 11.73 – 16.20 s | | six copies |
| *compute a miss runs, in memory* | 2.50 s | 2.48 – 2.51 s | | |
| *compute a hit runs instead* | 0.24 s | 0.22 – 0.24 s | | |

**1 000 documents (998 compiled, 4 970 chunks)**

| Arm | p50 | min – max | Rebuilt | Parse / chunk hits |
|---|---:|---:|---:|---:|
| cold | 55.03 s | 54.07 – 57.53 s | 998 | 0 / 0 |
| seeded | 35.80 s | 35.65 – 36.05 s | 998 | 998 / 998 |
| restored | 40.10 s | 39.89 – 40.68 s | 998 | 998 / 998 |
| restored-mtimes | **1.56 s** | 1.55 – 1.71 s | **0** | — |
| *seeding, before seeded* | 39.07 s | 36.88 – 40.64 s | | 1 996 rows |
| *restoring, before either restored arm* | 54.00 s | 53.47 – 55.50 s | | six copies |
| *compute a miss runs, in memory* | 10.00 s | 9.98 – 10.05 s | | |
| *compute a hit runs instead* | 0.81 s | 0.80 – 0.82 s | | |

**What each p50 says** (seconds; a negative saving is a loss against building cold):

| | 250 documents | 1 000 documents |
|---|---:|---:|
| **The ceiling** — cold − seeded | **8.17** (52.6 %) | **19.23** (34.9 %) |
| of which computation — miss − hit | 2.26 (14.6 % of cold) | 9.19 (16.7 % of cold) |
| of which file operations the build skipped | 5.90 | 10.04 |
| The ceiling less the seeding — a remote cache that keeps its hits | +0.21 | **−19.84** |
| A restored directory, build only | +7.85 | +14.93 |
| … less the restore | −4.80 | −39.07 |
| A restored directory with mtimes kept, build only | **+14.94** (96.2 %) | **+53.47** (97.2 %) |
| … less the restore | +2.30 | −0.54 |

**Portability.** A checkout rewritten with CRLF endings — a Windows clone under
`core.autocrlf` — seeded from the LF build hit **250 of 250** and **998 of 998** parse and chunk
keys and published identical output. Every seeded arm already builds at a different path with
new mtimes, and hits every key too. Build keys are portable across paths, mtimes and line
endings.

**Where the build's own time goes** (median stage timers, 1 000 documents): cold spends
46.9 s compiling and 5.4 s writing the index; seeded compiles in 24.7 s and writes the index in
5.3 s; restored-mtimes compiles nothing and plans in 0.8 s. The plan stage runs about **3 s
longer** in both arms whose `.mycelium/` was written just before the build (4.8 s and 4.2 s,
against 1.7 s cold), most likely the scanner working through the files the seeding or the
restore had just written — not measured separately.

**Calibration:** a warm read of one small Markdown file, p50 **1.24 ms**, p95 1.84 ms, over
250 files of the corpus.

## Interpretation

**1. The most a remote stage cache could buy is about half a cold build at 250 documents and a
third at 1 000 — and on this machine most of that is not computation.** The ceiling is 8.2 s
and 19.2 s. The computation a hit saves is 2.3 s and 9.2 s — **about 9 ms a document on this
CPU**, and that is the part of the ceiling that travels to any machine. The rest is two blob
writes per document that a seeded build skips because the blobs are already there.

**2. A cache that keeps what it fetches pays those writes back, and here that erases the
saving or reverses it.** Seeding writes the same blobs the build no longer writes, and costs
8.0 s and 39.1 s. At 1 000 documents a remote cache at infinite bandwidth that persists its hits
locally — the ordinary design — would make a cold build **about 20 s slower** than building. The
reason is the calibration row: a small file here costs milliseconds, and every design that
materialises artifacts as files pays per file. A design that used a hit without persisting it
could approach the ceiling, and would give up what a persisted blob is for: restoring an older
snapshot (ADR-0016).

**3. The directory cache nobody needs to build does as well as the ideal stage cache, and
then the mtime stops it.** A restored `.mycelium/` builds in 7.7 s and 40.1 s — within a few
seconds of the seeded ceiling — because it hands over the same stage artifacts. It cannot do
better, because every document of a fresh checkout has a new mtime, a document record carries
its file's mtime (ADR-0009), and so every document is re-assembled and re-stored whatever the
cache holds. **Give the same checkout the mtimes the cache was built with and nothing is rebuilt
at all: 0.59 s and 1.56 s**, the incremental floor roadmap 6.20 measured — a cold build made
**26× and 35× faster** in the build itself, against the ideal remote cache's 2.1× and 1.5×. On
this machine the restore's own copy, 12.6 s and 54.0 s, is what spends it, and that too is per
file.

**4. What this does not say.** It is one machine, and the one whose file costs are the benchmark
README's reason for a calibration row; on an unencumbered SSD the seeding and the restore would
cost a fraction of what they cost here, and the ordering of the designs could change — *likely*,
from the calibration, and not measured. The seeded arm is a cache with no network at all. The
restore copies a directory locally rather than downloading and unpacking an archive, which is
what a CI cache does. Three rounds, one generated corpus per scale, and BUG-0034's single source.
The compute split is the most portable number here, and it is still one CPU's.

**What it answers.** Roadmap 7.1 as written — a Bazel-style remote cache of stage artifacts —
has a ceiling of about 9 ms of computation per document wherever it runs, and on a machine like
this one a design that keeps its hits loses to building cold at 1 000 documents. The larger
number in this report belongs to something 7.1 does not describe: a document record that did not
carry the checkout's mtime would let a cache nobody has to build make a fresh clone incremental.
That is filed as roadmap 7.7. Whether any of it is *pain* is the question the trigger now asks a
team to answer with its own corpus and its own cold-build rate (ADR-0154).

## Reproduce

```bash
git archive 9b8d8cc docs | tar -x -C <export>
git rev-parse 9b8d8cc > <export>/COMMIT
python tools/measure_cache_ceiling.py --out <scratch> --scales 250,1000 --rounds 3 \
    --harvest-root <export> --manifest <path>.json
```

The corpus digests in the manifest (`corpus.corpus_digests`) say whether a rerun generated the
same documents. Measure on an idle machine: every arm is wall-clock, and the rotation spreads
drift across the arms rather than removing it. On a team's own corpus:

```bash
python tools/measure_cache_ceiling.py --corpus <repository> --out <scratch> --rounds 1 \
    --people <N> --cold-builds-per-week <N>
```
