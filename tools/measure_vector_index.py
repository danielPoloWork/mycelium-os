#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-run the evidence behind ADR-0028: can an index beat the exact scan?

    python tools/measure_vector_index.py [corpus-root] [--scale]

Two measurements, and they answer different halves of the question.

**Recall, on real embeddings.** Every candidate index is scored against the exact
top-50 it is trying to approximate, using the vectors in a *built* corpus. Random
vectors would not do: they are IVF's best case for latency and its worst for
structure, and the whole finding here is about the structure real embeddings have
(ADR-0025's cone).

**Latency, at the reference profile.** `--scale` synthesises 10^5 vectors — the
top of the v1 envelope (D-002) — and times a cold-process query. Geometry does not
change how long it takes to touch bytes, so synthetic vectors are honest here.

The table this prints is the one in ADR-0028. If it ever stops agreeing with that
ADR, one of the two is wrong and the ADR is the one that cannot be re-run.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from mycelium.store import SqliteStore  # noqa: E402

TOP_K = 50
"""spec 04 §3's vector-leg depth: the list an index has to reproduce."""
BUDGET_MS = 60
"""spec 04 §1's candidate-generation budget."""
REFERENCE_N = 100_000
"""D-002's upper envelope, where the exact scan misses the budget."""


def corpus_vectors(root: Path) -> tuple[np.ndarray, str]:
    """Every vector in a built corpus, as one float32 matrix."""
    with SqliteStore.open(root, read_only=True) as store:
        counts = store.vector_counts()
        if not counts:
            msg = f"{root} holds no vectors; build it with the embedding stage on"
            raise SystemExit(msg)
        model = next(iter(counts))
        rows = store._connection.execute(  # noqa: SLF001 - a measurement, not a client
            "SELECT vec, dim FROM vectors WHERE model_id = ?", (model,)
        ).fetchall()
    dim = int(rows[0]["dim"])
    flat = np.frombuffer(b"".join(bytes(row["vec"]) for row in rows), dtype="<f4")
    return np.ascontiguousarray(flat.reshape(len(rows), dim)), model


def probe_queries(matrix: np.ndarray, count: int = 60, noise: float = 0.15) -> np.ndarray:
    """Queries near real passages: a corpus vector, perturbed, re-normalised.

    Not corpus vectors themselves — an index that returns a query's own row is
    answering a question nobody asked — and not random directions, which land
    nowhere near the cone the corpus occupies.
    """
    rng = np.random.default_rng(11)
    picked = matrix[rng.choice(len(matrix), count, replace=False)]
    queries = picked + rng.standard_normal(picked.shape).astype("<f4") * noise
    return queries / np.linalg.norm(queries, axis=1, keepdims=True)


def exact_top(matrix: np.ndarray, query: np.ndarray) -> set[int]:
    return set(np.argsort(-(matrix @ query))[:TOP_K].tolist())


def recall_of(matrix: np.ndarray, queries: np.ndarray, select) -> float:
    """Fraction of the exact top-50 an index actually returns."""
    hits = sum(len(exact_top(matrix, q) & set(select(q).tolist())) for q in queries)
    return hits / (TOP_K * len(queries))


def ivf(matrix: np.ndarray, nlist: int, seed: int = 20260831, iters: int = 12):
    """Coarse quantisation: k-means centroids, then probe the nearest lists."""
    rng = np.random.default_rng(seed)
    centroids = matrix[rng.choice(len(matrix), nlist, replace=False)].copy()
    for _ in range(iters):
        assign = np.argmax(matrix @ centroids.T, axis=1)
        for cluster in range(nlist):
            members = matrix[assign == cluster]
            if len(members):
                centre = members.mean(axis=0)
                norm = np.linalg.norm(centre)
                if norm:
                    centroids[cluster] = centre / norm
    assign = np.argmax(matrix @ centroids.T, axis=1)
    order = np.argsort(assign, kind="stable")
    bounds = np.searchsorted(assign[order], np.arange(nlist + 1))
    return centroids, order, bounds


def report_recall(root: Path) -> None:
    matrix, model = corpus_vectors(root)
    queries = probe_queries(matrix)
    count, dim = matrix.shape
    print(f"\nRECALL on {count} real vectors from {root} ({model}, dim {dim})")
    print(f"  {'mechanism':<44} {'work':>7} {'recall@50':>10}")

    nlist = max(8, int(np.sqrt(count)))
    centroids, order, bounds = ivf(matrix, nlist)
    for nprobe in (2, 4, 8, 16, 24, 32):
        if nprobe > nlist:
            break
        touched = []

        def select(query: np.ndarray, nprobe: int = nprobe, touched=touched) -> np.ndarray:
            probes = np.argsort(-(centroids @ query))[:nprobe]
            rows = np.concatenate([order[bounds[c] : bounds[c + 1]] for c in probes])
            touched.append(len(rows) / count)
            scores = matrix[rows] @ query
            keep = min(TOP_K, len(scores))
            return rows[np.argpartition(-scores, keep - 1)[:keep]]

        value = recall_of(matrix, queries, select)
        print(f"  {'IVF, nprobe=' + str(nprobe):<44} {np.mean(touched) * 100:6.1f}% {value:10.3f}")

    mean = matrix.mean(axis=0)
    centred = matrix - mean
    _, _, components = np.linalg.svd(centred, full_matrices=False)
    for reduced in (64, 128):
        projection = np.ascontiguousarray(components[:reduced].T)
        projected = np.ascontiguousarray(centred @ projection)

        def select(query: np.ndarray, projected=projected, projection=projection) -> np.ndarray:
            approx = projected @ ((query - mean) @ projection)
            candidates = np.argpartition(-approx, 199)[:200]
            scores = matrix[candidates] @ query
            return candidates[np.argpartition(-scores, TOP_K - 1)[:TOP_K]]

        label = f"PCA d'={reduced}, rescore 200 exactly"
        print(
            f"  {label:<44} {reduced / dim * 100:6.1f}% {recall_of(matrix, queries, select):10.3f}"
        )

    scale = float(np.abs(matrix).max())
    quantised = np.clip(np.round(matrix / scale * 127), -127, 127).astype(np.int8)
    for candidates in (100, 200):

        def select(query: np.ndarray, candidates: int = candidates) -> np.ndarray:
            coarse = quantised.astype(np.float32) @ query
            picked = np.argpartition(-coarse, candidates - 1)[:candidates]
            scores = matrix[picked] @ query
            return picked[np.argpartition(-scores, TOP_K - 1)[:TOP_K]]

        label = f"int8 first pass, rescore {candidates} exactly"
        print(f"  {label:<44} {25.0:6.1f}% {recall_of(matrix, queries, select):10.3f}")


def timed(label: str, mode: str, scratch: Path, rounds: int = 5) -> float:
    """Time one query per *process*, which is the only honest way to measure this.

    Timing repeated calls inside one process measures something no code path does.
    A store maps its packed matrix once per handle (ADR-0026), so a long-lived
    server re-uses that mapping and a CLI invocation makes exactly one. Re-mapping
    the same 154 MB file in a loop is neither: it costs about 71 ms a call against
    31 ms for the first, and reporting that as "cold" is what ADR-0030 had to
    correct in two earlier ADRs.
    """
    samples = []
    for _ in range(rounds):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", mode, str(scratch)],
            capture_output=True,
            text=True,
            check=True,
        )
        samples.append(float(result.stdout.strip()))
    samples.sort()
    median = samples[len(samples) // 2]
    verdict = "within" if median <= BUDGET_MS else "OVER"
    print(f"  {label:<44} {median:7.2f} ms  {verdict} the {BUDGET_MS} ms budget")
    return median


def reference_paths(scratch: Path) -> tuple[Path, Path, int]:
    """The synthetic reference matrix, written once."""
    dim = 384
    matrix_path = scratch / f"reference-{REFERENCE_N}.f32"
    quantised_path = scratch / f"reference-{REFERENCE_N}.i8"
    if not matrix_path.exists():
        rng = np.random.default_rng(20260831)
        matrix = rng.standard_normal((REFERENCE_N, dim)).astype("<f4")
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix_path.write_bytes(matrix.tobytes())
        scale = float(np.abs(matrix).max())
        quantised_path.write_bytes(
            np.clip(np.round(matrix / scale * 127), -127, 127).astype(np.int8).tobytes()
        )
    return matrix_path, quantised_path, dim


def child(mode: str, scratch: Path) -> None:
    """One query, then exit - the whole point of being a separate process."""
    matrix_path, quantised_path, dim = reference_paths(scratch)
    query = np.random.default_rng(7).standard_normal(dim).astype("<f4")
    query /= np.linalg.norm(query)

    started = time.perf_counter()
    if mode == "exact":
        packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
        scores = packed @ query
    elif mode.startswith("partial"):
        fraction, runs = float(mode.split(":")[1]), 16
        packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
        rows = int(REFERENCE_N * fraction / runs)
        starts = np.linspace(0, REFERENCE_N - rows - 1, runs).astype(int)
        scores = np.concatenate([np.asarray(packed[s : s + rows]) @ query for s in starts])
    else:
        coarse = np.memmap(quantised_path, dtype=np.int8, mode="r", shape=(REFERENCE_N, dim))
        approx = coarse.astype(np.float32) @ query
        picked = np.argpartition(-approx, 99)[:100]
        packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
        scores = np.asarray(packed[picked]) @ query
    best = np.argpartition(-scores, min(TOP_K, len(scores) - 1))[:TOP_K]
    best[np.argsort(-scores[best])]
    print((time.perf_counter() - started) * 1000)


def report_latency(scratch: Path) -> None:
    """Time a query at the reference profile. Geometry-free, so synthetic is honest."""
    matrix_path, _, _ = reference_paths(scratch)
    size = matrix_path.stat().st_size / 1e6
    print(f"one query per fresh process, {REFERENCE_N:,} vectors ({size:.0f} MB) - LATENCY")
    timed("exact scan, every vector (ADR-0026)", "exact", scratch)
    for fraction in (0.0625, 0.25, 0.58):
        timed(
            f"partial scan, {fraction * 100:.0f}% of rows (an IVF probe)",
            f"partial:{fraction}",
            scratch,
        )
    timed("int8 first pass + exact rescore of 100", "int8", scratch)


def main() -> int:
    if "--child" in sys.argv:
        index = sys.argv.index("--child")
        child(sys.argv[index + 1], Path(sys.argv[index + 2]))
        return 0

    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    root = Path(args[0]) if args else ROOT / "eval" / "corpora" / "uv-docs"
    report_recall(root)
    if "--scale" in sys.argv:
        scratch = Path(__file__).resolve().parent.parent / ".mycelium" / "measurements"
        scratch.mkdir(parents=True, exist_ok=True)
        report_latency(scratch)
    else:
        print("\n(pass --scale to time a cold query at 10^5 vectors; it writes ~190 MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
