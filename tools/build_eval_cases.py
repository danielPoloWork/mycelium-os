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
from mycelium.eval.cases import validate_judged_set, write_cases  # noqa: E402
from mycelium.sdk.types import EvalCase, EvalSlice, RelevantAnchor  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

SKIP_TOP = frozenset({".git", ".mycelium", "export", ".venv"})
"""Never staged: version control, derived state, and the virtualenv. Everything
else is copied, and `mycelium.toml`'s own `exclude` decides what is *corpus* —
the same rule the gates run under.

Staging a hand-written list of paths instead was a quiet flaw: the judged set was
validated against a smaller corpus than the one it is scored on, so an
`unanswerable` case could pass here and be answerable in CI (ADR-0027)."""

# (case_id, query, slices, [(anchor, grade)], note)
Judgment = tuple[str, str, tuple[EvalSlice, ...], tuple[tuple[str, int], ...], str]

DEV: tuple[Judgment, ...] = (
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
            ("README.md#build-test-run/1", 3),
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
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/2", 3),
            ("docs/adr/0009-adopt-build-publication-semantics.md#alternatives-considered/0", 2),
        ),
        "The spec contradicts itself here; the ADR is the only place the answer exists.",
    ),
    (
        "q-0014",
        "which ADR supersedes the cross-language source layout",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0003-adopt-flat-python-src-layout.md#/0", 3),
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
        "sourdough levain autolyse fermentation",
        (EvalSlice.UNANSWERABLE,),
        (),
        "Vocabulary the corpus does not contain at all; must return nothing.",
    ),
    (
        "q-0018",
        "peregrine falcon stoop velocity",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
    (
        "q-0019",
        "counterpoint fugue stretto cadenza",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
    (
        "q-0020",
        "tidal estuary sediment deposition",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As q-0017, in a different domain.",
    ),
)


RELEASE: tuple[Judgment, ...] = (
    (
        "r-0001",
        "how do I report a security vulnerability",
        (EvalSlice.FACT,),
        (("SECURITY.md#reporting-a-vulnerability/0", 3),),
        "A procedure with its own section, asked in a reader's words.",
    ),
    (
        "r-0002",
        "which versions still receive security fixes",
        (EvalSlice.FACT,),
        (("SECURITY.md#supported-versions/0", 3),),
        "A policy fact stated once.",
    ),
    (
        "r-0003",
        "Conventional Commits",
        (EvalSlice.EXACT,),
        (
            ("docs/workflow/git-workflow.md#3-commit-messages-conventional-commits/0", 3),
            ("CONTRIBUTING.md#making-a-change/0", 1),
        ),
        "A literal term naming a section; the easiest lexical case, kept as a floor.",
    ),
    (
        "r-0004",
        "may an agent merge its own pull request",
        (EvalSlice.CONCEPTUAL,),
        (("docs/workflow/git-workflow.md#1-boundary-between-agent-and-human/0", 3),),
        "A yes/no question whose answer is a boundary the workflow defines.",
    ),
    (
        "r-0005",
        "what exactly does the determinism gate claim",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0", 3),),
        "The claim is stated deliberately narrowly; the question asks for the boundary.",
    ),
    (
        "r-0006",
        "why does a rollback rewrite data instead of just moving a pointer",
        (EvalSlice.CONCEPTUAL, EvalSlice.RELATIONSHIP),
        (
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),
            ("docs/adr/0016-make-snapshots-restorable.md#context/0", 2),
        ),
        "A why-question whose answer is a design constraint, phrased without the ADR's words.",
    ),
    (
        "r-0007",
        "when does the export refuse to produce a bundle",
        (EvalSlice.FACT,),
        (("docs/adr/0020-adopt-the-jsonl-interchange-bundle.md#decision/0", 3),),
        "A refusal condition buried inside a long decision section.",
    ),
    (
        "r-0008",
        "which documents must a pull request keep in sync",
        (EvalSlice.FACT,),
        (
            ("docs/workflow/documentation.md#artifacts-and-when-to-touch-them/0", 3),
            ("docs/workflow/documentation.md#same-pr-discipline/0", 2),
        ),
        "A checklist-shaped answer split across two sections of one document.",
    ),
    (
        "r-0009",
        "what has to be true before a design pattern is added to the catalogue",
        (EvalSlice.CONCEPTUAL,),
        (("docs/patterns/README.md#how-to-use-this-catalogue/0", 3),),
        "A rule stated in a catalogue's own instructions.",
    ),
    (
        "r-0010",
        "how should a branch be named",
        (EvalSlice.FACT,),
        (("docs/workflow/git-workflow.md#2-branch-naming/0", 3),),
        "A convention with a short, specific answer.",
    ),
    (
        "r-0011",
        "who signs off that a contribution may be contributed",
        (EvalSlice.RELATIONSHIP,),
        (
            ("CONTRIBUTING.md#developer-certificate-of-origin-dco/2", 3),
            ("CONTRIBUTING.md#before-you-start/0", 1),
        ),
        "Relates a legal mechanism to the contribution flow; the query uses neither's noun.",
    ),
    (
        "r-0012",
        "what does a pull request have to carry besides a title",
        (EvalSlice.FACT,),
        (("docs/workflow/git-workflow.md#4-pull-requests/4-2-metadata-every-pr/0", 3),),
        "A metadata checklist under a nested heading.",
    ),
    (
        "r-0013",
        "dressage piaffe pirouette",
        (EvalSlice.UNANSWERABLE,),
        (),
        "A domain this project will never document; every term verified clean here.",
    ),
    (
        "r-0014",
        "escapement tourbillon mainspring",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As r-0013, in a different domain.",
    ),
)


def stage_corpus(destination: Path) -> None:
    """Copy the repository into `destination` — the committed tree is never built.

    Everything but version control and derived state, so `mycelium.toml` decides
    the corpus here exactly as it does in CI.
    """
    for source in sorted(ROOT.rglob("*")):
        relative = source.relative_to(ROOT)
        if not source.is_file() or relative.parts[0] in SKIP_TOP or ".git" in relative.parts:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


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
    dev, release = cases_of(DEV), cases_of(RELEASE)

    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch) / "corpus"
        stage_corpus(workspace)
        build(workspace)
        with SqliteStore.open(workspace, read_only=True) as store:
            errors, warnings = validate_judged_set(dev + release, store)

    for warning in warnings:
        print(f"  warning: {warning}")

    if errors:
        print("The judged set does not hold against the corpus:")
        for error in errors:
            print(f"  {error}")
        return 1

    destination = ROOT / "eval"
    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", dev)
    write_cases(destination / "release.jsonl", release)
    print(f"wrote {len(dev)} dev and {len(release)} release cases to {destination.name}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
