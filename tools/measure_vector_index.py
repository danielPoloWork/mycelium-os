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


def timed(label: str, run, rounds: int = 9) -> float:
    run()  # warm the page cache: this measures a cold *process*, not a cold disk
    samples = []
    for _ in range(rounds):
        started = time.perf_counter()
        run()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    median = samples[len(samples) // 2]
    verdict = "within" if median <= BUDGET_MS else "OVER"
    print(f"  {label:<44} {median:7.2f} ms  {verdict} the {BUDGET_MS} ms budget")
    return median


def report_latency(scratch: Path) -> None:
    """Time a cold-process query at the reference profile. Geometry-free by design."""
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

    query = np.random.default_rng(7).standard_normal(dim).astype("<f4")
    query /= np.linalg.norm(query)
    size = matrix_path.stat().st_size / 1e6
    print(f"\nLATENCY, cold process, {REFERENCE_N:,} vectors ({size:.0f} MB float32)")

    def exact() -> np.ndarray:
        packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
        scores = packed @ query
        best = np.argpartition(-scores, TOP_K)[:TOP_K]
        return best[np.argsort(-scores[best])]

    def partial(fraction: float, runs: int = 16):
        """What an IVF probe costs: `fraction` of the rows as contiguous runs."""

        def run() -> np.ndarray:
            packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
            rows = int(REFERENCE_N * fraction / runs)
            starts = np.linspace(0, REFERENCE_N - rows - 1, runs).astype(int)
            scores = np.concatenate([np.asarray(packed[s : s + rows]) @ query for s in starts])
            best = np.argpartition(-scores, TOP_K)[:TOP_K]
            return best[np.argsort(-scores[best])]

        return run

    def two_pass() -> np.ndarray:
        coarse = np.memmap(quantised_path, dtype=np.int8, mode="r", shape=(REFERENCE_N, dim))
        approx = coarse.astype(np.float32) @ query
        picked = np.argpartition(-approx, 99)[:100]
        packed = np.memmap(matrix_path, dtype="<f4", mode="r", shape=(REFERENCE_N, dim))
        scores = np.asarray(packed[picked]) @ query
        best = np.argpartition(-scores, TOP_K - 1)[:TOP_K]
        return picked[best[np.argsort(-scores[best])]]

    timed("exact scan, every vector (ADR-0026)", exact)
    for fraction in (0.0625, 0.25, 0.58):
        timed(f"partial scan, {fraction * 100:.0f}% of rows (an IVF probe)", partial(fraction))
    timed("int8 first pass + exact rescore of 100", two_pass)


def main() -> int:
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
