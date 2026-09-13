#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Author the judged sets over the second corpus — `uv`'s documentation.

    python tools/build_uv_docs_cases.py [--check]

Writes `eval/corpora/uv-docs/eval/{dev,release}.jsonl`, validating every anchor
against a real build first (`mycelium.eval.cases.validate_judged_set`).

**`--check` regenerates and compares instead of writing**, and it exists because
running this file without it used to destroy work. The judgements below are the
sets' only source, so a case added to a committed set by hand is invisible here
and is deleted by the next run. That is not hypothetical: PRs #88 and #90 edited
`dev.jsonl` directly — re-judging `u-0006` and adding `u-0013`..`u-0022` — and
neither edit reached this file, so from 2026-09-08 until it was triggered at
roadmap 5.30 this generator silently reverted ten judged cases and one
re-judgement ([BUG-0026]). The sibling generators were already checked —
`tools/build_ingested_cases.py --check` in CI, `tools/build_eval_cases.py`
by a test — and this one was not, which is why only this one drifted. It is now
a rung of `tools/verify.py` at `code` and a step in CI's `ingest / lanes` job,
beside the carry check it is the upstream half of: checking that the carry still
derives from the source, while the source itself goes unchecked, is the weaker
half of the pair — and it is the half that held while this one drifted.

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

