# Second judged corpus — `uv` documentation

Documentation **this project did not write**, vendored so the evaluation has a corpus whose
documents were authored by someone other than the agent being measured (spec 04 §7.6,
ADR-0027).

| | |
|---|---|
| Upstream | [astral-sh/uv](https://github.com/astral-sh/uv) |
| Pinned commit | `7896d580c245493c88ea5be56724e6e42ee7d197` (2026-08-29) |
| Vendored | `docs/**/*.md` — 81 files, ~700 KB. Images, CSS, JS and HTML were dropped: the corpus is prose |
| Licence | MIT, [`LICENSE`](LICENSE) — Copyright (c) 2025 Astral Software Inc. |
| Modifications | None. The Markdown is byte-for-byte upstream |

## Why vendored rather than fetched

A benchmark that downloads its corpus measures whatever upstream happens to hold that day.
Pinning a commit fixes *what*; vendoring fixes *when* — the corpus is in the repository, so
an evaluation run months from now compares against the same bytes, offline, with no network
call in a gate (D-017).

The cost is ~700 KB of third-party Markdown in the tree, and the obligation MIT attaches:
the licence and copyright notice travel with the copy, which is what `LICENSE` is for.

## Why this corpus

It is *unlike* ours in the ways that matter for generalisation. Our own corpus is
architecture decisions and specifications — long, cross-referential, heavy with defined
terms. This one is task documentation for a command-line tool: short pages, imperative
mood, command names and flags rather than concepts. A retriever tuned to one and measured
only on it would learn the shape of that one corpus, which is precisely what the dev/release
split and this second corpus exist to detect.

## What it is not

It is not a claim about `uv`, and no judgment here is a statement about that project's
documentation quality. The cases ask questions the documentation answers, and grade the
passages that answer them.

## Refreshing it

Don't, casually. The judged anchors point at headings in these files, so moving to a newer
upstream commit invalidates cases wholesale — `python tools/build_uv_docs_cases.py` will
name every anchor that no longer exists. A refresh is a deliberate act with a re-judging
pass attached, not a routine update.
