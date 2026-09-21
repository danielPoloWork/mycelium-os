# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Stemmer benchmarks: cold against memoised (roadmap 6.31, ADR-0146).

Roadmap 6.19 profiled a 1 000-document cold build and found the lexical
index's four stem columns per chunk (ADR-0048) call `stem()` **620 293**
times over **10 339 distinct words** — 98.3 % of the calls ask for an answer
already computed. Memoising cut that measured cost from 7.44 s to 0.31 s
(23.6x). These two benchmarks re-take that comparison on a real repository
document rather than a synthetic word list, so CI carries the evidence rather
than the prose alone.

`test_stem_text_cold` clears the cache before every round via
`benchmark.pedantic`'s `setup`, so it prices a vocabulary nobody has seen —
the worst case, and the bound `stem` pays regardless of corpus size.
`test_stem_text_warm` primes the cache once and re-stems the same words, which
is what every chunk after the first occurrence of a word actually pays. The
ratio between them is this file's version of ADR-0132's 23.6x.
"""

import re
from pathlib import Path

from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.store.stemming import stem, stem_text

_WORD = re.compile(r"\w+", re.UNICODE)

# A real repository document: real vocabulary, real repetition, not a stand-in.
_WORDS = _WORD.findall(
    (Path(__file__).parents[2] / "AGENTS.md").read_text(encoding="utf-8").lower()
)


def test_stem_text_cold(benchmark: BenchmarkFixture) -> None:
    benchmark.pedantic(  # type: ignore[no-untyped-call]
        stem_text, args=(_WORDS,), setup=stem.cache_clear, rounds=30, iterations=1
    )


def test_stem_text_warm(benchmark: BenchmarkFixture) -> None:
    stem_text(_WORDS)  # prime the cache once, outside the timed region
    benchmark(stem_text, _WORDS)
