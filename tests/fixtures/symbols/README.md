# Inputs that once faulted the grammar binding

Each file here is a code fence, byte for byte as the compiler handed it to the binding, that
killed the build process through a fault in native code — an access violation no `except`
can catch. [`tools/check_known_faults.py`](../../../tools/check_known_faults.py) replays each
one in a fresh interpreter and refuses a file whose digest has moved; `tests/test_symbols.py`
replays them in the locked development environment, and `tools/check_distribution.py` in a
clean one holding the newest versions the published ranges allow (roadmap 8.2,
[ADR-0162](../../../docs/adr/0162-hold-a-defect-pin-with-a-test-and-verify-the-ranges-a-wheel-resolves.md)).

| File | Record | Bytes | SHA-256 |
|---|---|---|---|
| `bug-0022-fence.txt` | [BUG-0022](../../../docs/bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md) | 20 644 | `e4b47df88f4ffdeaf5a82d4105934cdb60c993ebdafa1fe80c6703359fffb69b` |

The files are `binary` in `.gitattributes`: LF-only, with no final newline, and a line-ending
filter rewriting one on checkout would change the input the record says faults.

## `bug-0022-fence.txt`

The ```` ```python ```` fence of
`eval/corpora/uv-docs-ingested/knowledge/evidence/config-pdf-4803c1e3.md` as it stood at commit
`db84cc5`: opened at line 52 and never closed, so it runs to the document's last line, 440. A
PDF projection of uv's configuration documentation produced it by tagging recovered prose with
the language the extractor guessed. On `tree-sitter==0.26.0` the Python grammar's tags query
faults on it; 0.25.2 reads it. Measured on Windows 11 for roadmap 8.2: one read per fresh
process faulted 4 times in 10, five reads per process 10 times in 10.

The corpus stopped carrying it on 2026-09-12, when the twin was re-rendered in the dialect it
is written in (#122, BUG-0025), and the record that named the corpus as its guard was not told.
That is why the input is committed here rather than left there.

Recovered with the compiler's own parser, so the bytes are the KIR node's text in UTF-8 — what
`read_fence` receives:

```bash
git show db84cc5:eval/corpora/uv-docs-ingested/knowledge/evidence/config-pdf-4803c1e3.md > doc.md
```

```python
from pathlib import Path

from mycelium.markdown import parse_markdown

document = parse_markdown(Path("doc.md").read_bytes().decode("utf-8"), doc_id="01J00000000000000000000000")
fence = next(node for node in document.kir.nodes if node.lang == "python")
Path("bug-0022-fence.txt").write_bytes(fence.text.encode("utf-8"))
```

## Licence

The text is a projection of uv's documentation ([astral-sh/uv](https://github.com/astral-sh/uv)),
MIT-licensed, Copyright (c) 2025 Astral Software Inc. The notice is in [`LICENSE`](LICENSE),
as it is beside the corpus the fence came from.
