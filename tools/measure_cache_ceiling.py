#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What a remote build cache could buy, measured before anybody builds one (roadmap 7.4).

    python tools/measure_cache_ceiling.py --out <scratch> [--scales 250,1000] [--rounds 3]
        [--harvest-root <clean export>] [--manifest docs/benchmarks/manifests/<name>.json]
    python tools/measure_cache_ceiling.py --corpus <repository> --out <scratch>
        [--people N] [--cold-builds-per-week N] [--rounds 1]

Roadmap 7.1 is the remote build cache, and spec 06 §3 defers it until **"≥ 1 team
dogfooding with measured duplicate-build pain"**. Nothing could take that
measurement: the pain has no unit and there was no instrument, so the trigger could
only ever be asserted — the defect ADR-0138 found in the adoption gates, one row
further down the same table. This tool is the instrument. It prices the one thing a
remote cache can change, **a cold build**, because after the first build every
rebuild is incremental and a cache has nothing left to skip (roadmap 6.20).

**Every arm builds a fresh checkout**: a copy of the corpus at a new path, every file
written anew, which is what `git clone` and `actions/checkout` produce. Only what is
in `.mycelium/` differs:

- **cold** — nothing. What every clone and every CI runner pays today.
- **seeded** — exactly what a stage cache could deliver and nothing else: every
  parse and chunk artifact, as the CAS blob, with the index row that names it
  (spec 02 §4.1). No document state, no index, no snapshot. This is a remote cache
  that answers instantly — **the ceiling**, because a real one only adds a network.
- **restored** — another checkout's whole `.mycelium/`, copied in. What a CI job
  caching the directory buys today, with no feature built.
- **restored-mtimes** — the same, with every document's mtime set to the one the
  cached checkout had. Until roadmap 7.7 a document record carried its file's mtime
  (ADR-0009), so a fresh checkout re-assembled and re-stored every document whatever
  its cache held, and this arm priced that dependency: 40 s against 1.6 s at 1 000
  documents (ADR-0154). D-032 took the timestamps out of the record, so `restored`
  and this arm now coincide; the arm stays as the control that says so — a gap
  between the two would be the mtime finding its way back into the record.

The seeding and the restore are timed separately from the build they precede. The
seeding is the local half of every fetch — the bytes re-hashed and written, the rows
inserted — so `cold − (seeded + seeding)` is what a remote cache at infinite
bandwidth would return, and `cold − seeded` is the most anything could.

**Only part of any saving travels.** On the machine of record a small-file operation
costs about a hundred times what an unencumbered SSD charges (the calibration constant
in `docs/benchmarks/README.md`), so each scale also times, in memory and with no file
touched, the computation a miss runs against the one a hit runs instead
(:func:`measure_compute`). That difference is the part of the ceiling every machine
collects; the rest is file operations, and only a machine that pays for them saves them.

**An arm is only evidence if it measured what it names.** So each build's cache hits
are recorded beside its time, and its manifest's `documents`, `chunks`, `edges` and
`symbols` digests are compared with the cold arm's: a cache that changed the output
would be a bug, and a seeded arm that missed would be timing a cold build under
another name. The `documents` digest joined that list at roadmap 7.7: until then it
was *expected* to differ between checkouts, because a document record carried its
file's mtime (ADR-0009), and that expectation was the finding that became D-032.

**Portability is measured, not assumed.** A remote cache is worthless if two
machines mint different keys for the same commit, so each scale also seeds a
checkout rewritten with CRLF endings — a Windows clone under `core.autocrlf` — from
the LF build, and counts the hits.

