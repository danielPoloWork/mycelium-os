#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Author the agent-task suite over the second corpus — `uv`'s documentation.

    python tools/build_uv_docs_tasks.py [--check]

Writes `eval/corpora/uv-docs/eval/tasks.jsonl`, validating every required anchor
against a clean build first. A task citing an anchor the corpus does not hold
cannot be committed.

**Why a second suite exists at all.** ADR-0053 settled the principle for the
judged sets — *report* on the corpus we author, *gate* on the one we do not — and
the agent-task suite had only ever had the first half: all twenty-two tasks in
`eval/tasks.jsonl` are anchored into this repository's own README, SECURITY and
ADRs. That was right while spec 04 §7.4 scored the comparison qualitatively, and
it is the blocker the moment the verdict is meant to *gate* at 1.0, because every
property that makes the comparison move is ours to change: which documents exist,
how large they are, where the chunker puts a boundary under an anchor, and — as
roadmap 6.22 measured — the single file that supplied 93 % of the incumbent's
cost. A suite whose corpus its own authors edit every merge cannot carry a gate
(roadmap 6.23, ADR-0120).

**Judging provenance, precisely** — the same statement `build_uv_docs_cases.py`
makes, because the same bias applies. These prompts and required anchors were
written by the same agent that builds the retriever they measure. What the second
corpus removes is the other half of that bias: nobody here wrote the documents,
so a prompt cannot be phrased in the words the document's author happened to
choose — it has to be guessed the way any reader's would be (ADR-0027).

Every anchor below was judged by **reading the document**, never by running a
query and keeping what came back. That is a discipline rather than an enforceable
rule, so it is recorded here where a reader can weigh it, and the file is
committed *before* anything is scored on it.

**What a task is, and what `requires` means.** A task is not a query: it is what
someone asks an agent to do, and `requires` is the evidence any correct answer
has to rest on. The suite scores a task `found` only when **every** required
anchor's text reached the agent — a conjunction — so an anchor is listed when the
answer is wrong or unsupported without it, never as a second place a retriever
might also have looked.

**`--check` regenerates and compares instead of writing.** It exists because
running a generator without it used to destroy work: the judgements below are the
suite's only source, so a task added to the committed file by hand is invisible
here and the next run deletes it ([BUG-0026], roadmap 5.30). The sibling
generators are checked in CI and in `tools/verify.py`; this one joins them.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import HEADING_STUB_TOKENS  # noqa: E402
from mycelium.eval.tasks import AgentTask, TaskKind, encode_tasks, write_tasks  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

CORPUS = ROOT / "eval" / "corpora" / "uv-docs"

Judgment = tuple[str, TaskKind, str, tuple[str, ...], str]

# (task_id, kind, prompt, required anchors, note)
ANSWER: tuple[Judgment, ...] = (
    (
        "ut-0001",
        "answer",
        "What licence is uv released under? Cite the source.",
        ("docs/reference/policies/license.md#/0",),
        "The simplest question the corpus admits, and the counterpart of `t-0001` on "
        "our own: if this costs a whole document, nothing will be cheap.",
    ),
    (
        "ut-0002",
        "answer",
        "Is it safe to run two uv commands at the same time against the same virtual environment?",
        ("docs/concepts/cache.md#cache-safety/0",),
        "A yes with a caveat attached — the answer is safe *and* never modify the cache "
        "by hand — so retrieving half of it is a wrong answer rather than a partial one.",
    ),
    (
        "ut-0003",
        "answer",
        "We ship on Windows on ARM. Is that supported, and what does that level of "
        "support actually promise?",
        ("docs/reference/policies/platforms.md#/0",),
        "The platform is in a list and the promise is in the prose under it; a hit on "
        "the list alone answers the first half and misleads on the second.",
    ),
    (
        "ut-0004",
        "answer",
        "I rebuilt a wheel into my --find-links directory under the same filename and uv "
        "keeps installing the old one. Why?",
        ("docs/concepts/cache.md#dependency-caching/0",),
        "A surprising rule stated once, inside a bulleted list about something broader: "
        "flat index contents are assumed immutable and cached by name.",
    ),
    (
        "ut-0005",
        "answer",
        "If a package exists on both our private index and PyPI, which one does uv "
        "install from, and can that be changed?",
        ("docs/concepts/indexes.md#searching-across-multiple-indexes/0",),
        "A default plus the reason for it — dependency confusion — plus the opt-out. An "
        "answer that gives only the flag has given the dangerous half.",
    ),
    (
        "ut-0006",
        "answer",
        "Why does uv build a package from source when I am only generating a lockfile?",
        ("docs/reference/troubleshooting/build-failures.md#why-does-uv-build-a-package/0",),
        "Reasoning rather than a fact: the answer is an argument about metadata a model "
        "has to read, and it lives in a troubleshooting document.",
    ),
    (
        "ut-0007",
        "answer",
        "Ctrl-C does not seem to reach the program I started with uv run. What does uv "
        "do with signals?",
        ("docs/concepts/projects/run.md#signal-handling/0",),
        "A rule with named exceptions on two operating systems; the exceptions are the "
        "half that is easy to skim past.",
    ),
    (
        "ut-0008",
        "answer",
        "How do I stop uv from downloading Python versions on its own?",
        ("docs/concepts/python-versions.md#disabling-automatic-python-downloads/0",),
        "A setting, its two values and the flag that overrides it — stated in a short "
        "section whose heading is almost the question.",
    ),
    (
        "ut-0009",
        "answer",
        "uv pip install will not install into my system Python the way pip does. What is "
        "the rule, and how do I override it?",
        ("docs/pip/compatibility.md#virtual-environments-by-default/0",),
        "A deliberate incompatibility with the tool being replaced, which is where a "
        "migrating reader's questions concentrate.",
    ),
    (
        "ut-0010",
        "answer",
        "What is the difference between uv cache clean and uv cache prune?",
        ("docs/concepts/cache.md#clearing-the-cache/0",),
        "Two commands one letter apart, distinguished in one passage. Returning the "
        "document is not the same as returning the passage that separates them.",
    ),
)