import json
import sys
from collections.abc import Sequence
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
            ("docs/guides/tools.md#running-tools/", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "A bare command name: the symbol slice, and it appears across several "
        "documents. Graded on the convention its siblings follow — the section "
        "that documents the command at 3, the section that frames the interface "
        "at 2, the feature-list entry at 1 (ADR-0062, ADR-0065).",
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
        (
            EvalSlice.CONCEPTUAL,
            EvalSlice.FACT,
        ),
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
    (
        "u-0013",
        "UV_PREVIEW",
        (EvalSlice.EXACT,),
        (("docs/concepts/preview.md#enabling-preview-features/0", 3),),
        "An environment variable name. The section that documents it names it "
        "four times; `unicode61` splits it into `uv preview`, which is the same "
        "shape u-0001 already has.",
    ),
    (
        "u-0014",
        "--bare",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/init.md#creating-a-minimal-project/0", 3),
            ("docs/concepts/projects/init.md#/0", 1),
        ),
        "A CLI flag. The section that documents it uses it five times; the "
        "document's own root mentions it once, which is grade 1 for the reason "
        "u-1019 gives - it answers only that the flag exists.",
    ),
    (
        "u-0015",
        "UV_PROJECT_ENVIRONMENT",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/config.md#project-environment-path/", 3),),
        "An environment variable whose tokens are all common words once split - "
        "the harder end of `exact`, and deliberately kept. Section-scoped: 326 "
        "tokens is one chunk under this setting and may not be under another "
        "(ADR-0043).",
    ),
    (
        "u-0016",
        "uv build",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/build.md#using-uv-build/0", 3),
            ("docs/guides/package.md#building-your-package/0", 2),
            ("docs/concepts/projects/build.md#/0", 1),
        ),
        "The heading of the grade-3 section names the command and its body uses "
        "it eleven times; the guide teaches it in a tutorial step, and the "
        "concept document's root frames building without naming the command.",
    ),
    (
        "u-0017",
        "uv venv",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/environments.md#creating-a-virtual-environment/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "The section that documents the command is the one that runs it; the "
        "feature list says only `uv venv: Create a new virtual environment`, "
        "which is grade 1.",
    ),
    (
        "u-0018",
        "uv init",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/init.md#/0", 3),
            ("docs/guides/projects.md#creating-a-new-project/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The closest call in this batch: the concept document exists to document "
        'this command ("uv supports creating a project with uv init") while the '
        "guide teaches it as a tutorial step. Three tiers so the judgement does "
        "not hinge on the tie - whichever a retriever prefers, it is credited.",
    ),
    (
        "u-0019",
        "can another tool read the lockfile uv writes",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/projects/layout.md#the-lockfile/relationship-to-pylock-toml/",
                3,
            ),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
        ),
        "Relates uv's own lockfile to the standardised format: one is "
        "tool-agnostic, the other is not, and uv keeps its own inside the "
        "project. The query names neither `uv.lock` nor `pylock.toml`.",
    ),
    (
        "u-0020",
        "why can uv install into an environment it did not create",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/environments.md#using-arbitrary-python-environments/", 3),
            ("docs/pip/environments.md#discovery-of-python-environments/0", 2),
        ),
        "Two halves in one document: that uv has no dependency on Python and can "
        "target any environment, and the order in which it discovers one. "
        "Section-scoped on the first at 547 tokens (ADR-0043).",
    ),
    (
        "u-0021",
        "what has to be in pyproject.toml before the project can be built",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/build-backend.md#using-the-uv-build-backend/0", 3),
            ("docs/concepts/projects/layout.md#the-pyproject-toml/0", 2),
        ),
        "Relates the build backend to the file that declares it: the grade-3 "
        "section shows the `[build-system]` table that has to be there, the "
        "grade-2 one lists a build system among the file's contents without "
        "showing it.",
    ),
    (
        "u-0022",
        "what decides whether a new project is set up as an application or a library",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/init.md#applications/", 3),
            ("docs/concepts/projects/init.md#libraries/", 2),
        ),
        "The two templates are documented in one section each and the answer is "
        "the contrast between them - applications are the default, libraries need "
        "`--lib` and always require a packaged project. Both section-scoped at "
        "364 and 432 tokens.",
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
        (
            ("docs/concepts/indexes.md#defining-an-index/", 3),
            ("docs/concepts/indexes.md#/0", 2),
        ),
        "A literal configuration key, documented in one section of the document that "
        "names it twenty-six times. Re-judged at roadmap 5.30: the preamble names the "
        "key in one subordinate clause and says what it is *for*, which is `u-1001`'s "
        "grade for the same passage; the section says what an entry is, which fields "
        "it takes, how indexes are prioritised and what the command line and "
        "environment equivalents are (ADR-0101).",
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
        (
            ("docs/guides/tools.md#installing-tools/", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "A command with two homes, and the first judgement named the lesser one "
        "(roadmap 4.34). This corpus vendors no CLI reference, so the command is "
        "*documented* by the guide's `Installing tools` section - what it does, where "
        "the executables land, how it differs from `uv pip install`, the flags - which "
        "is the grade-3 unit its three sibling `symbol` cases all name. Section-scoped "
        "because the answer is spread across the whole of it (ADR-0029). The concepts "
        "page keeps grade 2: it frames the interface and mentions the command in one "
        "sentence, which is more than 'it exists' and less than its documentation. The "
        "feature list is graded 1 on u-1019's precedent - it answers only that the "
        "command exists.",
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
            ("docs/concepts/authentication/cli.md#logging-in-to-a-service/", 3),
            ("docs/concepts/authentication/http.md#/0", 1),
        ),
        "A motivation-shaped question; the corpus answers the mechanism, not the motive. "
        "Scoped to the section at 4.12: the stdin recommendation is one paragraph of a "
        "six-chunk section that packing makes a single 204-token chunk, so no chunk "
        "anchor here is true under both settings.",
    ),
    # Nine cases added at roadmap 4.26, to give the thin slices enough judgements
    # to carry a gate (ADR-0052 asks for four). `symbol` takes three of them and
    # `exact` three, because those were the two rows a single case was speaking
    # for; the last three are the relationship and conceptual questions the
    # corpus can honestly be asked. Written from the documents, as every other
    # judgement here was — the passages first, the anchors looked up afterwards.
    (
        "u-1017",
        "uv lock --check",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#checking-the-lockfile/0", 3),),
        "A command with a flag, and the section that documents it is named for the "
        "question rather than for the command.",
    ),
    (
        "u-1018",
        "--no-sources",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/disabling-sources/0", 3),),
        "A literal flag. It appears in four documents and is *explained* in one, which is "
        "the discrimination an exact query has to make.",
    ),
    (
        "u-1019",
        "uv python pin",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/python-versions.md#requesting-a-version/python-version-files/0",
                3,
            ),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "The command is named in a feature list and explained under a heading that does "
        "not contain it; the list is graded 1 because it answers only that the command "
        "exists.",
    ),
    (
        "u-1020",
        "free-threaded Python",
        (EvalSlice.EXACT,),
        (("docs/concepts/python-versions.md#free-threaded-python/0", 3),),
        "A term quoted verbatim from its own heading, and one the corpus uses nowhere "
        "else - the counterpart to `storage directories` on the second corpus.",
    ),
    (
        "u-1021",
        "PEP 508",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#dependency-specifiers/0", 3),),
        "A standard's number, cited in four documents. Only one says what it *is*, and "
        "the others link it in passing - so a hit anywhere is not an answer.",
    ),
    (
        "u-1022",
        "why is my project environment already up to date when I run a command",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),
            ("docs/concepts/projects/run.md#/0", 2),
        ),
        "Two documents state the two halves: one that locking and syncing are automatic, "
        "the other that `uv run` ensures the environment is current first. The query uses "
        "neither's noun - it says neither `lock` nor `sync`.",
    ),
    (
        "u-1023",
        "can I adopt part of uv without adopting all of it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/getting-started/features.md#/0", 3),),
        "The answer is one clause of an overview document - the interface breaks into "
        "sections usable independently or together - phrased the way someone deciding "
        "would ask it.",
    ),
    (
        "u-1024",
        "where do I record which Python a project needs, and what reads that",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/python-versions.md#requesting-a-version/python-version-files/0",
                3,
            ),
            ("docs/concepts/projects/run.md#/0", 1),
        ),
        "A two-part question: the file that records the request, and the commands that "
        "honour it. Graded 1 on the second because it states the mechanism without "
        "naming the file.",
    ),
    (
        "u-1025",
        "uv export",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#exporting-the-lockfile/0", 3),),
        "The third `symbol` case, and the one that takes the slice to the four ADR-0052 "
        "enforces on. A command whose section is titled by what it produces.",
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


def encode_cases(cases: Sequence[EvalCase]) -> str:
    """The bytes `write_cases` would write, without writing them.

    The same one-liner as the writer rather than a re-implementation that could
    disagree with it, and — for now — the same one-liner as
    `tools/build_ingested_cases.py`'s. Both copies want to be one function in
    `mycelium.eval.cases`, beside the writer they must agree with; that module is
    a tuning path, so a change re-judging a frozen release set may not touch it
    (`tools/check_frozen_release_sets.py`). Filed as roadmap 5.33.
    """
    lines = [
        json.dumps(case.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for case in cases
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    if not (CORPUS / "docs").is_dir():
        print(f"the vendored corpus is missing: {CORPUS / 'docs'}")
        return 1

    dev, release = cases_of(DEV), cases_of(RELEASE)
    # Clean for the reason [BUG-0018] records: this corpus is compiled in place,
    # so an incremental build would validate the judgements against whatever
    # chunking the local store already held.
    build(CORPUS, clean=True, pin_identity=False)  # a committed corpus (ADR-0046)
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
    summary = f"{len(dev)} dev and {len(release)} release cases"

    if check_only:
        # A judged set its own generator no longer reproduces is the defect, not
        # a reason to regenerate quietly: the file on disk may be the only copy
        # of a judgement somebody wrote ([BUG-0026]).
        differences = [
            (destination / f"{name}.jsonl").relative_to(ROOT).as_posix()
            for name, cases in (("dev", dev), ("release", release))
            if encode_cases(cases)
            != (
                (destination / f"{name}.jsonl").read_text(encoding="utf-8")
                if (destination / f"{name}.jsonl").is_file()
                else ""
            )
        ]
        print(summary)
        if differences:
            print("the judged sets do not reproduce from this tree:")
            for relative in differences:
                print(f"  {relative}")
            print(
                "a case edited into the set by hand is invisible to this file and the "
                "next run deletes it; move the judgement into DEV/RELEASE above, then "
                "re-run `python tools/build_uv_docs_cases.py` and review the diff"
            )
            return 1
        print("judged sets reproduce byte-for-byte")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", dev)
    write_cases(destination / "release.jsonl", release)
    print(f"wrote {summary} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
