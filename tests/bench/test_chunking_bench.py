# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Chunker hot-path benchmarks (roadmap 2.5).

Parse and chunk run for every dirty document on every build, so they sit under the
incremental-build budget (< 2 s p95 for a single-document rebuild, RFC-0001).
Baseline only; no performance claim is made yet.
"""

from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.chunking import chunk_document
from mycelium.markdown import parse_markdown

SECTION = """## Section {index}

Prose paragraph with enough words in it to look like real documentation text,
mentioning [[a-wikilink]] and a [link](https://example.invalid) along the way.

- a list item
- another list item

| column | value |
|--------|-------|
| one    | 1     |

```python
value = {index}
```
"""

DOCUMENT = "# Reference Document\n\n" + "\n".join(SECTION.format(index=i) for i in range(20))
KIR = parse_markdown(DOCUMENT).kir


def test_parse_markdown_document(benchmark: BenchmarkFixture) -> None:
    benchmark(parse_markdown, DOCUMENT)


def test_chunk_document(benchmark: BenchmarkFixture) -> None:
    benchmark(chunk_document, KIR, doc_path="reference.md")