LOCATE: tuple[Judgment, ...] = (
    (
        "ut-0011",
        "locate",
        "Find where the order uv searches in for a virtual environment is defined.",
        ("docs/pip/environments.md#discovery-of-python-environments/0",),
        "The `locate` shape from spec 04 §7.4: find where X is defined. The prompt uses "
        "neither of the heading's nouns — `discovery`, `environments` — on purpose.",
    ),
    (
        "ut-0012",
        "locate",
        "Where is it written which directory uv puts executables in, the one that should "
        "be on my PATH?",
        ("docs/reference/storage.md#storage-directories/executable-directory/0",),
        "One subsection of a document that is nothing but directories, so the whole "
        "document matches and only one part of it answers.",
    ),
    (
        "ut-0013",
        "locate",
        "Find the rule that decides whether the lockfile counts as out of date.",
        ("docs/concepts/projects/sync.md#checking-the-lockfile/0",),
        "A decision stated inside a long document, under a heading that does not "
        "contain the word the question is about.",
    ),
    (
        "ut-0014",
        "locate",
        "Where is it decided what happens to packages that are installed but not in the lockfile?",
        (
            "docs/concepts/projects/sync.md#syncing-the-environment/handling-of-extraneous-packages/0",
        ),
        "The answer is a default that differs between two commands, in a subsection "
        "two levels down — the shape path-shaped anchors exist to make addressable.",
    ),
    (
        "ut-0015",
        "locate",
        "Find where a single preview feature can be turned on without enabling all of them.",
        ("docs/concepts/preview.md#enabling-preview-features/0",),
        "A flag, an environment variable and a configuration key, all in one section; "
        "the document's other sections are about the same subject and answer nothing.",
    ),
    (
        "ut-0016",
        "locate",
        "Where does it say which glibc version the official Linux builds need?",
        ("docs/reference/policies/platforms.md#linux-versions/0",),
        "A fact encoded in wheel tags rather than written as a sentence, in a section "
        "of a document whose opening is about something else (`ut-0003`).",
    ),
)

RELATE: tuple[Judgment, ...] = (
    (
        "ut-0017",
        "relate",
        "Is the uv.lock schema version part of uv's public API, and which releases are "
        "allowed to change it?",
        (
            "docs/concepts/resolution.md#lockfile-versioning/0",
            "docs/reference/policies/versioning.md#lockfile-versioning/0",
        ),
        "The `relate` shape: the policy document makes the promise, the concept "
        "document says what a version mismatch does to you. Either alone is half an "
        "answer, and the policy half is four sentences long.",
    ),
    (
        "ut-0018",
        "relate",
        "If I run uv cache clean, what happens to a tool I ran with uvx, and to one I "
        "installed with uv tool install?",
        (
            "docs/concepts/tools.md#tool-environments/0",
            "docs/reference/storage.md#types-of-data/tools/0",
        ),
        "Two documents, and the relation is the answer: one environment is in the cache "
        "and disposable, the other is in the tools directory and is not.",
    ),
    (
        "ut-0019",
        "relate",
        "We have one repository with several packages whose requirements conflict. Is a "
        "workspace the right shape, and what would the members share?",
        (
            "docs/concepts/projects/workspaces.md#/0",
            "docs/concepts/projects/workspaces.md#when-not-to-use-workspaces/0",
        ),
        "A recommendation that inverts between two sections of one document: what a "
        "workspace shares is exactly what makes it wrong here, and the second section "
        "names the alternative.",
    ),
    (
        "ut-0020",
        "relate",
        "Our CI cache keeps growing. What does uv recommend trimming it with, and what "
        "does the GitHub Actions workflow step look like?",
        (
            "docs/concepts/cache.md#caching-in-continuous-integration/0",
            "docs/guides/integration/github.md#caching/0",
        ),
        "The concept document argues the strategy and the guide shows the step. A "
        "reader asking this wants both, and they are in different parts of the tree.",
    ),
    (
        "ut-0021",
        "relate",
        "Where does the environment for a project live, and how do I run something in it "
        "without activating anything?",
        (
            "docs/concepts/projects/layout.md#the-project-environment/0",
            "docs/concepts/projects/run.md#/0",
        ),
        "Two documents that each answer one half and point at the other; the second is "
        "a document preamble, which is where introductions to a command usually sit.",
    ),
    (
        "ut-0022",
        "relate",
        "Are uvx and uv tool run the same thing, and when should I install a tool instead "
        "of just running it?",
        (
            "docs/concepts/tools.md#the-uv-tool-interface/0",
            "docs/concepts/tools.md#execution-vs-installation/0",
        ),
        "The equivalence is stated in one section and the recommendation in the next, "
        "and the second never repeats the alias — so a retriever that stops at the "
        "first match answers the smaller half.",
    ),
)


