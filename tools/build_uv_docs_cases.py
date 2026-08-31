#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Author the judged sets over the second corpus — `uv`'s documentation.

    python tools/build_uv_docs_cases.py

Writes `eval/corpora/uv-docs/eval/{dev,release}.jsonl`, validating every anchor
against a real build first (`mycelium.eval.cases.validate_judged_set`).

**Judging provenance, precisely.** These queries and grades were assigned by the
same agent that builds the retriever they measure — that bias is not removed by a
second corpus and this file does not pretend otherwise. What *is* removed is the
other half of it: nobody here wrote the documents being judged. Our own set was
judged by the author of its corpus, so a query could be phrased in the words the
author happened to use; here the phrasing has to be guessed like any reader's
would (ADR-0027).

Judgments were written from the documents' own text, never from retrieval output.
That is a discipline rather than an enforceable rule, so it is recorded where a
reader can weigh it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import validate_judged_set, write_cases  # noqa: E402
from mycelium.sdk.types import EvalCase, EvalSlice, RelevantAnchor  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

CORPUS = ROOT / "eval" / "corpora" / "uv-docs"

Judgment = tuple[str, str, tuple[EvalSlice, ...], tuple[tuple[str, int], ...], str]

DEV: tuple[Judgment, ...] = (
    (
        "u-0001",
        "UV_CACHE_DIR",
        (EvalSlice.EXACT,),
        (("docs/concepts/cache.md#cache-directory/0", 3),),
        "A literal environment variable name; exact retrieval should be trivial.",
    ),
    (
        "u-0002",
        "where does the cache directory live on Windows",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#cache-directory/0", 3),),
        "One specific fact stated in a numbered list, phrased as a reader would ask it.",
    ),
    (
        "u-0003",
        "how do I clear the cache for a single package",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/cache.md#clearing-the-cache/0", 3),
            ("docs/concepts/cache.md#dependency-caching/0", 2),
        ),
        "The answer is a command; the concepts section repeats it in prose.",
    ),
    (
        "u-0004",
        "what is a workspace",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/workspaces.md#/0", 3),),
        "A definitional question whose answer is a document's opening section.",
    ),
    (
        "u-0005",
        "which platforms are tier 1 supported",
        (EvalSlice.FACT,),
        (("docs/reference/policies/platforms.md#/0", 3),),
        "A list-shaped fact in a policy document.",
    ),
    (
        "u-0006",
        "uvx",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 3),
            ("docs/guides/tools.md#/0", 2),
        ),
        "A bare command name: the symbol slice, and it appears across several documents.",
    ),
    (
        "u-0007",
        "what does resolution mean",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#/0", 3),),
        "The concept the document is named for, defined in its first paragraph.",
    ),
    (
        "u-0008",
        "how are breaking changes versioned",
        (EvalSlice.CONCEPTUAL, EvalSlice.FACT),
        (("docs/reference/policies/versioning.md#/0", 3),),
        "A policy stated in prose, asked in words the document does not use verbatim.",
    ),
    (
        "u-0009",
        "dressage piaffe pirouette",
        (EvalSlice.UNANSWERABLE,),
        (),
        "A domain this corpus will never cover; every term verified clean against both retrievers.",
    ),
    (
        "u-0010",
        "escapement tourbillon mainspring",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As u-0009, in a different domain.",
    ),
    (
        "u-0011",
        "how do I run a script that declares its own dependencies",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/scripts.md#/", 2),),
        "A guide-shaped question; the opening frames it and later sections answer in detail.",
    ),
    (
        "u-0012",
        "where does uv look for a configuration file",
        (EvalSlice.FACT,),
        (("docs/concepts/configuration-files.md#/", 3),),
        "A search-order fact stated in the document's first section.",
    ),
)

