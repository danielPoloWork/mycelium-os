# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Symbol extraction hot path (roadmap 5.1).

Extraction runs for every dirty document on every build, beside link extraction,
so it sits under the incremental-build budget (< 2 s p95 for a single-document
rebuild, RFC-0001). Baseline only; no performance claim is made yet.
"""

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.markdown import parse_markdown
from mycelium.symbols import extract_definitions, extract_symbols, load_grammar

FENCE = '''class Policy{index}:
    """Bounded retries."""

    attempts = {index}

    def delay(self, attempt: int) -> float:
        return 2.0 ** attempt


def build_policy_{index}() -> Policy{index}:
    return Policy{index}()
'''

SECTION = """## Policy{index}

Prose introducing the policy, with a [[wikilink]] and a term list.

policy_{index}
: What section {index} defines.

```python
{fence}```
"""

DOCUMENT = "# Reference\n\n" + "\n".join(
    SECTION.format(index=i, fence=FENCE.format(index=i)) for i in range(20)
)
PARSED = parse_markdown(DOCUMENT)
CHUNKS = chunk_document(PARSED.kir, doc_path="reference.md", policy=ChunkingPolicy())


@pytest.fixture(scope="module")
def python_grammar() -> object:
    loaded = load_grammar("python")
    if loaded is None:
        pytest.skip("the symbols extra is not installed")
    return loaded


def test_extract_one_python_fence(benchmark: BenchmarkFixture, python_grammar: object) -> None:
    source = FENCE.format(index=0).encode("utf-8")
    benchmark(extract_definitions, python_grammar, source)  # type: ignore[arg-type]


def test_extract_symbols_of_a_document(benchmark: BenchmarkFixture, python_grammar: object) -> None:
    benchmark(extract_symbols, PARSED.kir, CHUNKS, doc_path="reference.md")
