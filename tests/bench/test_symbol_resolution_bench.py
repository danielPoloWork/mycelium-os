# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The global symbol resolution pass (roadmap 5.1, 5.2) — decoded once, not twice.

`resolve_symbols` and `symbol_edges` run on every build, over every document,
whether or not anything changed (a symbol's `defined_in` and an edge's target may
depend on a document this build never touched). Roadmap 6.20 profiled a
1 000-document no-op rebuild and found the symbol stage costing 235 ms of a
1.36 s floor, and roadmap 6.32 traced it to decoding: called back to back, as
every real caller does, the two passes independently decoded each document's
`symbols` and `symbol_uses` from `doc_state`'s stored JSON — three decodes of
`symbols` and two of `symbol_uses` per rebuild where one of each does the same
work (ADR-0147).

`resolve_symbols` and `symbol_edges` stay independently callable and
independently decoding — a caller that only needs one still gets it without
building the other — so both paths coexist in the shipped code, and the first
two benchmarks below are that comparison: the same corpus, the same output,
paid for once or paid for three times over. `resolve_symbols_and_edges` is what
every real caller uses now.
"""

from collections.abc import Mapping

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.sdk.identity import doc_ref
from mycelium.sdk.types import (
    Edge,
    EdgeProvenance,
    EdgeStatus,
    EdgeType,
)
from mycelium.store import SqliteStore
from mycelium.symbols import (
    CODE_FENCE,
    SymbolRef,
    encode_symbols,
    resolve_symbols,
    resolve_symbols_and_edges,
    symbol_edges,
)

DOCUMENTS = 150
"""Small beside the reference profile's 1 000 — pytest-benchmark repeats a round
many times, and this is chosen to keep a round in the tens of milliseconds while
still holding thousands of uses, the regime the fix targets."""

USES_PER_DOCUMENT = 15
"""Cross-document, round-robin: every document uses symbols other documents
define, which is what makes resolution a whole-corpus pass rather than a
per-document one (ADR-0018) and is close to what generated prose in code fences
produces in practice."""


def _corpus() -> tuple["_State", ...]:
    states = []
    for index in range(DOCUMENTS):
        path = f"knowledge/doc-{index:04d}.md"
        defines = tuple(
            encode_symbols(
                [
                    SymbolRef(
                        "python", f"func_{index}_a", "function", CODE_FENCE, 1, f"{path}#a/0"
                    ),
                    SymbolRef(
                        "python", f"func_{index}_b", "function", CODE_FENCE, 2, f"{path}#b/0"
                    ),
                ]
            )
        )
        uses = tuple(
            encode_symbols(
                [
                    SymbolRef(
                        "python",
                        f"func_{(index + offset) % DOCUMENTS}_a",
                        "call",
                        CODE_FENCE,
                        10 + offset,
                        f"{path}#use-{offset}/0",
                    )
                    for offset in range(1, USES_PER_DOCUMENT + 1)
                ]
            )
        )
        states.append(_State(path, defines, uses))
    return tuple(states)


class _State:
    """A `SymbolState` the resolver can read, with nothing else on it."""

    def __init__(
        self,
        path: str,
        symbols: tuple[Mapping[str, object], ...],
        symbol_uses: tuple[Mapping[str, object], ...],
    ) -> None:
        self.path = path
        self.symbols = symbols
        self.symbol_uses = symbol_uses
        self.symbol_gaps: tuple[str, ...] = ()


CORPUS = _corpus()


def test_resolve_then_edges_two_calls(benchmark: BenchmarkFixture) -> None:
    """The pattern every caller used before roadmap 6.32: two calls, two decodes
    each of `symbols` (once inside each function) plus a second decode of
    `symbol_uses` in `symbol_edges` on top of `resolve_symbols`'s own."""

    def run() -> None:
        symbols = resolve_symbols(CORPUS)
        symbol_edges(CORPUS, symbols)

    benchmark(run)


def test_resolve_and_edges_combined(benchmark: BenchmarkFixture) -> None:
    """What ships: one decode of `symbols`, one of `symbol_uses`, both passes."""
    benchmark(resolve_symbols_and_edges, CORPUS)


def test_put_edges_of_a_thousand_edges(
    tmp_path_factory: pytest.TempPathFactory, benchmark: BenchmarkFixture
) -> None:
    """The store side of the same item: an edge's id, serialized once per write
    rather than twice (ADR-0147). One of the two `canonical_json(provenance)`
    calls `SqliteStore.put_edges` used to make is gone; this is the floor with
    it removed, so a future regression has something to be measured against.

    Writing the same edges repeatedly is the steady state `put_edges` documents:
    re-deriving an edge already on disk is idempotent (`ON CONFLICT ... DO
    UPDATE`), which is exactly what every build after the first does.
    """
    edges = tuple(
        Edge(
            from_=doc_ref(f"knowledge/doc-{index:04d}.md"),  # type: ignore[call-arg]
            to=f"sym:python:func_{index}_a",
            type=EdgeType.DEFINES,
            status=EdgeStatus.EXTRACTED,
            provenance=EdgeProvenance(kind=CODE_FENCE, anchor=f"doc-{index:04d}.md#a/0"),
        )
        for index in range(1000)
    )
    store = SqliteStore.open(tmp_path_factory.mktemp("bench-edges"))

    def write() -> None:
        with store.transaction():
            store.put_edges(edges)

    benchmark(write)
    store.close()
