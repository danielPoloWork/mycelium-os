#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Measure the performance claims at the scale they are stated for (roadmap 6.4).

    python tools/benchmark_reference_profile.py --out <dir> [--chunks 100000]
    python tools/benchmark_reference_profile.py --check          # cheap, CI-safe

Three numbers are claimed in three places — spec 01 §8, spec 04 §1 / NFR-2, and
spec 06 §Phase 1 — and all three are stated against a **reference profile**:

| Claim | Budget | Stated conditions |
|---|---|---|
| Cold build | < 60 s | 1 000 documents |
| Incremental single-document rebuild | < 2 s p95 | equals a clean rebuild |
| End-to-end `mycelium_search` | ≤ 150 ms p95 | local profile, **10⁵ chunks**, warm store |

The reference corpus those conditions name has never existed. Gate G5 enforces the
query budget on whatever corpus the evaluation ran, and says so in its own detail
string — the largest is this repository at ~1 400 chunks, which is **seventy times
smaller** than the profile. A gate that cannot fail is not evidence, and *"search
p95 < 150 ms on the 10⁵-chunk reference corpus"* has been a closed Phase-1 exit
gate since v0.3.0 on the strength of a measurement at 1/70th of its scale.

This tool builds the profile and measures against it.

**Two modes, because one of the budgets cannot be reached by compiling.** `--scales`
generates documents and *compiles* them, which is the only honest way to time a
build. `--query-scale` writes chunks straight into a store, which is the only
practical way to reach 10⁵ of them: loading a corpus that size through the
compiler takes about nine hours, for the reason BUG-0031 records — a delete from
an `UNINDEXED` FTS5 column that SQLite answers with a full scan, once per chunk.
NFR-2's condition is what the retriever *reads*, and the retriever reads the
derived store and nothing else, so the two paths present the same substrate; that
is checked rather than assumed, by running both at a size each can reach.

**The corpus is generated, not committed, and that is the only honest option at
this size.** 10⁵ chunks is ~20 000 documents and hundreds of megabytes; a
repository that committed it would be mostly benchmark. So it is *derived*: real
prose harvested from the corpora this project already vendors, recomposed into
distinct documents by a seeded generator. Same seed, same corpus, on any machine —
which is what makes a number reproducible without shipping the bytes it was taken
over.

**What "realistic" means here, and what it does not.** The blocks are real
technical documentation — real vocabulary, real term frequencies, real headings,
real code fences — so the lexical index sees a term distribution it would meet in
the field rather than random words, which would make BM25 look far better than it
is. What the generator cannot reproduce is a real corpus's *link structure*: its
documents cross-reference each other and these do not, so the graph stage is
under-exercised and the edge count is low for the corpus size. Wikilinks are
stripped for the same reason they would otherwise mislead — 20 000 dangling
references are not what a real vault looks like either. Both limits belong in the
report beside the numbers.

**Every measurement here is wall-clock on one machine.** That is what the budgets
are about, and it means the manifest has to carry the hardware or the number means
nothing (`docs/benchmarks/README.md`, spec 04 §7.5). A committed report cites its
manifest; `tools/consistency_lint.py` refuses one that does not.
"""

import argparse
import cProfile
import ctypes
import hashlib
import json
import os
import platform
import pstats
import random
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.__about__ import __version__  # noqa: E402
from mycelium.build import build  # noqa: E402
from mycelium.build.publish import CURRENT_FILENAME  # noqa: E402
from mycelium.config import RetrievalConfig  # noqa: E402
from mycelium.embedding import EmbeddingError, build_embedder  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.mcp.tools import handle_search  # noqa: E402
from mycelium.retrieval import search  # noqa: E402
from mycelium.sdk.identity import canonical_json, encode_ulid, heading_slug  # noqa: E402
from mycelium.sdk.types import (  # noqa: E402
    Document,
    DocumentStats,
    Provenance,
    TrustClass,
    VerificationStatus,
)
from mycelium.store import STORE_DIRNAME, SqliteStore  # noqa: E402

# `_stemmed` is imported private on purpose: the stem columns must be tokenised by
# *the* function the compiler uses, and a second copy of that expression in this
# tool is exactly the drift that would make the benchmark's index differ from the
# product's.
from mycelium.store.sqlite import _stemmed  # noqa: E402

_DIGEST: Final = "sha256:" + "6f2a" * 16
"""A placeholder *document* content digest. Nothing in the query path reads it."""


def _chunk_digest(anchor: str) -> str:
    """A distinct content digest per chunk, derived from its anchor.

    The chunks used to share :data:`_DIGEST`, on the true observation that the
    lexical path never reads this column. The vector path does: vectors are keyed
    ``(chunk_digest, model_id)`` (D-013) and `search_vectors` hydrates its results
    by that key, so one shared digest would have meant **one vector for a hundred
    thousand chunks** and a hydration that returned all of them (roadmap 6.21).

    Derived from the anchor rather than drawn from the generator's `random.Random`
    so the prose is byte-identical to what the same seed produced before: the rng
    stream is untouched, and only this column moves. Nothing the lexical
    measurement can see changes, which is what lets 6.4's published numbers and
    these be read as measurements of one corpus."""
    return "sha256:" + hashlib.sha256(anchor.encode("utf-8")).hexdigest()


SCHEMA: Final = "mycelium/benchmark/v0"
"""The manifest's own schema tag. Not a record contract and not frozen: a
benchmark manifest is a harness asset, like `AgentTask` and for ADR-0022's
reason — it changes when the measurement changes."""

REPORTS: Final = ROOT / "docs" / "benchmarks"
MANIFESTS: Final = REPORTS / "manifests"

SOURCE_CORPORA: Final = (
    Path("eval/corpora/uv-docs/knowledge"),
    Path("docs"),
)
"""Where the prose comes from: the vendored documentation corpus, and this
repository's own. Two sources rather than one so the vocabulary is not a single
project's."""

REAL_CORPORA: Final = (
    Path("."),
    Path("eval/corpora/uv-docs"),
    Path("eval/corpora/uv-docs-ingested"),
)
"""Corpora compiled by the real compiler from real documentation, measured as a
cross-check on the generated ones.

They are far too small to test a budget stated at 10⁵ chunks — that is the whole
problem — but they are the answer to *"is the constant an artifact of your
generator?"*. It is not: the end-to-end overhead is the same on documentation this
project did not write."""

QUERY_SETS: Final = (Path("eval/release.jsonl"), Path("eval/dev.jsonl"))
"""Real judged queries, so the measurement is over questions somebody wrote to be
answered rather than over terms picked to be fast."""

COLD_BUILD_DOCUMENTS: Final = 1_000
"""Spec 01 §8's cold-build claim is stated per thousand documents."""

