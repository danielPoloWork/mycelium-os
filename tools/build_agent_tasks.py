# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Write `eval/tasks.jsonl` — the agent-task suite (spec 04 §7.4, D-010).

Built the way the judged cases are (`build_eval_cases.py`): the tasks live here
as data, every required anchor is validated against a real build before the file
is written, and a task citing an anchor the corpus does not contain cannot be
committed.

A task is not a query. It is what someone actually asks an agent to do, and the
`requires` list is the evidence any correct answer has to rest on — judged by
reading the document, not by asking a retriever what it liked. Several of these
reuse anchors already judged in `cases.jsonl`, which is the point: if an anchor
is the answer to the question, it is the evidence for the task.

    python tools/build_agent_tasks.py
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from build_eval_cases import stage_corpus  # noqa: E402

from mycelium.build import build  # noqa: E402
from mycelium.eval.tasks import AgentTask, write_tasks  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

# (task_id, kind, prompt, required anchors, note)
TASKS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "t-0001",
        "answer",
        "What licence is this project released under? Cite the source.",
        ("README.md#license/0",),
        "The simplest possible question; if this costs a whole file, nothing will be cheap.",
    ),
    (
        "t-0002",
        "answer",
        "How do I report a security vulnerability in this project?",
        ("SECURITY.md#reporting-a-vulnerability/0",),
        "A question whose answer is a policy, not a fact scattered across documents.",
    ),
    (
        "t-0003",
        "answer",
        "Which Python version does the project require?",
        ("README.md#build-test-run/1",),
        "A fact stated once, in a section about something else.",
    ),
    (
        "t-0004",
        "answer",
        "What is the maximum chunk size in tokens, and what happens at the boundary?",
        ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0",),
        "A number plus the rule around it: retrieving the number alone is not an answer.",
    ),
    (
        "t-0005",
        "answer",
        "Why is SQLite described as replaceable rather than a foundation?",
        ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#context/0",),
        "Reasoning, not a fact. The answer is an argument a model has to read.",
    ),
    (
        "t-0006",
        "answer",
        "Why was the official MCP SDK not taken as a runtime dependency?",
        ("docs/adr/0011-implement-mcp-stdio-in-repo.md#alternatives-considered/0",),
        "The answer lives in a rejected alternative, which is where reasons usually hide.",
    ),
    (
        "t-0007",
        "answer",
        "Why does chunking not use overlapping windows?",
        ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0",),
        "A design question whose answer contradicts the common RAG default.",
    ),
    (
        "t-0008",
        "answer",
        "Why does the build write a mycelium_id into document frontmatter?",
        ("docs/adr/0009-adopt-build-publication-semantics.md#decision/2",),
        "Touches the one tier-2 write the compiler makes; an agent must not guess here.",
    ),
    (
        "t-0009",
        "answer",
        "Why are the record contracts frozen and closed to unknown fields?",
        ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#decision/0",),
        "Reasoning behind a constraint a contributor will otherwise try to relax.",
    ),
    (
        "t-0010",
        "answer",
        "What does the determinism gate actually claim, and what does it deliberately exclude?",
        ("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0",),
        "The exclusions are the interesting half, and they are easy to miss by skimming.",
    ),
)

