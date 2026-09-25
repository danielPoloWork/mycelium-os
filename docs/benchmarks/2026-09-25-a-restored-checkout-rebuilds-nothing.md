# Benchmark Report: a restored checkout rebuilds nothing

- **Date:** 2026-09-25
- **Version / commit:** v0.6.0 @ `8670f3e` plus roadmap 7.7's change (the working tree of
  the pull request; the manifest's `commit` names the base)
- **Environment:** Windows 11 (10.0.26200), Intel family 6 model 151, 20 logical CPUs,
  31.7 GiB; CPython 3.12.10. A real-time scanner sits in the file path (a warm small-file read
  costs ~1.3 ms here). Two rounds per scale, arms rotated; the machine otherwise idle.
- **Command:** `python tools/measure_cache_ceiling.py --out <scratch> --scales 250,1000
  --rounds 2 --harvest-root <git archive 8670f3e docs eval/corpora/uv-docs/docs>
  --manifest docs/benchmarks/manifests/2026-09-25-a-restored-checkout-rebuilds-nothing.json`
- **Manifest:** [`manifests/2026-09-25-a-restored-checkout-rebuilds-nothing.json`](manifests/2026-09-25-a-restored-checkout-rebuilds-nothing.json)

## Scenario

The same instrument and the same four arms as the
[2026-09-23 report](2026-09-23-the-ceiling-a-remote-cache-could-buy.md), run after roadmap
7.7 took `created_at`/`updated_at` out of the Document record (D-032,
[ADR-0157](../adr/0157-take-the-timestamps-out-of-the-document-record.md)). That report's
largest number was the **restored** arm — another checkout's whole `.mycelium/`, copied
in — still re-assembling and re-storing every document, because each record carried its
file's mtime and a fresh checkout's mtimes are all new; only the **restored-mtimes** control,
which gave the checkout the cached mtimes back, rebuilt nothing. This run asks whether the
two arms now coincide, which is the claim the change makes.

## Results

p50 of two rounds; cold build is two samples.

| Arm | 250 documents | 1 000 documents | 1 000, on 2026-09-23 |
|---|---:|---:|---:|
| cold | 14.2 s | 58.3 s | 55.0 s |
| seeded (every stage artifact) | 6.6 s | 37.0 s | 35.8 s |
| **restored** (whole `.mycelium/`) | **0.8 s** | **5.4 s** | 40.1 s |
| restored-mtimes (control) | 0.6 s | 2.4 s | 1.6 s |

Every restored build reported **0 documents rebuilt** at both scales, in every round; every
seeded build hit all its stage keys; the CRLF checkout hit 250 of 250 and 1 000 of 1 000;
and every arm's `documents`, `chunks`, `edges` and `symbols` digests equalled the source
build's — the `documents` digest for the first time, since it no longer folds a timestamp.

## Interpretation

**1. The restored arm rebuilds nothing, and the number is the memo, not the compiler.**
5.4 s against 40.1 s at 1 000 documents — a cold build that a directory cache nobody had to
build now makes incremental. The 3 s between `restored` and its control is what a
mtime-keyed memo costs on a checkout whose mtimes are all new: every file is read and
digested once (a thousand ~1.3 ms reads here, in the scanner's path) and the memo is
refreshed, and the second build pays neither. The control keeps its lead only because its
memo already matches; nothing in either arm re-assembles a record.

**2. The ceiling of a remote *stage* cache is unchanged, and now it is the smaller number
twice over.** Seeded takes 21 s off 58 s at 1 000 documents, of which 11.6 s is computation —
the same order ADR-0154 measured. Restoring the directory takes 53 s off, before the restore
itself. The item 7.1 describes is worth a third of what a copied directory is worth, on the
same evidence.

**3. What this does not say.** One machine, two rounds, one corpus per scale; the restore is
a local copy rather than a download; and the cold builds differ from 2026-09-23's by the
generator change roadmap 7.6 published, not by anything in the compiler — the two reports'
corpora are on different sides of that break.

## Reproduce

```bash
mkdir export && git archive 8670f3e docs eval/corpora/uv-docs/docs | tar -x -C export
git rev-parse 8670f3e > export/COMMIT
python tools/measure_cache_ceiling.py --out <scratch> --scales 250,1000 --rounds 2 \
    --harvest-root export --manifest <path>.json
```

`tests/test_measure_cache_ceiling.py` pins the claim at four documents on every CI run:
both restored arms rebuild nothing, and the `documents` digest is portable.