REFERENCE_CHUNKS: Final = 100_000
"""Spec 04 §1's 10⁵-chunk reference profile."""

QUERY_BUDGET_MS: Final = 150
CANDIDATE_BUDGET_MS: Final = 60
"""Spec 04 §1's budget for plan + candidate generation, the stage the vector leg is."""
INCREMENTAL_BUDGET_MS: Final = 2_000
COLD_BUILD_BUDGET_S: Final = 60

VECTOR_FRESH_SAMPLES: Final = 12
"""Fresh-handle vector samples. Each opens a store and maps a 154 MB file, so this
is deliberately fewer than the warm pass; the manifest records the count."""

INCREMENTAL_SAMPLES: Final = 20
"""Single-document edits timed for the p95. Twenty is the fewest that makes a p95
mean anything at all — the 95th percentile of twenty is the worst sample — and the
manifest records the count so a reader can weigh it."""

DEFAULT_SCALES: Final = (250, 1_000, 2_500, 5_000)
"""The curve, in documents. A single point at the reference size would say whether
the budget is met and nothing about *why*; the curve says which cost grows with the
corpus and which is a constant, which is the difference between a number and a
finding. 1 000 is spec 01 §8's own cold-build condition."""

VECTOR_MODEL_ID: Final = "reference-profile-384"
VECTOR_DIM: Final = 384
"""The synthetic embedding the vector profile is measured over (roadmap 6.21).

**A model id of its own, not the shipped model's.** The vectors are random unit
vectors, and writing them under `bge-small-en-v1.5` would leave a store claiming to
hold embeddings of its own prose that are nothing of the kind. The dimension is the
shipped model's, because that is what decides the matrix's size and therefore every
cost here.

**Random is honest for a *cost* measurement and would not be for a *quality* one.**
The scan is exact and touches every vector whatever they contain, so geometry
cannot change how long it takes to multiply the matrix — the same reasoning
`tools/measure_vector_index.py` states, and the reason ADR-0028's *recall* half
insists on real embeddings instead."""

CHUNKS_PER_DOCUMENT: Final = 5
BLOCKS_PER_CHUNK: Final = 2
"""The shape a compiled corpus of this generator's documents actually has.

Not guessed — read off the curve: 998 generated documents compile to 4 939
chunks, so ~5 chunks a document, and each document carries ~10 harvested blocks,
so ~2 blocks a chunk. A directly-populated store has to match *text volume per
chunk* or it measures a smaller index than the compiler would build: at one block
a chunk the same store answered a query in 28.5 ms where the compiled corpus took
twice that. `--query-scale` at a size the curve also covers is the check that these
two numbers are the same measurement."""

IO_CALIBRATION_FILES: Final = 400
"""How many generated files the I/O calibration reads.

Every build number here is dominated by what it costs this machine to *open a small
file*, and that is not a property of the compiler. On the machine of record a warm
read of a 4 KB Markdown file costs ~1.2 ms — roughly a hundred times an unencumbered
SSD, because a real-time malware scanner sits in the open path. A reader who does not
know that will read a build number as a compiler cost. So the manifest carries the
constant, and every build figure can be divided by the reader's own."""

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Hardware — a number without its machine is not comparable
# ---------------------------------------------------------------------------


def _total_memory_bytes() -> int | None:
    """Physical memory, or ``None`` where this platform will not say.

    Written without `psutil` on purpose: a benchmark tool must not add a runtime
    dependency to the project it measures (D-013's spirit), and both platforms
    this runs on answer through their own standard interface.
    """
    names = getattr(os, "sysconf_names", {})
    sysconf = getattr(os, "sysconf", None)
    if sysconf is not None and "SC_PHYS_PAGES" in names and "SC_PAGE_SIZE" in names:
        try:
            return int(sysconf("SC_PAGE_SIZE")) * int(sysconf("SC_PHYS_PAGES"))
        except (OSError, ValueError):  # pragma: no cover - platform-dependent
            return None

    windll = getattr(ctypes, "windll", None)
    if windll is None:  # pragma: no cover - platform-dependent
        return None

    class _MemoryStatus(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None  # pragma: no cover - platform-dependent
    return int(status.ullTotalPhys)


def hardware() -> dict[str, Any]:
    """The machine, as the benchmarks methodology requires it to be recorded."""
    memory = _total_memory_bytes()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpus": os.cpu_count(),
        "memory_gib": None if memory is None else round(memory / 1024**3, 1),
    }


def _commit() -> str | None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


# ---------------------------------------------------------------------------
# Harvesting real prose
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Prose:
    """Real blocks and headings, harvested once and sampled many times."""

    blocks: tuple[str, ...]
    headings: tuple[str, ...]

    @property
    def words(self) -> int:
        return sum(len(block.split()) for block in self.blocks)


def _blocks_of(text: str) -> tuple[list[str], list[str]]:
    """Split one document into (blocks, headings), keeping code fences whole.

    A fence split on blank lines is the bug this function exists to avoid: half a
    fence in a generated document is markup the adapter reads as something else,
    and the corpus stops resembling documentation at the one place the symbol
    stage looks hardest.
    """
    blocks: list[str] = []
    headings: list[str] = []
    current: list[str] = []
    fence: str | None = None

    def flush() -> None:
        joined = "\n".join(current).strip()
        current.clear()
        if joined:
            blocks.append(joined)

    for line in text.splitlines():
        marker = _FENCE.match(line)
        if fence is not None:
            current.append(line)
            if marker and line.strip().startswith(fence):
                fence = None
                flush()
            continue
        if marker:
            flush()
            fence = marker.group(1)
            current.append(line)
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            title = heading.group(2).strip()
            if 3 <= len(title) <= 70:
                headings.append(title)
            continue
        if line.strip():
            current.append(line)
        else:
            flush()
    flush()
    return blocks, headings


def harvest(root: Path, sources: Sequence[Path] = SOURCE_CORPORA) -> Prose:
    """Collect blocks and headings from the corpora this repository already holds."""
    blocks: list[str] = []
    headings: list[str] = []
    for relative in sources:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):  # pragma: no cover - corpus is clean
                continue
            text = _FRONTMATTER.sub("", text)
            # A wikilink in a generated document would resolve to nothing: 20 000
            # dangling references are no more realistic than none, and they would
            # put the link stage under a load a real vault never applies.
            text = _WIKILINK.sub(lambda match: match.group(2) or match.group(1), text)
            found, titles = _blocks_of(text)
            blocks.extend(block for block in found if 40 <= len(block) <= 1_200)
            headings.extend(titles)
    if len(blocks) < 100 or len(headings) < 20:
        msg = (
            f"harvested only {len(blocks)} blocks and {len(headings)} headings from "
            f"{[str(s) for s in sources]} - is this a full checkout?"
        )
        raise SystemExit(msg)
    return Prose(blocks=tuple(blocks), headings=tuple(headings))