`--corpus` runs the same arms on a repository somebody already has, copying the
documents its configuration compiles into scratch (nothing in the repository is
written), and prints the report spec 06 §3's trigger reads: paste it into an issue
and `tools/adoption_report.py` evaluates it (ADR-0154). `--people` and
`--cold-builds-per-week` are the team's own figures; the tool cannot know them and
does not guess.
"""

import argparse
import json
import os
import platform
import shutil
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

# The report schema belongs to the gate that reads it, so the instrument imports it
# rather than restating it: one tag, two readers (ADR-0120's discipline).
from adoption_report import CACHE_REPORT_SCHEMA  # noqa: E402

# The manifest schema, the machine block, the corpus generator and the calibration
# constant are the reference profile's, read rather than restated (spec 04 §7.5).
from benchmark_reference_profile import (  # noqa: E402
    COLD_BUILD_BUDGET_S,
    COLD_BUILD_DOCUMENTS,
    SCHEMA,
    Measurement,
    _commit,
    generate,
    hardware,
    harvest,
    measure_file_io,
)
from benchmark_reference_profile import SOURCE_CORPORA as HARVEST_SOURCES  # noqa: E402

from mycelium.__about__ import __version__  # noqa: E402
from mycelium.build import BuildResult, build  # noqa: E402
from mycelium.build.cas import cas_get, cas_put  # noqa: E402
from mycelium.build.dag import (  # noqa: E402
    decode_chunks_artifact,
    decode_parse_artifact,
    encode_chunks_artifact,
    encode_parse_artifact,
)
from mycelium.chunking import chunk_document  # noqa: E402
from mycelium.config import load_config  # noqa: E402
from mycelium.corpus import CorpusScope, scan  # noqa: E402
from mycelium.markdown import parse_markdown  # noqa: E402
from mycelium.sdk.identity import digest_bytes  # noqa: E402
from mycelium.store import STORE_DIRNAME, SqliteStore  # noqa: E402

ARMS: Final = ("cold", "seeded", "restored", "restored-mtimes")
"""Rotated one place per round, so drift across a run cannot land on one arm."""

PORTABLE_DIGESTS: Final = ("documents", "chunks", "edges", "symbols")
"""The manifest digests two checkouts of one tree must agree on (spec 03 §7).

`documents` was deliberately absent until roadmap 7.7: a document record carried the
file's mtime as `created_at`/`updated_at` (ADR-0009), and a fresh checkout's mtimes
are the moment it was written. D-032 removed the timestamps, so every published
digest is now a function of the tree."""

DEFAULT_SCALES: Final = (250, COLD_BUILD_DOCUMENTS)
DEFAULT_ROUNDS: Final = 3


# ---------------------------------------------------------------------------
# Checkouts
# ---------------------------------------------------------------------------


def _remove(path: Path) -> None:
    """Delete a scratch checkout, tolerating a scanner that still holds a handle."""
    for attempt in range(5):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5)


def checkout(template: Path, dest: Path, *, crlf: bool = False) -> Path:
    """A fresh checkout of `template` at `dest`: same bytes, new path, new mtimes.

    `shutil.copy` rather than `copy2` on purpose — a clone does not preserve the
    author's mtimes, and neither does this. `crlf` rewrites every Markdown file with
    Windows line endings, which is what `core.autocrlf=true` checks out.
    """
    if dest.exists():
        _remove(dest)
    shutil.copytree(
        template,
        dest,
        copy_function=shutil.copy,
        ignore=shutil.ignore_patterns(STORE_DIRNAME),
    )
    if crlf:
        for path in sorted(dest.rglob("*.md")):
            text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    return dest


def copy_corpus(repository: Path, dest: Path) -> int:
    """Copy the documents `repository` compiles, and its configuration, into `dest`.

    Only what a build reads — the same scan the compiler runs — so a repository's
    `.git/`, its virtual environment and its own `.mycelium/` are never touched, and
    nothing is written anywhere inside it. Returns the number of documents copied.
    """
    config = load_config(repository)
    if dest.exists():
        _remove(dest)
    dest.mkdir(parents=True)
    found = scan(repository, CorpusScope.of(config.project))
    for item in found:
        target = dest / item.path.relative_to(repository)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(item.path, target)
    configuration = repository / "mycelium.toml"
    if configuration.is_file():
        shutil.copy(configuration, dest / "mycelium.toml")
    return len(found)


def corpus_digest(template: Path) -> str:
    """One digest over every file of a corpus, by path, so a rerun can prove its input.

    The generated corpus is derived from prose harvested out of this repository's own
    `docs/`, which moves with every merge; the seed alone does not name it.
    """
    listing = [
        f"{path.relative_to(template).as_posix()}\0{digest_bytes(path.read_bytes())}"
        for path in sorted(template.rglob("*"))
        if path.is_file() and STORE_DIRNAME not in path.relative_to(template).parts
    ]
    return digest_bytes("\n".join(listing).encode("utf-8"))


# ---------------------------------------------------------------------------
# What a cache can hand a checkout
# ---------------------------------------------------------------------------


def seed(source: Path, target: Path) -> tuple[float, int]:
    """Give `target` every stage artifact `source` built, and nothing else; time it.

    Each blob is read back through :func:`cas_get` — which re-hashes it, as any client
    of a remote CAS must — and written through :func:`cas_put`, and each index row is
    inserted in one transaction. That is the local half of a fetch. Returns the
    seconds it took and the rows seeded.
    """
    started = time.perf_counter()
    with SqliteStore.open(source, read_only=True) as store:
        entries = store.cache_entries()
    source_dir = source / STORE_DIRNAME
    target_dir = target / STORE_DIRNAME
    seeded = 0
    target_store = SqliteStore.open(target)
    with target_store, target_store.transaction():
        for entry in entries:
            text = cas_get(source_dir, entry.artifact_digest)
            if text is None:
                continue
            cas_put(target_dir, text)
            target_store.cache_put(entry.build_key, entry.artifact_digest, entry.created_at)
            seeded += 1
    return time.perf_counter() - started, seeded


def restore(source: Path, target: Path) -> float:
    """Copy `source`'s whole `.mycelium/` into `target`, as a directory cache would; time it."""
    started = time.perf_counter()
    shutil.copytree(source / STORE_DIRNAME, target / STORE_DIRNAME)
    return time.perf_counter() - started


