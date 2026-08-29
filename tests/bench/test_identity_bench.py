# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Identity hot-path benchmarks (roadmap 2.3).

Every document and every chunk is normalized and digested on every build, and dirty
detection re-digests unchanged sources to prove they are unchanged — so `digest_text`
sits directly under the incremental-build budget (< 2 s p95 for a single-document
rebuild, RFC-0001). These record the baseline; no perf claim is made yet.
"""

from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.sdk.identity import UlidFactory, digest_text, heading_slug

# ~16 KB of prose with CRLF endings and trailing whitespace — the normalizer's real work.
DOCUMENT = ("# Heading\r\n\r\nBody text with trailing space   \r\n" * 400) + "tail"


def test_digest_text_on_a_typical_document(benchmark: BenchmarkFixture) -> None:
    benchmark(digest_text, DOCUMENT)


def test_heading_slug(benchmark: BenchmarkFixture) -> None:
    benchmark(heading_slug, "Build Keys & Content-Addressed Caching")


def test_monotonic_ulid_minting(benchmark: BenchmarkFixture) -> None:
    factory = UlidFactory()
    benchmark(factory.new)