# ---------------------------------------------------------------------------
# Generating the corpus
# ---------------------------------------------------------------------------

_ULID_EPOCH_MS: Final = 1_767_225_600_000
"""2026-01-01T00:00:00Z, the same instant the determinism gate pins mtimes to.

Non-zero on purpose: a zero timestamp is how `is_derived_ulid` recognises a
*derived* id (ADR-0046), and these are minted, not derived."""


def _document(rng: random.Random, prose: Prose, index: int) -> str:
    """One generated document: pinned identity, a title, and two to six sections."""
    identity = encode_ulid(_ULID_EPOCH_MS + index, rng.randbytes(10))
    title = f"{rng.choice(prose.headings)} ({index})"
    lines = [
        "---",
        f"mycelium_id: {identity}",
        f"title: {title.replace(':', ' -')}",
        "---",
        "",
        f"# {title}",
        "",
        rng.choice(prose.blocks),
        "",
    ]
    for _ in range(rng.randint(2, 6)):
        lines += [f"## {rng.choice(prose.headings)}", ""]
        for _ in range(rng.randint(1, 3)):
            lines += [rng.choice(prose.blocks), ""]
    return "\n".join(lines).rstrip() + "\n"


def generate(dest: Path, prose: Prose, documents: int, *, seed: int) -> int:
    """Write `documents` generated documents under `dest`, deterministically.

    Returns the number written. Documents are foldered a hundred to a directory:
    a single directory of 20 000 files is not what a repository looks like, and
    it measures the filesystem rather than the compiler.
    """
    knowledge = dest / "knowledge"
    if knowledge.exists():
        shutil.rmtree(knowledge)
    rng = random.Random(seed)
    for index in range(documents):
        folder = knowledge / f"part-{index // 100:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"doc-{index:05d}.md").write_text(
            _document(rng, prose, index), encoding="utf-8", newline="\n"
        )
    (dest / "mycelium.toml").write_text(
        "# Generated by tools/benchmark_reference_profile.py - the reference profile\n"
        "# spec 04 §1 states its budgets against (roadmap 6.4).\n"
        "[project]\n"
        'name = "reference-profile"\n'
        "\n"
        "[embedding]\n"
        "# The shipped default query path is lexical (ADR-0017), so the profile is\n"
        "# built without vectors: embedding 10^5 chunks would measure the embedder,\n"
        "# which has its own benchmark, and would not change a lexical query's cost.\n"
        'provider = "none"\n',
        encoding="utf-8",
        newline="\n",
    )
    return documents


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    """One timed claim, and the budget it is claimed against."""

    name: str
    unit: str
    budget: float | None
    samples: list[float] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def p50(self) -> float:
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        ordered = sorted(self.samples)
        return ordered[max(0, min(len(ordered) - 1, int(0.95 * (len(ordered) - 1))))]

    def as_dict(self) -> dict[str, Any]:
        within = None if self.budget is None else self.p95 <= self.budget
        return {
            "name": self.name,
            "unit": self.unit,
            "budget": self.budget,
            "samples": len(self.samples),
            "min": round(min(self.samples), 3),
            "p50": round(self.p50, 3),
            "p95": round(self.p95, 3),
            "max": round(max(self.samples), 3),
            "mean": round(statistics.fmean(self.samples), 3),
            "within_budget": within,
            **self.notes,
        }