def keep_mtimes(source: Path, target: Path) -> int:
    """Give every file of `target` the mtime its counterpart has in `source`.

    What a checkout looks like when its mtimes are a function of the commit rather
    than of the moment it was written. Returns the number of files it touched.
    """
    touched = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if STORE_DIRNAME in relative.parts or not path.is_file():
            continue
        stat = path.stat()
        os.utime(target / relative, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        touched += 1
    return touched


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Built:
    """One timed build and what it proves about itself."""

    seconds: float
    result: BuildResult

    @property
    def rebuilt(self) -> int:
        return self.result.stats.rebuilt

    @property
    def parse_hits(self) -> int:
        return self.result.stats.parse_hits

    @property
    def chunk_hits(self) -> int:
        return self.result.stats.chunk_hits

    @property
    def stages_ms(self) -> dict[str, int]:
        return dict(self.result.manifest.timings_ms)

    def digests(self) -> dict[str, str]:
        found = self.result.manifest.artifact_digests
        return {name: found[name] for name in PORTABLE_DIGESTS if name in found}


def timed_build(root: Path) -> Built:
    """Build `root` as a clone would — `--no-pin`, so no source file is ever written."""
    started = time.perf_counter()
    result = build(root, pin_identity=False)
    return Built(seconds=time.perf_counter() - started, result=result)


def measure_compute(source: Path, *, rounds: int) -> tuple[Measurement, Measurement]:
    """What a cache hit saves in *computation* alone, with no file touched.

    The build arms are wall-clock on one machine, and on the machine of record a
    small-file operation costs about a hundred times what it costs on an unencumbered
    SSD (`docs/benchmarks/README.md`, the calibration constant). So a saving measured
    there is part compiler and part filesystem, and only the first part travels.
    This separates them: for every document `source` compiled, in memory, the work a
    **miss** does — parse, chunk, encode both artifacts and hash them for their CAS
    names — against the work a **hit** does instead — re-hash both blobs, as
    :func:`cas_get` does, and decode them back into validated records. Each sample is
    one pass over the whole corpus.
    """
    config = load_config(source)
    policy = config.chunking.to_policy()
    namespace = config.project.namespace
    with SqliteStore.open(source, read_only=True) as store:
        states = store.doc_states()
    documents = [
        (state.path, state.doc_id, (source / state.path).read_bytes().decode("utf-8"))
        for state in states
    ]
    count = len(documents)
    miss = Measurement(
        name=f"compute a miss runs (parse, chunk, encode, hash), {count} documents",
        unit="s",
        budget=None,
    )
    hit = Measurement(
        name=f"compute a hit runs instead (re-hash, decode), {count} documents",
        unit="s",
        budget=None,
    )
    for _ in range(rounds):
        blobs: list[tuple[bytes, bytes]] = []
        started = time.perf_counter()
        for doc_path, doc_id, raw in documents:
            parsed = parse_markdown(raw, doc_id=doc_id)
            chunks = chunk_document(
                parsed.kir, doc_path=doc_path, policy=policy, namespace=namespace
            )
            parse_blob = encode_parse_artifact(parsed).encode("utf-8")
            chunk_blob = encode_chunks_artifact(chunks).encode("utf-8")
            digest_bytes(parse_blob)
            digest_bytes(chunk_blob)
            blobs.append((parse_blob, chunk_blob))
        miss.samples.append(time.perf_counter() - started)
        started = time.perf_counter()
        for parse_blob, chunk_blob in blobs:
            digest_bytes(parse_blob)
            decode_parse_artifact(parse_blob.decode("utf-8"))
            digest_bytes(chunk_blob)
            decode_chunks_artifact(chunk_blob.decode("utf-8"))
        hit.samples.append(time.perf_counter() - started)
    for measurement, arm in ((miss, "compute-miss"), (hit, "compute-hit")):
        measurement.notes.update({"arm": arm, "documents": count})
    return miss, hit


def _median_stages(builds: Sequence[Built]) -> dict[str, float]:
    stages = sorted({stage for built in builds for stage in built.stages_ms})
    return {
        stage: round(statistics.median(built.stages_ms.get(stage, 0) for built in builds), 1)
        for stage in stages
    }


def _arm_measurement(arm: str, documents: int, builds: Sequence[Built]) -> Measurement:
    names = {
        "cold": "cold build of a fresh checkout",
        "seeded": "seeded build: every stage artifact present, nothing else",
        "restored": "restored build: a previous checkout's whole .mycelium",
        "restored-mtimes": "restored build with that checkout's mtimes kept",
    }
    measurement = Measurement(
        name=f"{names[arm]}, {documents} documents",
        unit="s",
        budget=COLD_BUILD_BUDGET_S if arm == "cold" and documents == COLD_BUILD_DOCUMENTS else None,
        samples=[built.seconds for built in builds],
    )
    measurement.notes.update(
        {
            "arm": arm,
            "rebuilt": [built.rebuilt for built in builds],
            "parse_hits": [built.parse_hits for built in builds],
            "chunk_hits": [built.chunk_hits for built in builds],
            "stages_ms_median": _median_stages(builds),
        }
    )
    return measurement


def _preparation(name: str, samples: Sequence[float], notes: dict[str, Any]) -> Measurement:
    measurement = Measurement(name=name, unit="s", budget=None, samples=list(samples))
    measurement.notes.update(notes)
    return measurement


def measure(
    template: Path, workspace: Path, *, rounds: int, label: str, crlf_check: bool = True
) -> dict[str, Any]:
    """Every arm over `rounds` rounds against one corpus, and what they prove.

    `template` is the pristine corpus; nothing builds it in place. One untimed
    *source* build produces the artifacts the seeded and restored arms are handed,
    and warms the interpreter so the first timed arm is not charged for imports.
    """
    source = checkout(template, workspace / "source")
    reference = timed_build(source)
    documents = reference.result.manifest.counts.documents
    print(
        f"\n--- {label}: {documents} documents, "
        f"{reference.result.manifest.counts.chunks} chunks ---",
        flush=True,
    )
    print(f"  source build     {reference.seconds:8.1f} s   (warm-up, not a sample)", flush=True)

    builds: dict[str, list[Built]] = {arm: [] for arm in ARMS}
    seeding: list[float] = []
    seeded_rows: list[int] = []
    restoring: list[float] = []
    for round_index in range(rounds):
        offset = round_index % len(ARMS)
        for arm in ARMS[offset:] + ARMS[:offset]:
            target = checkout(template, workspace / f"{arm}-{round_index}")
            if arm == "seeded":
                seconds, rows = seed(source, target)
                seeding.append(seconds)
                seeded_rows.append(rows)
            elif arm.startswith("restored"):
                restoring.append(restore(source, target))
                if arm == "restored-mtimes":
                    keep_mtimes(source, target)
            built = timed_build(target)
            builds[arm].append(built)
            print(
                f"  round {round_index + 1} {arm:<16}{built.seconds:8.1f} s   "
                f"parse hits {built.parse_hits}/{built.rebuilt}, "
                f"chunk hits {built.chunk_hits}/{built.rebuilt}",
                flush=True,
            )
            _remove(target)

    expected = reference.digests()
    identical = all(
        built.digests() == expected for arm_builds in builds.values() for built in arm_builds
    )
    measurements = [_arm_measurement(arm, documents, builds[arm]) for arm in ARMS]
    measurements.append(
        _preparation(
            f"seeding the stage artifacts into a fresh checkout, {documents} documents",
            seeding,
            {"arm": "seeding", "rows": seeded_rows},
        )
    )
    measurements.append(
        _preparation(
            f"restoring a whole .mycelium into a fresh checkout, {documents} documents",
            restoring,
            {"arm": "restoring"},
        )
    )
    miss, hit = measure_compute(source, rounds=rounds)
    measurements += [miss, hit]
    by_arm = {str(measurement.notes["arm"]): measurement for measurement in measurements}
    cold, seeded, seeds = by_arm["cold"], by_arm["seeded"], by_arm["seeding"]
    restored, kept, restores = by_arm["restored"], by_arm["restored-mtimes"], by_arm["restoring"]
    saved = cold.p50 - seeded.p50
    share = saved / cold.p50 if cold.p50 > 0 else 0.0
    computed = miss.p50 - hit.p50
    documents_digest = reference.result.manifest.artifact_digests.get("documents")
    ceiling = {
        "cold_p50_s": round(cold.p50, 3),
        "seeded_p50_s": round(seeded.p50, 3),
        "restored_p50_s": round(restored.p50, 3),
        "restored_mtimes_p50_s": round(kept.p50, 3),
        "seeding_p50_s": round(seeds.p50, 3),
        "restoring_p50_s": round(restores.p50, 3),
        "ceiling_s": round(saved, 3),
        "ceiling_share": round(share, 4),
        "ceiling_with_seeding_s": round(saved - seeds.p50, 3),
        "compute_saved_s": round(computed, 3),
        "compute_share_of_cold": round(computed / cold.p50, 4) if cold.p50 > 0 else 0.0,
        "file_operations_saved_s": round(saved - computed, 3),
        "restored_saving_s": round(cold.p50 - restored.p50, 3),
        "restored_saving_with_restore_s": round(cold.p50 - restored.p50 - restores.p50, 3),
        "restored_mtimes_saving_s": round(cold.p50 - kept.p50, 3),
        "restored_mtimes_saving_with_restore_s": round(cold.p50 - kept.p50 - restores.p50, 3),
        "ranges_separated": max(seeded.samples) < min(cold.samples),
        "outputs_identical": identical,
        "documents_digest_varies_by_checkout": any(
            built.result.manifest.artifact_digests.get("documents") != documents_digest
            for arm in ("cold", "seeded", "restored")
            for built in builds[arm]
        ),
        "documents_digest_kept_with_mtimes": all(
            built.result.manifest.artifact_digests.get("documents") == documents_digest
            for built in builds["restored-mtimes"]
        ),
    }

    portability: dict[str, Any] = {}
    if crlf_check:
        target = checkout(template, workspace / "crlf", crlf=True)
        seed(source, target)
        built = timed_build(target)
        portability = {
            "checkout": "CRLF line endings, seeded from the LF source build",
            "rebuilt": built.rebuilt,
            "parse_hits": built.parse_hits,
            "chunk_hits": built.chunk_hits,
            "outputs_identical": built.digests() == expected,
        }
        print(
            f"  CRLF checkout    parse hits {built.parse_hits}/{built.rebuilt}, "
            f"chunk hits {built.chunk_hits}/{built.rebuilt}, "
            f"outputs identical: {portability['outputs_identical']}",
            flush=True,
        )
        _remove(target)
    _remove(source)

    print(
        f"  ceiling          {saved:8.1f} s   ({100 * share:.1f} % of {cold.p50:.1f} s), "
        f"of which compute {computed:.1f} s; less the seeding {saved - seeds.p50:.1f} s\n"
        f"  restored         saves {cold.p50 - restored.p50:.1f} s, "
        f"with mtimes kept {cold.p50 - kept.p50:.1f} s, "
        f"before a {restores.p50:.1f} s restore; outputs identical: {identical}",
        flush=True,
    )
    return {
        "label": label,
        "documents": documents,
        "chunks": reference.result.manifest.counts.chunks,
        "rounds": rounds,
        "measurements": [measurement.as_dict() for measurement in measurements],
        "ceiling": ceiling,
        "portability": portability,
    }


# ---------------------------------------------------------------------------
# The report spec 06 §3's trigger reads
# ---------------------------------------------------------------------------


def pain_report(
    block: dict[str, Any], *, people: int | None, cold_builds_per_week: int | None
) -> dict[str, Any]:
    """The evidence record `tools/adoption_report.py` evaluates (ADR-0154).

    Numbers only, and no path or document name — a report is meant to be pasted into
    a public issue, and what it has to prove is a cost, not a corpus. `people` and
    `cold_builds_per_week` are the reporter's own figures, passed through unchanged.
    """
    by_arm = {
        str(measurement["arm"]): measurement
        for measurement in block["measurements"]
        if isinstance(measurement, dict) and "arm" in measurement
    }
    ceiling = block["ceiling"]
    weekly = (
        None
        if cold_builds_per_week is None
        else round(float(ceiling["ceiling_s"]) * cold_builds_per_week, 1)
    )
    return {
        "schema": CACHE_REPORT_SCHEMA,
        "mycelium": __version__,
        "documents": int(block["documents"]),
        "chunks": int(block["chunks"]),
        "rounds": int(block["rounds"]),
        "cold_s": {key: by_arm["cold"][key] for key in ("p50", "min", "max")},
        "seeded_s": {key: by_arm["seeded"][key] for key in ("p50", "min", "max")},
        "restored_s": by_arm["restored"]["p50"],
        "restored_mtimes_s": by_arm["restored-mtimes"]["p50"],
        "restoring_s": by_arm["restoring"]["p50"],
        "seeding_s": by_arm["seeding"]["p50"],
        "ceiling_s": ceiling["ceiling_s"],
        "ceiling_share": ceiling["ceiling_share"],
        "compute_saved_s": ceiling["compute_saved_s"],
        "outputs_identical": ceiling["outputs_identical"],
        "people": people,
        "cold_builds_per_week": cold_builds_per_week,
        "weekly_ceiling_s": weekly,
        "platform": platform.system(),
        "logical_cpus": os.cpu_count(),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _profile(args: argparse.Namespace) -> dict[str, Any]:
    harvest_root = args.harvest_root.resolve()
    prose = harvest(harvest_root)
    print(
        f"harvested {len(prose.blocks)} blocks, {len(prose.headings)} headings from {harvest_root}",
        flush=True,
    )
    scales = [int(item) for item in str(args.scales).split(",") if item.strip()]
    blocks: list[dict[str, Any]] = []
    calibration: dict[str, Any] | None = None
    digests: dict[str, str] = {}
    for index, documents in enumerate(scales):
        template = args.out / f"template-{documents:06d}"
        # One seed per scale, the reference profile's convention: the sizes are
        # different corpora, not prefixes of one.
        generated = generate(template, prose, documents, seed=args.seed + index)
        digests[str(documents)] = corpus_digest(template)
        if calibration is None:
            calibration = measure_file_io(template).as_dict()
        block = measure(
            template,
            args.out / f"scale-{documents:06d}",
            rounds=args.rounds,
            label=f"reference profile, {documents} documents",
        )
        if int(block["documents"]) != generated:
            # The same refusal `benchmark_reference_profile.compiled_all` makes: a
            # corpus that compiled short is not at the size it names (BUG-0035).
            msg = (
                f"generated {generated} documents but the builds compiled "
                f"{block['documents']} - the run is not at the size it names"
            )
            raise SystemExit(msg)
        blocks.append(block)
        _remove(template)
    return {
        "corpus": {
            "kind": "generated reference profile (tools/benchmark_reference_profile.py)",
            "generator": "tools/measure_cache_ceiling.py",
            "seed": args.seed,
            "scales": scales,
            "sources": [path.as_posix() for path in HARVEST_SOURCES],
            "harvested_from": _commit_of(harvest_root),
            "corpus_digests": digests,
        },
        "file_io": calibration,
        "cache_profile": blocks,
    }


def _commit_of(root: Path) -> str | None:
    """The commit the prose was harvested at: a clean export names it in a marker file.

    `git archive` writes no `.git`, so an export made for a measurement carries its
    commit in `COMMIT` beside the files; a harvest from this checkout is HEAD's.
    """
    marker = root / "COMMIT"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip() or None
    return _commit() if root.resolve() == ROOT else None


def _corpus(args: argparse.Namespace) -> dict[str, Any]:
    repository = args.corpus.resolve()
    template = args.out / "template"
    documents = copy_corpus(repository, template)
    print(f"copied {documents} documents from {repository} into scratch", flush=True)
    block = measure(
        template,
        args.out / "scale",
        rounds=args.rounds,
        label="your corpus",
    )
    _remove(template)
    report = pain_report(block, people=args.people, cold_builds_per_week=args.cold_builds_per_week)
    print(
        "\nPaste this into an issue on the repository; tools/adoption_report.py reads it "
        "as the evidence the remote-cache trigger of spec 06 section 3 asks for:\n"
    )
    print("```json")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("```")
    return {
        "corpus": {"kind": "a corpus supplied with --corpus", "documents": documents},
        "cache_profile": [block],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Scratch directory.")
    parser.add_argument("--corpus", type=Path, help="Measure this repository's corpus instead.")
    parser.add_argument("--scales", default=",".join(str(size) for size in DEFAULT_SCALES))
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument(
        "--harvest-root",
        type=Path,
        default=ROOT,
        help="Where the generator harvests its prose (a clean export, for a published run).",
    )
    parser.add_argument("--people", type=int, help="People who build this corpus (--corpus).")
    parser.add_argument(
        "--cold-builds-per-week",
        type=int,
        help="Cold builds of this corpus a week, across people and CI (--corpus).",
    )
    parser.add_argument("--manifest", type=Path, help="Write the run manifest here.")
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")

    args.out.mkdir(parents=True, exist_ok=True)
    measured = _corpus(args) if args.corpus is not None else _profile(args)
    document = {
        "schema": SCHEMA,
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "commit": _commit(),
        "toolchain": {"mycelium": __version__, "python": platform.python_version()},
        "hardware": hardware(),
        "budgets": {
            "cold_build_s": COLD_BUILD_BUDGET_S,
            "cold_build_documents": COLD_BUILD_DOCUMENTS,
        },
        **measured,
    }
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nmanifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