def tasks_of(judgments: Sequence[Judgment]) -> tuple[AgentTask, ...]:
    return tuple(
        AgentTask(task_id=task_id, kind=kind, prompt=prompt, requires=requires, note=note or None)
        for task_id, kind, prompt, requires, note in judgments
    )


def validate(tasks: Sequence[AgentTask], store: SqliteStore) -> tuple[list[str], list[str]]:
    """Errors that refuse the write, and warnings that only ask a question.

    The same two checks the judged-set validator runs, for the same two reasons: an
    anchor the corpus does not hold names nothing (and would be scored as an
    *unresolved* task rather than a miss, so it measures neither strategy —
    ADR-0120), and a heading stub reads like the right section while carrying none
    of the answer (roadmap 3.7).
    """
    errors: list[str] = []
    warnings: list[str] = []
    for task in tasks:
        if not task.requires:
            errors.append(f"{task.task_id}: no required anchor — the task scores nothing")
        for anchor in task.requires:
            chunk = store.get_chunk(anchor)
            if chunk is None:
                errors.append(f"{task.task_id}: {anchor} — no such chunk")
            elif chunk.tokens < HEADING_STUB_TOKENS:
                warnings.append(
                    f"{task.task_id}: {anchor} is {chunk.tokens} tokens — check it carries "
                    "the answer rather than the heading above it"
                )
    return errors, warnings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Author the uv-docs agent-task suite.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate and compare against the committed suite instead of writing it.",
    )
    args = parser.parse_args(argv)

    if not (CORPUS / "docs").is_dir():
        print(f"the vendored corpus is missing: {CORPUS / 'docs'}")
        return 1

    tasks = tasks_of((*ANSWER, *LOCATE, *RELATE))

    # Clean for the reason [BUG-0018] records: this corpus is compiled in place, so
    # an incremental build would validate the judgements against whatever chunking
    # the local store already held. `pin_identity=False` because the corpus is
    # committed (ADR-0046) and a generator that dirties 81 tracked files is one
    # nobody can run from a clean tree.
    build(CORPUS, clean=True, pin_identity=False)
    with SqliteStore.open(CORPUS, read_only=True) as store:
        errors, warnings = validate(tasks, store)

    for warning in warnings:
        print(f"  warning: {warning}")
    if errors:
        print("The suite does not hold against the corpus:")
        for error in errors:
            print(f"  {error}")
        print(
            "A heading probably moved: re-judge the task against the current text, by "
            "reading it (ADR-0022), rather than re-pointing it at whatever still exists."
        )
        return 1

    destination = CORPUS / "eval" / "tasks.jsonl"
    kinds = ", ".join(
        f"{kind} {sum(1 for task in tasks if task.kind == kind)}"
        for kind in ("answer", "locate", "relate")
    )
    summary = f"{len(tasks)} tasks ({kinds})"

    if args.check:
        committed = destination.read_text(encoding="utf-8") if destination.is_file() else ""
        print(summary)
        if encode_tasks(tasks) != committed:
            print(f"the suite does not reproduce from this tree: {destination.relative_to(ROOT)}")
            print(
                "a task edited into the file by hand is invisible to this generator and the "
                "next run deletes it; move the judgement into this file, then re-run "
                "`python tools/build_uv_docs_tasks.py` and review the diff"
            )
            return 1
        print("the suite reproduces byte-for-byte")
        return 0

    destination.parent.mkdir(parents=True, exist_ok=True)
    write_tasks(destination, tasks)
    print(f"wrote {summary} to {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