def populate_store(workspace: Path, prose: Prose, chunks: int, *, seed: int) -> int:
    """Write `chunks` chunks of real prose straight into a store, and publish it.

    **For the query measurement only, and the distinction is the point.** NFR-2's
    condition is *10⁵ chunks, warm store* — a statement about what the retriever
    reads, not about how the rows got there. The retriever reads the derived store
    and nothing else (spec 04 §1's token-frugality contract), so a store filled
    directly is the same substrate a compiled one presents, and BM25 cannot tell
    the difference: the FTS5 index is written by the same `put_chunks` the
    compiler calls.

    It would be worthless for a *build* measurement, where how the rows got there
    is the entire question — which is why the cold-build and incremental figures
    come from compiled corpora and only these two come from here.

    Returns the number of chunks written.
    """
    rng = random.Random(seed)
    store_dir = workspace / STORE_DIRNAME
    if store_dir.exists():
        shutil.rmtree(store_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "mycelium.toml").write_text(
        '[project]\nname = "reference-profile-query"\n\n[embedding]\nprovider = "none"\n',
        encoding="utf-8",
        newline="\n",
    )

    per_document = CHUNKS_PER_DOCUMENT
    documents = max(1, chunks // per_document)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    headings: list[tuple[str, str, str]] = []
    with SqliteStore.open(workspace) as store:
        for start in range(0, documents, 2_000):
            with store.transaction():
                for index in range(start, min(start + 2_000, documents)):
                    doc_id = encode_ulid(_ULID_EPOCH_MS + index, rng.randbytes(10))
                    path = f"knowledge/part-{index // 100:04d}/doc-{index:05d}.md"
                    heading = rng.choice(prose.headings)
                    headings.append((doc_id, path, heading))
                    store.put_document(
                        Document(
                            doc_id=doc_id,
                            path=path,
                            title=heading,
                            content_digest=_DIGEST,
                            trust_class=TrustClass.AUTHORED,
                            verification_status=VerificationStatus.VERIFIED,
                            provenance=Provenance(),
                            stats=DocumentStats(tokens=0, headings=1, chunks=0, links_out=0),
                            created_at=now,
                            updated_at=now,
                        )
                    )

    # The chunks go in through plain SQL rather than `put_chunks`, and the reason is
    # a defect this very report measured (BUG-0031): `put_chunks` deletes the anchor's
    # row from `chunks_fts` before inserting, `anchor` is an UNINDEXED column of an
    # FTS5 table, and SQLite can only answer that with a full scan — so loading N
    # chunks costs O(N^2) and 10^5 of them is about nine hours. The statements below
    # are `put_chunks`'s own, minus that delete, which has nothing to remove in a
    # store built once: the rows, the columns and the tokenisation are identical, so
    # the index a query reads is the index the compiler would have built.
    written = 0
    connection = sqlite3.connect(workspace / STORE_DIRNAME / "store.db")
    try:
        for start in range(0, len(headings), 2_000):
            rows: list[tuple[Any, ...]] = []
            fts: list[tuple[Any, ...]] = []
            for doc_id, path, heading in headings[start : start + 2_000]:
                for ordinal in range(per_document):
                    text = "\n\n".join(rng.choice(prose.blocks) for _ in range(BLOCKS_PER_CHUNK))
                    anchor = f"{path}#{heading_slug(heading)}/{ordinal}"
                    rows.append(
                        (
                            anchor,
                            doc_id,
                            _chunk_digest(anchor),
                            canonical_json([heading]),
                            canonical_json([f"n{ordinal}"]),
                            text,
                            len(text.split()),
                            "prose",
                            canonical_json([ordinal * 10, ordinal * 10 + 9]),
                            "default",
                        )
                    )
                    fts.append(
                        (
                            anchor,
                            text,
                            heading,
                            heading,
                            "",
                            _stemmed(text),
                            _stemmed(heading),
                            _stemmed(heading),
                            "",
                        )
                    )
            connection.execute("BEGIN")
            connection.executemany(
                "INSERT INTO chunks(anchor, doc_id, chunk_digest, heading_path_json,"
                " kir_nodes_json, text, tokens, kind, lines_json, namespace)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            connection.executemany(
                "INSERT INTO chunks_fts(anchor, text, title, heading, ancestors,"
                " text_stem, title_stem, heading_stem, ancestors_stem)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                fts,
            )
            connection.commit()
            written += len(rows)
            print(f"    {written} chunks", flush=True)
    finally:
        connection.close()
    # `handle_search` refuses a repository with no published snapshot, and the
    # pointer is the whole of publication a reader consults (ADR-0009).
    (store_dir / CURRENT_FILENAME).write_text(
        encode_ulid(_ULID_EPOCH_MS, bytes(10)) + "\n", encoding="utf-8", newline="\n"
    )
    return written


class _ProfileEmbedder:
    """A deterministic stand-in for the query side of the vector leg.

    It satisfies :class:`~mycelium.embedding.base.Embedder` and returns a seeded
    unit vector, so `search` runs its whole hybrid path — plan, lexical leg,
    vector leg, fusion — without a 133 MB model in the loop.

    **What this excludes is measured separately and named in the report.** A real
    hybrid query also pays one `embed_query` call against the local model, and
    that cost belongs to the *embedder* rather than to retrieval; it is timed on
    its own by :func:`measure_query_embedding` where the model is present, so a
    reader adds two numbers instead of being handed one that hides which is which.
    """

    model_id = VECTOR_MODEL_ID
    provider = "reference-profile"
    dim = VECTOR_DIM
    deterministic = True

    def __init__(self, queries: Sequence[str] = ()) -> None:
        # Precomputed, and that is not an optimisation — it is what keeps the
        # instrument out of the measurement. Drawing 384 gaussians in Python costs
        # milliseconds, and `search` calls `embed_query` *inside* the region a
        # hybrid query is timed over, so a generated vector would have been
        # charged to retrieval. The real embedder's cost is measured on its own
        # by `measure_query_embedding` (roadmap 6.21).
        self._cache = {query: self._draw(query) for query in queries}

    def _draw(self, text: str) -> tuple[float, ...]:
        rng = random.Random(hashlib.sha256(text.encode("utf-8")).digest())
        values = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        norm = sum(value * value for value in values) ** 0.5
        return tuple(value / norm for value in values)

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> tuple[float, ...]:
        cached = self._cache.get(text)
        if cached is None:
            cached = self._cache[text] = self._draw(text)
        return cached


def populate_vectors(workspace: Path, *, seed: int) -> int:
    """Write one synthetic unit vector per chunk, and let the store pack them.

    Every chunk the store holds, keyed by the digest `populate_store` gave it, so
    the matrix has exactly the shape a compiled corpus of that size would present.
    The write goes through `put_vectors` inside a transaction — the same path the
    embed stage uses — so the commit triggers `repack_vectors` and the memory-mapped
    matrix (ADR-0026) is built by the code that builds it in production rather than
    by this file.

    Embedding 10⁵ real chunks with the local model is hours of work that would
    measure the *embedder*; the scan's cost does not depend on what the vectors
    contain, which is why synthetic ones are the honest choice here and why
    `tests/bench/test_retrieval_bench.py` has always used them at 10 000
    (roadmap 6.21).

    Returns the number of vectors written.
    """
    rng = random.Random(seed)
    written = 0
    with SqliteStore.open(workspace) as store:
        digests = [
            str(row["chunk_digest"])
            for row in store._connection.execute("SELECT DISTINCT chunk_digest FROM chunks")
        ]
        for start in range(0, len(digests), 5_000):
            batch = digests[start : start + 5_000]
            with store.transaction():
                written += store.put_vectors(
                    VECTOR_MODEL_ID, ((digest, _unit_vector(rng)) for digest in batch)
                )
            print(f"    {written} vectors", flush=True)
    return written


def _unit_vector(rng: random.Random) -> tuple[float, ...]:
    values = [rng.gauss(0.0, 1.0) for _ in range(VECTOR_DIM)]
    norm = sum(value * value for value in values) ** 0.5
    return tuple(value / norm for value in values)


def measure_vector_path(
    workspace: Path, queries: Sequence[str]
) -> tuple[list[Measurement], dict[str, Any]]:
    """Time the vector leg and the whole hybrid query at this scale (roadmap 6.21).

    Four measurements, because four different things were being confused.

    **The vector leg on a fresh handle** is what a CLI invocation pays: a store
    maps its packed matrix once per handle (ADR-0026), so the first query carries
    the mapping and the process then exits. **On a warm handle** is what the MCP
    server pays, every query after the first.

    **The hybrid query, warm** is what a caller actually waits for with
    `[retrieval] profile = "hybrid"`: the lexical leg, the vector leg and the
    fusion of the two. **The lexical query, warm** is the same store and the same
    questions with the vector leg off — the comparison that says what hybrid costs
    *over* the shipped default rather than in the abstract.

    Hybrid queries are split by whether the vector leg actually ran. It is
    withheld where the lexical leg found nothing (ADR-0025), so folding those
    into one mean would report the cost of a leg that did not run; the two
    buckets and their counts are reported instead.

    The page cache is warm for all of them: the pack was just written. A genuinely
    cold file-system read is a property of the machine and the report says so
    rather than pretending this measures it.
    """
    embedder = _ProfileEmbedder(queries)
    hybrid_config = RetrievalConfig(profile="hybrid")
    lexical_config = RetrievalConfig()
    probe = embedder.embed_query("candidate generation over the reference profile")

    fresh = Measurement(
        name="vector leg, first query on a fresh handle (a CLI invocation)",
        unit="ms",
        budget=CANDIDATE_BUDGET_MS,
    )
    for query in queries[:VECTOR_FRESH_SAMPLES]:
        with SqliteStore.open(workspace, read_only=True) as handle:
            vector = embedder.embed_query(query)
            started = time.perf_counter()
            handle.search_vectors(vector, VECTOR_MODEL_ID, limit=50)
            fresh.samples.append((time.perf_counter() - started) * 1000)

    warm = Measurement(
        name="vector leg, warm handle (the MCP server)", unit="ms", budget=CANDIDATE_BUDGET_MS
    )
    hybrid = Measurement(
        name="search, hybrid, both legs ran, warm store (in-process)",
        unit="ms",
        budget=QUERY_BUDGET_MS,
    )
    withheld = Measurement(
        name="search, hybrid configured but the vector leg withheld (ADR-0025)",
        unit="ms",
        budget=QUERY_BUDGET_MS,
    )
    lexical = Measurement(
        name="search, lexical, warm store (in-process)", unit="ms", budget=QUERY_BUDGET_MS
    )
    precondition = Measurement(
        name="vector_counts(), the hybrid precondition `search` runs per query",
        unit="ms",
        budget=None,
    )
    with SqliteStore.open(workspace, read_only=True) as store:
        store.search_vectors(probe, VECTOR_MODEL_ID, limit=50)  # map the pack
        for query in queries:
            vector = embedder.embed_query(query)
            started = time.perf_counter()
            store.search_vectors(vector, VECTOR_MODEL_ID, limit=50)
            warm.samples.append((time.perf_counter() - started) * 1000)

        for query in queries:  # one pass to warm the page cache for both legs
            search(store, query, limit=10, config=hybrid_config, embedder=embedder)
        # Counted across every timed query, not read off the last one. The vector
        # leg is *withheld* where the lexical leg found nothing (ADR-0025's
        # precondition: hybrid abstains wherever lexical abstains), so a question
        # this corpus cannot answer costs the lexical price and belongs in a
        # different bucket. Sampling the final query's `legs` reported `lexical`
        # for a pass in which the leg had run on almost all of them — an instrument
        # defect caught before it reached a report (roadmap 6.21).
        both_legs = 0
        for query in queries:
            started = time.perf_counter()
            outcome = search(store, query, limit=10, config=hybrid_config, embedder=embedder)
            elapsed = (time.perf_counter() - started) * 1000
            if "vector" in outcome.legs:
                both_legs += 1
                hybrid.samples.append(elapsed)
            else:
                withheld.samples.append(elapsed)
        for query in queries:
            started = time.perf_counter()
            search(store, query, limit=10, config=lexical_config)
            lexical.samples.append((time.perf_counter() - started) * 1000)
        # `search` asks this once per hybrid query, to decide whether the snapshot
        # holds vectors for the model at all (ADR-0025's degradation path). It is a
        # `GROUP BY` over the whole `vectors` table, so it is timed here rather
        # than left inside the residual (roadmap 6.21).
        for _ in queries:
            started = time.perf_counter()
            store.vector_counts()
            precondition.samples.append((time.perf_counter() - started) * 1000)
        vectors = store.vector_counts().get(VECTOR_MODEL_ID, 0)
        packed = store._pack_for(VECTOR_MODEL_ID) is not None

    notes: dict[str, Any] = {
        "vectors": vectors,
        "dim": VECTOR_DIM,
        "matrix_bytes": vectors * VECTOR_DIM * 4,
        "packed": packed,
        "queries": len(queries),
        "queries_that_ran_both_legs": both_legs,
        "queries_with_the_vector_leg_withheld": len(queries) - both_legs,
        "embedder": "synthetic unit vectors; see populate_vectors()",
    }
    measured = [fresh, warm, hybrid, lexical, precondition]
    if withheld.samples:
        measured.insert(3, withheld)
    return measured, notes


def measure_query_embedding(queries: Sequence[str]) -> Measurement | None:
    """What one `embed_query` costs against the shipped local model, if it is here.

    The half :class:`_ProfileEmbedder` leaves out. It is a property of the model
    and the machine rather than of the corpus, so it does not scale with the
    profile — which is exactly why it is measured once, separately, and added by
    the reader rather than folded into the hybrid number.

    ``None`` when the model is not on this machine: CI has no model by design
    (D-013), and a benchmark that invented the number would be worse than one that
    says it is missing.
    """
    try:
        embedder = build_embedder(provider="local-onnx", model_id="bge-small-en-v1.5")
    except EmbeddingError as error:
        print(f"  query embedding: not measured - {error}", flush=True)
        return None
    if embedder is None:  # pragma: no cover - provider "none" is not passed here
        return None
    measurement = Measurement(
        name="embed_query, local ONNX model (excluded from the hybrid figure above)",
        unit="ms",
        # No budget: spec 04 §1 budgets the stages of the query path, and the
        # embedder is a property of the model and the machine, not of retrieval.
        budget=None,
        notes={"model_id": embedder.model_id, "provider": embedder.provider, "dim": embedder.dim},
    )
    for query in queries[:8]:  # warm the session
        embedder.embed_query(query)
    for query in queries:
        started = time.perf_counter()
        embedder.embed_query(query)
        measurement.samples.append((time.perf_counter() - started) * 1000)
    return measurement


def measure_file_io(workspace: Path, *, files: int = IO_CALIBRATION_FILES) -> Measurement:
    """What one small-file open costs on this machine, warm.

    The calibration constant the build measurements have to be read against. It is
    taken over the generated corpus itself, so it is the same files, on the same
    filesystem, through the same interpreter as the build that follows.
    """
    paths = sorted((workspace / "knowledge").rglob("*.md"))[:files]
    for path in paths:  # warm the page cache; the scanner is what we are measuring
        path.read_bytes()
    measurement = Measurement(name="read one small Markdown file, warm", unit="ms", budget=None)
    for path in paths:
        started = time.perf_counter()
        path.read_bytes()
        measurement.samples.append((time.perf_counter() - started) * 1000)
    measurement.notes["files"] = len(paths)
    measurement.notes["mean_bytes"] = round(statistics.fmean(path.stat().st_size for path in paths))
    return measurement


def _queries(root: Path) -> tuple[str, ...]:
    found: list[str] = []
    for relative in QUERY_SETS:
        path = root / relative
        if path.is_file():
            found.extend(case.query for case in load_cases(path))
    if not found:  # pragma: no cover - the sets are committed
        msg = "no judged queries found; the reference profile measures real questions"
        raise SystemExit(msg)
    return tuple(found)


def measure_cold_build(workspace: Path, prose: Prose, documents: int, *, seed: int) -> Measurement:
    """Time one clean build of `documents` generated documents (spec 01 §8).

    The manifest's own per-stage timings are carried into the notes (roadmap
    6.19). A total says whether a budget is met; the stages say which part to
    look at, and carrying them costs nothing because the compiler already
    measured them — `timings_ms` is in every snapshot manifest (spec 03 §7).
    """
    generate(workspace, prose, documents, seed=seed)
    started = time.perf_counter()
    result = build(workspace, clean=True, pin_identity=False)
    elapsed = time.perf_counter() - started
    timings = dict(result.manifest.timings_ms)
    return Measurement(
        name=f"cold build, {documents} documents",
        unit="s",
        budget=COLD_BUILD_BUDGET_S if documents == COLD_BUILD_DOCUMENTS else None,
        samples=[elapsed],
        notes={
            "documents": result.manifest.counts.documents,
            "chunks": result.manifest.counts.chunks,
            "documents_per_second": round(result.manifest.counts.documents / elapsed, 1),
            "ms_per_document": round(1000 * elapsed / max(1, result.manifest.counts.documents), 1),
            "stages_ms": timings,
            "stage_share": {
                stage: round(100 * value / timings["total"], 1)
                for stage, value in sorted(timings.items(), key=lambda row: -row[1])
                if stage != "total" and timings.get("total")
            },
        },
    )


def profile_cold_build(
    workspace: Path, prose: Prose, documents: int, *, seed: int, top: int = 25
) -> dict[str, Any]:
    """Where a cold build's time actually goes, by cumulative time (roadmap 6.19).

    Filed as its own step rather than folded into the measurement above, because
    a profiler's overhead is real and a timed run must not carry it. What it is
    *for* is the rule ADR-0026 established the hard way: the cost everyone
    assumed was the vector arithmetic turned out to be reading the vectors row by
    row, so the stage that looks expensive is not evidence about the line that
    is. Nothing here is optimised on the strength of a guess.

    Reports both `cumtime` — which names the stage — and `tottime`, which names
    the line, because a function high in one and low in the other is a caller
    rather than a cost.
    """
    generate(workspace, prose, documents, seed=seed)
    profiler = cProfile.Profile()
    profiler.enable()
    build(workspace, clean=True, pin_identity=False)
    profiler.disable()

    stats = pstats.Stats(profiler)
    entries: list[tuple[str, int, float, float]] = [
        (f"{Path(func[0]).name}:{func[1]}({func[2]})", primitive, tottime, cumtime)
        for func, (_calls, primitive, tottime, cumtime, _callers) in stats.stats.items()  # type: ignore[attr-defined]
    ]
    # Summed rather than read off `Stats.total_tt`, which the stubs do not carry:
    # the sum of every function's self time *is* the profiled total, by definition.
    total = sum(tottime for _name, _primitive, tottime, _cumtime in entries)
    rows: list[dict[str, Any]] = [
        {
            "function": name,
            "calls": primitive,
            "tottime_s": round(tottime, 3),
            "cumtime_s": round(cumtime, 3),
            "tottime_share": round(100 * tottime / total, 1) if total else 0.0,
        }
        for name, primitive, tottime, cumtime in entries
    ]
    by_self = sorted(rows, key=lambda row: -float(row["tottime_s"]))[:top]
    by_cumulative = sorted(rows, key=lambda row: -float(row["cumtime_s"]))[:top]
    return {
        "documents": documents,
        "profiled_seconds": round(total, 2),
        "note": (
            "under cProfile, so the total is inflated against the timed run; the "
            "shares are what this is for"
        ),
        "by_self_time": by_self,
        "by_cumulative_time": by_cumulative,
    }


def measure_incremental(workspace: Path, *, samples: int = INCREMENTAL_SAMPLES) -> Measurement:
    """Time single-document edits, rebuilt incrementally (NFR-3, spec 06 Phase 1).

    The edit is an appended sentence to a document chosen round-robin across the
    tree, so the measurement is not one lucky file's.
    """
    documents = sorted((workspace / "knowledge").rglob("*.md"))
    measurement = Measurement(
        name="incremental rebuild, one document edited",
        unit="ms",
        budget=INCREMENTAL_BUDGET_MS,
        notes={"corpus_documents": len(documents)},
    )
    step = max(1, len(documents) // samples)
    for index in range(samples):
        target = documents[(index * step) % len(documents)]
        target.write_text(
            target.read_text(encoding="utf-8")
            + f"\nThe retry policy was revised in revision {index}.\n",
            encoding="utf-8",
            newline="\n",
        )
        started = time.perf_counter()
        build(workspace, pin_identity=False)
        measurement.samples.append((time.perf_counter() - started) * 1000)
    return measurement


def measure_queries(
    workspace: Path, queries: Sequence[str]
) -> tuple[Measurement, Measurement, int]:
    """Time the query path two ways: warm in-process, and as an MCP call.

    Both are reported because NFR-2 names `mycelium_search` **end to end**, and
    the difference between them is a cost the in-process number hides: the tool
    handler opens a fresh store per call *by design*, so that a long-lived agent
    session sees each published snapshot rather than the one that existed when
    the server started. At 1 400 chunks that was microseconds. Whether it still is
    at 10⁵ is exactly the kind of thing a reference profile exists to find out.
    """
    warm = Measurement(name="search, warm store (in-process)", unit="ms", budget=QUERY_BUDGET_MS)
    end_to_end = Measurement(
        name="mycelium_search, end to end (MCP handler)", unit="ms", budget=QUERY_BUDGET_MS
    )
    with SqliteStore.open(workspace, read_only=True) as store:
        chunks = store.counts()["chunks"]
        for query in queries:  # one pass to warm the page cache
            search(store, query, limit=10)
        for query in queries:
            started = time.perf_counter()
            search(store, query, limit=10)
            warm.samples.append((time.perf_counter() - started) * 1000)
    for query in queries:
        started = time.perf_counter()
        handle_search(workspace, {"query": query})
        end_to_end.samples.append((time.perf_counter() - started) * 1000)
    return warm, end_to_end, chunks


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _incremental_samples(documents: int) -> int:
    """Fewer timed edits on a big corpus, because each one costs a whole rebuild.

    Stated rather than hidden: a p95 over five samples is the worst of five, and the
    manifest records the count beside the number so nobody reads it as more.
    """
    if documents <= 2_500:
        return INCREMENTAL_SAMPLES
    return 8 if documents <= 5_000 else 5


def _scale(
    out: Path, prose: Prose, queries: Sequence[str], documents: int, *, seed: int
) -> dict[str, Any]:
    """Every measurement, at one corpus size."""
    workspace = out / f"scale-{documents:06d}"
    print(f"\n--- {documents} documents ---", flush=True)

    cold = measure_cold_build(workspace, prose, documents, seed=seed)
    print(
        f"  cold build      {cold.p50:8.1f} s   "
        f"{cold.notes['chunks']} chunks, {cold.notes['documents_per_second']} docs/s",
        flush=True,
    )
    shares = cold.notes.get("stage_share")
    if isinstance(shares, dict):
        # Which stage to look at, printed beside the total it adds up to. A build
        # that misses its budget is a question; the stages are where to ask it.
        print(
            "  stages          "
            + "  ".join(f"{stage} {share:.0f}%" for stage, share in list(shares.items())[:6]),
            flush=True,
        )

    disk = measure_file_io(workspace)
    print(f"  file open       {disk.p50:8.3f} ms  (calibration, warm)", flush=True)

    samples = _incremental_samples(documents)
    incremental = measure_incremental(workspace, samples=samples)
    print(
        f"  incremental     {incremental.p95:8.0f} ms p95 ({samples} edits)",
        flush=True,
    )

    warm, end_to_end, chunks = measure_queries(workspace, queries)
    print(
        f"  search warm     {warm.p95:8.1f} ms p95   end-to-end {end_to_end.p95:.1f} ms p95",
        flush=True,
    )

    # The corpus is the expensive part and there may be several more sizes to go.
    shutil.rmtree(workspace, ignore_errors=True)

    return {
        "documents": cold.notes["documents"],
        "chunks": chunks,
        "measurements": [item.as_dict() for item in (cold, incremental, warm, end_to_end, disk)],
    }


def run(
    out: Path,
    *,
    chunks: int,
    seed: int,
    scales: Sequence[int],
    reference: bool,
    query_scale: int = 0,
    vectors: bool = False,
    real_corpora: bool = False,
    profile: int = 0,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Measure every claim across the curve, and return the manifest."""
    prose = harvest(ROOT)
    queries = _queries(ROOT)
    print(
        f"harvested {len(prose.blocks)} blocks ({prose.words} words), "
        f"{len(prose.headings)} headings; {len(queries)} judged queries"
    )
    out.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "commit": _commit(),
        "toolchain": {"mycelium": __version__, "python": platform.python_version()},
        "hardware": hardware(),
        "corpus": {
            "kind": "generated",
            "generator": "tools/benchmark_reference_profile.py",
            "seed": seed,
            "sources": [str(path).replace("\\", "/") for path in SOURCE_CORPORA],
            "queries": len(queries),
            "query_sets": [str(path).replace("\\", "/") for path in QUERY_SETS],
            # The corpus is *compiled* with the embedder off, which is what the
            # shipped default reads. `--vectors` adds a synthetic matrix to the
            # finished store afterwards and documents it under `vector_profile`;
            # saying so here keeps the two from reading as a contradiction.
            "profile": (
                "lexical (the shipped default, ADR-0017); compiled with the embedder off"
                + (
                    ". A synthetic vector matrix was written into the finished store "
                    "afterwards - see `vector_profile` (roadmap 6.21)"
                    if vectors
                    else ", and no vectors were written"
                )
            ),
        },
        "budgets": {
            "cold_build_1k_s": COLD_BUILD_BUDGET_S,
            "incremental_p95_ms": INCREMENTAL_BUDGET_MS,
            "search_p95_ms": QUERY_BUDGET_MS,
            "reference_chunks": REFERENCE_CHUNKS,
        },
        "scales": [],
    }

    def flush() -> None:
        """Write what has been measured so far.

        The reference scale takes hours, and a run that is interrupted at the last
        size must still leave the curve behind rather than nothing.
        """
        if manifest_path is not None:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    targets = list(scales)
    for index, documents in enumerate(targets):
        manifest["scales"].append(_scale(out, prose, queries, documents, seed=seed + index))
        flush()

    if profile:
        print(f"\n=== where a {profile}-document cold build spends its time ===", flush=True)
        report = profile_cold_build(out / "profile", prose, profile, seed=seed)
        for row in report["by_self_time"][:12]:
            print(
                f"  {row['tottime_share']:5.1f}%  {row['tottime_s']:7.2f} s self  "
                f"{row['cumtime_s']:8.2f} s cum  {row['function']}",
                flush=True,
            )
        manifest["build_profile"] = report
        flush()

    if real_corpora:
        print("\n=== cross-check: the real corpora, already built ===", flush=True)
        rows: list[dict[str, Any]] = []
        for relative in REAL_CORPORA:
            root = ROOT / relative
            if not (root / STORE_DIRNAME).is_dir():
                print(f"  {relative}: not built, skipped", flush=True)
                continue
            warm, end_to_end, chunks = measure_queries(root, queries)
            print(
                f"  {str(relative):24} {chunks:6} chunks   warm p95 {warm.p95:6.1f} ms   "
                f"end-to-end p95 {end_to_end.p95:6.1f} ms",
                flush=True,
            )
            rows.append(
                {
                    "corpus": str(relative).replace("\\", "/"),
                    "chunks": chunks,
                    "measurements": [warm.as_dict(), end_to_end.as_dict()],
                }
            )
        manifest["real_corpora"] = rows
        flush()

    if query_scale:
        workspace = out / f"query-{query_scale:07d}"
        print(
            f"\n=== query profile: {query_scale} chunks written straight into a store ===",
            flush=True,
        )
        started = time.perf_counter()
        written = populate_store(workspace, prose, query_scale, seed=seed)
        print(f"  populated {written} chunks in {time.perf_counter() - started:.0f} s", flush=True)
        warm, end_to_end, chunks = measure_queries(workspace, queries)
        print(
            f"  search warm     {warm.p95:8.1f} ms p95   end-to-end {end_to_end.p95:.1f} ms p95",
            flush=True,
        )
        manifest["query_profile"] = {
            "chunks": chunks,
            "documents": max(1, query_scale // 5),
            "kind": "store populated directly (no compiler run); see populate_store()",
            "measurements": [warm.as_dict(), end_to_end.as_dict()],
        }
        flush()

        if vectors:
            # The vector leg and the hybrid query at the same scale, on the same
            # store, so the two halves of spec 04 §3's fusion are comparable
            # rather than measured a milestone apart (roadmap 6.21).
            print("\n=== vector profile: one synthetic vector per chunk ===", flush=True)
            started = time.perf_counter()
            written = populate_vectors(workspace, seed=seed + 1)
            print(
                f"  wrote and packed {written} vectors in {time.perf_counter() - started:.0f} s",
                flush=True,
            )
            measurements, notes = measure_vector_path(workspace, queries)
            for measurement in measurements:
                print(
                    f"  {measurement.name:<52} {measurement.p50:8.1f} ms p50"
                    f"   {measurement.p95:8.1f} ms p95",
                    flush=True,
                )
            embedding = measure_query_embedding(queries)
            if embedding is not None:
                print(
                    f"  {embedding.name:<52} {embedding.p50:8.1f} ms p50"
                    f"   {embedding.p95:8.1f} ms p95",
                    flush=True,
                )
                measurements.append(embedding)
            manifest["vector_profile"] = {
                "chunks": chunks,
                **notes,
                "measurements": [item.as_dict() for item in measurements],
            }
            flush()

        shutil.rmtree(workspace, ignore_errors=True)

    if reference:
        measured = manifest["scales"][-1]
        per_document = measured["chunks"] / max(1, measured["documents"])
        documents = max(1, round(chunks / per_document))
        print(
            f"\n=== reference profile: {documents} documents for ~{chunks} chunks "
            f"({per_document:.1f} chunks/document) ===",
            flush=True,
        )
        manifest["scales"].append(_scale(out, prose, queries, documents, seed=seed + len(targets)))
        flush()

    return manifest


# ---------------------------------------------------------------------------
# --check: the committed reports still answer for themselves
# ---------------------------------------------------------------------------

REQUIRED_MANIFEST_KEYS: Final = (
    "schema",
    "generated_at",
    "commit",
    "toolchain",
    "hardware",
    "corpus",
    "budgets",
)
"""What every manifest must carry to be evidence rather than a note.

`commit` and `hardware` are the two that make a number comparable at all; `budgets`
is here so a reader can see what the run was measured *against* without going to the
spec, and so a changed budget is visible in a diff."""

MEASUREMENT_SECTIONS: Final = (
    "scales",
    "query_profile",
    "vector_profile",
    "real_corpora",
    "task_profile",
)
"""(`build_profile` is deliberately absent: it holds a profiler's shares rather than
timings, so it has no `p95` and cannot make a manifest evidence on its own.)"""
"""Where measurements live. A manifest needs at least one non-empty section — a run
that timed nothing is a note about a machine.

`task_profile` is `tools/measure_agent_task_band.py`'s (roadmap 6.22), and it is
the first section here whose measurements are not milliseconds: it reports the
*context* each strategy puts in front of a model, in tokens. The `p95` every
measurement must carry still means what it means — a distribution's tail over the
suite's tasks — which is why it needed no exception."""


def _measurement_blocks(section: Any) -> list[list[Any]]:
    """The `measurements` lists inside one manifest section, whatever its shape.

    `scales` and `real_corpora` are lists of blocks; `query_profile` is one block.
    Reading all three the same way keeps the check from needing to know which is
    which — and from silently skipping a section somebody adds later.
    """
    blocks = section if isinstance(section, list) else [section]
    return [
        block["measurements"]
        for block in blocks
        if isinstance(block, dict) and isinstance(block.get("measurements"), list)
    ]


def check() -> int:
    """Every committed manifest is readable and carries what makes it evidence.

    Cheap enough for CI, which is the point: the expensive half of this tool is
    run by hand when a claim is being substantiated, and the report it leaves
    behind is what everything afterwards reads.
    """
    problems: list[str] = []
    manifests = sorted(MANIFESTS.glob("*.json")) if MANIFESTS.is_dir() else []
    reports = [
        path
        for path in (sorted(REPORTS.glob("*.md")) if REPORTS.is_dir() else [])
        if path.name not in {"README.md", "template.md"}
    ]
    if not manifests and not reports:
        # Nothing has been published, so nothing is claimed. The congruence lint owns
        # the other direction — a report that cites no manifest.
        print("benchmark manifests: none, and no report claims one")
        return 0
    if not manifests:
        problems.append(f"no benchmark manifests under {MANIFESTS.relative_to(ROOT).as_posix()}")
    for path in manifests:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            problems.append(f"{path.name}: unreadable ({error})")
            continue
        missing = [key for key in REQUIRED_MANIFEST_KEYS if key not in document]
        if missing:
            problems.append(f"{path.name}: missing {', '.join(missing)}")
            continue
        if document["schema"] != SCHEMA:
            problems.append(f"{path.name}: schema {document['schema']!r}, expected {SCHEMA!r}")
        if not any(document.get(section) for section in MEASUREMENT_SECTIONS):
            problems.append(
                f"{path.name}: no measurements in any of {', '.join(MEASUREMENT_SECTIONS)}"
            )
        if document["hardware"].get("platform") is None:
            problems.append(f"{path.name}: no hardware recorded - the number is not comparable")
        if not document["commit"]:
            problems.append(f"{path.name}: no commit recorded - the run names no tree")
        for section in MEASUREMENT_SECTIONS:
            for block in _measurement_blocks(document.get(section)):
                for measurement in block:
                    if not isinstance(measurement, dict) or "p95" not in measurement:
                        problems.append(f"{path.name}: a measurement carries no p95")
                        break

    for problem in problems:
        print(f"[benchmark] {problem}")
    if problems:
        return 1
    print(f"benchmark manifests: OK - {len(manifests)} readable, each with its hardware")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate committed manifests only.")
    parser.add_argument("--out", type=Path, help="Where to generate the corpora.")
    parser.add_argument("--chunks", type=int, default=REFERENCE_CHUNKS)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument(
        "--scales",
        default=",".join(str(size) for size in DEFAULT_SCALES),
        help="Comma-separated corpus sizes, in documents.",
    )
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help=(
            "Stop after the curve; do not COMPILE the 10^5-chunk profile. Compiling it "
            "is ~9 hours (BUG-0031), so the query claim is measured with --query-scale "
            "instead and this flag is the normal case."
        ),
    )
    parser.add_argument(
        "--real-corpora",
        action="store_true",
        help="Also measure the query path on the repository's own built corpora.",
    )
    parser.add_argument(
        "--query-scale",
        type=int,
        default=0,
        help=(
            "Measure the query path at this many chunks, written straight into a store "
            "instead of compiled. NFR-2's condition is what the retriever reads, so this "
            "measures it at the reference size without a multi-hour build."
        ),
    )
    parser.add_argument(
        "--vectors",
        action="store_true",
        help=(
            "With --query-scale: write one synthetic vector per chunk and measure the "
            "vector leg and the hybrid query at that scale (roadmap 6.21)."
        ),
    )
    parser.add_argument(
        "--profile",
        type=int,
        default=0,
        metavar="DOCUMENTS",
        help=(
            "Also run one cold build of this many documents under cProfile and record "
            "where its time goes (roadmap 6.19). Separate from the timed run, whose "
            "number must not carry the profiler's overhead."
        ),
    )
    parser.add_argument("--manifest", type=Path, help="Write the manifest here.")
    args = parser.parse_args(argv)

    if args.check:
        return check()
    if args.out is None:
        parser.error("--out is required (the generated corpus needs somewhere to live)")

    manifest = run(
        args.out,
        chunks=args.chunks,
        seed=args.seed,
        scales=[int(size) for size in args.scales.split(",") if size.strip()],
        reference=not args.no_reference,
        query_scale=args.query_scale,
        vectors=args.vectors,
        real_corpora=args.real_corpora,
        profile=args.profile,
        manifest_path=args.manifest,
    )
    if args.manifest:
        print(f"\nmanifest: {args.manifest}")
    else:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
