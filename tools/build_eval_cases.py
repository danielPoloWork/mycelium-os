#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Author `eval/cases.jsonl` — the judged set over Mycelium OS's own docs.

    python tools/build_eval_cases.py

The judgments live here as data rather than in a JSONL file edited by hand, so
that every anchor is validated against a real build before the set is written: a
case that cites an anchor the corpus does not contain is a broken case, and it
should be impossible to commit one.

**Judging provenance.** These grades were assigned by the agent that wrote the
documents being judged (see `eval/README.md`). That is a real methodological
weakness, disclosed rather than hidden: it makes the set a *seed*, useful for
regression detection and for the grep comparison, and not an independent
benchmark. Independent judgments arrive with the public corpus at 3.7.
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import write_cases  # noqa: E402
from mycelium.sdk.types import EvalCase, EvalSlice, RelevantAnchor  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

CORPUS_PATHS = (
    "README.md",
    "ROADMAP.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "docs/adr",
    "docs/patterns",
    "docs/workflow",
)
"""What the self-evaluation corpus contains. `docs/journal/` is excluded: it grows
every session, so including it would churn judgments for no evaluative gain."""

# (case_id, query, slices, [(anchor, grade)], note)
JUDGMENTS: tuple[tuple[str, str, tuple[EvalSlice, ...], tuple[tuple[str, int], ...], str], ...] = (
    (
        "q-0001",
        "Apache-2.0 license",
        (EvalSlice.EXACT,),
        (
            ("README.md#license/0", 3),
            ("CONTRIBUTING.md#developer-certificate-of-origin-dco/0", 1),
        ),
        "A literal term that appears in few places; exact retrieval should be trivial.",
    ),
    (
        "q-0002",
        "BEGIN IMMEDIATE transaction",
        (EvalSlice.EXACT, EvalSlice.SYMBOL),
        (
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/1", 3),
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#consequences/0", 2),
        ),
        "An identifier-like phrase from SQL, not prose.",
    ),
    (
        "q-0003",
        "SqliteStore",
        (EvalSlice.SYMBOL,),
        (("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#decision/0", 3),),
        "A CamelCase symbol; the planner will route these to exact lookup (spec 04 §2).",
    ),
    (
        "q-0004",
        "UlidFactory",
        (EvalSlice.SYMBOL,),
        (
            ("docs/adr/0005-adopt-in-repo-identity-library.md#decision/0", 3),
            ("docs/adr/0005-adopt-in-repo-identity-library.md#consequences/0", 2),
        ),
        "Same shape as q-0003 but discussed in two sections.",
    ),
    (
        "q-0005",
        "what license does the project use",
        (EvalSlice.FACT,),
        (("README.md#license/0", 3),),
        "The natural-language form of q-0001; the pair shows what phrasing costs.",
    ),
    (
        "q-0006",
        "what is the maximum chunk size in tokens",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#context/0", 1),
        ),
        "A specific number stated in one decision.",
    ),
    (
        "q-0007",
        "how do I report a security vulnerability",
        (EvalSlice.FACT,),
        (("SECURITY.md#reporting-a-vulnerability/0", 3),),
        "A question a newcomer actually asks.",
    ),
    (
        "q-0008",
        "which Python version does the project require",
        (EvalSlice.FACT,),
        (
            ("README.md#build-test-run/0", 3),
            ("docs/adr/0003-adopt-flat-python-src-layout.md#context/0", 1),
        ),
        "The answer is in the README, with supporting context in an ADR.",
    ),
    (
        "q-0009",
        "why is SQLite replaceable rather than a foundation",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#context/0", 3),
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#decision/0", 3),
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#consequences/0", 1),
        ),
        "A rationale question: the answer is spread across an ADR's sections.",
    ),
    (
        "q-0010",
        "why was the official MCP SDK not used as a dependency",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#alternatives-considered/0", 3),
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#context/0", 2),
        ),
        "Rejected alternatives live in a predictable ADR section.",
    ),
    (
        "q-0011",
        "why are record contracts frozen and closed to unknown fields",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#decision/0", 3),
            ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#consequences/0", 2),
        ),
        "Two-part rationale, decision plus consequence.",
    ),
    (
        "q-0012",
        "why does chunking not use overlap",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#alternatives-considered/0", 2),
        ),
        "A negative design question: why something was *not* done.",
    ),
    (
        "q-0013",
        "why does the build write mycelium_id into frontmatter",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/0", 3),
            ("docs/adr/0009-adopt-build-publication-semantics.md#alternatives-considered/0", 2),
        ),
        "The spec contradicts itself here; the ADR is the only place the answer exists.",
    ),
    (
        "q-0014",
        "which ADR supersedes the cross-language source layout",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0003-adopt-flat-python-src-layout.md#decision/0", 3),
            ("docs/adr/0002-adopt-cross-language-source-layout.md#decision/0", 2),
            ("docs/adr/README.md#index/0", 2),
        ),
        "Needs the relation between two documents, not the content of either alone.",
    ),
    (
        "q-0015",
        "what does the determinism gate depend on",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0", 3),
            ("docs/adr/0012-adopt-the-g6-determinism-gate.md#context/0", 2),
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/0", 1),
        ),
        "The dependency (mtime as an input) is stated in one ADR and caused by another.",
    ),
    (
        "q-0016",
        "returned content is data not instructions",
        (EvalSlice.INJECTION,),
        (
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0", 3),
            ("README.md#try-it/1", 2),
            ("docs/adr/0010-adopt-cli-output-conventions.md#context/0", 1),
        ),
        "The injection doctrine (D-017). The adversarial corpus proper is milestone 6.3.",
    ),
    (
        "q-0017",
        "kubernetes helm istio deployment",
        (EvalSlice.UNANSWERABLE,),
        (),
        "Vocabulary the corpus does not contain at all; must return nothing.",
    ),
    (
        "q-0018",
        "graphql resolver subscriptions",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
    (
        "q-0019",
        "kafka zookeeper broker rebalance",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
    (
        "q-0020",
        "terraform ansible provisioning playbook",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
)


def stage_corpus(destination: Path) -> None:
    """Copy the corpus into `destination` — the committed repo is never built."""
    for relative in CORPUS_PATHS:
        source = ROOT / relative
        if not source.exists():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)


def main() -> int:
    cases = tuple(
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
        for case_id, query, slices, relevant, note in JUDGMENTS
    )

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch) / "corpus"
        stage_corpus(workspace)
        build(workspace)
        with SqliteStore.open(workspace, read_only=True) as store:
            missing = [
                (case.case_id, relevant.anchor)
                for case in cases
                for relevant in case.relevant
                if store.get_chunk(relevant.anchor) is None
            ]

    if missing:
        print("These judged anchors do not exist in the corpus:")
        for case_id, anchor in missing:
            print(f"  {case_id}: {anchor}")
        print("\nA heading probably moved. Re-judge the case against the current text.")
        return 1

    destination = ROOT / "eval" / "cases.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_cases(destination, cases)
    print(f"wrote {len(cases)} cases to {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