RELEASE: tuple[Judgment, ...] = (
    (
        "u-1001",
        "how do I add a package index other than PyPI",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/indexes.md#defining-an-index/", 3),
            ("docs/concepts/indexes.md#/0", 2),
        ),
        "The answer is a configuration table shown in a named section.",
    ),
    (
        "u-1002",
        "is uv a drop-in replacement for pip",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#/0", 3),),
        "A yes-but question the document answers carefully in its opening.",
    ),
    (
        "u-1003",
        "tool.uv.index",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#/0", 3),),
        "A literal configuration key.",
    ),
    (
        "u-1004",
        "how do I pin one package to a specific index",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#pinning-a-package-to-an-index/", 3),),
        "A task with its own section; the question avoids the section's wording.",
    ),
    (
        "u-1005",
        "what is the difference between a managed and a system Python installation",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#managed-and-system-python-installations/0", 3),),
        "A distinction the document defines explicitly.",
    ),
    (
        "u-1006",
        "which Python version formats can I request",
        (EvalSlice.FACT,),
        (("docs/concepts/python-versions.md#requesting-a-version/", 3),),
        "A list of accepted formats, asked without the document's noun.",
    ),
    (
        "u-1007",
        "uv tool install",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/tools.md#the-uv-tool-interface/0", 2),),
        "A command name that appears in several documents; the concept page frames it.",
    ),
    (
        "u-1008",
        "how do I add a dependency to my project",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#adding-dependencies/", 3),),
        "The commonest task in the corpus. The answer is the section - the command, the "
        "entry it writes, the flags that vary it - so judging one paragraph of it was "
        "judging where the chunker splits (ADR-0029).",
    ),
    (
        "u-1009",
        "why does a single lockfile cover every package in a workspace",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/workspaces.md#/0", 3),
            ("docs/concepts/resolution.md#/0", 1),
        ),
        "Relates two ideas — workspace membership and shared resolution — stated in one place.",
    ),
    (
        "u-1010",
        "what happens to the cache when the format changes between releases",
        (EvalSlice.RELATIONSHIP, EvalSlice.FACT),
        (
            ("docs/concepts/cache.md#cache-versioning/0", 3),
            ("docs/reference/policies/versioning.md#cache-versioning/0", 2),
        ),
        "The same subject in two documents: a concept page and a policy page.",
    ),
    (
        "u-1011",
        "chitin exoskeleton pupation",
        (EvalSlice.UNANSWERABLE,),
        (),
        "A domain this corpus will never cover.",
    ),
    (
        "u-1012",
        "annealing kiln borosilicate gaffer",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As u-1011, in a different domain.",
    ),
    (
        "u-1013",
        "how do I stop uv from using the network at all",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#cache-directory/", 1),),
        "A question the corpus answers only partially — a weak-evidence case on purpose.",
    ),
    (
        "u-1014",
        "what does uv do about TLS certificates from a corporate proxy",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/certificates.md#custom-certificates/0", 3),),
        "A real-world phrasing whose answer sits under a differently-worded heading.",
    ),
    (
        "u-1015",
        "storage directories",
        (EvalSlice.EXACT,),
        (("docs/reference/storage.md#storage-directories/0", 3),),
        "A heading quoted verbatim: the easiest possible lexical case, kept as a floor.",
    ),
    (
        "u-1016",
        "how do I keep credentials out of my shell history when logging in to an index",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/authentication/cli.md#logging-in-to-a-service/3", 3),
            ("docs/concepts/authentication/http.md#/0", 1),
        ),
        "A motivation-shaped question; the corpus answers the mechanism, not the motive.",
    ),
)


def cases_of(judgments: tuple[Judgment, ...]) -> tuple[EvalCase, ...]:
    return tuple(
        EvalCase(
            case_id=case_id,
            query=query,
            slices=slices,
            relevant=tuple(
                RelevantAnchor(anchor=anchor, grade=grade) for anchor, grade in relevant
            ),
            answerable=bool(relevant),
            note=note,
        )
        for case_id, query, slices, relevant, note in judgments
    )


def main() -> int:
    if not (CORPUS / "docs").is_dir():
        print(f"the vendored corpus is missing: {CORPUS / 'docs'}")
        return 1

    dev, release = cases_of(DEV), cases_of(RELEASE)
    build(CORPUS)
    with SqliteStore.open(CORPUS, read_only=True) as store:
        errors, warnings = validate_judged_set(dev + release, store)

    for warning in warnings:
        print(f"  warning: {warning}")

    if errors:
        print("The judged set does not hold against the corpus:")
        for error in errors:
            print(f"  {error}")
        return 1

    destination = CORPUS / "eval"
    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", dev)
    write_cases(destination / "release.jsonl", release)
    print(f"wrote {len(dev)} dev and {len(release)} release cases to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