LOCATE_AND_RELATE: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "t-0011",
        "locate",
        "Find where the publication order is defined: lock, transaction, pointer swap.",
        ("docs/adr/0009-adopt-build-publication-semantics.md#decision/1",),
        "The `locate` shape from spec 04 s7.4: find where X is defined.",
    ),
    (
        "t-0012",
        "locate",
        "Where is it decided how vectors are keyed so unchanged text is never re-embedded?",
        ("docs/adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md#decision/0",),
        "A decision stated inside a long ADR, not in its title.",
    ),
    (
        "t-0013",
        "locate",
        "Find the rule that makes a snapshot restorable rather than merely named.",
        ("docs/adr/0016-make-snapshots-restorable.md#decision/0",),
        "",
    ),
    (
        "t-0014",
        "locate",
        "Where is the two-level build cache described - the rows and the blobs?",
        ("docs/adr/0015-adopt-content-addressed-incremental-builds.md#decision/0",),
        "",
    ),
    (
        "t-0015",
        "locate",
        "Find where link extraction is separated from link resolution, and why.",
        ("docs/adr/0018-build-the-graph-from-authored-links.md#decision/0",),
        "",
    ),
    (
        "t-0016",
        "locate",
        "Where is it decided that filesystem events choose when to build, not what to build?",
        ("docs/adr/0019-adopt-watch-mode.md#decision/0",),
        "",
    ),
    (
        "t-0017",
        "relate",
        "Which ADR supersedes the cross-language source layout, and what replaced it?",
        (
            "docs/adr/0003-adopt-flat-python-src-layout.md#/0",
            "docs/adr/0002-adopt-cross-language-source-layout.md#context/0",
        ),
        "The `relate` shape: two documents, and the answer is the relation between them.",
    ),
    (
        "t-0018",
        "relate",
        "Which gate decided that hybrid retrieval is not the default, and what did it measure?",
        (
            "docs/adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md"
            "#decision/and-the-decision-g2-made-hybrid-does-not-earn-the-default/0",
        ),
        "An answer that lives in a subsection, which path-shaped anchors make addressable.",
    ),
    (
        "t-0019",
        "relate",
        "How does the parser relate to markdown-it: what does this project own, and what not?",
        ("docs/adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md#decision/0",),
        "",
    ),
    (
        "t-0020",
        "relate",
        "What does rollback depend on that a plain pointer swap would not give it?",
        (
            "docs/adr/0016-make-snapshots-restorable.md#decision/0",
            "docs/adr/0009-adopt-build-publication-semantics.md#decision/1",
        ),
        "Evidence in two ADRs: the second is what the first had to work around.",
    ),
    (
        "t-0021",
        "answer",
        "What is the contribution sign-off policy for a pull request?",
        ("CONTRIBUTING.md#developer-certificate-of-origin-dco/0",),
        "A process question a contributor asks before their first PR.",
    ),
    (
        "t-0022",
        "answer",
        "What does the project promise about content returned to an agent: data or instructions?",
        ("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0",),
        "The injection doctrine (D-017), which an agent integrating this must not get wrong.",
    ),
)


def main() -> int:
    tasks = tuple(
        AgentTask(task_id=task_id, kind=kind, prompt=prompt, requires=requires, note=note or None)
        for task_id, kind, prompt, requires, note in (*TASKS, *LOCATE_AND_RELATE)
    )

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch) / "corpus"
        stage_corpus(workspace)
        build(workspace)
        with SqliteStore.open(workspace, read_only=True) as store:
            missing = [
                (task.task_id, anchor)
                for task in tasks
                for anchor in task.requires
                if store.get_chunk(anchor) is None
            ]
            # Same lint as the case builder: a heading stub reads like the right
            # section and carries none of the answer (roadmap 3.7).
            stubs = [
                (task.task_id, anchor, chunk.tokens)
                for task in tasks
                for anchor in task.requires
                if (chunk := store.get_chunk(anchor)) is not None and chunk.tokens < 30
            ]

    if stubs:
        print("These required anchors are heading stubs - check they carry the answer:")
        for task_id, anchor, tokens in stubs:
            print(f"  {task_id}: {anchor} ({tokens} tokens)")

    if missing:
        print("These required anchors do not exist in the corpus:")
        for task_id, anchor in missing:
            print(f"  {task_id}: {anchor}")
        print("A heading probably moved. Re-judge the task against the current text.")
        return 1

    destination = ROOT / "eval" / "tasks.jsonl"
    write_tasks(destination, tasks)
    print(f"wrote {len(tasks)} tasks to {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
