---
id: BUG-0022
title: tree-sitter 0.26.0 faults with an access violation on a projected PDF fence, killing the build process
status: confirmed
severity: high
reporter: internal
discovered: 2026-09-10
affected-versions: ">=0.5.0"
---

# BUG-0022: the grammar binding faults on a fence, and no `except` can catch it

## Summary

Building `eval/corpora/uv-docs-ingested` — one of the three corpora the evaluation gates run
on — dies with `Windows fatal exception: access violation` inside the symbol stage. The
process is killed; there is no traceback to catch, no quarantine record, and the build lock
is left behind for the next run to trip over.

The trigger is one document: `knowledge/evidence/config-pdf-4803c1e3.md`, a projection of a
PDF, whose fifth fence is 20 644 bytes of mangled prose tagged ```` ```python ````. Reading it
through the Python grammar's tags query faults **deterministically** on the first call in a
fresh process, on `tree-sitter==0.26.0`.

It is a defect in the binding, not in the corpus and not in the grammar wheels: **0.25.2
reads the same bytes five times in a row without faulting, and produces byte-identical
definitions for every one of the ten grammars' samples.**

Found while measuring roadmap 5.2 across the three corpora. Roadmap 5.1 shipped the symbol
stage without ever building this corpus by hand — `tools/verify.py` did build it, and passed,
because 5.1 asked each fence only for its definitions; 5.2 asks the same parse for its
*references* as well, and that is the call that faults.

## Reproduction

```python
from mycelium.symbols import load_grammar, read_fence
from pathlib import Path

# the fence's bytes, as the compiler hands them over
source = Path("fence.txt").read_bytes()   # 20 644 bytes, extracted from the document below
read_fence(load_grammar("python"), source)  # access violation, first call, fresh process
```

Whole-corpus form, which is what CI runs:

```bash
python -c "from mycelium.build import build; from pathlib import Path; build(Path('eval/corpora/uv-docs-ingested'), clean=True)"
```

## Diagnosis

The fault is **not** in the shape of the input, and **not** in object lifetime:

| Observation | Result |
|---|---|
| Parse tree of the faulting fence | 388 lines, 71 root children, **max depth 14** — shallow |
| Running both tags-query passes over it, touching nothing after | survives |
| Holding every captured node after the cursor is dropped, then reading `text`/`type`/`parent` | survives |
| The same work with prints between phases | survives |
| `read_fence` itself | faults, first call |
| Under `PYTHONMALLOC=debug`, and with the cycle collector disabled | faults, no allocator diagnostic |
| Reported fault line across runs | `code.py:504`, `:544`, `:549` — it moves |

A fault whose location moves with allocation timing, in memory the extension owns, is heap
corruption inside the binding. Nothing in `mycelium.symbols` writes memory; it reads captured
nodes and builds Python objects.

The decisive experiment is the version: `pip install tree-sitter==0.25.2` and the same call,
on the same bytes, in the same process, five times over — no fault. Back to 0.26.0 — fault.

## Impact

**High, and it cannot be contained in-process.** An access violation is not an exception: the
per-fence `try/except` that turns a parse failure into a document warning (ADR-0073) never
runs, the build's quarantine path never runs, and the operator gets a dead process. The
256 KiB per-fence ceiling does not help either — the faulting fence is 20 KB.

The blast radius is any corpus containing a code fence of the right shape, which is precisely
what an *ingested* corpus contains: a PDF projection tags its recovered text with whatever
language the extractor guessed, so arbitrary prose reaches a programming-language grammar.

## Fix

Pinned: `tree-sitter>=0.25,<0.26`, in the `symbols` extra and in the dev group, with the
reason written beside the pin in `pyproject.toml` and re-locked. `grammar_fingerprint()`
already carries the binding's version into the build key (ADR-0073), so the pin is visible in
every build key and a snapshot records which binding compiled it.

Not fixed upstream by us, hence `confirmed` rather than `fixed`: this record stays open as
the reason the pin exists. Lifting it needs a release that survives `pytest -m determinism`
**and** a clean build of `eval/corpora/uv-docs-ingested`, which is the regression guard —
`tools/verify.py` builds that corpus from `retrieval` mode upward, so a bad binding fails the
ladder within seconds rather than reaching a merge.

No minimal fixture is committed: bisecting the fence by line reached 14 268 bytes / 258 lines
and no further, so the smallest known trigger is a large blob of mangled documentation. The
vendored corpus is a better guard than a checked-in copy of part of it.

## Lesson

An in-process C parser makes "a parser failure is a per-document warning" a promise the
process cannot keep. The threat model said so as a control (B14); it is now amended to say
what is actually true — a faulting grammar takes the build with it, and the control is the
version pin plus the corpus that reproduces it.
