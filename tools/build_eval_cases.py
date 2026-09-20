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
            ("CONTRIBUTING.md#developer-certificate-of-origin-dco/", 1),
        ),
        "A literal term that appears in few places; exact retrieval should be trivial.",
    ),
    (
        "q-0002",
        "BEGIN IMMEDIATE transaction",
        (EvalSlice.EXACT, EvalSlice.SYMBOL),
        (
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/", 3),
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#consequences/0", 2),
        ),
        "An identifier-like phrase from SQL, not prose. Scoped to the section at 4.12: "
        "the Decision is one argument in three parts - the lead-in, the publication "
        "sequence the phrase belongs to, and the crash windows that sequence creates - "
        "and packing merges all three into one chunk, so the section is the smallest "
        "unit that holds the answer under every configuration this set is scored on.",
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
            ("README.md#build-test-run/", 3),
            ("docs/adr/0003-adopt-flat-python-src-layout.md#context/0", 1),
        ),
        "The answer is in the README, with supporting context in an ADR. Scoped to the "
        "section at 4.12: the version is stated in the toolchain paragraph that follows "
        "the install commands, and packing joins the two into one chunk.",
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
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/", 3),
            ("docs/adr/0009-adopt-build-publication-semantics.md#alternatives-considered/0", 2),
        ),
        "The spec contradicts itself here; the ADR is the only place the answer exists - "
        "the 'identity pinning is the build's only tier-2 write' paragraph of the "
        "Decision. Scoped to the section at 4.12, which packing makes a single chunk.",
    ),
    (
        "q-0014",
        "which ADR supersedes the cross-language source layout",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0003-adopt-flat-python-src-layout.md#/0", 3),
            ("docs/adr/0002-adopt-cross-language-source-layout.md#decision/", 2),
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
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/", 1),
        ),
        "The dependency (mtime as an input) is stated in one ADR and caused by another.",
    ),
    (
        "q-0016",
        "returned content is data not instructions",
        (EvalSlice.INJECTION,),
        (
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0", 3),
            ("README.md#try-it/", 2),
            ("docs/adr/0010-adopt-cli-output-conventions.md#context/0", 1),
        ),
        "The injection doctrine (D-017). The adversarial corpus proper is milestone 6.3. "
        "The README anchor is scoped to its section at 4.12: the notice is the closing "
        "paragraph of a two-chunk section that packing makes one.",
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
        (("SECURITY.md#supported-versions/", 3),),
        "A policy fact stated once.",
    ),
    (
        "r-0003",
        "Conventional Commits",
        (EvalSlice.EXACT,),
        (
            ("AGENTS.md#6-git-workflow/6-3-commit-messages-conventional-commits/", 3),
            ("docs/workflow/git-workflow.md#3-commit-messages-conventional-commits/", 3),
            ("CONTRIBUTING.md#making-a-change/0", 1),
        ),
        "A literal term naming a section; the easiest lexical case, kept as a floor. "
        "AGENTS.md was added at 4.12, and not because a ranking wanted it: the rule is "
        "documented in three places and the judgment named two, omitting the one this "
        "repository calls its source of truth (CLAUDE.md: 'read it first'). Both AGENTS.md "
        "6.3 and git-workflow.md 3 are titled with the term and state the template, so "
        "both grade 3; CONTRIBUTING.md mentions it in passing among the branch and PR "
        "steps, which is what grade 1 is for.",
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
            ("CONTRIBUTING.md#developer-certificate-of-origin-dco/", 3),
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
        "r-0015",
        "Reciprocal Rank Fusion",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/retrieval-is-lexical-by-default-and-that-was-measured/0",
                3,
            ),
        ),
        "A literal term with exactly one home in the corpus. Added at 4.20: `exact` on this "
        "set held a single case, so its mean was a case wearing a slice's name (ADR-0044).",
    ),
    (
        "r-0016",
        "Contributor Covenant",
        (EvalSlice.EXACT,),
        (
            ("CODE_OF_CONDUCT.md#attribution/0", 3),
            ("CODE_OF_CONDUCT.md#/0", 1),
        ),
        "The literal term appears twice in one document, and only one of the two answers "
        "the question a reader asking it has: Attribution names the covenant and its "
        "version, while the title is the term with nothing behind it. Grade 1 rather than 0 "
        "because a reader landing on the title has found the right document.",
    ),
    (
        "r-0017",
        "STRIDE",
        (EvalSlice.EXACT,),
        (
            ("docs/security/threat-model.md#2-stride-pass/0", 3),
            ("AGENTS.md#7-documentation-maintenance/0", 1),
        ),
        "An acronym that appears in three documents, where only one of them *is* the thing "
        "named; the other two say the threat model contains it. That is what makes it a "
        "harder exact case than a heading quoted back verbatim.",
    ),
    (
        "r-0018",
        "can an agent keep querying while a build is running",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#decision/0", 3),
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/0", 2),
        ),
        "Relates two mechanisms decided in two different ADRs — WAL with read-only "
        "connections, and the single-writer lock with its pointer swap — and the query uses "
        "neither's noun. Added at 4.20, where `relationship` held two cases.",
    ),
    (
        "r-0019",
        "why do the compiler and the file watcher never disagree about what a document is",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0021-scope-the-corpus-and-gate-the-evaluation.md#decision/", 3),
            ("docs/adr/0019-adopt-watch-mode.md#decision/0", 1),
        ),
        "The relation is stated in one place and its consequence in another. Named as a "
        "section rather than a chunk: the decision runs to two chunks and the answer is the "
        "paragraph inside it, which is the reading ADR-0029 asks for.",
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
    # --- retrieval and the compiler, as the ADRs record them ---
    (
        "r-0020",
        "MAX_QUERY_TERMS",
        (EvalSlice.EXACT,),
        (("docs/adr/0129-bound-the-question-once-before-anything-reads-it.md#decision/0", 3),),
        "A constant named in the decision that introduced it, which is also the only "
        "place that says what happens to the terms beyond it.",
    ),
    (
        "r-0021",
        "why is a query cut to a fixed number of terms before anything reads it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0129-bound-the-question-once-before-anything-reads-it.md#decision/0", 3),),
        "A bound taken once rather than per leg, and the reason is about what every "
        "downstream stage would otherwise have to repeat.",
    ),
    (
        "r-0022",
        "which dependency group holds the renderer",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md#decision/0",
                3,
            ),
        ),
        "A group name and an exact pin, in the decision that put them there.",
    ),
    (
        "r-0023",
        "why does the default sync remove typst",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md#decision/0",
                3,
            ),
        ),
        "Deliberate rather than accidental, which is exactly the sentence the decision "
        "spends its words on.",
    ),
    (
        "r-0024",
        "which MCP methods does the in-repo server implement",
        (EvalSlice.FACT,),
        (("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0", 3),),
        "A five-item list inside a decision whose headline is about not taking a dependency.",
    ),
    (
        "r-0025",
        "how does the documentation site get published",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0127-publish-docs-site-from-a-workflow-artifact-tracking-main.md"
                "#decision/0",
                3,
            ),
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-"
                "duplicating.md"
                "#decision/0",
                2,
            ),
        ),
        "One ADR builds the site and another publishes it; the question is about the "
        "second and the vocabulary belongs to the first.",
    ),
    (
        "r-0026",
        "mkdocs build --strict",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0127-publish-docs-site-from-a-workflow-artifact-tracking-main.md"
                "#decision/0",
                3,
            ),
        ),
        "A command line quoted in two documents; the decision is the one that says why "
        "the same command runs in two places.",
    ),
    (
        "r-0027",
        "how many agent tasks are judged against uv's documentation",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-"
                "them-rather-than-re-judge-them.md#decision/0",
                3,
            ),
        ),
        "A count and its breakdown by kind, in the decision that authored them.",
    ),
    (
        "r-0028",
        "why is the twin's suite carried instead of judged again",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-"
                "them-rather-than-re-judge-them.md#decision/0",
                3,
            ),
            ("docs/adr/0039-measure-what-projection-costs.md#decision/0", 2),
        ),
        "The newer ADR applies the older one's rule to a second asset; the older one is "
        "where the rule is argued.",
    ),
    (
        "r-0029",
        "why is markup removed from the text that gets indexed",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0110-drop-the-markup-and-keep-the-words-on-evidence-a-placeholder-"
                "cannot-forge.md#decision/0",
                3,
            ),
        ),
        "A decision that is careful about what it is *not*: nothing is parsed, nothing "
        "is resolved, and what is left is what a reader sees.",
    ),
    (
        "r-0030",
        "which markdown dialect is the corpus read in",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0095-read-the-corpus-in-the-dialect-it-is-written-in.md#decision/0",
                3,
            ),
        ),
        "A one-word answer with four sentences of justification around it.",
    ),
    (
        "r-0031",
        "why does a parser declare what it cannot carry instead of reporting each loss",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#decision/0", 3),
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 2),
        ),
        "The rule is quoted from the older ADR inside the newer one, which is why both "
        "are needed and why only one of them is the answer.",
    ),
    (
        "r-0032",
        "why were the new judged cases committed before anything was scored on them",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0067-grow-the-dev-set-before-asking-it-a-question.md#decision/0",
                3,
            ),
        ),
        "The evidence is the commit order, which is a claim about process rather than about code.",
    ),
    (
        "r-0033",
        "plan_query",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0083-route-the-query-and-report-that-routing-cannot-save-a-lost-"
                "ablation.md#decision/0",
                3,
            ),
        ),
        "A function name that appears in one ADR and names the planner spec 04 §2 asks for.",
    ),
    (
        "r-0034",
        "how many columns does the lexical index have",
        (EvalSlice.FACT,),
        (("docs/adr/0048-index-the-stem-beside-the-surface-form.md#decision/0", 3),),
        "Six, and the answer is only useful with the reason - three fields, each indexed twice.",
    ),
    (
        "r-0035",
        "STEM_WEIGHT",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0048-index-the-stem-beside-the-surface-form.md#decision/0", 3),
            ("docs/adr/0048-index-the-stem-beside-the-surface-form.md#/0", 2),
        ),
        "A constant whose value was halved by a later ADR, which the status line of "
        "this one records - so the document's opening is part of the answer.",
    ),
    (
        "r-0036",
        "how many documents does the ingested corpus hold",
        (EvalSlice.FACT,),
        (("docs/adr/0039-measure-what-projection-costs.md#decision/0", 3),),
        "A number that is the same number as the second corpus's, which is the point of "
        "the sentence it sits in.",
    ),
    (
        "r-0037",
        "pack_atomic",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0042-let-an-atomic-block-share-its-chunk.md#decision/0", 3),
            (
                "docs/adr/0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md#decision/0",
                2,
            ),
        ),
        "A setting introduced switched off by one ADR and switched on by another; the "
        "first documents what it does.",
    ),
    (
        "r-0038",
        "what does atomic mean for a chunk",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0042-let-an-atomic-block-share-its-chunk.md#decision/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 2),
        ),
        "A definition reinterpreted: indivisible, not solitary. The older ADR is where "
        "the word was first used the other way.",
    ),
    (
        "r-0039",
        "when does gate G3 enforce a slice",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md"
                "#decision/one-the-enforcement-contract-stated-and-implemented/0",
                3,
            ),
        ),
        "Three conditions, all of which must hold, in the subsection that states the contract.",
    ),
    (
        "r-0040",
        "where does the rule against naming an anchor twice live",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0108-put-the-repeated-anchor-rule-on-the-record-not-on-the-corpus-"
                "lint.md#decision/0",
                3,
            ),
            (
                "docs/adr/0104-merge-what-the-projection-could-not-tell-apart-and-record-that-"
                "it-could-not.md#decision/0",
                2,
            ),
        ),
        "The rule moved from a lint to the record itself; the ADR that added the lint "
        "is the other half of the answer.",
    ),
    (
        "r-0041",
        "py.typed",
        (EvalSlice.EXACT,),
        (("docs/adr/0071-advertise-the-types-and-check-the-tools.md#decision/0", 3),),
        "An empty file worth 73 of 184 errors, which is the sentence that makes this "
        "more than a filename.",
    ),
    (
        "r-0042",
        "what does the per-case whole mark print beside the share",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-"
                "half-the-reading.md#decision/0",
                3,
            ),
        ),
        "A notation - `0.509@1` - and the reason the grade has to travel with it.",
    ),
    (
        "r-0043",
        "serialize_by_alias",
        (EvalSlice.EXACT,),
        (("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#decision/0", 3),),
        "A pydantic setting named once, with the field that forced the version floor it "
        "sits beside.",
    ),
    (
        "r-0044",
        "what name is the package published under",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-"
                "defined-thing.md#decision/0",
                3,
            ),
        ),
        "Two names in one sentence - the distribution and the import package - and the "
        "question is about the first.",
    ),
    (
        "r-0045",
        "how does the grep baseline rank what it finds",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0013-adopt-the-evaluation-harness.md#decision/0", 3),),
        "A ranking rule written as a description of a person reading grep output.",
    ),
    (
        "r-0046",
        "in what order does a build publish its results",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/", 3),
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 2),
        ),
        "The order is a code block in one ADR; what it writes so that it can be undone "
        "is the other's subject.",
    ),
    (
        "r-0047",
        "why does the intermediate representation have no field for emphasis",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0107-refuse-to-model-emphasis-and-name-the-lane-the-disagreement-is-"
                "in.md#decision/0",
                3,
            ),
        ),
        "A refusal with a criterion behind it: a code span is a naming and emphasis is not.",
    ),
    (
        "r-0048",
        "fts_schema",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md"
                "#decision/0",
                3,
            ),
        ),
        "A function whose output is what a recorded verdict is fingerprinted against.",
    ),
    (
        "r-0049",
        "what does a snapshot record so that it can be restored",
        (EvalSlice.FACT,),
        (("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),),
        "A per-document list of seven things, in canonical JSON, written as one blob.",
    ),
    (
        "r-0050",
        "build_cache",
        (EvalSlice.EXACT,),
        (("docs/adr/0015-adopt-content-addressed-incremental-builds.md#decision/0", 3),),
        "A table name, and the decision that says what it indexes and where the blobs "
        "it points at live.",
    ),
    (
        "r-0051",
        "why were three candidate re-rankings all refused",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0031-refuse-three-rerankings.md#decision/0", 3),),
        "A table of measurements and a refusal, where the interesting part is that "
        "nothing in the query path changed.",
    ),
    (
        "r-0052",
        "what did the hybrid gate actually measure",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md"
                "#decision/and-the-decision-g2-made-hybrid-does-not-earn-the-default/0",
                3,
            ),
        ),
        "A results table in a subsection, against a document whose other sections are "
        "about the embedder rather than the verdict.",
    ),
    (
        "r-0053",
        "in watch mode, what do filesystem events decide",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0019-adopt-watch-mode.md#decision/0", 3),),
        "Two sentences that are the whole design: events decide when, the build decides what.",
    ),
    (
        "r-0054",
        "what happens when the passage a citation names has moved",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md"
                "#decision/0",
                3,
            ),
        ),
        "A response shape with three fields, and the refusal to serve it silently.",
    ),
    (
        "r-0055",
        "what weight does a leaf heading carry in ranking",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#decision/0",
                3,
            ),
        ),
        "A number that moved on the third attempt, and the ancestors' weight that did "
        "not move with it.",
    ),
    (
        "r-0056",
        "what happens when two judged passages land on the same chunk",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0104-merge-what-the-projection-could-not-tell-apart-and-record-that-"
                "it-could-not.md#decision/0",
                3,
            ),
            ("docs/adr/0039-measure-what-projection-costs.md#decision/0", 2),
        ),
        "A merge rule and a receipt; the carry it modifies is defined in the older ADR.",
    ),
    (
        "r-0057",
        "what opens a section's first chunk",
        (EvalSlice.FACT,),
        (("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 3),),
        "The heading, and the two reasons it is kept rather than stripped.",
    ),
    (
        "r-0058",
        "why could the hybrid gate not decide the default",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0064-measure-the-gate-that-decides-the-default.md#decision/0", 3),),
        "An item closed with a measurement rather than a fix, which is the shape of the answer.",
    ),
    # --- the graph, the symbol table, and the gates that judge them ---
    (
        "r-0059",
        "what counts as an entity in this corpus",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-"
                "rest.md#decision/0",
                3,
            ),
        ),
        "A definition by refusal: declared by the corpus, never inferred from prose.",
    ),
    (
        "r-0060",
        "how many edge types have a derivation",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md"
                "#decision/0",
                3,
            ),
        ),
        "Six of eight, and the other two have a written reason - the count alone is not "
        "the answer.",
    ),
    (
        "r-0061",
        "part_of",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md"
                "#decision/0",
                3,
            ),
            ("docs/adr/0018-build-the-graph-from-authored-links.md#decision/0", 2),
        ),
        "An edge type whose derivation is defined in one ADR and whose vocabulary comes "
        "from another.",
    ),
    (
        "r-0062",
        "--against",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md"
                "#decision/0",
                3,
            ),
        ),
        "A flag that turned a one-off comparison into part of every run, which is the "
        "decision rather than the flag.",
    ),
    (
        "r-0063",
        "what does the incumbent have to reach for the harness to trust it",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0081-check-the-incumbents-reach-not-its-ranking.md#decision/0",
                3,
            ),
        ),
        "One assertion replaced by another, with the two that did not change beside it.",
    ),
    (
        "r-0064",
        "why does the symbol leg ship switched off",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-"
                "sites.md#decision/0",
                3,
            ),
        ),
        "A leg built exactly as the spec words it and shipped off anyway, which is a "
        "reasoning question rather than a fact.",
    ),
    (
        "r-0065",
        "why is the root changelog kept out of the corpus",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0125-exclude-the-root-changelog-because-unreleased-is-the-restatement-"
                "early.md#decision/0",
                3,
            ),
            (
                "docs/adr/0072-keep-our-own-restatements-out-of-our-own-benchmark.md#decision/0",
                2,
            ),
        ),
        "The newer ADR applies the older one's rule to the one file it had missed; the "
        "rule itself is in the older one.",
    ),
    (
        "r-0066",
        "how does a callout affect where a chunk ends",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md#decision/0",
                3,
            ),
        ),
        "It bounds rather than atomises, and the distinction is the whole decision.",
    ),
    (
        "r-0067",
        "is the documentation site part of the judged corpus",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0126-measure-the-docs-site-before-deciding-whether-it-joins-the-"
                "corpus.md#decision/0",
                3,
            ),
        ),
        "A yes, reached by measurement rather than by assertion, in a short decision.",
    ),
    (
        "r-0068",
        "what does it mean when a projected case scores higher than the document it came from",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md"
                "#decision/0",
                3,
            ),
        ),
        "The title states the position and the decision is the argument for leaving "
        "everything alone.",
    ),
    (
        "r-0069",
        "where do the production sources live",
        (EvalSlice.FACT,),
        (("docs/adr/0003-adopt-flat-python-src-layout.md#decision/0", 3),),
        "A four-line tree, in the ADR that superseded the layout before it.",
    ),
    (
        "r-0070",
        "why does the model return line numbers rather than the text it segmented",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md"
                "#decision/0",
                3,
            ),
        ),
        "A custody rule expressed as an interface: the content never leaves the "
        "operator's own text.",
    ),
    (
        "r-0071",
        "how much does one case move a slice of n cases",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0044-name-what-a-two-case-slice-can-and-cannot-say.md"
                "#decision/two-no-and-the-numbers-say-how-badly/0",
                3,
            ),
        ),
        "An arithmetic answer - one nth of one case's swing - against a threshold, in "
        "the subsection that does the sum.",
    ),
    (
        "r-0072",
        "measure_slice_decay.py",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0044-name-what-a-two-case-slice-can-and-cannot-say.md"
                "#decision/one-it-was-the-corpus-it-was-one-case-and-that-case-was-never-being-"
                "retrieved/0",
                3,
            ),
        ),
        "A tool named in the subsection that explains what it is for - the instrument "
        "the gate cannot be.",
    ),
    (
        "r-0073",
        "why was the length split refused",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0066-refuse-the-length-split-and-name-the-anti-correlation.md#decision/0",
                3,
            ),
        ),
        "Five settings refused at once, and the reason is that the item's own bar could "
        "not be met by any of them.",
    ),
    (
        "r-0074",
        "what two fingerprints does a corpus carry",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0045-ask-the-documents-whether-two-runs-are-comparable.md#decision/0",
                3,
            ),
        ),
        "Two named digests that answer different questions, which is the point of having both.",
    ),
    (
        "r-0075",
        "why were the function-word candidates refused",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0057-drop-the-function-words-and-score-the-seam-that-ships.md#decision/0",
                3,
            ),
        ),
        "Three refusals and one fix, where the refusals rest on the classes not being "
        "separable by document frequency.",
    ),
    (
        "r-0076",
        "what did graph expansion do to the scores",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-"
                "lost.md#decision/1",
                3,
            ),
            (
                "docs/adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-"
                "lost.md#decision/0",
                2,
            ),
        ),
        "The table is in the second half of a decision whose first half describes the "
        "mechanism; the numbers are the answer and the mechanism is the context.",
    ),
    (
        "r-0077",
        "what weight do a heading's ancestors carry",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0063-split-the-leaf-heading-from-its-ancestors.md#decision/0", 3),
            (
                "docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#decision/0",
                2,
            ),
        ),
        "The split ADR sets the ancestor weight; the later one moved the leaf and left "
        "the ancestors where they were.",
    ),
    (
        "r-0078",
        "Crockford base32",
        (EvalSlice.EXACT,),
        (("docs/adr/0005-adopt-in-repo-identity-library.md#decision/0", 3),),
        "An encoding named once, in the sentence that says how few lines the identity library is.",
    ),
    (
        "r-0079",
        "what happens to the vector leg when the lexical leg finds nothing",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#decision/0",
                3,
            ),
        ),
        "A precondition and what the outcome carries when it is not met.",
    ),
    (
        "r-0080",
        "CURRENT",
        (EvalSlice.EXACT,),
        (("docs/adr/0020-adopt-the-jsonl-interchange-bundle.md#decision/0", 3),),
        "A pointer file whose name is an ordinary word, so the section that says what "
        "is read from it is the only usable evidence.",
    ),
    (
        "r-0081",
        "why are a source document's links rendered back as links",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-"
                "asserted-them.md#decision/0",
                3,
            ),
        ),
        "A reversal that became safe once edges carried who asserted them, which is the "
        "reasoning the question asks for.",
    ),
    (
        "r-0082",
        "which headings define a name",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-"
                "documents-a-name.md#decision/0",
                3,
            ),
        ),
        "A rule with worked examples on both sides of the line it draws.",
    ),
    (
        "r-0083",
        "why is the journal index generated rather than written by hand",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-"
                "file.md#decision/0",
                3,
            ),
            ("docs/adr/0001-record-architecture-decisions.md#decision/0", 2),
        ),
        "A small decision recorded because the project records decisions like it, which "
        "is the older ADR's whole subject.",
    ),
    (
        "r-0084",
        "what does a symbol judgment name",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0062-a-symbol-judgment-names-where-the-thing-is-documented.md#decision/0",
                3,
            ),
        ),
        "A grading rule with three tiers, stated once and applied ever since.",
    ),
    (
        "r-0085",
        "where do a code fence's definitions come from",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-"
                "name.md#decision/0",
                3,
            ),
        ),
        "The grammar's own tags query, per language, from a registry - a fact with "
        "three moving parts.",
    ),
    (
        "r-0086",
        "which symbol stage is cached per document and which one runs every build",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-"
                "name.md#decision/1",
                3,
            ),
            ("docs/adr/0018-build-the-graph-from-authored-links.md#decision/0", 2),
        ),
        "The seam is cut the same way twice - once for links, once for symbols - and "
        "the older ADR is where it was cut first.",
    ),
    # --- the promise, the release, and the workflow documents ---
    (
        "r-0087",
        "how many contracts does the compatibility promise cover",
        (EvalSlice.FACT,),
        (("docs/compatibility.md#the-five-stable-contracts/0", 3),),
        "A count and the five names, in the section written to hold exactly that.",
    ),
    (
        "r-0088",
        "is the command line covered by the compatibility promise",
        (EvalSlice.FACT,),
        (("docs/compatibility.md#what-is-not-covered/0", 3),),
        "A no with a qualification - it is public and under SemVer, and still not one "
        "of the five - which is the half a reader gets wrong.",
    ),
    (
        "r-0089",
        'extra="forbid"',
        (EvalSlice.EXACT,),
        (
            (
                "docs/compatibility.md"
                "#what-stable-means/reader-rules-and-why-there-are-two-of-them/0",
                3,
            ),
            ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#decision/0", 2),
        ),
        "A pydantic setting quoted as a rule about readers; the ADR that adopted it is "
        "where it is a decision rather than a consequence.",
    ),
    (
        "r-0090",
        "how is the compatibility promise checked rather than asserted",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/compatibility.md#how-the-promise-is-checked/0", 3),
            (
                "docs/adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-"
                "before-the-tag-that-binds-it.md#decision/0",
                2,
            ),
        ),
        "The document says what the test does; the ADR says why goldens of shape rather "
        "than prose.",
    ),
    (
        "r-0091",
        "which release level carries an additive change after 1.0",
        (EvalSlice.FACT,),
        (("docs/compatibility.md#what-stable-means/from-v1-0-0/0", 3),),
        "A list of four additive shapes and the level they ship in.",
    ),
    (
        "r-0092",
        "what is the first step in cutting a release",
        (EvalSlice.FACT,),
        (("docs/workflow/release.md#cutting-a-release-the-steps/0", 3),),
        "The answer is a step that happens in its own pull request before anything "
        "else, which is easy to read past.",
    ),
    (
        "r-0093",
        "who re-blesses the baseline before a release",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/release.md#boundary/0", 3),
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-"
                "incumbents.md#decision/0",
                2,
            ),
        ),
        "A table of who does what, and the ADR that explains why the step exists at all.",
    ),
    (
        "r-0094",
        "what does a minor version bump mean before 1.0",
        (EvalSlice.FACT,),
        (
            ("docs/workflow/release.md#versioning/0", 3),
            ("AGENTS.md#11-versioning-release/0", 2),
        ),
        "The same rule in two places; the workflow document states it as the policy and "
        "the contract restates it for agents.",
    ),
    (
        "r-0095",
        "how does a security fix reach users",
        (EvalSlice.FACT,),
        (("docs/workflow/maintenance.md#security-fixes/0", 3),),
        "Five steps in forty tokens - embargo, coordinated release, advisory, changelog "
        "entry, backport.",
    ),
    (
        "r-0096",
        "what does deprecating a public symbol require",
        (EvalSlice.FACT,),
        (("docs/workflow/maintenance.md#deprecation-policy/0", 3),),
        "A level, a window and a record - and the symbol keeps working throughout.",
    ),
    (
        "r-0097",
        "how does a confirmed bug reach a released version",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/maintenance.md#bug-lifecycle/0", 3),
            ("docs/workflow/maintenance.md#hotfix-backport/0", 2),
        ),
        "The lifecycle names three steps and hands the third to the section below it; "
        "the answer needs both halves.",
    ),
    (
        "r-0098",
        "which merge strategy is this repository configured for",
        (EvalSlice.FACT,),
        (
            (
                "docs/workflow/github-setup.md"
                "#1-merge-strategy-squash-only-pr-title-body-as-the-commit/0",
                3,
            ),
        ),
        "One strategy and the two it disables, with the consequence for what the commit "
        "message becomes.",
    ),
    (
        "r-0099",
        "why must the labels exist before the first Dependabot run",
        (EvalSlice.FACT,),
        (("docs/workflow/github-setup.md#2-labels-one-type-label-per-pr/0", 3),),
        "A silent failure mode - GitHub drops a label that does not exist, with no "
        "error - which is the only reason the ordering matters.",
    ),
    (
        "r-0100",
        "check_repo_settings.py",
        (EvalSlice.EXACT,),
        (
            (
                "docs/workflow/github-setup.md#0-which-of-these-is-actually-installed/0",
                3,
            ),
            ("docs/workflow/release.md#boundary/0", 2),
        ),
        "A tool documented where it is run and named again in the release boundary "
        "table, which is the only other place it has a job.",
    ),
    (
        "r-0101",
        "what marks an ADR as superseded",
        (EvalSlice.FACT,),
        (("docs/workflow/documentation.md#amending-an-adr-roadmap-5-21/0", 3),),
        "A status line and a frontmatter key, with the distinction from an amendment "
        "that the section exists to draw.",
    ),
    (
        "r-0102",
        "when does a specification have to be updated",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/documentation.md#artifacts-and-when-to-touch-them/0", 3),
            ("AGENTS.md#7-documentation-maintenance/0", 2),
        ),
        "A table of artifacts and their triggers, and the contract section it expands.",
    ),
    (
        "r-0103",
        "where does a translated page live",
        (EvalSlice.FACT,),
        (("docs/workflow/documentation.md#translations-d-028/0", 3),),
        "A path rule plus the two things a translation may never do.",
    ),
    (
        "r-0104",
        "what goes into the wheel",
        (EvalSlice.FACT,),
        (("docs/workflow/packaging.md#artifact/0", 3),),
        "Two archives described as allowlists rather than as whatever the build swept "
        "up - the table is the answer and the sentence above it is why.",
    ),
    (
        "r-0105",
        "how do I verify an artifact I downloaded",
        (EvalSlice.FACT,),
        (
            (
                "docs/workflow/packaging.md"
                "#provenance-what-a-release-ships-beside-the-archives/"
                "verifying-what-you-downloaded/0",
                3,
            ),
        ),
        "One command, in the subsection whose first sentence is the reason it is "
        "written down at all.",
    ),
    (
        "r-0106",
        "what has to happen before the first upload to the index",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/packaging.md#turning-the-publish-on/0", 3),
            (
                "docs/adr/0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-"
                "defined-thing.md#decision/0",
                2,
            ),
        ),
        "Three acts that belong to the maintainer, and the ADR that decided the name "
        "they will be performed under.",
    ),
    (
        "r-0107",
        "how many components does the default SBOM list",
        (EvalSlice.FACT,),
        (
            (
                "docs/workflow/packaging.md"
                "#provenance-what-a-release-ships-beside-the-archives/"
                "the-sbom-and-what-it-can-and-cannot-claim/0",
                3,
            ),
        ),
        "A number attached to a command, and the claim the document is careful not to "
        "make with it.",
    ),
    (
        "r-0108",
        "which two distributions does this repository build",
        (EvalSlice.FACT,),
        (("docs/workflow/packaging.md#a-second-distribution-modules/0", 3),),
        "Two names and a table comparing their sources, in a section about the second one.",
    ),
    (
        "r-0109",
        "how many judged case sets does the project hold",
        (EvalSlice.FACT,),
        (("eval/README.md#the-case-sets/0", 3),),
        "Six, and the table that follows says which corpus each belongs to.",
    ),
    (
        "r-0110",
        "what does a blessed baseline record",
        (EvalSlice.FACT,),
        (
            (
                "eval/README.md"
                "#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/what-a-baseline-records/0",
                3,
            ),
        ),
        "A field-by-field table of what the gate reads, which is a different question "
        "from what the gate does.",
    ),
    (
        "r-0111",
        "which gates can be enforced on this repository's own corpus",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "eval/README.md"
                "#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/"
                "which-sets-a-gate-can-live-on/0",
                3,
            ),
            (
                "docs/adr/0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md"
                "#decision/0",
                2,
            ),
        ),
        "The evaluation README states which set a gate can live on; the ADR is where "
        "the rule was decided and named.",
    ),
    (
        "r-0112",
        "g2-verdict.json",
        (EvalSlice.EXACT,),
        (
            (
                "eval/README.md"
                "#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/"
                "what-gate-g2-s-verdict-records/0",
                3,
            ),
            ("docs/adr/0068-give-gate-g2-a-runner-by-dating-its-verdict.md#decision/0", 2),
        ),
        "A committed file whose fields are listed in one document and argued for in another.",
    ),
    (
        "r-0113",
        "when does a case count as abstained",
        (EvalSlice.FACT,),
        (("eval/README.md#known-limitations/0", 3),),
        "A narrow definition, stated as a limitation rather than as a feature.",
    ),
    (
        "r-0114",
        "what does a trailing slash mean in a judged anchor",
        (EvalSlice.RELATIONSHIP,),
        (
            ("eval/README.md#chunk-or-section-the-judging-rule/0", 3),
            ("docs/adr/0029-let-a-judgment-name-a-section.md#decision/0", 2),
        ),
        "A notation defined in the README and decided in the ADR; the question is about "
        "the notation and the reason lives next door.",
    ),
    (
        "r-0115",
        "which architecture style is committed",
        (EvalSlice.FACT,),
        (
            ("docs/patterns/README.md#architecture-style/0", 3),
            ("docs/patterns/design-patterns.md#5-architectural-application-styles/0", 2),
        ),
        "A one-word commitment plus the discipline that goes with it; the taxonomy is "
        "where the word is defined.",
    ),
    (
        "r-0116",
        "what must accompany a pattern when it is adopted",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/patterns/README.md#how-to-use-this-catalogue/0", 3),
            ("AGENTS.md#7-documentation-maintenance/0", 2),
        ),
        "A row, an ADR link and a real code path - the catalogue's own rule, and the "
        "contract that requires it.",
    ),
    (
        "r-0117",
        "what coverage does new code have to reach",
        (EvalSlice.FACT,),
        (("AGENTS.md#10-enterprise-quality-bar/0", 3),),
        "One row of the quality-bar table, among a dozen others that look alike.",
    ),
    (
        "r-0118",
        "who bumps the version and who publishes the release",
        (EvalSlice.RELATIONSHIP,),
        (
            ("AGENTS.md#11-versioning-release/0", 3),
            ("docs/workflow/release.md#boundary/0", 2),
        ),
        "The boundary is stated in the contract and tabulated in the workflow document; "
        "either alone leaves half the answer out.",
    ),
    (
        "r-0119",
        "which three security artifacts does the project keep apart",
        (EvalSlice.FACT,),
        (("docs/security/README.md#/0", 3),),
        "Three artifacts, three jobs, one table - and the section exists because they "
        "are easy to confuse.",
    ),
    (
        "r-0120",
        "did the security review leave anything critical open",
        (EvalSlice.FACT,),
        (("docs/security/audit-2026-09-17-review-pass.md#verdicts/0", 3),),
        "A verdict paragraph that answers with a no and characterises what was found instead.",
    ),
    # --- the front door, the RFC, the spec, and the security documents ---
    (
        "r-0121",
        "mycelium init",
        (EvalSlice.EXACT,),
        (("README.md#try-it/", 3),),
        "A command named in the walkthrough that documents it, among nine others in the "
        "same section.",
    ),
    (
        "r-0122",
        "mycelium://",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/"
                "a-citation-that-has-gone-stale-tells-you-instead-of-quietly-answering/0",
                3,
            ),
            (
                "docs/adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md"
                "#decision/0",
                2,
            ),
        ),
        "A URI scheme: the README section shows what it keys on, the ADR decides what "
        "happens when the passage moves.",
    ),
    (
        "r-0123",
        "what does building without pinning identity avoid writing",
        (EvalSlice.FACT,),
        (("README.md#try-it/", 3),),
        "A flag whose effect is what it does *not* do to your files.",
    ),
    (
        "r-0124",
        "which stages does a document pass through when it is compiled",
        (EvalSlice.FACT,),
        (("README.md#how-it-compiles/0", 3),),
        "A pipeline drawn as a diagram, which is the whole answer and hard to match on words.",
    ),
    (
        "r-0125",
        "what is different about compiling knowledge instead of retrieving it",
        (EvalSlice.CONCEPTUAL,),
        (("README.md#what-makes-it-different/0", 3),),
        "A comparison table whose first row is the answer: when the work happens.",
    ),
    (
        "r-0126",
        "what does ingestion keep of the file it read",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/"
                "the-original-is-kept-and-hostile-files-are-refused-before-they-cost-anything/0",
                3,
            ),
        ),
        "Custody plus refusal, in the section that pairs them deliberately.",
    ),
    (
        "r-0127",
        "why is an ingested document's link never counted as something a person asserted",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "README.md#what-makes-it-different/"
                "an-ingested-document-joins-the-graph-and-is-never-mistaken-for-something-"
                "someone-wrote/0",
                3,
            ),
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-"
                "never-call-them-authored.md#decision/0",
                2,
            ),
        ),
        "The README states the guarantee; the ADR is where the typing rule that makes "
        "it true was decided.",
    ),
    (
        "r-0128",
        "what does the verify command measure",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/"
                "nothing-becomes-verified-without-a-gate-and-a-person/0",
                3,
            ),
        ),
        "A measurement and a human step, and the section's point is that neither alone "
        "promotes a document.",
    ),
    (
        "r-0129",
        "llm-wiki",
        (EvalSlice.EXACT,),
        (("README.md#inspiration-origins/0", 3),),
        "A project name that appears once in the corpus, in the section that credits it.",
    ),
    (
        "r-0130",
        "which toolchain does this project build with",
        (EvalSlice.FACT,),
        (("README.md#build-test-run/0", 3),),
        "A list of tools in a short section that also carries the three commands a "
        "newcomer runs first.",
    ),
    (
        "r-0131",
        "can I install this from PyPI today",
        (EvalSlice.FACT,),
        (
            ("README.md#install/0", 3),
            ("docs/workflow/packaging.md#turning-the-publish-on/0", 2),
        ),
        "A not-yet with the install line that does work; the packaging document is what "
        "it defers to for when that changes.",
    ),
    (
        "r-0132",
        "what does the planner tell you about a query",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "README.md#what-makes-it-different/"
                "your-query-is-planned-and-the-plan-tells-you-which-rule-chose-it/0",
                3,
            ),
            (
                "docs/adr/0083-route-the-query-and-report-that-routing-cannot-save-a-lost-"
                "ablation.md#decision/0",
                2,
            ),
        ),
        "The README shows what the explain block carries; the ADR is where the rules "
        "and their limits were decided.",
    ),
    (
        "r-0133",
        "why does the index hold both the word and its stem",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "README.md#what-makes-it-different/"
                "the-lexical-index-matches-inflections-and-still-prefers-your-exact-word/0",
                3,
            ),
            ("docs/adr/0048-index-the-stem-beside-the-surface-form.md#decision/0", 2),
        ),
        "A user-facing explanation and the decision that sets the weight between them.",
    ),
    (
        "r-0134",
        "which three outcomes does a search distinguish for a term",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/"
                "retrieval-is-lexical-by-default-and-that-was-measured/1",
                3,
            ),
        ),
        "Three named outcomes in a continuation chunk, which is where a section's "
        "second half lands.",
    ),
    (
        "r-0135",
        "how does a chat export become citable knowledge",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "README.md#what-makes-it-different/"
                "your-chatbot-conversations-become-citable-knowledge-through-a-real-plugin/0",
                3,
            ),
            ("contrib/chats/README.md#/0", 2),
        ),
        "The README explains the shape; the module's own README is the thing being "
        "described, one distribution away.",
    ),
    (
        "r-0136",
        "D-014",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/"
                "the-graph-is-typed-and-every-type-is-derived-from-something-you-wrote/0",
                3,
            ),
        ),
        "A decision identifier used as a citation; the section it is cited in is the "
        "one that says what it fixed.",
    ),
    (
        "r-0137",
        "what does the RFC adopt as the design of record",
        (EvalSlice.FACT,),
        (("docs/rfc/0001-mycelium-os-v1.md#decision/0", 3),),
        "A package of specification documents and the milestones it is delivered against.",
    ),
    (
        "r-0138",
        "why was rewriting the legacy implementation rejected",
        (EvalSlice.CONCEPTUAL,),
        (("docs/rfc/0001-mycelium-os-v1.md#alternatives/0", 3),),
        "A rejection with a number attached, among four alternatives each rejected on "
        "its own concrete reason.",
    ),
    (
        "r-0139",
        "which numeric budgets does the design commit to",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/rfc/0001-mycelium-os-v1.md#decision/scalability-budgets-scalability/0",
                3,
            ),
            ("docs/specs/01_spec_mycelium.md#3-non-functional-requirements/0", 2),
        ),
        "The RFC lists one target per axis; the specification is where each becomes a "
        "numbered requirement.",
    ),
    (
        "r-0140",
        "D-017",
        (EvalSlice.EXACT,),
        (("docs/rfc/0001-mycelium-os-v1.md#decision/cross-cutting/0", 3),),
        "The injection doctrine's identifier, in the subsection that states it in one sentence.",
    ),
    (
        "r-0141",
        "which public contracts does the design promise",
        (EvalSlice.FACT,),
        (
            (
                "docs/rfc/0001-mycelium-os-v1.md#decision/api-contract-api-systemdesign/0",
                3,
            ),
        ),
        "Two consumer-facing and one contributor-facing, counted exactly.",
    ),
    (
        "r-0142",
        "what does the evaluation requirement in the specification ask for",
        (EvalSlice.FACT,),
        (("docs/specs/01_spec_mycelium.md#2-functional-requirements/0", 3),),
        "One numbered requirement among many in a single long section.",
    ),
    (
        "r-0143",
        "which budget does the search latency requirement state",
        (EvalSlice.FACT,),
        (
            ("docs/specs/01_spec_mycelium.md#3-non-functional-requirements/0", 3),
            ("docs/benchmarks/2026-09-17-reference-profile.md#/0", 2),
        ),
        "The requirement states the number and its conditions; the benchmark report is "
        "where it was finally measured against them.",
    ),
    (
        "r-0144",
        "how many trust boundaries does the threat model name",
        (EvalSlice.FACT,),
        (("docs/security/threat-model.md#1-scope-trust-boundaries/0", 3),),
        "A table of boundaries with their untrusted inputs, in the longest section of "
        "the document.",
    ),
    (
        "r-0145",
        "what happens to a threat that survives analysis",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/security/threat-model.md#3-findings-the-risk-register/0", 3),
            ("docs/security/README.md#/0", 2),
        ),
        "The threat model hands it to the register; the security README is where the "
        "division of labour between the two is stated.",
    ),
    (
        "r-0146",
        "when may a security finding be accepted rather than fixed",
        (EvalSlice.FACT,),
        (
            (
                "docs/security/threat-model.md"
                "#3-findings-the-risk-register/"
                "a-deferral-names-the-condition-that-ends-it-roadmap-6-16-adr-0118/0",
                3,
            ),
        ),
        "A deferral with a named ending condition, which is the whole rule.",
    ),
    (
        "r-0147",
        "what does a reporter get after sending a vulnerability report",
        (EvalSlice.FACT,),
        (("SECURITY.md#what-to-expect/0", 3),),
        "Three steps, and the decision tree the fix's level comes from.",
    ),
    (
        "r-0148",
        "what are the ways into this project for a new contributor",
        (EvalSlice.FACT,),
        (("CONTRIBUTING.md#the-ladder/0", 3),),
        "Five rungs, deliberately specific, in the section that says why vagueness "
        "would not be information.",
    ),
    (
        "r-0149",
        "which commands does the development setup run",
        (EvalSlice.FACT,),
        (("CONTRIBUTING.md#development-setup/0", 3),),
        "Six commands in order, and the same list appears nowhere else in this form.",
    ),
    (
        "r-0150",
        "what should I do when a property test fails only sometimes",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "CONTRIBUTING.md#development-setup/when-a-property-test-fails-intermittently/0",
                3,
            ),
            (
                "docs/bugs/2026/09/"
                "BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md#/0",
                2,
            ),
        ),
        "The contributor document gives the profile and the advice; the bug record is "
        "the instance that produced it.",
    ),
    (
        "r-0151",
        "how long may a commit subject be",
        (EvalSlice.FACT,),
        (
            (
                "docs/workflow/git-workflow.md#3-commit-messages-conventional-commits/",
                3,
            ),
        ),
        "A number inside a template, which is the kind of fact that hides in a code block.",
    ),
    (
        "r-0152",
        "what does a pull request title become after merge",
        (EvalSlice.FACT,),
        (
            (
                "docs/workflow/git-workflow.md"
                "#4-pull-requests/4-1-title-body-the-squash-merge-commit/0",
                3,
            ),
        ),
        "A consequence of the merge method, stated where the title rules are.",
    ),
    (
        "r-0153",
        "may an agent push straight to the default branch",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/git-workflow.md#1-boundary-between-agent-and-human/0", 3),
            ("AGENTS.md#6-git-workflow/0", 2),
        ),
        "A no in two documents, one of which is the contract the other expands.",
    ),
    # --- constants, protocols and the rules that name them ---
    (
        "r-0154",
        "require_pandoc()",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0105-pandoc-gets-a-floor-not-a-pin-because-nothing-it-writes-can-be-"
                "checked.md#decision/0",
                3,
            ),
        ),
        "A preflight function named after its sibling, in the ADR that says why the two "
        "are not treated the same.",
    ),
    (
        "r-0155",
        "why does pandoc get a floor where the renderer gets a pin",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0105-pandoc-gets-a-floor-not-a-pin-because-nothing-it-writes-can-be-"
                "checked.md#decision/0",
                3,
            ),
            (
                "docs/adr/0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md#decision/0",
                2,
            ),
        ),
        "The newer ADR is written against the older one's precedent; the difference is "
        "whether the output can be checked.",
    ),
    (
        "r-0156",
        "format-rotation.json",
        (EvalSlice.EXACT,),
        (("docs/adr/0056-make-the-format-assignment-append-only.md#decision/0", 3),),
        "A committed file whose whole purpose is to record an order, named once.",
    ),
    (
        "r-0157",
        "MIN_WHOLE",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0111-a-floor-can-reject-what-a-preference-must-not-choose.md#decision/0", 3),
            (
                "docs/adr/0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-"
                "with-it.md#decision/0",
                2,
            ),
        ),
        "A constant with a value and a narrowing: the earlier ADR recorded the metric "
        "and refused to choose with it.",
    ),
    (
        "r-0158",
        "supersedes:",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-"
                "unlandable.md#decision/0",
                3,
            ),
        ),
        "One key added to a closed contract, with the count of the field set before and after.",
    ),
    (
        "r-0159",
        "MODULE_SURFACE",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-"
                "one-consumer.md#decision/0",
                3,
            ),
        ),
        "A mapping that exists to name reasons rather than symbols, which is the "
        "decision it encodes.",
    ),
    (
        "r-0160",
        "pytest.mark.boundary",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-"
                "may-cost-to-read.md#decision/0",
                3,
            ),
        ),
        "A marker that ties a test file to a threat-model boundary, declared at module level.",
    ),
    (
        "r-0161",
        "target_tokens",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0023-make-the-chunk-target-steer-size.md#decision/0", 3),
            ("docs/adr/0014-adopt-partial-strict-configuration.md#/0", 2),
        ),
        "A knob whose meaning was amended: the later ADR gives it a job, the earlier "
        "one's status line records that it had none.",
    ),
    (
        "r-0162",
        "ChunkingConfig",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md#decision/0",
                3,
            ),
        ),
        "A shipped-default class named beside the chunker's own policy, because the two "
        "disagreeing is the trap the decision closes.",
    ),
    (
        "r-0163",
        "sym:cli:",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-"
                "promotion-can-and-cannot-reorder.md#decision/0",
                3,
            ),
        ),
        "An identity prefix, and the two conditions a command has to meet to earn one.",
    ),
    (
        "r-0164",
        "cite_sections_only",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md"
                "#decision/1",
                3,
            ),
        ),
        "A declaration on an evidence document, in the half of the decision that pairs "
        "vocabulary with a check.",
    ),
    (
        "r-0165",
        "outputSchema",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-"
                "before-the-tag-that-binds-it.md#decision/1",
                3,
            ),
        ),
        "A schema key added beside one that was always there, and the suite that "
        "validates every payload against it.",
    ),
    (
        "r-0166",
        "tests/conftest.py",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0060-declare-the-property-test-budget-and-keep-the-falsifying-"
                "example.md#decision/0",
                3,
            ),
            (
                "CONTRIBUTING.md#development-setup/when-a-property-test-fails-intermittently/0",
                2,
            ),
        ),
        "A file named where the profiles are declared, and again where a contributor is "
        "told what to do about a flaky run.",
    ),
    (
        "r-0167",
        "PDFium",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#decision/0",
                3,
            ),
        ),
        "An engine named in the refusal that keeps it: the text layer, page-scoped, "
        "with a warning attached.",
    ),
    (
        "r-0168",
        "mycelium.sdk.protocols",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md#decision/0", 3),
            ("docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md#decision/0", 2),
        ),
        "A module that holds two protocols in one ADR and gains a third in another.",
    ),
    (
        "r-0169",
        "how many engines does ingestion adapt",
        (EvalSlice.FACT,),
        (("docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md#decision/0", 3),),
        "Four, behind two protocols, with one pinned list - the count is only half the answer.",
    ),
    (
        "r-0170",
        "what does the PDF parser warn about on every document",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#decision/0",
                3,
            ),
        ),
        "A warning that is a declaration of what the lane cannot see, which is the "
        "refusal's whole mitigation.",
    ),
    (
        "r-0171",
        "where does a distillation write its output",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md"
                "#decision/0",
                3,
            ),
        ),
        "A path, and the fact that it is an authoring-time command rather than a build stage.",
    ),
    (
        "r-0172",
        "which hypothesis profiles does the test suite register",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0060-declare-the-property-test-budget-and-keep-the-falsifying-"
                "example.md#decision/0",
                3,
            ),
        ),
        "Two profiles and which one is loaded where, with the deadline each carries.",
    ),
    (
        "r-0173",
        "how many keys does the frontmatter contract hold",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-"
                "unlandable.md#decision/0",
                3,
            ),
        ),
        "A count before and after one addition, which is how the decision states its own size.",
    ),
    (
        "r-0174",
        "when does the packer close a run of prose",
        (EvalSlice.FACT,),
        (("docs/adr/0023-make-the-chunk-target-steer-size.md#decision/0", 3),),
        "At the first paragraph boundary after a threshold, with a ceiling it still may not cross.",
    ),
    (
        "r-0175",
        "what does the vector scan cost at the reference profile",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0030-correct-the-vector-scan-cost-model.md#decision/0", 3),
            ("docs/adr/0026-pack-the-vectors-into-a-memory-mapped-matrix.md#/0", 2),
        ),
        "A corrected number, and the status line of the ADR it corrects is where the "
        "correction is announced.",
    ),
    (
        "r-0176",
        "how is an unanswerable case checked",
        (EvalSlice.FACT,),
        (("docs/adr/0021-scope-the-corpus-and-gate-the-evaluation.md#decision/1", 3),),
        "Mechanically, against both retrievers, because the corpus grows into the "
        "query - which is the reason rather than the rule.",
    ),
    (
        "r-0177",
        "which release sets does gate G3 enforce on",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md"
                "#decision/0",
                3,
            ),
        ),
        "A table of set, corpus and verdict, stated so it need not be deduced from digests.",
    ),
    (
        "r-0178",
        "what does an exact judgment name",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0101-let-the-exact-slice-name-the-section-that-documents-the-"
                "literal.md#decision/0",
                3,
            ),
            (
                "docs/adr/0062-a-symbol-judgment-names-where-the-thing-is-documented.md#decision/0",
                2,
            ),
        ),
        "A rule stated for one slice by borrowing the rule another ADR wrote for its sibling.",
    ),
    (
        "r-0179",
        "why does no approximate vector index ship",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0028-keep-the-vector-scan-exact.md#decision/0", 3),),
        "A refusal that leaves the gap open, named and measured, rather than closing it "
        "with something that answers a different question.",
    ),
    (
        "r-0180",
        "why was the section-indexing family closed rather than refused again",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0041-bound-the-section-unit-and-refuse-six-more.md#decision/0", 3),),
        "An upper bound instead of a seventh refusal, which is a decision about how to "
        "stop asking.",
    ),
    (
        "r-0181",
        "what must be true before a synthesized document is written",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md#decision/0", 3),),
        "Every claim cites evidence that exists, and the lane refuses to write anything "
        "else - a rule about what a model is allowed to do.",
    ),
    (
        "r-0182",
        "what does the agent-task suite measure in place of an agent",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0022-measure-the-agent-loop-without-an-agent.md#decision/0", 3),
            ("eval/README.md#the-agent-task-suite/0", 2),
        ),
        "The substrate rather than the loop; the README is where the same choice is "
        "explained to a reader of the sets.",
    ),
    (
        "r-0183",
        "why is configuration loaded strictly but honoured only partly",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0014-adopt-partial-strict-configuration.md#decision/0", 3),),
        "Two halves of one policy, and the decision is careful to say which sections are which.",
    ),
    (
        "r-0184",
        "how does a module use the engine without reaching into it",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-"
                "one-consumer.md#decision/0",
                3,
            ),
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md#decision/0",
                2,
            ),
        ),
        "The surface is declared in one ADR and exercised by the module the other one built.",
    ),
    (
        "r-0185",
        "what did the contract freeze add to the MCP tools",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-"
                "before-the-tag-that-binds-it.md#decision/1",
                3,
            ),
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0", 2),
        ),
        "A declared output schema on a surface the older ADR built without one.",
    ),
    (
        "r-0186",
        "what happened to the links an ingested document carries",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-"
                "never-call-them-authored.md#decision/0",
                3,
            ),
            (
                "docs/adr/0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-"
                "asserted-them.md#decision/0",
                2,
            ),
        ),
        "One ADR left them in tier 1 and the follow-up moved them into tier 2; the "
        "first is the one that says so.",
    ),
    (
        "r-0187",
        "what does a judgment name when two configurations chunk differently",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md#decision/0",
                3,
            ),
            ("docs/adr/0029-let-a-judgment-name-a-section.md#decision/0", 2),
        ),
        "The smallest unit that holds the answer under every configuration - which "
        "needs the section form the other ADR introduced.",
    ),
    (
        "r-0188",
        "what replaced the rule that a derived set may not move with its source",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0056-make-the-format-assignment-append-only.md#decision/0", 3),
            ("docs/adr/0039-measure-what-projection-costs.md#decision/0", 2),
        ),
        "A regeneration check in place of a rule about commits; the carry it checks is "
        "the older ADR's.",
    ),
    # --- gates, custody, and the instruments that watch them ---
    (
        "r-0189",
        "citation_precision",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0122-score-what-a-citation-names-and-read-it-from-the-chunk.md"
                "#decision/0",
                3,
            ),
        ),
        "A metric introduced beside an older one, so the section that defines it is the "
        "only place the difference is stated.",
    ),
    (
        "r-0190",
        "--no-pin",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-"
                "write.md#decision/0",
                3,
            ),
            ("README.md#try-it/", 2),
        ),
        "A flag whose ADR gives it a semantics - tier 2 left byte-identical - and whose "
        "README line only shows it being used.",
    ),
    (
        "r-0191",
        "case_set_digest",
        (EvalSlice.EXACT,),
        (("docs/adr/0051-hold-the-judgements-fixed-too.md#decision/0", 3),),
        "A digest over judgements rather than documents, which is the distinction the "
        "ADR exists to draw.",
    ),
    (
        "r-0192",
        "observe_build",
        (EvalSlice.EXACT,),
        (("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0", 3),),
        "The function the determinism gate is built on, named where the claim it makes is stated.",
    ),
    (
        "r-0193",
        "quarantine",
        (EvalSlice.EXACT,),
        (("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 3),),
        "A record kind and a directory; the section says who writes it and who decides "
        "what to do next.",
    ),
    (
        "r-0194",
        "enforceable_at",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md#decision/0",
                3,
            ),
            ("docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#decision/0", 2),
        ),
        "A function that replaced a guessed constant; the older ADR is where the "
        "constant was guessed.",
    ),
    (
        "r-0195",
        "SearchFilters",
        (EvalSlice.EXACT,),
        (("docs/adr/0024-serve-what-the-configuration-admits.md#decision/0", 3),),
        "A record whose fields became set-valued, and the SQL shape that follows from it.",
    ),
    (
        "r-0196",
        "store/base.py",
        (EvalSlice.EXACT,),
        (("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#decision/0", 3),),
        "A file path that is really a boundary: every operation stated in records "
        "rather than rows.",
    ),
    (
        "r-0197",
        "LinkRefs",
        (EvalSlice.EXACT,),
        (("docs/adr/0018-build-the-graph-from-authored-links.md#decision/0", 3),),
        "The type extraction yields, named where the per-document and global halves are separated.",
    ),
    (
        "r-0198",
        "stat memo",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-"
                "holds-for.md#decision/0",
                3,
            ),
        ),
        "A two-word name the ADR coins for what it records beside a digest.",
    ),
    (
        "r-0199",
        "mycelium.ingest.encoding",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0134-own-the-decode-and-stop-asking-whatever-is-importable.md#decision/0",
                3,
            ),
        ),
        "A module introduced to take a decision away from whatever happened to be installed.",
    ),
    (
        "r-0200",
        "amends",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0092-leave-the-amendment-relation-in-prose-and-check-the-prose.md"
                "#decision/0",
                3,
            ),
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-"
                "unlandable.md#decision/0",
                2,
            ),
        ),
        "A word that is deliberately *not* an edge type; the sibling ADR is where the "
        "key that is one was added.",
    ),
    (
        "r-0201",
        "chunks_fts",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md"
                "#decision/0",
                3,
            ),
            ("docs/adr/0008-adopt-sqlite-store-behind-a-store-protocol.md#decision/0", 2),
        ),
        "A table named in the ADR that changed how it is addressed, and in the one that "
        "created it.",
    ),
    (
        "r-0202",
        "what two numbers does the harness report beside citation coverage",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0122-score-what-a-citation-names-and-read-it-from-the-chunk.md"
                "#decision/0",
                3,
            ),
        ),
        "Two metrics defined in one paragraph, per case and per slice.",
    ),
    (
        "r-0203",
        "what does verification refuse to report as a number",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md"
                "#decision/0",
                3,
            ),
        ),
        "A component that cannot be measured is reported as not measured - a rule about "
        "reporting rather than about measuring.",
    ),
    (
        "r-0204",
        "what does the query gate ask the corpus",
        (EvalSlice.FACT,),
        (("docs/adr/0054-gate-the-query-not-the-documents.md#decision/0", 3),),
        "One question with a limit of one row, before the open search - the two SQL "
        "lines are the answer.",
    ),
    (
        "r-0205",
        "who writes the corpus declaration the ingestion gate compares against",
        (EvalSlice.FACT,),
        (("docs/adr/0038-declare-the-corpus-then-compare-it.md#decision/0", 3),),
        "A person, against a source they can read - which is the whole reason the "
        "declaration exists.",
    ),
    (
        "r-0206",
        "how does the projector decide whether to escape a block",
        (EvalSlice.FACT,),
        (("docs/adr/0099-ask-the-compiler-whether-the-prose-survived.md#decision/0", 3),),
        "It renders, re-parses with the build's own reader, and compares - a procedure "
        "rather than a rule.",
    ),
    (
        "r-0207",
        "which trees does the type checker read",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0124-check-the-tests-like-the-source-because-there-was-no-middle-"
                "setting.md#decision/0",
                3,
            ),
        ),
        "Four paths and a count of the errors that had to be resolved to add the last two.",
    ),
    (
        "r-0208",
        "what does the verification ladder derive from the diff",
        (EvalSlice.FACT,),
        (("docs/adr/0055-run-the-gates-the-change-implicates.md#decision/0", 3),),
        "Four modes, narrowest first, derived rather than declared.",
    ),
    (
        "r-0209",
        "where does an ingested original live",
        (EvalSlice.FACT,),
        (("docs/adr/0033-keep-the-original-and-bound-the-hostile.md#decision/0", 3),),
        "A named subtree the collector never sweeps, written before anything is parsed.",
    ),
    (
        "r-0210",
        "which milestone gate was carried forward rather than waived",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md"
                "#decision/0",
                3,
            ),
        ),
        "Three of four gates closed a milestone and the fourth was carried by name, "
        "with the item that owns it.",
    ),
    (
        "r-0211",
        "what does the docs site do instead of duplicating the documentation",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-"
                "of-duplicating.md#decision/0",
                3,
            ),
        ),
        "A page of links, named one by one, and the reason duplication was refused.",
    ),
    (
        "r-0212",
        "what is cached for the life of the process and what is not",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-"
                "instead-of-importing-them.md#decision/0",
                3,
            ),
        ),
        "Two lifetimes, one cached and one deliberately not, with the prediction the "
        "item made about them.",
    ),
    (
        "r-0213",
        "what does the markdown adapter own and what does it borrow",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md#decision/0",
                3,
            ),
        ),
        "A division of labour: the token stream is borrowed, the mapping and its "
        "guarantees are owned.",
    ),
    (
        "r-0214",
        "why is the bar that a slice trips not moved when it fires",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0069-read-g2s-slices-case-by-case-and-keep-the-bar.md#decision/0", 3),),
        "A refusal argued from a decomposition rather than from deference, which is the "
        "distinction the decision insists on.",
    ),
    (
        "r-0215",
        "why can one section not be the documenting home of two commands",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0065-one-section-cannot-document-two-commands.md#decision/0", 3),),
        "A re-judgement that makes the same section carry the same grade for both "
        "commands - the consistency is the argument.",
    ),
    (
        "r-0216",
        "why was a conceded slice decomposed before anything was changed",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0058-decompose-a-conceded-slice-before-believing-it.md#decision/0", 3),),
        "An instrument shipped instead of a ranking change, because the aggregate that "
        "filed the item was not evidence.",
    ),
    (
        "r-0217",
        "why does a deferral have to name the condition that ends it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#decision/0", 3),),
        "A rule about deferrals expressed as a machine-checkable condition, and what "
        "happens to one that cannot be.",
    ),
    (
        "r-0218",
        "what does the agent-task gate actually enforce",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-"
                "instrument-not-the-verdict.md#decision/1",
                3,
            ),
            ("eval/README.md#the-agent-task-suite/0", 2),
        ),
        "The integrity of the suite rather than its verdict; the README states the same "
        "split for a reader of the sets.",
    ),
    (
        "r-0219",
        "what happened to the lead the agent-task comparison reported",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-"
                "along.md#decision/1",
                3,
            ),
            (
                "docs/adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-"
                "instrument-not-the-verdict.md#decision/0",
                2,
            ),
        ),
        "A condition that stopped passing when the instrument was repaired, and the ADR "
        "that had quantified it.",
    ),
    (
        "r-0220",
        "which corpora does the retrieval mode build and gate",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0059-make-the-plan-one-implementation-too.md#decision/0", 3),
            ("docs/adr/0055-run-the-gates-the-change-implicates.md#decision/0", 2),
        ),
        "A mode widened in one ADR after another had defined what a mode is.",
    ),
    (
        "r-0221",
        "how is a passage that landed only partly recorded",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-"
                "with-it.md#decision/0",
                3,
            ),
            (
                "docs/adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-"
                "half-the-reading.md#decision/0",
                2,
            ),
        ),
        "A number recorded by one ADR and made legible by another, and the question is "
        "about the first.",
    ),
    (
        "r-0222",
        "what does the build write when it may not modify the tree",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-"
                "write.md#decision/0",
                3,
            ),
            ("docs/adr/0009-adopt-build-publication-semantics.md#decision/", 2),
        ),
        "A derived identity in place of a minted one; the publication ADR is where "
        "minting was decided.",
    ),
    (
        "r-0223",
        "why is the superseded layout still in the repository",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0002-adopt-cross-language-source-layout.md#/0", 3),
            ("docs/adr/0001-record-architecture-decisions.md#decision/0", 2),
        ),
        "A superseded record kept rather than deleted, which is exactly what the "
        "record-keeping decision requires.",
    ),
    # --- the bug ledger, the docs site, and the module ---
    (
        "r-0224",
        "MAX_NESTING",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0029-a-long-emphasis-run-recurses-past-the-interpreter-limit.md"
                "#fix-workaround/0",
                3,
            ),
        ),
        "A constant introduced by a fix, recorded in the ledger entry rather than in an "
        "ADR of its own.",
    ),
    (
        "r-0225",
        "DeadlineExceeded",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md"
                "#expected-vs-actual/on-ci/0",
                3,
            ),
        ),
        "An exception name quoted from a CI log, which is how a reader searching for it "
        "would have seen it.",
    ),
    (
        "r-0226",
        "refuse_unreadable_sources",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md"
                "#fix/0",
                3,
            ),
            (
                "docs/adr/0095-read-the-corpus-in-the-dialect-it-is-written-in.md#decision/0",
                2,
            ),
        ),
        "A guard named in the ledger's fix and decided in the ADR beside it.",
    ),
    (
        "r-0227",
        "UNINDEXED",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md"
                "#environment/0",
                3,
            ),
            (
                "docs/adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md"
                "#decision/0",
                2,
            ),
        ),
        "A SQLite keyword that turned out to be the cause of a quadratic; the ledger "
        "names it, the ADR removes the need for it.",
    ),
    (
        "r-0228",
        "SafeLoader",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0027-a-yaml-alias-bomb-in-frontmatter-stalls-the-build.md"
                "#fix-workaround/0",
                3,
            ),
        ),
        "A loader subclass named in the fix, with the reason the profile can afford to "
        "refuse aliases outright.",
    ),
    (
        "r-0229",
        "AnyUrl",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md"
                "#root-cause/0",
                3,
            ),
        ),
        "A type union quoted from a third-party declaration, in the root cause of a "
        "platform-specific defect.",
    ),
    (
        "r-0230",
        "mycelium_explain",
        (EvalSlice.EXACT,),
        (
            (
                "docs-site/how-to/query-over-mcp.md"
                "#mycelium-explain-debug-a-result-that-looks-wrong/0",
                3,
            ),
            ("docs/adr/0011-implement-mcp-stdio-in-repo.md#decision/0", 2),
        ),
        "A tool name whose how-to says what it returns and, more usefully, what it "
        "refuses to return.",
    ),
    (
        "r-0231",
        "mycelium_neighbors",
        (EvalSlice.EXACT,),
        (
            ("docs-site/how-to/query-over-mcp.md#mycelium-neighbors-follow-the-graph/0", 3),
            ("docs/adr/0018-build-the-graph-from-authored-links.md#decision/0", 2),
        ),
        "The graph-walking tool: the how-to shows the call, the ADR is where the edges "
        "it walks come from.",
    ),
    (
        "r-0232",
        "mycelium-chats",
        (EvalSlice.EXACT,),
        (
            ("contrib/chats/README.md#install-and-enable/0", 3),
            ("docs/workflow/packaging.md#a-second-distribution-modules/0", 2),
        ),
        "A distribution name: the module's README says how to install and enable it, "
        "the packaging document says what it is beside the main package.",
    ),
    (
        "r-0233",
        "i18n-freshness",
        (EvalSlice.EXACT,),
        (
            ("docs/i18n/README.md#freshness-is-gated-not-promised/0", 3),
            ("docs/i18n/translation-status.md#/0", 2),
        ),
        "A lint check named where the rule is stated; the status table is what it reads.",
    ),
    (
        "r-0234",
        "what does installing the chats module change on its own",
        (EvalSlice.FACT,),
        (("contrib/chats/README.md#install-and-enable/0", 3),),
        "Nothing, until it is named in the configuration - which is the sentence the "
        "section is built around.",
    ),
    (
        "r-0235",
        "what does a distillation need before it will call a provider",
        (EvalSlice.RELATIONSHIP,),
        (
            ("contrib/chats/README.md#distilling-a-conversation/0", 3),
            ("docs-site/how-to/verify-and-promote.md#1-configure-a-provider/0", 2),
        ),
        "A configured provider, stated in the module's README and in the how-to that "
        "says nothing is called until the line is present.",
    ),
    (
        "r-0236",
        "what does init write into a new repository",
        (EvalSlice.FACT,),
        (
            ("docs-site/tutorial.md#2-scaffold-a-repository/0", 3),
            ("README.md#try-it/", 2),
        ),
        "A configuration file and a tree with three status folders; the README line "
        "names the command without the contents.",
    ),
    (
        "r-0237",
        "how do I widen a citation to the section around it",
        (EvalSlice.FACT,),
        (
            ("docs-site/how-to/query-over-mcp.md#mycelium-fetch-read-more-around-a-result/0", 3),
            (
                "docs/adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md"
                "#decision/0",
                2,
            ),
        ),
        "One parameter on one tool, and the ADR that decided what happens when the "
        "passage it names has moved.",
    ),
    (
        "r-0238",
        "what does garbage collection remove, and what does it never touch",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs-site/how-to/roll-back-a-snapshot.md"
                "#garbage-collection-and-rollback-interact/0",
                3,
            ),
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 2),
        ),
        "The how-to states the interaction with rollback; the ADR is where the live set "
        "it depends on was defined.",
    ),
    (
        "r-0239",
        "what does the snapshot listing show",
        (EvalSlice.FACT,),
        (("docs-site/how-to/roll-back-a-snapshot.md#list-what-you-have/0", 3),),
        "A manifest per entry, newest first, with the current one marked.",
    ),
    (
        "r-0240",
        "what happens to the synthesis lane during an ordinary ingest",
        (EvalSlice.FACT,),
        (
            (
                "docs-site/how-to/verify-and-promote.md#2-ingest-and-let-the-synthesis-lane-run/0",
                3,
            ),
        ),
        "It is not a separate command, which is the fact the section leads with.",
    ),
    (
        "r-0241",
        "what does a quarantined document cost the build",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/bugs/2026/09/BUG-0027-a-yaml-alias-bomb-in-frontmatter-stalls-the-build.md"
                "#impact/0",
                3,
            ),
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 2),
        ),
        "The ledger states the impact of a file the compiler could not refuse cleanly; "
        "the ADR is where clean refusal was designed.",
    ),
    (
        "r-0242",
        "why did two contributors get different evidence documents from the same source",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0032-an-importable-package-changes-what-html-ingestion-projects.md"
                "#expected-vs-actual/0",
                3,
            ),
            (
                "docs/adr/0134-own-the-decode-and-stop-asking-whatever-is-importable.md#decision/0",
                2,
            ),
        ),
        "A reproducibility failure caused by an installed package, and the decision "
        "that took the choice back.",
    ),
    (
        "r-0243",
        "what did the quadratic in the lexical index cost a thousand-document build",
        (EvalSlice.FACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md"
                "#impact/0",
                3,
            ),
        ),
        "A number against a budget, which is what makes the record more than a description.",
    ),
    (
        "r-0244",
        "which structure does a swallowed fence destroy",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/bugs/2026/09/"
                "BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md#impact/0",
                3,
            ),
            (
                "docs/adr/0093-escape-the-prose-that-would-open-a-block-and-report-what-that-"
                "costs.md#decision/0",
                2,
            ),
        ),
        "The ledger separates fidelity from trust; the ADR is the fix and the cost it reports.",
    ),
    (
        "r-0245",
        "which denial-of-service defects did the security review close",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/security/audit-2026-09-17-review-pass.md#findings/0", 3),
            (
                "docs/adr/0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-"
                "may-cost-to-read.md#decision/0",
                2,
            ),
        ),
        "A findings table and the ADR that fixed what it found, which is the pairing "
        "the register is written for.",
    ),
    (
        "r-0246",
        "what does a translated page have to record",
        (EvalSlice.FACT,),
        (("docs/i18n/README.md#adding-or-updating-a-translation/0", 3),),
        "A path rule, a translation rule and a commit SHA - and the last one is what "
        "the lint reads.",
    ),
    (
        "r-0247",
        "where does the reading order for a newcomer start",
        (EvalSlice.FACT,),
        (("docs/README.md#reading-order-for-newcomers/0", 3),),
        "A short ordered list in the documentation index, which is the one place it is "
        "written down.",
    ),
    (
        "r-0248",
        "what is the ten-minute budget the tutorial is written against",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs-site/tutorial.md#/0", 3),
            ("docs/specs/01_spec_mycelium.md#3-non-functional-requirements/0", 2),
        ),
        "The tutorial names the requirement it is measured against; the specification "
        "is where that requirement is stated.",
    ),
    # --- citations, modules, and the records that date a verdict ---
    (
        "r-0249",
        "KirNode.spans",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md#decision/0",
                3,
            ),
            (
                "docs/adr/0107-refuse-to-model-emphasis-and-name-the-lane-the-disagreement-is-"
                "in.md#decision/0",
                2,
            ),
        ),
        "A field added for code runs, and the later ADR that refuses to extend it for "
        "emphasis - which is where the criterion is stated.",
    ),
    (
        "r-0250",
        "parse_citation_uri",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-"
                "extensible.md#decision/0",
                3,
            ),
        ),
        "The function whose extensibility was fixed before anything was added to the "
        "grammar, which is the ADR's first decision.",
    ),
    (
        "r-0251",
        "retrieval_identity",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md"
                "#decision/0",
                3,
            ),
            ("docs/adr/0068-give-gate-g2-a-runner-by-dating-its-verdict.md#decision/0", 2),
        ),
        "A fingerprint function named where its input was narrowed, and used where a "
        "verdict is dated.",
    ),
    (
        "r-0252",
        "doc_state",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0015-adopt-content-addressed-incremental-builds.md#decision/0", 3),
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-"
                "holds-for.md#decision/0",
                2,
            ),
        ),
        "A table introduced by the incremental build and given a new column years "
        "later; the first is where it is defined.",
    ),
    (
        "r-0253",
        "config_digest",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0", 3),
            (
                "docs/adr/0045-ask-the-documents-whether-two-runs-are-comparable.md#decision/0",
                2,
            ),
        ),
        "A digest recorded by the determinism observation, and read again where two "
        "runs are compared.",
    ),
    (
        "r-0254",
        "snapshot_state",
        (EvalSlice.EXACT,),
        (("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),),
        "A row that makes a snapshot restorable rather than merely named.",
    ),
    (
        "r-0255",
        "trust_classes",
        (EvalSlice.EXACT,),
        (("docs/adr/0024-serve-what-the-configuration-admits.md#decision/0", 3),),
        "A filter field whose set-valued shape is the decision, with the SQL it becomes.",
    ),
    (
        "r-0256",
        "mycelium doctor",
        (EvalSlice.EXACT,),
        (("docs/adr/0010-adopt-cli-output-conventions.md#decision/0", 3),),
        "One of the five commands the first CLI shipped, named in the section that "
        "fixes the output conventions for all of them.",
    ),
    (
        "r-0257",
        "uv workspace",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md"
                "#decision/contrib-chats-is-a-distribution-of-its-own-in-a-uv-workspace/0",
                3,
            ),
            ("docs/workflow/packaging.md#a-second-distribution-modules/0", 2),
        ),
        "The mechanism that lets a second distribution live in this repository, named "
        "in the ADR and used by the packaging document.",
    ),
    (
        "r-0258",
        "candidate",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md"
                "#decision/0",
                3,
            ),
            (
                "docs/adr/0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md"
                "#decision/0",
                2,
            ),
        ),
        "A verification status that is also an ordinary word, so the section that "
        "defines what it means is the only usable evidence.",
    ),
    (
        "r-0259",
        "how does a citation report that its passage changed rather than moved",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-"
                "extensible.md#decision/1",
                3,
            ),
            (
                "docs/adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md"
                "#decision/0",
                2,
            ),
        ),
        "Two independent signals, and the earlier ADR is the one that decided to report "
        "rather than serve silently.",
    ),
    (
        "r-0260",
        "which arm judges the code-span leg",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md#decision/0",
                3,
            ),
            (
                "docs/adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-"
                "promotion-can-and-cannot-reorder.md#decision/0",
                2,
            ),
        ),
        "A spans field written back for one lane, and the symbol rule that decides what "
        "it can mint.",
    ),
    (
        "r-0261",
        "how does a module get a command of its own",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md"
                "#decision/the-module-mechanism-one-entry-point-group-one-protocol-one-command-"
                "surface/0",
                3,
            ),
            (
                "docs/adr/0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-"
                "one-consumer.md#decision/0",
                2,
            ),
        ),
        "One entry-point group, one protocol, one command surface - and the ADR that "
        "declares what such a module may import.",
    ),
    (
        "r-0262",
        "why does strict configuration accept a section it has never heard of",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md"
                "#decision/the-api-fix-a-module-may-own-the-section-named-after-it/0",
                3,
            ),
            ("docs/adr/0014-adopt-partial-strict-configuration.md#decision/0", 2),
        ),
        "An exception carved for modules in a loader whose whole point is refusing unknown keys.",
    ),
    (
        "r-0263",
        "when does the recorded hybrid verdict stop describing the product",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0068-give-gate-g2-a-runner-by-dating-its-verdict.md#decision/0", 3),
            (
                "docs/adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md"
                "#decision/0",
                2,
            ),
        ),
        "A verdict dated by fingerprints, and the ADR that narrowed which fingerprint matters.",
    ),
    (
        "r-0264",
        "what keeps the verification ladder and CI from drifting apart",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0068-give-gate-g2-a-runner-by-dating-its-verdict.md#decision/1", 3),
            ("docs/adr/0059-make-the-plan-one-implementation-too.md#decision/0", 2),
        ),
        "A test that reads both, widened to scripts in one ADR after another made the "
        "plan comparable at all.",
    ),
    (
        "r-0265",
        "how often is this repository's own baseline re-blessed",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-"
                "incumbents.md#decision/0",
                3,
            ),
            ("docs/adr/0051-hold-the-judgements-fixed-too.md#decision/0", 2),
        ),
        "A cadence rather than a trigger, and the ADR that decided what a baseline has "
        "to hold fixed.",
    ),
    (
        "r-0266",
        "what does a section-scoped judgement credit",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0029-let-a-judgment-name-a-section.md#decision/0", 3),
            (
                "docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md#decision/0",
                2,
            ),
        ),
        "Once, whichever chunk satisfies it - and the later ADR is what makes the "
        "notation necessary across configurations.",
    ),
    (
        "r-0267",
        "which commands did the first command line ship with",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0010-adopt-cli-output-conventions.md#decision/0", 3),
            ("README.md#try-it/", 2),
        ),
        "Five, with the ones deferred to later milestones named; the README shows what "
        "the surface grew into.",
    ),
    (
        "r-0268",
        "how does the build decide a document has not changed",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0015-adopt-content-addressed-incremental-builds.md#decision/0", 3),
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-"
                "holds-for.md#decision/0",
                2,
            ),
        ),
        "A digest, and the later ADR that stopped reading every file to compute one.",
    ),
    (
        "r-0269",
        "what does the determinism golden record about the optional stages",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0012-adopt-the-g6-determinism-gate.md#decision/0", 3),
            (
                "docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-"
                "rest.md#decision/1",
                2,
            ),
        ),
        "The gate records an observation; the entities ADR is where the fixture had to "
        "switch a stage on so the gate could see it.",
    ),
    (
        "r-0270",
        "how is a conversation chunked when it becomes knowledge",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md"
                "#decision/the-projection-a-heading-per-message-and-content-that-cannot-escape-"
                "it/0",
                3,
            ),
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 2),
        ),
        "A heading per message, chosen so the compiler's own structure-first rule "
        "produces the unit the module wants.",
    ),
    (
        "r-0271",
        "why does a module mount in main rather than at import",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-"
                "what-it-could-not-reach.md"
                "#decision/mounting-happens-in-main-and-the-failure-is-reported/0",
                3,
            ),
            ("docs/adr/0010-adopt-cli-output-conventions.md#decision/0", 2),
        ),
        "A failure that has to be reportable, which is a property of the CLI's output "
        "conventions rather than of the module.",
    ),
    (
        "r-0272",
        "what does the incumbent contribute to a run manifest",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md"
                "#decision/0",
                3,
            ),
            ("eval/README.md#gates-evaluated-here/1", 2),
        ),
        "A comparison computed inside the run, and the README line that says it is "
        "reported and never gated.",
    ),
    (
        "r-0273",
        "what makes a benchmark report evidence rather than an anecdote",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-"
                "instrument-not-the-verdict.md#decision/0",
                3,
            ),
            ("docs/benchmarks/README.md#/0", 2),
        ),
        "A manifest beside the report, and the methodology page that states the rule "
        "the ADR enforces.",
    ),
    (
        "r-0274",
        "how does a lane say it could not carry something",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#decision/0", 3),
            ("docs/adr/0038-declare-the-corpus-then-compare-it.md#decision/0", 2),
        ),
        "A declaration per document, and the gate that compares such declarations with "
        "what an engine actually produced.",
    ),
    (
        "r-0275",
        "what does the same-PR rule cover",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/documentation.md#same-pr-discipline/0", 3),
            ("AGENTS.md#10-enterprise-quality-bar/0", 2),
        ),
        "A discipline stated in the workflow document and enforced by the quality bar "
        "that forbids a follow-up.",
    ),
    # --- a last set of reasoning questions, where the ADRs argue rather than state ---
    (
        "r-0276",
        "why is a benchmark that filed a gap corrected rather than deleted",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0030-correct-the-vector-scan-cost-model.md#decision/0", 3),
            ("docs/adr/0026-pack-the-vectors-into-a-memory-mapped-matrix.md#/0", 2),
        ),
        "A correction that says the gap does not exist, and the status line of the ADR "
        "that filed it is where the correction is announced.",
    ),
    (
        "r-0277",
        "why does a refused file leave a record instead of only an error",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 3),),
        "A record the caller can find, and a re-raise - the decision is that the lane "
        "does not get to decide what happens next.",
    ),
    (
        "r-0278",
        "why is the incumbent judged on what it reaches rather than on how it ranks",
        (EvalSlice.CONCEPTUAL,),
        (("docs/adr/0081-check-the-incumbents-reach-not-its-ranking.md#decision/0", 3),),
        "One assertion swapped for another, and the argument is about what a baseline is for.",
    ),
    (
        "r-0279",
        "why is the SBOM generator kept out of the dependencies",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/workflow/packaging.md"
                "#provenance-what-a-release-ships-beside-the-archives/"
                "the-generator-is-not-a-dependency-and-that-is-not-tidiness/0",
                3,
            ),
            (
                "docs/adr/0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md#decision/1",
                2,
            ),
        ),
        "A subsection whose title is the answer, and the ADR that holds the test which "
        "keeps it true.",
    ),
    (
        "r-0280",
        "why is the index fingerprinted rather than the store it lives in",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md"
                "#decision/0",
                3,
            ),
        ),
        "A narrowing argued from what BM25 can actually see, which is the reasoning the "
        "title compresses.",
    ),
    (
        "r-0281",
        "why is the property-test budget declared in one place",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0060-declare-the-property-test-budget-and-keep-the-falsifying-"
                "example.md#decision/0",
                3,
            ),
        ),
        "One declaration and one reproducibility requirement, and the second is why the "
        "first is not merely tidiness.",
    ),
    (
        "r-0282",
        "why does a citation carry content identity as well as a position",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-"
                "extensible.md#decision/1",
                3,
            ),
        ),
        "Two signals that answer different questions - where the passage sat, and what "
        "it said - checked independently on purpose.",
    ),
    (
        "r-0283",
        "why is what a profile found left unfixed in the change that profiled it",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md"
                "#decision/1",
                3,
            ),
        ),
        "A rule this project has applied since one item filed six others rather than six patches.",
    ),
    (
        "r-0284",
        "why does the escaping ask the compiler instead of a pattern",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0099-ask-the-compiler-whether-the-prose-survived.md#decision/0", 3),
            (
                "docs/adr/0093-escape-the-prose-that-would-open-a-block-and-report-what-that-"
                "costs.md#decision/0",
                2,
            ),
        ),
        "A round trip through the build's own reader, replacing the line-shape list the "
        "earlier ADR wrote.",
    ),
    (
        "r-0285",
        "why was the leaf heading weight taken only on the third asking",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#decision/0",
                3,
            ),
            ("docs/adr/0063-split-the-leaf-heading-from-its-ancestors.md#decision/0", 2),
        ),
        "A refusal lifted because the evidence arrived, not because the argument "
        "changed - and the split that made the smaller question askable.",
    ),
    (
        "r-0286",
        "why does the project keep a bug ledger separate from the issue tracker",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/bugs/README.md#/0", 3),
            ("AGENTS.md#7-documentation-maintenance/0", 2),
        ),
        "A ledger of verified, reproducible defects - and the contract section that says "
        "an unsubstantiated report is never recorded as one.",
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
