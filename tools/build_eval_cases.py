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
    (
        "q-0021",
        "why is hybrid retrieval still off by default when it beats lexical on most of the judged "
        "sets",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "README.md#what-makes-it-different/retrieval-is-lexical-by-default-and-that-was-measured/",
                3,
            ),
        ),
        "The explanation is genuinely spread over the whole section: gate G2's two conditions, the "
        "three-to-three re-measurement, the slice bar at four to seven cases, and the conclusion "
        "that the default rests on an undischarged burden of proof rather than on a weighing. No "
        "single chunk carries the reasoning.",
    ),
    (
        "q-0022",
        "why does the lexical index carry a stem column beside the surface form instead of using a "
        "stemming tokenizer",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "README.md#what-makes-it-different/the-lexical-index-matches-inflections-and-still-prefers-your-exact-word/0",
                3,
            ),
        ),
        "This section states the reason directly: a stem column at a tenth of the weight gives "
        "reach without losing the literal match, whereas swapping in a stemming tokenizer "
        "regressed the exact and conceptual slices and failed gate G3 on both corpora.",
    ),
    (
        "q-0023",
        "why does the search drop function words from my question before searching",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "README.md#what-makes-it-different/your-question-is-answered-by-its-content-words/0",
                3,
            ),
        ),
        "The section explains the failure it fixes - 'what' and 'does' matching a heading at three "
        "times a body's weight - and why the vector leg still receives the whole question, plus "
        "what was refused (an IDF floor, removing 'mean').",
    ),
    (
        "q-0024",
        "why can't i generate a synthesizer plugin from the cookiecutter",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md#alternatives-considered/0",
                3,
            ),
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md#context/0",
                2,
            ),
        ),
        "The alternatives section records offering a fourth 'synthesizer' kind and rejects it: a "
        "package that imports cleanly, satisfies the Protocol and loads nowhere is worse than not "
        "offering the choice. Context states the underlying fact - there is no entry-point lookup "
        "for a third-party Synthesizer.",
    ),
    (
        "q-0025",
        "why is entailment reported as not measured instead of estimated offline",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "README.md#what-makes-it-different/nothing-becomes-verified-without-a-gate-and-a-person/0",
                3,
            ),
            ("docs-site/how-to/verify-and-promote.md#3-check-its-grounding/0", 2),
        ),
        "The README section carries the refusal verbatim: term overlap would produce a number in "
        "the right range and it would be a fabricated grounding score. The how-to restates the "
        "outcome - not measured rather than a number nobody computed - without the reasoning.",
    ),
    (
        "q-0026",
        "why doesn't watch mode use the filesystem events as the dirty set",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0019-adopt-watch-mode.md#context/0", 3),
            ("docs/adr/0019-adopt-watch-mode.md#decision/0", 2),
        ),
        "Context gives the four reasons an event stream is not a dirty set (dropped events, temp- "
        "file-and-rename, trees rewritten behind the watcher, the wrong directory) and names them "
        "all as false cleans. The decision states the resulting rule in one line.",
    ),
    (
        "q-0027",
        "what is wrong with an absolute file:// path in an evidence document's frontmatter",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/bugs/2026/09/BUG-0017-evidence-frontmatter-carries-an-absolute-path.md#summary/0",
                3,
            ),
        ),
        "The summary lists the three consequences in increasing seriousness: the document is not "
        "portable, two people ingesting the same source produce different digests, and the path "
        "leaks a username and local layout into a committed file.",
    ),
    (
        "q-0028",
        "why does the project benchmark itself against grep rather than another search engine",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0013-adopt-the-evaluation-harness.md#context/0", 3),
            ("docs/adr/0013-adopt-the-evaluation-harness.md#decision/0", 2),
        ),
        "Context quotes D-010's standard — the real incumbent is the agent's built-in "
        "grep/glob/read loop, and losing to it means fixing the product — which is the "
        "explanation. The decision adds why the baseline shipped in v0 and was built to be fair.",
    ),
    (
        "q-0029",
        "why can't rollback just repoint CURRENT the way the spec describes",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0016-make-snapshots-restorable.md#context/0", 3),
            ("docs/adr/0016-make-snapshots-restorable.md#alternatives-considered/0", 2),
        ),
        "Context explains that the one-line reading assumes a versioned store, while this store is "
        "mutable and always holds the newest build, so a pointer swap yields a repository whose "
        "CURRENT names one snapshot and whose data is another. Alternatives records the same "
        "option being rejected.",
    ),
    (
        "q-0030",
        "why does garbage collection need a separate retention dial for the build cache",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),
            ("docs/adr/0016-make-snapshots-restorable.md#context/0", 2),
        ),
        "The decision explains the two dials and why the second is not a convenience: without "
        "--cache-max-age the cache pins every blob it ever wrote and the sweep can never collect "
        "anything. Context sets up the problem that build_cache is a cache, not a record of what a "
        "snapshot needs.",
    ),
    (
        "q-0031",
        "why is an edge derived from an ingested document not treated as something the corpus "
        "asserts",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md#decision/0",
                3,
            ),
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md#context/0",
                2,
            ),
        ),
        "The decision states the rule and its reasoning: status follows the document's origin "
        "rather than the syntax, enforced where the assertion is made, so an ingested document's "
        "edges are extracted. Context shows the forgery that made the rule necessary.",
    ),
    (
        "q-0032",
        "why doesn't the documentation site hold the adrs and the specification itself",
        (EvalSlice.CONCEPTUAL,),
        (("docs-site/project.md#/0", 3),),
        "The page explains the split directly: the site is tutorial and how-to material, while the "
        "canonical record of why the system is built as it is stays in the repository as reviewed, "
        "versioned files rather than a second copy the site would have to keep in sync.",
    ),
    (
        "q-0033",
        "why did an accepted risk expire without anyone noticing it had",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#context/0", 3),
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#decision/0", 2),
        ),
        "Context gives the three structural reasons: a risk register is a document nobody re- "
        "reads, the roadmap item carrying the trigger was ticked and closed, and the threat model "
        "recorded the premise as a standing assumption. The decision is the remedy.",
    ),
    (
        "q-0034",
        "the exact slice fell after the corpus was re-rendered - was that a retrieval regression",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md#context/0",
                3,
            ),
            (
                "docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md#decision/0",
                2,
            ),
        ),
        "Context shows the judged chunk was byte-equivalent in tokens before and after, that a "
        "repaired rival rose past it, and that the Markdown source ranks them in the new order — "
        "so the fall is the twin agreeing with its source. The decision states the conclusion that "
        "nothing is adjusted.",
    ),
    (
        "q-0035",
        "why does this project write decision records instead of leaving the rationale in commit "
        "messages",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0001-record-architecture-decisions.md#context/0", 3),
            ("docs/adr/0001-record-architecture-decisions.md#alternatives-considered/0", 2),
        ),
        "The context gives the reasoning - decisions in commits or chat are lost, decisions in "
        "code are visible without their rationale - and the alternatives section records the "
        "explicit rejection of relying on commits/PRs, because rationale scatters and reviewers "
        "re-litigate settled questions.",
    ),
    (
        "q-0036",
        "why doesn't the agent-task benchmark put a real model in the loop",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0022-measure-the-agent-loop-without-an-agent.md#context/0", 3),
            (
                "docs/adr/0022-measure-the-agent-loop-without-an-agent.md#alternatives-considered/0",
                2,
            ),
        ),
        "The context explains the incompatibility directly: a model needs a key, a budget and a "
        "network and answers differently every run, none of which belongs in an offline three- "
        "platform CI gate. The alternatives record the rejection of both a paid API model and a "
        "local judging model.",
    ),
    (
        "q-0037",
        "why is there no similarity threshold on the vector leg",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#decision/0", 3),
            (
                "docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#alternatives-considered/0",
                2,
            ),
            ("docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#context/0", 2),
        ),
        "The decision states the refusal and its reason - a floor is a per-corpus, per-model "
        "constant that claims a detection power the probes show it lacks, and it would silently "
        "rot in a deployment with no judged unanswerable set. The alternatives reject the "
        "calibrated floor on the probe table; the context carries the background-similarity "
        "measurement behind it.",
    ),
    (
        "q-0038",
        "why was docling's layout pipeline refused when all three of its objections turned out to "
        "be satisfiable",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#decision/0", 3),
            ("docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#context/0", 2),
        ),
        "The decision is explicit that the refusal is on the merits rather than the constraints: "
        "closure, network and determinism are all satisfiable, and what fails is the case for the "
        "feature - a measured retrieval regression against the Markdown control. The context sets "
        "up the three grounds as acceptance criteria rather than obstacles.",
    ),
    (
        "q-0039",
        "why doesn't the entity stage use document titles as its vocabulary",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md#decision/0",
                3,
            ),
            (
                "docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision refuses titles on the measurement and says why it matters - a table whose "
        "most-cited members are README and Documentation is wrong in the way that reads as "
        "coverage - and gives the alternative rule, a title becomes a name only when the document "
        "carries an aliases key. The alternatives section repeats the 587-hit count behind the "
        "refusal.",
    ),
    (
        "q-0040",
        "why does the segmenter ask the model for line numbers rather than the segmented text",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md#decision/0",
                3,
            ),
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision's opening explains the mechanism: the module slices the segments out of the "
        'operator\'s own text, so "content stays verbatim" is a property of the shape - a model '
        "that hallucinated a sentence has nowhere to put it. The alternatives reject returning "
        "segmented text because verbatim content would then be something to verify by string "
        "comparison.",
    ),
    (
        "q-0041",
        "why does reading g3's verdict against an old baseline mislead a reader",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#context/what-the-drift-actually-is/0",
                3,
            ),
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#context/0",
                2,
            ),
        ),
        "This subsection is the explanation: sixteen new documents diluted the grep incumbent by "
        "13% and left ours within half a percent, so read against a stale baseline the product's "
        "own claim shows up as our numbers falling - and it names the session at 5.40 that nearly "
        "mis-attributed it to a change under test.",
    ),
    (
        "q-0042",
        "why does the chunker estimate token counts instead of using a real tokenizer",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0007-adopt-structure-first-chunking.md#alternatives-considered/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 3),
        ),
        "The alternatives section states the rejection in full — tiktoken/HuggingFace ship or "
        "download vocabulary files, breaking the offline default, and a tokenizer bump would "
        "silently move chunk boundaries. The decision section gives the positive half: "
        "estimate_tokens ships no model files and returns the same number on every platform, which "
        "byte-identical rebuilds depend on.",
    ),
    (
        "q-0043",
        "why does a file that fails ingestion get a record written instead of just a warning",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#context/0", 3),
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 2),
        ),
        "The context section is the explanation: an operator watches three warnings scroll by and "
        "an hour later cannot answer which three and why, while the answer (the stored original) "
        "already existed and nothing pointed at it. The decision section states the resulting "
        "mechanism — a quarantine record written by the lane, which re-raises — so it frames "
        "rather than explains.",
    ),
    (
        "q-0044",
        "why is the set of gates a change runs derived from the diff instead of declared",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0055-run-the-gates-the-change-implicates.md#decision/0", 3),
            ("docs/adr/0055-run-the-gates-the-change-implicates.md#alternatives-considered/0", 2),
        ),
        "The decision section gives the reasoning directly: a declaration that could narrow is a "
        "way to land unverified code (boundary B13), the classifier fails wide, and one "
        "implementation serves both CI and the contributor so the two cannot drift. The "
        "alternatives entry 'Let a human declare the mode' adds the failure mode it guards against "
        "— haste, not malice.",
    ),
    (
        "q-0045",
        "why is lexical still the default retrieval profile instead of hybrid",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0064-measure-the-gate-that-decides-the-default.md#decision/0", 3),
            (
                "docs/adr/0064-measure-the-gate-that-decides-the-default.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision section re-measures G2 across six judged sets, finds three pass and three "
        "fail, and states the conclusion explicitly: the lexical default stands on the burden of "
        "proof rather than on a measurement, because a candidate failing three of six sets has not "
        "earned the default. The alternatives section rejects flipping the default and rejects "
        "loosening G2's bar.",
    ),
    (
        "q-0046",
        "why were the four relationship cases that score badly kept instead of rewritten",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0067-grow-the-dev-set-before-asking-it-a-question.md#the-mistake-in-four-of-the-ten-kept-rather-than-corrected/0",
                3,
            ),
            (
                "docs/adr/0067-grow-the-dev-set-before-asking-it-a-question.md#alternatives-considered/0",
                2,
            ),
        ),
        "That section names the mistake (every one of the four was also made a vocabulary-gap "
        "case) and gives the reason for keeping them: the error was found by measuring, and "
        "rewriting a case after seeing it score badly is indistinguishable from fitting the set. "
        "The alternatives section restates the refusal of the rewrite and of deleting the two "
        "zero-scoring cases.",
    ),
    (
        "q-0047",
        "why must a distilled conversation cite an individual message rather than the conversation",
        (EvalSlice.CONCEPTUAL,),
        (("contrib/chats/README.md#distilling-a-conversation/0", 3),),
        "This section is the whole argument: a conversation is long, so [[conversation]] means "
        "'somewhere in these fifty turns', which neither a reader nor the entailment judge behind "
        "mycelium verify can check. It also states the enforcement — message anchors are the "
        "model's complete citable vocabulary and a coarser draft is sent back.",
    ),
    (
        "q-0048",
        "why doesn't the loss budget count degraded elements",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#alternatives-considered/0",
                3,
            ),
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 2),
        ),
        "The alternatives section argues it: counting every imperfection makes the budget useless, "
        "because a normal PDF drops running headers by policy and every DOCX with a raw block "
        "degrades an element, so the default would fire on healthy documents. The decision's "
        "bucket table states the rule without the argument.",
    ),
    (
        "q-0049",
        "why does a plugin declare the engine's version rather than its own",
        (EvalSlice.CONCEPTUAL,),
        (("docs-site/plugin-author-guide.md#pluginmeta-what-every-plugin-declares/0", 3),),
        "This section explains the reasoning: every `PluginMeta` field is recorded in the snapshot "
        "manifest and in the stage's build key because a build must be explainable from its "
        "manifest alone, so `version` is the number that explains the output — pandoc's or "
        "docling's, never the plugin's own release.",
    ),
    (
        "q-0050",
        "why does a build that may not write derive an id from the path instead of minting one",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md#alternatives-considered/0",
                3,
            ),
            (
                "docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md#decision/0",
                2,
            ),
        ),
        "Alternatives is where the choice is argued against its rivals: minting and not writing "
        "leaves the corpus folding a different manifest every run, and deriving from the content "
        "digest would change the id on every edit. The decision states the derivation and its "
        "totality.",
    ),
    (
        "q-0051",
        "why is the comparison against grep reported instead of gated",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md#decision/0",
                3,
            ),
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision states it and gives the reason in a clause: spec 04 §7.4 defers the "
        "quantified gate to 1.0, and a baseline that can fail the build is a baseline nobody dares "
        "improve. Alternatives adds the second reason — on a seven-case slice the threshold would "
        "be invented.",
    ),
    (
        "q-0052",
        "how does the build decide what counts as a definition inside a code fence",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md#decision/",
                3,
            ),
            (
                "docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md#context/0",
                2,
            ),
        ),
        "Section-scoped deliberately: the answer runs the length of the decision — the grammar's "
        "own tags query supplies the definitions, the alias table selects the grammar, "
        "qualification is an ancestor walk with three enclosing hints, and a lowercase constant is "
        "dropped. Context frames why the grammar rather than a home-grown query decides.",
    ),
    (
        "q-0053",
        "why is a callout a chunk boundary rather than an atomic block",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md#decision/0", 3),
            ("docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md#context/0", 2),
        ),
        "The decision explains the mechanism and the three consequences: blocks in a callout pack "
        "only with each other, an oversize callout still splits at its own paragraph boundaries, "
        "and a nested table stays atomic. Context supplies the reason — a callout is a container "
        "of blocks, so half of one is still readable prose.",
    ),
    (
        "q-0054",
        "does rolling back to an older snapshot change anything under knowledge/",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs-site/how-to/roll-back-a-snapshot.md#roll-back/0", 3),
            ("docs-site/how-to/roll-back-a-snapshot.md#/0", 2),
        ),
        "The explanation is here: nothing under knowledge/ is touched because a snapshot is a fact "
        "about the compiled output rather than the source tree, and a later build is still "
        "incremental from the restored state.",
    ),
    (
        "q-0055",
        "why was section aggregation not shipped when it improved both dev sets",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0031-refuse-three-rerankings.md#decision/0", 3),
            ("docs/adr/0031-refuse-three-rerankings.md#consequences/0", 2),
        ),
        "The decision says it was implemented and then failed gate G3 on the held-out release set "
        "(conceptual -51.3 %), and draws the lesson that the dev/release split caught an overfit. "
        "Consequences add what must be disentangled before it is proposed again.",
    ),
    (
        "q-0056",
        "why do tiny code fences outrank the paragraphs that actually answer a query",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0031-refuse-three-rerankings.md#context/0", 3),
            ("docs/adr/0031-refuse-three-rerankings.md#decision/0", 2),
        ),
        "The context is the diagnosis: BM25 normalises by document length while our documents are "
        "chunks of wildly different sizes, so a three-token fence holding the query term has "
        "maximal term density, and SQLite's bm25() does not expose b. The decision adds why a "
        "length threshold cannot repair it.",
    ),
    (
        "q-0057",
        "why is the journal index generated rather than kept by hand",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md#decision/0",
                3,
            ),
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md#context/0",
                2,
            ),
        ),
        "The decision explains the reasoning: every row is a formatting of the checkpoint file's "
        "own H1, so the generator renders the whole Index section and a lint holds the committed "
        "file to a fresh run. The context establishes that the row was never a second fact.",
    ),
    (
        "q-0058",
        "why does choosing between the escaped and the plain rendering need no metric",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0106-escape-what-commonmark-will-see-and-keep-the-repairs-that-worked.md#decision/0",
                3,
            ),
        ),
        "The decision argues it: every character escaped is ASCII punctuation, so CommonMark "
        "consumes the backslash and the escaped rendering can only ever read back more of the "
        "source, never less — a difference between the two read-backs is by construction text the "
        "plain one was losing.",
    ),
    (
        "q-0059",
        "why is there no field recording which section documents a symbol",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md#decision/0",
                3,
            ),
            (
                "docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision states that no field claims the documenting site because nothing here can "
        "compute it, keeps defined_in as a naming fact, and puts every naming site in doc_refs "
        "instead. The alternatives reject the second-field candidate on the same ground.",
    ),
    (
        "q-0060",
        "python tools/verify.py",
        (EvalSlice.EXACT,),
        (("CLAUDE.md#claude-code-specifics/0", 3),),
        "This is the section that documents the command: run it before drafting a PR, it derives "
        "the gates the change implicates, --mode may only widen what it derived, and the "
        "congruence lint runs inside it.",
    ),
    (
        "q-0061",
        "[retrieval] symbol_lookup",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/a-name-in-your-query-is-looked-up-and-fifty-eight-cases-took-the-default-back-off/0",
                3,
            ),
        ),
        "The section documents the setting - what the symbol-lookup leg does, why it ships off "
        "again after fifty-eight judged cases inverted the reading, and the literal line that "
        "turns it on.",
    ),
    (
        "q-0062",
        "[ingest] parsers",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/ingestion-picks-its-parser-and-you-pick-which-one/0",
                3,
            ),
        ),
        "This section documents the key: the TOML block itself, the first-one-declaring-a-format- "
        "wins rule, that an unresolvable entry is an error naming what to install rather than a "
        "fall-back, and the default value.",
    ),
    (
        "q-0063",
        "ANCHOR_GONE",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/a-citation-that-has-gone-stale-tells-you-instead-of-quietly-answering/0",
                3,
            ),
            ("README.md#how-it-compiles/0", 2),
        ),
        "The stale-citation section documents the error in context - which edits kill an anchor "
        "deliberately, and the moved/rewritten/moved_and_rewritten annotations that cover the "
        "cases an anchor survives. How it compiles states the same typed error in one clause.",
    ),
    (
        "q-0064",
        "gate G7",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/nothing-becomes-verified-without-a-gate-and-a-person/0",
                3,
            ),
            ("docs-site/how-to/verify-and-promote.md#3-check-its-grounding/0", 2),
        ),
        "The README section names G7 and documents both halves - citation coverage recomputed "
        "against the corpus as it is, and sampled entailment, fail-closed. The how-to walks "
        "through the same two components without naming the gate.",
    ),
    (
        "q-0065",
        "[entities] enabled",
        (EvalSlice.EXACT,),
        (
            (
                "README.md#what-makes-it-different/entities-are-declared-by-your-vault-not-guessed-from-your-prose/0",
                3,
            ),
        ),
        "The section documents the switch: what turning it on produces (records, other names, "
        "mentions edges, entities.jsonl), that it is off by default, and the measured yield of one "
        "entity on this repository and none on the uv docs.",
    ),
    (
        "q-0066",
        "MAX_SEARCH_K",
        (EvalSlice.EXACT,),
        (
            (
                "docs/benchmarks/2026-09-20-the-budget-we-could-not-spend.md#results/both-strategies-as-the-caller-s-budget-moves/0",
                3,
            ),
        ),
        "This is where the constant is introduced and explained: mycelium now asks for "
        "MAX_SEARCH_K = 50, the cap mycelium_search states, and lets the caller's budget truncate "
        "instead of the old literal limit=10.",
    ),
    (
        "q-0067",
        "VerbatimChar",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#context/0", 3),
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#alternatives-considered/0", 2),
        ),
        "Context states what the string is and why it matters: pandoc writes inline code as a "
        "VerbatimChar run, 224 / 74 / 31 in three DOCX files, and docling's Formatting has no "
        "monospace field to carry it out. The alternatives explain why counting those runs was "
        "rejected as a number fitted to the fixture.",
    ),
    (
        "q-0068",
        "matrix.toolchain",
        (EvalSlice.EXACT,),
        (
            ("docs/bugs/2026/08/BUG-0001-release-workflow-matrix-context.md#summary/0", 3),
            ("docs/bugs/2026/08/BUG-0001-release-workflow-matrix-context.md#root-cause/0", 2),
        ),
        "The summary quotes the exact expression and states that draft-release declares no "
        "strategy.matrix, so the context is undefined there. Root cause explains how the shared CI "
        "setup block put it in a matrix-less job.",
    ),
    (
        "q-0069",
        "mycelium eval --bless",
        (EvalSlice.EXACT,),
        (("eval/README.md#/0", 3),),
        "The command block at the head of eval/README.md is where this flag is documented: it "
        "lists `mycelium eval --bless` with what it does, freeze this run as gate G3's baseline.",
    ),
    (
        "q-0070",
        "MAX_SOURCE_BYTES",
        (EvalSlice.EXACT,),
        (("docs/security/audit-2026-09-17-review-pass.md#findings/0", 3),),
        "Finding F10's row is where the constant is introduced: an authored document had no "
        "ceiling, so MAX_SOURCE_BYTES is set to the file connector's 64 MiB and a larger document "
        "is quarantined by name.",
    ),
    (
        "q-0071",
        "mycelium eval --retriever grep",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0013-adopt-the-evaluation-harness.md#decision/0", 3),
            ("eval/README.md#/0", 2),
        ),
        "ADR-0013's decision documents the flag itself: what the grep retriever scans, how it "
        "ranks, and what it lacks that the compiler adds. eval/README.md only lists the invocation "
        "in its command block.",
    ),
    (
        "q-0072",
        "[project] exclude",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md#fix-workaround/0",
                3,
            ),
            ("eval/README.md#candidate-re-rankings-and-why-none-of-them-shipped/2", 2),
        ),
        "BUG-0007's fix section is where the key is introduced and defined — glob patterns naming "
        "Markdown in a tree that is not documentation — with the effect on G4. eval/README states "
        "which paths this repository's own setting drops.",
    ),
    (
        "q-0073",
        "--triggers-only",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#decision/0", 3),
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#references/0", 1),
        ),
        "The decision defines the flag by defining the split it runs: condition evaluation needs "
        "only the public repo record, remedy verification needs admin rights, and `--triggers- "
        "only` runs the first half alone. References merely lists the command line.",
    ),
    (
        "q-0074",
        "EXTRACT_STAGE_VERSION",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md#decision/0",
                3,
            ),
        ),
        "The decision is where the constant is bumped 3 to 4 and where the reason is stated: the "
        "per-document state now carries a source URI, and without the bump an older store would "
        "keep resolving against an empty one.",
    ),
    (
        "q-0075",
        "mycelium rollback",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),
            ("docs/adr/0016-make-snapshots-restorable.md#context/0", 2),
        ),
        "The decision documents what the command actually does — take the writer lock, revalidate "
        "every artifact, replace the corpus in one transaction, then swap CURRENT. Context quotes "
        "the spec's one-line version and explains why that reading is unsafe.",
    ),
    (
        "q-0076",
        "deadline=None",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0061-count-the-population-before-decorating-it.md#decision/0", 3),
            (
                "docs/adr/0061-count-the-population-before-decorating-it.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision states the rule the guard enforces: a property test whose example body does "
        "filesystem or store setup must carry `deadline=None` or the suite fails and names it. "
        "Alternatives says what the decorator costs on a test that does not need it.",
    ),
    (
        "q-0077",
        "G4 Abstention: false-answer rate 25.00% on 4 unanswerable case(s); limit 5%",
        (EvalSlice.EXACT,),
        (
            ("docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md#reproduction/0", 3),
            ("docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md#summary/0", 2),
        ),
        "Reproduction is where this exact gate output is printed, together with the single false "
        "answer and the fixture chunk that produced it. The summary states in a clause what the "
        "message means.",
    ),
    (
        "q-0078",
        "[chunking] pack_atomic",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md#summary/0",
                3,
            ),
            (
                "docs/bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md#root-cause/0",
                2,
            ),
        ),
        'The summary states what the setting does ("moves every chunk boundary in the corpus - '
        'that is its entire purpose") and the defect attached to it; the root cause shows the '
        "chunk config slice the key was missing from.",
    ),
    (
        "q-0079",
        '[chats] segmenter = "llm"',
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md#decision/",
                3,
            ),
            ("docs/security/threat-model.md#1-scope-trust-boundaries/0", 2),
        ),
        "Section-scoped deliberately: the Decision both introduces the setting (off by default, "
        "reusing [synthesis]'s provider, two lanes two consents) and states everything it switches "
        "on, and that spans the section rather than one chunk. Boundary B10 frames what the "
        "setting causes to leave the machine.",
    ),
    (
        "q-0080",
        "check_repo_settings.py --triggers-only",
        (EvalSlice.EXACT,),
        (
            (
                "docs/security/threat-model.md#3-findings-the-risk-register/a-deferral-names-the-condition-that-ends-it-roadmap-6-16-adr-0118/0",
                3,
            ),
            ("docs/workflow/github-setup.md#0-which-of-these-is-actually-installed/0", 2),
        ),
        "The deferral subsection prints the flag and explains the split it implements - evaluating "
        "a deferral's trigger needs only the repository object, while verifying the remedy needs "
        "admin rights and reports unverifiable. The setup section frames the tool itself as "
        "report-only.",
    ),
    (
        "q-0081",
        "pull_request_target",
        (EvalSlice.EXACT,),
        (
            ("docs/security/threat-model.md#1-scope-trust-boundaries/0", 3),
            ("docs/security/threat-model.md#2-stride-pass/0", 2),
        ),
        "Boundary B1's assumptions column is where the rule lives - \"pull_request event only "
        '(never pull_request_target)" - with the read-only token beside it. The STRIDE pass '
        "restates it as the control on workflow-modification privilege escalation.",
    ),
    (
        "q-0082",
        "pytestmark = pytest.mark.boundary",
        (EvalSlice.EXACT,),
        (
            (
                "docs/security/threat-model.md#4-controls-and-the-tests-that-hold-them-roadmap-6-3-adr-0119/0",
                3,
            ),
        ),
        "Section 4 defines the marker, says it is registered in pyproject.toml so a misspelling "
        "errors, and explains that `uv run pytest -m boundary` is the suite it derives.",
    ),
    (
        "q-0083",
        "squash_merge_commit_title=PR_TITLE",
        (EvalSlice.EXACT,),
        (
            (
                "docs/workflow/github-setup.md#1-merge-strategy-squash-only-pr-title-body-as-the-commit/0",
                3,
            ),
            ("AGENTS.md#6-git-workflow/6-4-pull-requests/0", 2),
        ),
        "The setup document carries the literal inside the gh api call that sets the merge "
        "strategy, and says why it is set that way. AGENTS 6.4 frames the consequence - the PR "
        "title/body becomes the commit on main.",
    ),
    (
        "q-0084",
        "required_linear_history",
        (EvalSlice.EXACT,),
        (("docs/workflow/github-setup.md#3-branch-protection-ruleset-for-main/0", 3),),
        "The key appears in the branch-protection JSON body in this section, which is the section "
        "that documents what protection main is meant to carry and records that it was not "
        "installed as of 2026-09-14.",
    ),
    (
        "q-0085",
        "HF_HUB_OFFLINE=1",
        (EvalSlice.EXACT,),
        (("docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#the-measurements/0", 3),),
        "The measurements section is where the flag is tested and its limit recorded: with "
        "artifacts_path the pipeline is silent under HF_HUB_OFFLINE=1, but without it a transitive "
        "dependency fetches OCR weights from modelscope.cn and the flag does not stop it.",
    ),
    (
        "q-0086",
        "good first issue",
        (EvalSlice.EXACT,),
        (("AGENTS.md#6-git-workflow/6-1-boundary-between-agent-and-human/0", 3),),
        "This is the only section that documents the label: an agent does not take an issue "
        "carrying it, with the delivery-speed reason spelled out, and the note that `help wanted` "
        "carries no such reservation.",
    ),
    (
        "q-0087",
        "[ingest] redact_secrets",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 3),
            (
                "docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#consequences/0",
                2,
            ),
        ),
        "The decision section documents exactly what the key does and does not control: the scan "
        "always runs, and the setting decides only whether redaction acts, so secret_flags reaches "
        "Document either way. The consequences section records that it was the last accepted-and- "
        "inert key, which frames the setting without defining it.",
    ),
    (
        "q-0088",
        "target_min_tokens",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#alternatives-considered/0", 2),
        ),
        "The decision section documents the knob: declared but not enforced, with the three chunk "
        "kinds that fall below it named, and the reason lifting them would mean merging across a "
        "heading boundary. The alternatives section adds the explicit rejection of merging small "
        "sections to reach it.",
    ),
    (
        "q-0089",
        "HYPOTHESIS_PROFILE=debug",
        (EvalSlice.EXACT,),
        (("CONTRIBUTING.md#development-setup/when-a-property-test-fails-intermittently/0", 3),),
        "This is the only place the literal appears and it documents it: the command line to run, "
        "and what the debug profile changes — the deadline dropped, verbose output on, and 1000 "
        "examples instead of 100.",
    ),
    (
        "q-0090",
        "--dist loadfile",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0055-run-the-gates-the-change-implicates.md#context/0", 3),
            ("docs/adr/0055-run-the-gates-the-change-implicates.md#alternatives-considered/0", 2),
        ),
        "The context section is where the measurement lives: 562 s against 721 s serial, a 22 % "
        "saving, with the explanation that the cost is concentrated in a handful of expensive "
        "files so one worker holds the critical path. The alternatives entry repeats both numbers "
        "as the refusal.",
    ),
    (
        "q-0091",
        "tools/measure_hybrid_gate.py",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0064-measure-the-gate-that-decides-the-default.md#decision/0", 3),
            ("docs/adr/0064-measure-the-gate-that-decides-the-default.md#consequences/0", 2),
        ),
        "The decision section introduces the tool and says what it does: runs gate G2 across every "
        "corpus and both sets and prints, for any case id, where each judged anchor sits in the "
        "lexical, vector and fused lists. The consequences section adds the --cases invocation and "
        "the precedent it follows.",
    ),
    (
        "q-0092",
        "gh attestation verify",
        (EvalSlice.EXACT,),
        (
            (
                "docs/workflow/packaging.md#provenance-what-a-release-ships-beside-the-archives/verifying-what-you-downloaded/0",
                3,
            ),
        ),
        "This subsection exists to document that command — the exact invocation with --repo, what "
        "a pass means (those bytes were built by this repository's release workflow), and that it "
        "works on a wheel fetched from PyPI as well as from the GitHub Release, with no account "
        "needed.",
    ),
    (
        "q-0093",
        "fts_query",
        (EvalSlice.EXACT,),
        (
            ("docs/bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md#root-cause/0", 3),
            ("docs/bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md#fix-workaround/0", 2),
            ("docs/bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md#summary/0", 2),
        ),
        "The root-cause section shows exactly what the function produced and why FTS5's implicit "
        "AND between quoted terms zeroed the query. The fix section documents its current "
        "behaviour including the match_all argument, and the summary states what it did in one "
        "clause.",
    ),
    (
        "q-0094",
        "mycelium/quarantine/v0",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 3),
            (
                "docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#consequences/0",
                2,
            ),
        ),
        "The decision section is where the record is defined: written under .mycelium/quarantine/, "
        "one file per source keyed by a digest of its URI, with first_seen fixed and last_seen "
        "moving, and never swept or digested. The consequences section adds its status as a "
        "stable-ish artifact beside custody and fidelity, but does not define it.",
    ),
    (
        "q-0095",
        "git-policy.yaml",
        (EvalSlice.EXACT,),
        (("docs/workflow/git-workflow.md#3-commit-messages-conventional-commits/0", 3),),
        "The commit-message section documents the file: the same Conventional-Commit rules live in "
        "`git-policy.yaml` as data so a check reads this project's contract, and adding a "
        "subsystem scope means editing both the prose and that file.",
    ),
    (
        "q-0096",
        "mycelium ingest --forget",
        (EvalSlice.EXACT,),
        (("docs-site/how-to/ingest-a-document.md#3-read-the-fidelity-report/0", 3),),
        "The fidelity-report step is the only passage that documents this flag: after a refusal "
        "the document sits in `.mycelium/quarantine/`, `mycelium doctor` lists what is waiting, "
        "and `mycelium ingest --forget <source>` clears the record for a source that is never "
        "coming back.",
    ),
    (
        "q-0097",
        "[ingest] max_failed_elements",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 3),
            ("docs-site/how-to/ingest-a-document.md#3-read-the-fidelity-report/0", 2),
        ),
        "ADR-0034's decision is the section that says what the key bounds: `lost / elements`, not "
        "degraded and not policy drops, with the 5 % default and the zero-element refusal. The "
        "how-to names the key while explaining the report, which frames it for an operator but "
        "does not define the ratio.",
    ),
    (
        "q-0098",
        "MIN_ENFORCEABLE_SLICE_CASES",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#decision/one-the-enforcement-contract-stated-and-implemented/0",
                3,
            ),
        ),
        "This is the only passage that introduces the constant: it is condition three of G3's "
        "enforcement contract, set to 4, and the same passage argues four is not a statistical "
        "threshold and is written in one place so a reader can disagree with it there.",
    ),
    (
        "q-0099",
        "mycelium/fidelity/v0",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 3),
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#consequences/0", 2),
        ),
        "The decision names the schema string and says what the record is — a pure function of the "
        "KIR with three buckets, stored in custody and recomputable from the KIR blob. "
        "Consequences only records that it joins `RECORD_MODELS` and is not a snapshot artifact "
        "class.",
    ),
    (
        "q-0100",
        "NO_COLOR",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0010-adopt-cli-output-conventions.md#decision/0", 3),
            ("docs/adr/0010-adopt-cli-output-conventions.md#context/0", 2),
            ("docs/adr/0010-adopt-cli-output-conventions.md#references/0", 1),
        ),
        "The decision states the rule the variable obeys: colour off when `NO_COLOR` is set to any "
        "value, off when not a TTY, off under `--json`. Context lists it as one of spec 05 §1's "
        "four conventions; References merely links no-color.org as the convention's source.",
    ),
    (
        "q-0101",
        "TAGS_QUERY",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md#context/0",
                3,
            ),
        ),
        "Context is where the literal is explained: every tree-sitter grammar ships a `tags.scm`, "
        "the Python wheels expose it as `TAGS_QUERY`, nine of ten probed wheels carry one, and C# "
        "0.23.5 does not. The decision uses tags queries but never names the attribute.",
    ),
    (
        "q-0102",
        "PYTHONIOENCODING=utf-8",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md#fix-workaround/0",
                3,
            ),
        ),
        "The Fix/workaround section is the one that documents this environment variable, as the "
        "pre-fix workaround alongside invoking `mycelium serve` instead of `python -m "
        "mycelium.mcp`.",
    ),
    (
        "q-0103",
        "ENGAGED_ACTORS_BAR",
        (EvalSlice.EXACT,),
        (("docs/workflow/adoption.md#when-the-numbers-move/0", 3),),
        "This section is where the constant is named and its governance stated: the bars live in "
        "one place in code as `ENGAGED_ACTORS_BAR` and its siblings, moving one is an owner "
        "decision recorded as a new D-0NN, and `tests/test_adoption_report.py` fails if a bar "
        "changes without the decision.",
    ),
    (
        "q-0104",
        "MAX_GREP_FILES",
        (EvalSlice.EXACT,),
        (
            (
                "docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md#results/the-band-what-the-incumbent-buys-and-what-it-pays/0",
                3,
            ),
            ("docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md#scenario/0", 2),
        ),
        "The band section is where the constant is named and given its value: five reads is "
        "MAX_GREP_FILES, the shipped choice, with the table showing what one, two, three or five "
        "reads cost and return. The scenario only says the loop opens the five files its constant "
        "has always claimed.",
    ),
    (
        "q-0105",
        "journal-index lint check",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md#decision/0",
                3,
            ),
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md#consequences/0",
                2,
            ),
        ),
        "The decision names the check, says it is consistency_lint's tenth, that it shells out to "
        "update_journal_index.py --check, and that it fails by name on a mismatch. Consequences "
        "add that it runs in every mode docs upward.",
    ),
    (
        "q-0106",
        "mycelium gc --dry-run",
        (EvalSlice.EXACT,),
        (
            (
                "docs-site/how-to/roll-back-a-snapshot.md#garbage-collection-and-rollback-interact/0",
                3,
            ),
        ),
        "This is the only section that shows the command and says what gc does: it removes blobs "
        "no retained snapshot or build-cache row needs and never collects the snapshot CURRENT "
        "points at.",
    ),
    (
        "q-0107",
        "deadlineexceeded: test took 501.68ms",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md#expected-vs-actual/on-ci/0",
                3,
            ),
            (
                "docs/bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md#environment/0",
                2,
            ),
        ),
        "The 'On CI' subsection carries that exact failure text with the surrounding pytest "
        "summary and the reproduce_failure blob. Environment gives the same figure in context — "
        "the ubuntu-24.04 / CPython 3.12 cell against an 8-10 ms typical.",
    ),
    (
        "q-0108",
        "@settings(deadline=None)",
        (EvalSlice.EXACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md#fix-workaround/0",
                3,
            ),
            (
                "docs/bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md#root-cause/0",
                2,
            ),
        ),
        "Fix/workaround is where the setting is applied and justified, with the comment saying "
        "what the deadline was actually measuring. Root cause names the same setting as the "
        "precedent tests/test_build_incremental.py set at roadmap 3.1.",
    ),
    (
        "q-0109",
        'compgen -G "pyproject.toml"',
        (EvalSlice.EXACT,),
        (
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#summary/0", 3),
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#root-cause/0", 2),
        ),
        "The summary is where that probe string is quoted and explained: it is the single test the "
        "bootstrap job gated every toolchain job on, and why a build manifest is not enough. Root "
        "cause frames where the probe came from.",
    ),
    (
        "q-0110",
        "_MAPPING_KEY",
        (EvalSlice.EXACT,),
        (
            ("docs/bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md#root-cause/0", 3),
            ("docs/bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md#fix-workaround/0", 2),
        ),
        "Root cause gives the pattern in full and explains why the discriminator must run before "
        "YAML at all. Fix states what the pattern now accepts, so it frames the same identifier "
        "without defining it.",
    ),
    (
        "q-0111",
        "[retrieval] graph_expansion",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md#consequences/0",
                3,
            ),
            (
                "docs/adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md#context/0",
                2,
            ),
        ),
        "The Consequences bullet is where the key is documented as a shipped setting: it is real, "
        "defaults to false, the validator that used to refuse the value is gone, and an operator "
        "who turns it on gets a documented 0.0-4.1 % overall cost. Context only states that the "
        "key previously existed as a setting that refused to be set.",
    ),
    (
        "q-0112",
        "[synthesis] min_citation_coverage",
        (EvalSlice.EXACT,),
        (
            ("docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md#decision/0", 3),
            (
                "README.md#what-makes-it-different/an-llm-may-write-but-only-what-a-machine-can-check/0",
                2,
            ),
        ),
        "The Decision states the citation contract's third rule - claim-bearing blocks are "
        "covered, measured against [synthesis] min_citation_coverage, which defaults to 1.0 - "
        "which is the key's definition. The README section shows it in a configuration sample with "
        "a one-line gloss.",
    ),
    (
        "q-0113",
        "[modules] enabled",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md#decision/the-module-mechanism-one-entry-point-group-one-protocol-one-command-surface/0",
                3,
            ),
            (
                "docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md#context/0",
                2,
            ),
        ),
        "That subsection is the key's documentation: a name in [modules] enabled that no installed "
        "distribution provides is a ConfigError, duplicates are refused, the check reads installed "
        "metadata without importing, and enabling is per repository while installing is per "
        "machine. Context only shows the key in the sentence that no module existed yet.",
    ),
    (
        "q-0114",
        "MYCELIUM_API_VERSION",
        (EvalSlice.EXACT,),
        (
            (
                "docs-site/plugin-author-guide.md#the-naming-and-compatibility-discipline-this-all-rests-on/0",
                3,
            ),
            (
                "docs/compatibility.md#what-stable-means/until-v1-0-0-from-the-milestone-6-line-onward/0",
                2,
            ),
            ("docs/compatibility.md#the-five-stable-contracts/0", 1),
        ),
        "The guide says what the constant is for - the number telling a plugin author whether a "
        "Protocol they satisfy today still describes what a build expects, declared as an "
        "api_min/api_max range. The compatibility rule adds that an incompatible change bumps it "
        "first; the contracts table only names it as contract 5's version token.",
    ),
    (
        "q-0115",
        "SELECT EXISTS(SELECT 1 FROM vectors WHERE model_id = ?)",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#decision/the-probe/0",
                3,
            ),
            (
                "docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#decision/0",
                2,
            ),
        ),
        "The Probe subsection is the statement's documentation: it stops at the first matching "
        "row, costs 20 VM instructions on a hit against 120 033 for the GROUP BY it replaces, and "
        "still walks the table on a miss because nothing indexes model_id alone. The Decision "
        "names has_vectors as the method that issues it.",
    ),
    (
        "q-0116",
        "_VOCABULARY_CACHE_SIZE",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0146-memoise-the-stemmer-bounded-against-a-measured-vocabulary.md#decision/0",
                3,
            ),
        ),
        "The Decision is the only place the constant is defined and justified: 131 072 entries, "
        "roughly 11x the largest of the three corpora this project builds, ~9 MB measured with "
        "tracemalloc, and fixed rather than configurable because a knob with no eval evidence is "
        "refused.",
    ),
    (
        "q-0117",
        "--oracle",
        (EvalSlice.EXACT,),
        (("eval/README.md#candidate-re-rankings-and-why-none-of-them-shipped/0", 3),),
        "This section both lists the flag among measure_ranking.py's invocations and explains it - "
        "it scores, per case, the best any strategy achieves, so a ceiling near the incumbent "
        "closes the family. That is the flag's documenting home.",
    ),
    (
        "q-0118",
        "--rescan",
        (EvalSlice.EXACT,),
        (
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md#decision/0",
                3,
            ),
            ("README.md#try-it/0", 2),
        ),
        "The Decision documents the flag as one of the three guards on the stat memo: it reads and "
        "digests every document once at the old floor with every cache still applying, and is "
        "explicitly distinguished from --clean, which distrusts everything. The README mentions it "
        "in one clause as the remedy when you doubt the memo.",
    ),
    (
        "q-0119",
        "--with-markdown",
        (EvalSlice.EXACT,),
        (("docs/adr/0020-adopt-the-jsonl-interchange-bundle.md#decision/0", 3),),
        "The Decision gives the flag its rule - it copies the sources that were compiled or "
        "nothing, re-checking each file's digest against the content_digest its record carries and "
        "failing the export on any drift - and says why copying the working tree was refused.",
    ),
    (
        "q-0120",
        "which python version does mycelium-os require",
        (EvalSlice.FACT,),
        (
            ("README.md#build-test-run/0", 3),
            ("CLAUDE.md#tl-dr-do-not-skip-read-agents-md-anyway/0", 2),
        ),
        "Build, test, run gives the supported platforms as Linux / Windows / macOS on CPython "
        "3.12+. The CLAUDE.md TL;DR states the 3.12+ baseline in a clause about the persona rather "
        "than documenting it.",
    ),
    (
        "q-0121",
        "how do i skip the synthesis lane for a single ingest call",
        (EvalSlice.FACT,),
        (("docs-site/how-to/verify-and-promote.md#2-ingest-and-let-the-synthesis-lane-run/0", 3),),
        "This step says the synthesis lane is not a separate command - ingest runs it whenever "
        "[synthesis] names a provider - and that --no-synthesize skips it for one call without "
        "editing the config.",
    ),
    (
        "q-0122",
        "how much of a long query does the search actually read",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/your-question-is-answered-by-its-content-words/0",
                3,
            ),
        ),
        "The section states the bound: the first 64 terms are read and --explain says how many "
        "were not, with the 146-seconds-to-94-milliseconds measurement and the reason 64 was "
        "chosen.",
    ),
    (
        "q-0123",
        "how many edge types does the knowledge graph have",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/the-graph-is-typed-and-every-type-is-derived-from-something-you-wrote/0",
                3,
            ),
        ),
        "D-014 fixes a vocabulary of eight edge types and no graph database; the section names all "
        "eight and the fact each is derived from.",
    ),
    (
        "q-0124",
        "what recall does the int8 first pass with an exact rescore achieve against the exact top "
        "50",
        (EvalSlice.FACT,),
        (("docs/adr/0028-keep-the-vector-scan-exact.md#context/0", 3),),
        "The recall table measured on 2 090 real bge-small vectors gives int8 first pass with "
        "exact rescore of 100 a recall@50 of 1.000 at 25 % of the bytes on disk.",
    ),
    (
        "q-0125",
        "what grounding score ends up written into a synthesized document",
        (EvalSlice.FACT,),
        (
            (
                "README.md#what-makes-it-different/nothing-becomes-verified-without-a-gate-and-a-person/0",
                3,
            ),
        ),
        "The section states the score is min(coverage, entailment), and why: an average would let "
        "perfect citations hide a failed entailment.",
    ),
    (
        "q-0126",
        "how many agent tasks does mycelium find the evidence for on uv-docs at the shipped budget",
        (EvalSlice.FACT,),
        (
            (
                "docs/benchmarks/2026-09-20-the-budget-we-could-not-spend.md#results/both-strategies-as-the-caller-s-budget-moves/0",
                3,
            ),
            (
                "docs/benchmarks/2026-09-20-the-budget-we-could-not-spend.md#what-moved-and-what-did-not/0",
                2,
            ),
        ),
        "The uv-docs band table gives 19/22 at the shipped 4 000-token budget against grep's "
        "13/22. The following section repeats the 18 to 19 move as the summary of what changed.",
    ),
    (
        "q-0127",
        "what does evidence found mean in the agent task band measurement",
        (EvalSlice.FACT,),
        (("docs/benchmarks/2026-09-20-the-budget-we-could-not-spend.md#limits/0", 3),),
        "The limits section defines it: the required passages were in what the agent received. "
        "Whether a model would have used them is explicitly not asked by this instrument.",
    ),
    (
        "q-0128",
        "what did re-reading case u-0017 turn up",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md#consequences/0",
                3,
            ),
        ),
        "The consequences record the defect: u-0017's carry landed on a twin chunk headed 'uv pip "
        "compile' that does not contain 'uv venv' at all, the correct chunk scored 0.4731 and "
        "would have been dropped below the 0.50 floor, and the whole apparent projection cost is "
        "the mis-carry.",
    ),
    (
        "q-0129",
        "who opens and merges pull requests in this repository",
        (EvalSlice.FACT,),
        (
            ("CLAUDE.md#tl-dr-do-not-skip-read-agents-md-anyway/0", 3),
            ("CLAUDE.md#claude-code-specifics/0", 2),
        ),
        "The TL;DR states it outright: agents commit, push and draft PRs on feature branches, and "
        "the user opens and merges PRs manually. The Claude Code section repeats the operational "
        "half - never run gh pr merge, the user clicks Create and Merge.",
    ),
    (
        "q-0130",
        "which python version do i need to build and test mycelium-os locally",
        (EvalSlice.FACT,),
        (
            ("docs/development/local-build.md#prerequisites/0", 3),
            ("docs/development/local-build.md#/0", 2),
        ),
        "Prerequisites states Python 3.12+ as the toolchain requirement; the intro states that CI "
        "runs the same commands on CPython 3.12+ across three platforms.",
    ),
    (
        "q-0131",
        "how much line coverage does new behaviour need before i open a pr",
        (EvalSlice.FACT,),
        (("docs/development/local-build.md#before-you-open-a-pr/0", 3),),
        "The pre-PR checklist states the number: pytest -q passes and new or changed behavior is "
        "covered at 80% line or better.",
    ),
    (
        "q-0132",
        "how do i report someone breaking the code of conduct",
        (EvalSlice.FACT,),
        (("CODE_OF_CONDUCT.md#enforcement/0", 3),),
        "The Enforcement section names the two channels — GitHub private vulnerability reporting "
        "on the repository, or contacting danielPoloWork directly — and promises reporter privacy.",
    ),
    (
        "q-0133",
        "what happens on a first offence of inappropriate language in this community",
        (EvalSlice.FACT,),
        (
            ("CODE_OF_CONDUCT.md#enforcement-guidelines/1-correction/0", 3),
            ("CODE_OF_CONDUCT.md#enforcement-guidelines/0", 2),
        ),
        "Level 1 Correction is the rung for inappropriate or unprofessional language and states "
        "the consequence: a private written warning, possibly with a requested public apology. The "
        "parent section frames the ladder.",
    ),
    (
        "q-0134",
        "how many judged cases are in the release set for this repository's own documentation",
        (EvalSlice.FACT,),
        (("eval/README.md#the-case-sets/0", 3),),
        "The case-set table gives the count per set: release.jsonl holds 286 cases over this "
        "repository's documentation, against 20 in the dev set.",
    ),
    (
        "q-0135",
        "what query latency does gate g5 allow",
        (EvalSlice.FACT,),
        (("eval/README.md#gates-evaluated-here/1", 3),),
        "The gate table's G5 row states the budget — query p95 at 150 ms or below — and adds that "
        "it is defined at the 10^5-chunk reference profile, so passing on a smaller corpus is a "
        "floor.",
    ),
    (
        "q-0136",
        "how much faster is a rollback than a clean rebuild",
        (EvalSlice.FACT,),
        (("docs/adr/0016-make-snapshots-restorable.md#consequences/0", 3),),
        "The first consequence gives both measurements: 4.0 s rollback against a 15.2 s clean "
        "rebuild on 200 documents, 3.8x, plus the committed benchmark's 229 ms against 500 ms at "
        "30 documents.",
    ),
    (
        "q-0137",
        "how many property tests in the suite actually do filesystem or store setup inside an "
        "example",
        (EvalSlice.FACT,),
        (("docs/adr/0061-count-the-population-before-decorating-it.md#decision/0", 3),),
        "The decision reports the structural walk of all 24 @given functions: the population is "
        "two, both already exempt, and the other twenty-two touch no filesystem at all.",
    ),
    (
        "q-0138",
        "how many of the ingested corpus's link targets came out with a windows backslash",
        (EvalSlice.FACT,),
        (
            (
                "docs/bugs/2026/09/BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md#reproduction/0",
                3,
            ),
            (
                "docs/bugs/2026/09/BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md#summary/0",
                2,
            ),
        ),
        "Reproduction states the measurement: 159 link targets across all 81 sources on Windows, "
        "none on Linux. The summary repeats the figure as the number of the corpus's 507 links the "
        "CI check would have failed on.",
    ),
    (
        "q-0139",
        "what does a packed-matrix vector scan really cost in a process that maps the file once",
        (EvalSlice.FACT,),
        (
            ("docs/bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md#summary/0", 3),
            ("docs/bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md#root-cause/0", 2),
        ),
        "The summary gives the two numbers and which is real: about 71 ms per call when the 154 MB "
        "file is re-mapped in one process, about 31 ms for a process that maps it once, which is "
        "what every code path does. Root cause explains why the median hid it.",
    ),
    (
        "q-0140",
        "what is the p95 latency budget for a mycelium_search call",
        (EvalSlice.FACT,),
        (("docs/specs/01_spec_mycelium.md#3-non-functional-requirements/0", 3),),
        "NFR-2 states the number and its conditions: end-to-end p95 <= 150 ms on the local "
        "profile, 10^5 chunks, warm store.",
    ),
    (
        "q-0141",
        "which python version does this project require",
        (EvalSlice.FACT,),
        (
            ("AGENTS.md#9-coding-conventions/0", 3),
            ("AGENTS.md#1-persona/0", 2),
        ),
        "The coding conventions state the language standard outright - Python 3.12+ (CPython), "
        "Rust only for profiled hotspots post-1.0. The persona section repeats the floor as the "
        "default to write to.",
    ),
    (
        "q-0142",
        "who publishes a release to the package index",
        (EvalSlice.FACT,),
        (
            ("AGENTS.md#11-versioning-release/0", 3),
            ("AGENTS.md#6-git-workflow/6-1-boundary-between-agent-and-human/0", 2),
        ),
        "Section 11 answers it directly: publishing is the maintainer's always, publish.yml fires "
        "on workflow_dispatch and nothing else, and agents never run it. The 6.1 table frames the "
        'same split by row ("Publish the release - Human").',
    ),
    (
        "q-0143",
        "how many lines can a paste have before the llm segmenter refuses to send it",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md#consequences/0",
                3,
            ),
        ),
        "The consequences name the ceiling and its justification: 2000 lines, chosen not against a "
        "known pathology but as the statement that two thousand pasted lines is a document rather "
        "than a conversation.",
    ),
    (
        "q-0144",
        "what line coverage does new code have to reach",
        (EvalSlice.FACT,),
        (
            ("AGENTS.md#10-enterprise-quality-bar/0", 3),
            ("docs/specs/01_spec_mycelium.md#6-verification-test-strategy/0", 2),
        ),
        "The quality-bar table gives the gate: new code >= 80% line. The spec's verification "
        "strategy states the same threshold as layer (5) of the test strategy.",
    ),
    (
        "q-0145",
        "how many unresolved-link warnings did building this repository produce before the "
        "resolver was fixed",
        (EvalSlice.FACT,),
        (
            (
                "docs/bugs/2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md#fix-workaround/0",
                3,
            ),
            (
                "docs/bugs/2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md#summary/0",
                2,
            ),
        ),
        "The fix section gives both numbers - the build went from ~150 warnings to 3, and says why "
        "the remaining 3 are real. The summary states the ~150 figure and what was being warned "
        "about.",
    ),
    (
        "q-0146",
        "how many agent tasks ship and what shapes do they come in",
        (EvalSlice.FACT,),
        (("docs/adr/0022-measure-the-agent-loop-without-an-agent.md#decision/0", 3),),
        "The decision names the three shapes (answer, locate, relate) and the counts: twenty-two "
        "tasks, twelve/six/four.",
    ),
    (
        "q-0147",
        "has a trademark search been run on the mycelium os name",
        (EvalSlice.FACT,),
        (("docs/assets/brand/README.md#trademark/0", 3),),
        "The trademark section answers it in one sentence - no search has been run and no mark is "
        "claimed - and names roadmap 6.5 as the item that gates the public branding push on it.",
    ),
    (
        "q-0148",
        "how often is the ours/release baseline re-blessed",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#decision/0",
                3,
            ),
        ),
        "The decision sets the cadence: once per release, as its own PR, in the release "
        "procedure's pre-flight, written into docs/workflow/release.md so it has an owner and a "
        "moment.",
    ),
    (
        "q-0149",
        "what is the minimum pydantic version the record contracts require",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#decision/0", 3),
            ("docs/adr/0004-adopt-pydantic-v2-record-contracts.md#context/0", 2),
        ),
        "The decision pins pydantic >= 2.11 and says what forces that exact floor - "
        "serialize_by_alias, needed for the `from` field on edges. The context frames the floor as "
        "one of the things this ADR settles that the spec left open.",
    ),
    (
        "q-0150",
        "how many terms of a query does the search tool actually read",
        (EvalSlice.FACT,),
        (("docs-site/how-to/query-over-mcp.md#mycelium-search-find-passages/0", 3),),
        "This section states the bound outright — a question is read to its first 64 terms — and "
        "gives the consequences: a pasted document yields an answer to its opening rather than an "
        "error, and explain reports how many terms went unread.",
    ),
    (
        "q-0151",
        "how many mcp tools does mycelium serve",
        (EvalSlice.FACT,),
        (("docs-site/how-to/query-over-mcp.md#/0", 3),),
        "The page's opening states it directly: exactly four read-only MCP tools over stdio "
        "transport, and the page is organised as one section per tool.",
    ),
    (
        "q-0152",
        "what token range is a chunk supposed to fall in",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0007-adopt-structure-first-chunking.md#context/0", 3),
            ("docs/adr/0007-adopt-structure-first-chunking.md#decision/0", 2),
        ),
        "The context section quotes the policy spec 03 §5 fixes: heading-bounded, 200-800 tokens, "
        "atomic tables and code blocks, no mid-sentence splits, no overlap. The decision section "
        "frames how the ceiling is applied (prose accumulates until the next block would breach "
        "target_max_tokens) without restating the range.",
    ),
    (
        "q-0153",
        "how many secret-detection rules does the ingestion scanner have",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#decision/0", 3),
            (
                "docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision section states the count and the character of the set: eleven rules, each "
        "anchored on something that does not occur in prose, and no entropy heuristic. The "
        "alternatives section explains what those eleven therefore miss — a bare password or home- "
        "grown token goes through unflagged.",
    ),
    (
        "q-0154",
        "how many edge types does the controlled vocabulary allow",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md#context/0",
                3,
            ),
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md#consequences/0",
                2,
            ),
        ),
        "The context section opens with the fact: D-014 fixes a controlled vocabulary of eight "
        "edge types, extensible only by RFC, and says which six had derivations. The consequences "
        "section names all eight and records that every one now has a derivation.",
    ),
    (
        "q-0155",
        "how long did a cold build of 1 000 documents take when it was measured",
        (EvalSlice.FACT,),
        (
            (
                "docs/benchmarks/2026-09-17-reference-profile.md#results/against-the-three-budgets/0",
                3,
            ),
            ("docs/benchmarks/2026-09-17-reference-profile.md#results/the-curve/0", 2),
        ),
        "The budgets table is the verdict row: 193.5 s against a < 60 s budget, 3.2x over at "
        "exactly the stated size. The curve table carries the same figure beside the 250-document "
        "point, which is where the per-document degradation is visible.",
    ),
    (
        "q-0156",
        "what does a warm read of a 4 kb markdown file cost on the benchmark machine",
        (EvalSlice.FACT,),
        (
            ("docs/benchmarks/README.md#methodology/two-rules-added-at-roadmap-6-4-adr-0120/0", 3),
            ("docs/benchmarks/2026-09-17-reference-profile.md#what-these-numbers-do-not-say/0", 2),
        ),
        "The benchmarks README states the constant (~1.3 ms, about a hundred times an unencumbered "
        "SSD, because a real-time malware scanner sits in the open path) and makes recording it a "
        "standing rule with the reason. The report's limits section repeats it as a caveat on that "
        "particular run.",
    ),
    (
        "q-0157",
        "who opens and merges the release pull request",
        (EvalSlice.FACT,),
        (
            ("docs/workflow/release.md#boundary/0", 3),
            ("docs/workflow/release.md#cutting-a-release-the-steps/", 2),
        ),
        "The boundary table is the authoritative split and says 'Open / merge the release PR — "
        "Human', alongside what the agent does. The step list is section-scoped because the same "
        "answer is stated across steps 6 and 7 and the surrounding human checkpoints, not in one "
        "place.",
    ),
    (
        "q-0158",
        "which releases still get security fixes before 1.0",
        (EvalSlice.FACT,),
        (("SECURITY.md#supported-versions/0", 3),),
        "This section answers it with both the rule and the table: until v1.0.0 only the latest "
        "released minor line receives security fixes, older 0.x does not, and after 1.0.0 the "
        "window is defined in maintenance.md.",
    ),
    (
        "q-0159",
        "what branch name prefixes are allowed for a change",
        (EvalSlice.FACT,),
        (("CONTRIBUTING.md#making-a-change/0", 3),),
        "Step 1 lists the closed set explicitly — feat, fix, refactor, perf, docs, test, build, "
        "chore, ci — with the <type>/<short-kebab-description> shape and a pointer to the git "
        "workflow doc.",
    ),
    (
        "q-0160",
        "which commands does the cli ship in its first skeleton",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0010-adopt-cli-output-conventions.md#decision/0", 3),
            ("docs/adr/0010-adopt-cli-output-conventions.md#context/0", 2),
        ),
        "The decision names all five — `init`, `build`, `search`, `show`, `doctor` — and says when "
        "the rest arrive. Context frames the count by noting the spec's table lists sixteen "
        "commands and this item is a skeleton of five.",
    ),
    (
        "q-0161",
        "which ingest configuration key is still accepted but has no effect",
        (EvalSlice.FACT,),
        (("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#consequences/0", 3),),
        "Consequences answers it exactly: `parsers` and `connectors` landed at 4.1 and "
        "`max_failed_elements` here, so only `redact_secrets` (4.6) is still accepted-and-inert, "
        "and `doctor` still names it.",
    ),
    (
        "q-0162",
        "how many tracked files does building this repository's own corpus change",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md#context/0",
                3,
            ),
        ),
        "Context states the number and why it exists: compiling this repository's corpus to "
        "measure anything modifies 105 tracked files, because a pinning build inserts a minted "
        "`mycelium_id` into every unpinned document's frontmatter.",
    ),
    (
        "q-0163",
        "how many judged cases does the uv dev set hold",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#context/0", 3),
            ("docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#decision/0", 2),
        ),
        "Context gives the figure and its provenance: roadmap 4.39 grew `uv/dev` from twelve "
        "judged cases to twenty-two, committed before anything was scored on them. The decision's "
        "table repeats the count in its header while arguing the weight change.",
    ),
    (
        "q-0164",
        "what does the adoption report exit with when github cannot be reached",
        (EvalSlice.FACT,),
        (("docs/workflow/adoption.md#taking-the-count/0", 3),),
        "This section states the exit-code contract for `tools/adoption_report.py`: 0 when nothing "
        "in scope is failing, 1 when a condition is not met, 2 when GitHub could not be asked.",
    ),
    (
        "q-0165",
        "how long can a branch name be",
        (EvalSlice.FACT,),
        (("docs/workflow/git-workflow.md#2-branch-naming/0", 3),),
        "The branch-naming section gives the limit and the rest of the shape: `<type>/<short- "
        "kebab-description>`, lowercase kebab, at most 40 characters, describing the what rather "
        "than the issue number.",
    ),
    (
        "q-0166",
        "who is a pull request assigned to when an agent drafts it",
        (EvalSlice.FACT,),
        (("docs/workflow/git-workflow.md#4-pull-requests/4-2-metadata-every-pr/0", 3),),
        "The metadata section answers it directly: the assignee is the repository owner "
        "`danielPoloWork`, never `@me`, precisely because `@me` resolves to whichever actor runs "
        "`gh` and that is wrong when an agent drafts the PR.",
    ),
    (
        "q-0167",
        "when is a deprecated symbol actually removed",
        (EvalSlice.FACT,),
        (("docs/workflow/maintenance.md#deprecation-policy/0", 3),),
        "The deprecation policy gives the three steps and the timing: deprecate in a MINOR, keep "
        "it for at least the rest of the current MAJOR line, remove in the next MAJOR with a "
        "breaking-change ADR and a migration note.",
    ),
    (
        "q-0168",
        "how many callouts are there in the judged corpora",
        (EvalSlice.FACT,),
        (
            ("docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md#context/0", 3),
            (
                "docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md#consequences/0",
                2,
            ),
        ),
        "Context gives the count that shaped the change: zero callout nodes across this "
        "repository's 144 documents, uv's 81 and the ingested twin's 81, the only one being in the "
        "G6 fixture. Consequences restates it as the reason no baseline moves.",
    ),
    (
        "q-0169",
        "what does mycelium init create in a new repository",
        (EvalSlice.FACT,),
        (("docs-site/tutorial.md#2-scaffold-a-repository/0", 3),),
        "That step states exactly what init writes: mycelium.toml, a knowledge/ tree with "
        "verified/, candidate/ and evidence/, and a .mycelium/ cache directory with its own "
        ".gitignore entry.",
    ),
    (
        "q-0170",
        "how long should it take to get from installing mycelium to a cited answer",
        (EvalSlice.FACT,),
        (
            ("docs-site/tutorial.md#/0", 3),
            ("docs/rfc/0001-mycelium-os-v1.md#decision/scalability-budgets-scalability/0", 2),
        ),
        "The tutorial's opening states the budget as a number and its source: spec NFR-4, install "
        "to a cited answer in under ten minutes. The RFC's budget table restates it as the "
        "adoption axis and Phase-0 exit gate.",
    ),
    (
        "q-0171",
        "which tools does an agent get when it connects to the mycelium mcp server",
        (EvalSlice.FACT,),
        (
            ("docs-site/tutorial.md#5-serve-it-to-an-agent-over-mcp/0", 3),
            ("docs/rfc/0001-mycelium-os-v1.md#decision/api-contract-api-systemdesign/0", 3),
        ),
        "The tutorial step names all four — mycelium_search, mycelium_fetch, mycelium_neighbors, "
        "mycelium_explain — after mycelium serve. The RFC's API contract specifies the same four "
        "with their inputs and outputs.",
    ),
    (
        "q-0172",
        "what is the p95 latency budget for a mycelium_search query",
        (EvalSlice.FACT,),
        (("docs/rfc/0001-mycelium-os-v1.md#decision/scalability-budgets-scalability/0", 3),),
        "The scalability table states it with its stage split and its reference profile: end-to- "
        "end p95 <= 150 ms, candidates 60 / fusion 20 / graph 30 / stitch+pack 40, at 10^5 chunks "
        "on a laptop with a warm store.",
    ),
    (
        "q-0173",
        "what does a document lose when its frontmatter is read as prose instead of yaml",
        (EvalSlice.FACT,),
        (
            ("docs/bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md#impact/0", 3),
            ("docs/bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md#summary/0", 2),
        ),
        "Impact answers precisely: the content survives, the authored title, tags, collection and "
        "trust are lost, a chunk of YAML lands in the search index, and identity is unaffected in "
        "practice. The summary states the same loss more briefly.",
    ),
    (
        "q-0174",
        "from which version does the compatibility promise actually bind",
        (EvalSlice.FACT,),
        (("docs/compatibility.md#/0", 3),),
        "The opening paragraph gives both dates: it is published with roadmap 6.1 in the Milestone "
        "6 line that ships as v0.6.0, and it binds at the v1.0.0 tag, with the pre-1.0 rule "
        "applying until then.",
    ),
    (
        "q-0175",
        "how many journal checkpoint rows were missing from the index",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md#context/0",
                3,
            ),
        ),
        "The context gives the counts that produce the answer: the README listed 69 checkpoints "
        "while docs/journal/2026/** held 104, from twenty-four sessions across three days that "
        "closed without adding their row.",
    ),
    (
        "q-0176",
        "how many words besides the name may a heading carry and still define that name",
        (EvalSlice.FACT,),
        (
            (
                "docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md#decision/0",
                3,
            ),
        ),
        "The decision states the rule and the bound: the name itself or the name plus one framing "
        "word, and it explains that one extra word is the largest bound at which no corpus yields "
        "a non-name (three admits 'e.g', five admits 'x86_64').",
    ),
    (
        "q-0177",
        "what does the ci bootstrap guard require before it turns the toolchain jobs on",
        (EvalSlice.FACT,),
        (
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#fix-workaround/0", 3),
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#root-cause/0", 2),
        ),
        "The fix states the two-signal answer: the build manifest and a committed uv.lock, so "
        "pyproject.toml alone keeps the jobs skipped. Root cause frames why one signal was the "
        "wrong question to ask.",
    ),
    (
        "q-0178",
        "how is this different from retrieval-time rag",
        (EvalSlice.RELATIONSHIP,),
        (("README.md#what-makes-it-different/0", 3),),
        "This is the comparison table itself - when work happens, rebuild cost, reproducibility, "
        "provenance, publication and quality, each stated for retrieval-time RAG against Mycelium "
        "OS - plus the caveat that the quality row is measured against grep and could say so if it "
        "lost.",
    ),
    (
        "q-0179",
        "which graph edges count as authored and which as extracted",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "README.md#what-makes-it-different/the-graph-is-typed-and-every-type-is-derived-from-something-you-wrote/0",
                3,
            ),
            (
                "README.md#what-makes-it-different/an-ingested-document-joins-the-graph-and-is-never-mistaken-for-something-someone-wrote/0",
                2,
            ),
        ),
        "The typed-graph section splits the eight types into the five authored ones and the three "
        "extracted ones and states that extracted never becomes authored silently. The ingested- "
        "document section applies the same distinction to an acquired file, where every edge is "
        "extracted.",
    ),
    (
        "q-0180",
        "why does the docs site link out to the adrs instead of embedding them, when restatements "
        "were excluded from the corpus",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md#decision/0",
                3,
            ),
            (
                "docs/adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md#alternatives-considered/0",
                2,
            ),
        ),
        "The decision's first paragraph draws the contrast explicitly: ADR-0072 excluded "
        "docs/changelog and docs/releases because they restate the ADRs, while the site's own "
        "pages are not restatements and the parts that would be are links. The alternatives reject "
        "embedding the ADRs for the same reason.",
    ),
    (
        "q-0181",
        "how does the bar hybrid retrieval has to clear compare with the one graph expansion had "
        "to clear",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "README.md#what-makes-it-different/retrieval-is-lexical-by-default-and-that-was-measured/0",
                3,
            ),
            (
                "README.md#what-makes-it-different/the-graph-can-widen-a-search-and-it-did-not-earn-the-right-to/0",
                3,
            ),
        ),
        "Each half of the comparison is stated in one of these two passages: gate G2 asks hybrid "
        "for at least +5 % nDCG@10 with no slice worse than -2 %, while graph expansion's gate is "
        "+3 % on the relationship slice with no overall regression. Both legs ship off, for "
        "different reasons.",
    ),
    (
        "q-0182",
        "what does promote do that verify does not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs-site/how-to/verify-and-promote.md#4-promote-it/0", 3),
            (
                "README.md#what-makes-it-different/nothing-becomes-verified-without-a-gate-and-a-person/0",
                2,
            ),
        ),
        "The how-to step states the relation directly: promotion is a Git-visible move, a human "
        "action distinct from verify's measurement and stricter than it, refusing below thresholds "
        "including an unmeasured entailment unless forced. The README section adds that promote "
        "re-measures rather than trusting the number in the file.",
    ),
    (
        "q-0183",
        "is a watch session the same as running mycelium build in a loop",
        (EvalSlice.RELATIONSHIP,),
        (("docs/adr/0019-adopt-watch-mode.md#consequences/0", 3),),
        "The consequences answer it: a manual build in an unchanged repository publishes a new "
        "snapshot and a watch session does not, and that is the only deliberate difference - what "
        "each build produces is identical.",
    ),
    (
        "q-0184",
        "when is a lost element an opaque node and when is it a declared parser policy",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#decision/0", 3),
            ("docs/adr/0100-declare-what-a-lane-cannot-carry.md#consequences/0", 2),
        ),
        "The decision draws the line with the contrasting function one file away: a DOCX note body "
        "vanishes so it becomes an opaque lost node, while monospace naming loses no content so it "
        "is a per-document warning. The consequences show the element inventory confirming it - "
        "only the two policy lines moved, no kinds count or dispositions bucket.",
    ),
    (
        "q-0185",
        "is the query planner a chain of responsibility",
        (EvalSlice.RELATIONSHIP,),
        (("docs/patterns/README.md#rejected/0", 3),),
        "The rejected table has the Chain of Responsibility row for exactly this: nothing is "
        "passed along and nothing stops the chain, every rule is evaluated and the generators a "
        "plan asks for are the union of what matched, so first-match-wins would describe the "
        "opposite behaviour.",
    ),
    (
        "q-0186",
        "did the split passage on the grade-1 anchor cost case u-1019 anything",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md#context/0",
                3,
            ),
            (
                "docs/adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md#consequences/0",
                2,
            ),
        ),
        "Context prints both anchors' ranks on both corpora: the grade-1 anchor is first and "
        "scores 1.0000 alone on each side, and the whole of the -0.314 belongs to the grade-3 "
        "anchor falling from rank 2 to 10. The consequences restate it as the closed answer to "
        "roadmap 5.39.",
    ),
    (
        "q-0187",
        "what changed about findings f2 and f3 once the repository became public",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/security/audit-2026-08-29-bootstrap.md#findings/0", 3),
            ("docs/security/audit-2026-08-29-bootstrap.md#/0", 2),
        ),
        "The findings table carries both re-assessments: F2's deferral expired and holds at medium "
        "because the protection APIs now answer, and F3 moves low to medium because its own "
        "'exposure is nil' premise depended on the repository being private. The header note "
        "explains why the register was re-opened and names the first external fork.",
    ),
    (
        "q-0188",
        "how does gate g2's committed verdict differ from a g3 baseline file",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "eval/README.md#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/what-gate-g2-s-verdict-records/0",
                3,
            ),
            (
                "eval/README.md#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/what-a-baseline-records/0",
                2,
            ),
        ),
        "The G2 passage is written as the comparison: it tabulates g2-verdict.json's fields and "
        "then names the two that deliberately do not match their namesakes in "
        "baselines/<set>.json, with the reason. The baseline passage supplies the other side of "
        "that comparison.",
    ),
    (
        "q-0189",
        "what does the ingested twin corpus measure that the other two corpora cannot",
        (EvalSlice.RELATIONSHIP,),
        (
            ("eval/README.md#what-projection-costs/0", 3),
            ("eval/README.md#the-case-sets/0", 2),
        ),
        "The projection-cost section states the question the third corpus exists to answer — "
        "whether a document projected from a binary source is as retrievable as the Markdown a "
        "human would have written — and prints the per-format comparison. The case-set section "
        "says how that corpus was made.",
    ),
    (
        "q-0190",
        "do the docx html and pdf lanes lose the same things when a document is projected",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "eval/README.md#what-projection-costs/the-three-lanes-do-not-lose-the-same-things/0",
                3,
            ),
            ("eval/README.md#what-projection-costs/0", 2),
        ),
        "The subsection contrasts the three lanes with counts — 1215 code spans carried by HTML, "
        "zero by DOCX and PDF — and explains that pandoc's VerbatimChar run and docling's DOCX "
        "backend destroy the distinction before this project's adapter sees it. The parent section "
        "frames the per-format comparison.",
    ),
    (
        "q-0191",
        "is a twin case that collapses several judged units the same problem as one with a bigger "
        "target chunk",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md#decision/1",
                3,
            ),
            (
                "docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md#decision/0",
                2,
            ),
        ),
        "This passage separates the two mechanisms explicitly: u-1003 is the mild size effect, one "
        "unit on both sides at 535 tokens against 64, while u-1006 and u-1001 are collapse, where "
        "a case that asked for several units becomes one that asks for one. The earlier chunk "
        "tabulates the three cases.",
    ),
    (
        "q-0192",
        "which design pattern is the snapshot's stored state, and where is it catalogued",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0016-make-snapshots-restorable.md#decision/0", 3),
            ("docs/patterns/design-patterns.md#3-behavioral/0", 2),
            ("docs/adr/0016-make-snapshots-restorable.md#consequences/0", 1),
        ),
        "The decision names the pattern where it is applied: the doc_state blob is a Memento, the "
        "compiler's state captured so it can be handed back without consumers depending on its "
        "shape. The taxonomy gives Memento's canonical category and intent; the consequences "
        "bullet only records the catalogue entry.",
    ),
    (
        "q-0193",
        "adr-0079 said the docling separator bug changed no output - what changed",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/bugs/2026/09/BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md#summary/0",
                3,
            ),
            (
                "docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md#consequences/0",
                2,
            ),
        ),
        "The bug's summary is the passage that relates the two: it quotes the 5.7 note, then "
        "explains that 5.18 makes the projector write link targets into the committed evidence "
        "tree, so the check would have failed on 159 of 507 links. ADR-0079 is where the harmless- "
        "today note was made.",
    ),
    (
        "q-0194",
        "how is the grep baseline in the eval harness different from the agent-task suite",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0013-adopt-the-evaluation-harness.md#alternatives-considered/0", 3),
            ("eval/README.md#the-agent-task-suite/0", 2),
        ),
        "The first alternative weighs exactly this pair: deferring the grep baseline to the agent- "
        "task suite was rejected because the suite measures a different, harder thing — task "
        "success and tokens — while the retrieval comparison needs a denominator now. eval/README "
        "describes what the task suite actually runs.",
    ),
    (
        "q-0195",
        "how does the number of cases in a slice decide whether g3 enforces it",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "eval/README.md#candidate-re-rankings-and-why-none-of-them-shipped/which-slices-gate-g3-and-which-it-only-reports/0",
                3,
            ),
            (
                "eval/README.md#did-the-retriever-get-worse-or-did-the-corpus-get-bigger/what-a-2-slice-bar-means-over-four-cases/0",
                2,
            ),
        ),
        "The first passage states the three conditions a slice must meet to be enforced, including "
        "at least four judged cases, and says the four is a line on a continuum. The second is the "
        "arithmetic behind it: at these sizes the -2% bar is a per-case veto.",
    ),
    (
        "q-0196",
        "how does the security review pass connect the threat model's boundaries to the code",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/security/audit-2026-09-17-review-pass.md#/0", 3),
            ("docs/security/audit-2026-09-17-review-pass.md#what-the-walk-found-sound/0", 2),
        ),
        "The header states the method: a boundary walk over B1 to B15 with each control traced to "
        "code and to a test, then subprocess-bounded measurement of what a hostile input can make "
        "the system spend. The 'walk found sound' section is that tracing's per-boundary result.",
    ),
    (
        "q-0197",
        "what did re-measuring the unbounded query finding change about the numbers the review "
        "reported",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/security/audit-2026-09-17-review-pass.md#findings/f11-closed-at-roadmap-6-17-and-the-probe-understated-it/0",
                3,
            ),
            ("docs/security/audit-2026-09-17-review-pass.md#findings/0", 2),
        ),
        "The note revises its own F11 row on both counts: 146 s rather than 57 s once the whole "
        "search path including the symbol leg is run, and cost that is linear rather than "
        "superlinear except at the extreme. The findings table holds the original row it corrects.",
    ),
    (
        "q-0198",
        "do entities and the mentions over them carry the same status",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md#decision/0",
                3,
            ),
            ("docs/security/threat-model.md#2-stride-pass/0", 2),
        ),
        "The decision draws the distinction: every entity is status authored because a human wrote "
        "the declaration, while the mentions over them are extracted. The threat model's B11 "
        "entity row states the same pairing as the control that keeps an ingested source's "
        "vocabulary out of the authored graph.",
    ),
    (
        "q-0199",
        "what do the chats module's two llm lanes each send to the provider",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md#consequences/0",
                3,
            ),
            ("docs/security/threat-model.md#1-scope-trust-boundaries/0", 2),
        ),
        "The consequences contrast them explicitly: distillation sends the projection, which doc "
        "08 6 has already redacted, while segmentation sends a paste the module redacts on the way "
        "out and refuses when redaction cannot preserve its line count. B10's row records the same "
        "two widenings with their separate consents.",
    ),
    (
        "q-0200",
        "what did the lexical precondition do to gate g4, and what did it leave for gate g2",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#consequences/0",
                3,
            ),
            ("docs/adr/0025-make-lexical-evidence-the-vector-legs-precondition.md#decision/0", 2),
        ),
        "The consequences state both sides: G4 for hybrid goes 100% to 0% with every answerable "
        "metric byte-identical, while G2 is unchanged - +5.8% nDCG overall but conceptual -5.7% "
        "and injection -22.6% - so the item removes one of hybrid's two disqualifiers, not both. "
        "The decision explains the abstention-parity property that produces the G4 result.",
    ),
    (
        "q-0201",
        "how does the repository's merge setting decide the way a pr title and body must be "
        "written",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/workflow/github-setup.md#1-merge-strategy-squash-only-pr-title-body-as-the-commit/0",
                3,
            ),
            ("AGENTS.md#6-git-workflow/6-4-pull-requests/0", 2),
        ),
        "The setup section configures squash-only with PR_TITLE/PR_BODY as the commit and then "
        "draws the link itself: this is why the PR title/body is written as it should read in git "
        "log forever. AGENTS 6.4 states the writing rule the setting forces.",
    ),
    (
        "q-0202",
        "how did the ml-parsed pdf arm score against the markdown control",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#the-measurements/0", 3),
            ("docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md#decision/0", 2),
        ),
        "The measurements table puts all three arms side by side (markdown 0.398 nDCG@10, text "
        "layer 0.396, ML layout 0.327) and explains why the Markdown control is the comparison "
        "that means something, given ADR-0039's target-size confound. The decision restates the "
        "outcome as the ground for refusing.",
    ),
    (
        "q-0203",
        "what does the release cadence change about adr-0053's rule that a baseline must never be "
        "stale",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#decision/0",
                3,
            ),
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#context/0",
                2,
            ),
        ),
        'The decision addresses ADR-0053 by name: its "what it must never be is stale" is kept '
        "and given the meaning it lacked - at each release, against that release's corpus. The "
        "context frames the question the item was filed to settle.",
    ),
    (
        "q-0204",
        "how does trust boundary b13 relate to verify.py's --mode flag",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/security/threat-model.md#1-scope-trust-boundaries/0", 3),
            ("AGENTS.md#6-git-workflow/6-4-pull-requests/0", 2),
        ),
        "B13 is the boundary whose untrusted input is the diff and any request to widen or narrow "
        "the derived mode; its control is that --mode may only widen and one implementation serves "
        "both the local loop and CI. AGENTS 6.4 states the same rule from the contributor's side "
        "and names B13 as what it controls.",
    ),
    (
        "q-0205",
        "how does a contrib module fit the normative source layout",
        (EvalSlice.RELATIONSHIP,),
        (("AGENTS.md#5-source-tree-cross-language-layout/0", 3),),
        "Section 5 resolves exactly this: a module under contrib/<id>/src/<package>/ is a second "
        "distribution rather than a second shape, so the normative layout still holds - same src- "
        "layout, same component subdivision, one namespace per package - and a test enforces that "
        "it reaches only the published plugin API.",
    ),
    (
        "q-0206",
        "what does the agent-task success rate not tell you about the model",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0022-measure-the-agent-loop-without-an-agent.md#consequences/0", 3),
            ("docs/adr/0022-measure-the-agent-loop-without-an-agent.md#decision/0", 2),
        ),
        "The consequences state the ceiling plainly: the numbers say what reached the model, never "
        "what it did with it, and a retrieval handing over the right passage in a confusing order "
        "can score 100% and still lose the task. The decision frames the same limit as success "
        "being necessary and not sufficient.",
    ),
    (
        "q-0207",
        "how is amending an adr different from superseding one",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/workflow/documentation.md#amending-an-adr-roadmap-5-21/0", 3),
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md#decision/0",
                2,
            ),
        ),
        "This section sets the two side by side: a wholly replaced record is superseded and "
        "declares supersedes: in frontmatter, while a partly changed record is amended and the "
        "decision is still in force, with the amendment's placement rules and why no amends edge "
        "type exists. ADR-0082's decision section states the same boundary from the other side.",
    ),
    (
        "q-0208",
        "why did growing the uv dev set disarm gate g3 on the ingested corpus",
        (EvalSlice.RELATIONSHIP,),
        (("docs/adr/0067-grow-the-dev-set-before-asking-it-a-question.md#consequences/0", 3),),
        "The consequences section traces the coupling: the third corpus assigns docx/html/pdf in "
        "rotation over the judged documents, nine of the ten new cases named previously unjudged "
        "distractors, so six documents took a real format, their chunks changed, the ingested "
        "corpus digest moved and G3 switched from enforcing to reporting — plus the bless that "
        "rides with it.",
    ),
    (
        "q-0209",
        "how much of a search call is retrieval and how much is everything else",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/benchmarks/2026-09-17-reference-profile.md#results/where-the-end-to-end-cost-goes/0",
                3,
            ),
            (
                "docs/benchmarks/2026-09-17-reference-profile.md#results/cross-check-the-real-corpora/0",
                2,
            ),
        ),
        "The cost-breakdown section is the answer: a per-call table showing load_config at 230 ms "
        "(219 of it an uncached entry_points scan) against 7-1 089 ms for the search itself. The "
        "real-corpora cross-check shows the same split as measured numbers — 7 ms retrieval inside "
        "a 278 ms call on a 568-chunk corpus.",
    ),
    (
        "q-0210",
        "how does mycelium compare with a grep loop on the agent-task suite",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/benchmarks/2026-09-17-reference-profile.md#results/the-agent-task-comparison/0",
                3,
            ),
            (
                "docs/benchmarks/2026-09-17-reference-profile.md#interpretation/the-agent-task-verdict-gate-quantified/0",
                2,
            ),
        ),
        "The comparison section carries both arms of the table and, importantly, the warning not "
        "to quote the ratio, with the reason: one 80 996-token file is 93.3 % of the incumbent's "
        "cost, and the amendment recording the repaired incumbent at 14/22. The verdict-gate "
        "subsection frames the same comparison as the rule it will become.",
    ),
    (
        "q-0211",
        "how is a contrib module's version related to the core's release version",
        (EvalSlice.RELATIONSHIP,),
        (("docs/workflow/packaging.md#a-second-distribution-modules/0", 3),),
        "This section sets mycelium-os and mycelium-chats side by side and answers directly: a "
        "module's version is not in lockstep and the consistency lint does not check it, because "
        "spec 05 §4.3 lets a contrib module lag one minor and the binding statement is the plugin "
        "API generation declared in PluginMeta.",
    ),
    (
        "q-0212",
        "why must the release bless not ride along with a retrieval change",
        (EvalSlice.RELATIONSHIP,),
        (("docs/workflow/release.md#cutting-a-release-the-steps/0", 3),),
        "Step 0 states both the requirement and the reason for the separation: the re-bless is its "
        "own PR, and a bless beside a change under TUNING_PATHS is the one conjunction that can "
        "fit the retriever to the set. It also explains why the baseline goes stale between "
        "releases at all.",
    ),
    (
        "q-0213",
        "how does writing a plugin differ from changing the core as a contribution",
        (EvalSlice.RELATIONSHIP,),
        (("CONTRIBUTING.md#the-ladder/0", 3),),
        "Rungs 4 and 5 are stated against each other in one section: a plugin needs no permission "
        "and no core change, is its own distribution resolved through an entry point and held to a "
        "declared API generation, whereas changing the core needs an issue first, usually a "
        "roadmap item and an ADR, and an RFC for any of the five stable contracts.",
    ),
    (
        "q-0214",
        "how do the jsonl record and the markdown projection of a conversation relate",
        (EvalSlice.RELATIONSHIP,),
        (
            ("contrib/chats/README.md#two-files-per-conversation/0", 3),
            ("contrib/chats/README.md#/0", 2),
        ),
        "This section shows both paths and says what each is for: the JSONL is canonical, append- "
        "friendly and lossless, the Markdown is the derived view the compiler indexes with one "
        "heading and one callout per message so a citation resolves to a conversation and a "
        "message. The intro frames the projection into knowledge/ as what makes them searchable.",
    ),
    (
        "q-0215",
        "what is the difference between an authored and an extracted edge",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs-site/how-to/query-over-mcp.md#mycelium-neighbors-follow-the-graph/0", 3),
            (
                "docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md#decision/0",
                2,
            ),
        ),
        "The neighbors section defines the pair as the agent sees it — authored means a human "
        "wrote the link, extracted means a grammar found it, and the two are never conflated so a "
        "human's claim can be weighted differently. ADR-0082's decision applies the distinction to "
        "a concrete case: an ingested document's supersedes: is extracted because its text is "
        "untrusted.",
    ),
    (
        "q-0216",
        "what does mycelium ingest do that mycelium build does not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 3),
            (
                "docs-site/how-to/ingest-a-document.md#5-build-and-the-evidence-joins-the-corpus/0",
                2,
            ),
        ),
        "The decision draws the division explicitly: ingest acquires, stores, guards, parses, "
        "stores, accounts and projects, and build then compiles the projected file like any other "
        "authored document, which is how an ingested PDF gets chunks and citations without "
        "anything but the compiler writing an index. The how-to shows the same seam from the "
        "operator's side.",
    ),
    (
        "q-0217",
        "what is the difference between a degraded and a lost element",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs-site/how-to/ingest-a-document.md#3-read-the-fidelity-report/0", 3),
            ("docs/adr/0034-project-the-evidence-and-count-what-it-lost.md#decision/0", 2),
        ),
        "The how-to contrasts the two in the reader's terms — degraded lost structure but kept its "
        "content, lost is the ratio the budget bounds — which is the comparison asked for. The "
        "ADR's bucket table states the same distinction as `opaque` node variants.",
    ),
    (
        "q-0218",
        "why can i register a parser but not a synthesizer",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs-site/plugin-author-guide.md#the-three-contracts-and-the-one-that-is-not-open-yet/0",
                3,
            ),
        ),
        "This section is the comparison: the table gives Connector, Parser and Module with their "
        "entry-point groups and pinning keys, then states that `Synthesizer` is a real frozen "
        "Protocol with no registry path — `build_synthesizer` resolves one built-in and "
        "`[synthesis] plugin` refuses any other name.",
    ),
    (
        "q-0219",
        "how is a module different from the other plugin contracts",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs-site/plugin-author-guide.md#writing-a-module/0", 3),
            (
                "docs-site/plugin-author-guide.md#the-three-contracts-and-the-one-that-is-not-open-yet/0",
                2,
            ),
        ),
        "The module section states the distinction directly: a module is a packaged activatable "
        "capability, the only one of the four typed contracts the core never calls inside a "
        "pipeline, requiring a CLI sub-app and an entry in `[modules] enabled`. The contracts "
        "table frames it beside Connector and Parser in one row.",
    ),
    (
        "q-0220",
        "why did the mcp server corrupt non-ascii output when the cli did not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md#root-cause/0", 3),
            (
                "docs/bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md#expected-vs-actual/0",
                2,
            ),
        ),
        "Root cause holds the comparison: `mycelium serve` goes through `mycelium.cli.main`, which "
        "calls `configure_streams()`, while `python -m mycelium.mcp` is a second entry point that "
        "never did. Expected-vs-actual states the rule the CLI already followed, quoting ADR-0010.",
    ),
    (
        "q-0221",
        "why is gate g3 never enforced on our own release set but enforced on the uv ones",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#context/0", 3),
            ("docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#consequences/0", 2),
        ),
        "Context explains the asymmetry: this repository's documentation is its own corpus, so "
        "every PR changes it and G3 correctly takes its not-comparable branch (BUG-0014), leaving "
        "the uv rows as the ones actually enforced. Consequences repeats the consequence when "
        "counting which rows matter.",
    ),
    (
        "q-0222",
        "why couldn't the uv judged sets grow when the others did",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#decision/two-five-new-judged-cases-where-a-set-could-grow/0",
                3,
            ),
            ("docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md#alternatives-considered/0", 2),
        ),
        "This subsection names the coupling: the third corpus assigns DOCX/HTML/PDF by rotation "
        "over the sorted judged paths, so newly judging three documents re-rolls formats whose "
        "renderings are committed provenance that cannot be re-derived, and the frozen-set guard "
        "forbids a derived set moving with its source. Alternatives restates it when rejecting the "
        "option.",
    ),
    (
        "q-0223",
        "how did the dev set and the held-out sets disagree about the leaf heading weight",
        (EvalSlice.RELATIONSHIP,),
        (("docs/adr/0070-take-the-leaf-heading-weight-on-the-third-asking.md#decision/0", 3),),
        "The decision is where the two are put side by side: uv/dev has an interior optimum at 3.0 "
        "with 4.0 below the baseline, while the held-out uv/release prefers 4.0 (0.616 against "
        "0.611) — and the ADR reads that disagreement as the dev/release split working as "
        "intended.",
    ),
    (
        "q-0224",
        "how does the product's score against grep today compare with when the gap was filed",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md#the-measurement/0",
                3,
            ),
            (
                "docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md#context/0",
                2,
            ),
        ),
        "The measurement section is the then-versus-now table (uv/release nDCG@10 grep 0.409 vs "
        "0.249 at filing, 0.548 vs 0.519 today) and it carries the honesty note that the "
        "incumbent's own score moved because the corpus was re-judged. Context supplies the "
        "originally filed number.",
    ),
    (
        "q-0225",
        "what does adr-0043 change about adr-0029's rule against section-scoped judgments",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md#why-that-case-is-section-scoped-anyway/0",
                3,
            ),
            (
                "docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md#references/0",
                1,
            ),
        ),
        "That section quotes ADR-0029's objection, concedes u-1016 is exactly the shape it warns "
        "about, and overrides it for one case with three reasons. The references entry only names "
        "ADR-0029 as the caution overridden.",
    ),
    (
        "q-0226",
        "how much independent evidence do the uv release set and its ingested twin give about a "
        "conceded slice",
        (EvalSlice.RELATIONSHIP,),
        (("docs/adr/0058-decompose-a-conceded-slice-before-believing-it.md#context/", 3),),
        "Section-scoped deliberately: the argument runs across the whole context — the two sets "
        "share the same twenty-five case ids and queries, so 'both concede fact' is one "
        "observation counted twice, and the per-case table shows them conceding on different "
        "cases.",
    ),
    (
        "q-0227",
        "why does the symbol leg promote only cli symbols instead of every language",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md#alternatives-considered/0",
                3,
            ),
        ),
        "The alternatives weigh the two readings against each other: promoting every language is "
        "rejected on the release sets at -1.1 % and -2.7 % overall, both through u-1001, whose "
        "PyPI sites are an installation-methods listing.",
    ),
    (
        "q-0228",
        "what did the oracle symbol table say about add-only versus promotion before any source "
        "was built",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md#context/0",
                3,
            ),
        ),
        "The context reports the oracle run directly: under add-only the slice moves +0.0 % on "
        "five sets, because every judged chunk is already in the lexical leg's fifty candidates, "
        "while the same table under promotion lifts it +22.8 % to +115.9 %.",
    ),
    (
        "q-0229",
        "which kinds of question does grep answer better than mycelium in the agent-task suite",
        (EvalSlice.RELATIONSHIP,),
        (("docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md#interpretation/0", 3),),
        "Point 4 names the two tasks the incumbent wins and the mechanism: both are why-questions "
        "answered by an ADR's Decision section, and grep's file-level granularity reads the whole "
        "ADR while our ten hits spread across three and seven documents.",
    ),
    (
        "q-0230",
        "what happens to the gap against grep when the caller's token budget goes up",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md#results/the-band-as-the-caller-s-budget-moves/0",
                3,
            ),
        ),
        "This subsection sweeps the budget from 1 000 to 16 000 tokens and reads the comparison "
        "off it: the evidence lead never exceeds two tasks, and our cost stops growing at about 3 "
        "100 tokens because the harness asks for ten hits whatever the budget.",
    ),
    (
        "q-0231",
        "why do records refuse unknown fields while citation uris ignore unknown query keys",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/compatibility.md#what-stable-means/reader-rules-and-why-there-are-two-of-them/0",
                3,
            ),
        ),
        "This section exists to contrast the two rules: a record is closed because an undeclared "
        "field is producer drift caught at the boundary, while a URI travels between versions in "
        "transcripts nothing can update, so its parser steps over keys it does not know.",
    ),
    (
        "q-0232",
        "which defect was the bootstrap guard hiding while its probe was too coarse",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#root-cause/0", 3),
            ("docs/bugs/2026/08/BUG-0003-bootstrap-probe-too-coarse.md#references/0", 1),
        ),
        "Root cause states the relation: the failures the early activation exposed are BUG-0002, a "
        "real defect the guard was inadvertently hiding and that would otherwise have surfaced at "
        "roadmap 1.2. The references entry only names it.",
    ),
    (
        "q-0233",
        "does installing a generated plugin change what a repository compiles",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "tools/cookiecutter-mycelium-plugin/{{cookiecutter.project_slug}}/README.md#install/0",
                3,
            ),
        ),
        "The install section separates registration from activation: installing registers the "
        "plugin id in its entry-point group, and nothing runs until mycelium.toml names it under "
        "[modules] or [ingest].",
    ),
    (
        "q-0234",
        "why does the vectors probe get a cache when adr-0128 refused one on the same grounds",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#decision/why-the-cache-is-not-a-pessimisation-which-had-to-be-checked/0",
                3,
            ),
            (
                "docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#decision/the-cache-and-the-question-the-filing-item-asked-of-it/0",
                2,
            ),
        ),
        "That subsection applies ADR-0128's own test - a cache must buy more than the read it "
        "saves - and concedes the cache is six microseconds slower on the hit path, keeping it "
        "because the hybrid path reads the same generation one line later and because six "
        "microseconds against 10.6 ms on the miss path needs no second opinion.",
    ),
    (
        "q-0235",
        "how does the exists probe serve the degraded path adr-0025 defined",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#context/0", 3),
            (
                "docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md#decision/the-probe/0",
                2,
            ),
        ),
        "Context states the dependency directly: the yes/no before the vector leg is what "
        "ADR-0025's degradation path rests on, so a snapshot built before the embedder existed "
        "stays searchable and says it is degraded. The Probe adds that the absent-model miss is "
        "precisely that configuration, and is the reason the answer is cached.",
    ),
    (
        "q-0236",
        "what does min_whole claim that min_coverage cannot see",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0111-a-floor-can-reject-what-a-preference-must-not-choose.md#decision/0", 3),
            (
                "docs/adr/0111-a-floor-can-reject-what-a-preference-must-not-choose.md#context/why-coverage-chose-it/0",
                2,
            ),
        ),
        "The Decision sets the two floors against each other: MIN_WHOLE rejects an anchor whose "
        "winning chunk holds under two fifths of the passage's word occurrences, which is the same "
        "claim MIN_COVERAGE makes but on the one metric that can see a split passage. The context "
        "subsection shows why coverage is over-satisfied on a shattered passage.",
    ),
    (
        "q-0237",
        "what does the stat memo give up that adr-0015's read guaranteed",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md#context/what-the-read-was-protecting/0",
                3,
            ),
            (
                "docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md#decision/0",
                2,
            ),
        ),
        "That subsection takes ADR-0015's three reasons for reading every file - renames preserve "
        "mtimes, pinned-mtime trees, and a false clean - and weighs each against a size-and-mtime "
        "memo, leaving one residual case: a same-size edit that also restores the old mtime. The "
        "Decision then states the three guards that bound it.",
    ),
    (
        "q-0238",
        "why does cas_put drop the atomic write that publishing still relies on",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/adr/0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md#context/what-the-ceremony-was-protecting/0",
                3,
            ),
            (
                "docs/adr/0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md#decision/0",
                2,
            ),
        ),
        "That subsection separates the two cases: atomic_write_bytes exists so a name never "
        "appears before its content is durable, which a snapshot and the CURRENT pointer need, "
        "while a content-addressed blob's name is its digest. The Decision states the result - "
        "cas_put writes straight to the final name and the re-hash on read is the integrity story.",
    ),
    (
        "q-0239",
        "why must the symbol table be resolved before the edges over it",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/adr/0147-decode-and-hash-the-symbol-stage-once.md#context/0", 3),
            ("docs/adr/0147-decode-and-hash-the-symbol-stage-once.md#decision/decode-once/0", 2),
        ),
        "Context gives the ordering rule and its reason: a use becomes an edge only when the "
        "corpus defines what it names (ADR-0074), so resolve_symbols must run before symbol_edges, "
        "which is why the two are always called back to back and why each was decoding the same "
        "doc_state JSON. The Decode once subsection describes threading one decoded record through "
        "both passes.",
    ),
    (
        "q-0240",
        "why does an accepted risk have to say what would end it",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#decision/0", 3),
            ("docs/adr/0118-make-a-deferral-name-the-condition-that-ends-it.md#context/0", 2),
        ),
        "Decision states the rule itself - a deferral names its ending condition in a form a "
        "machine can evaluate - which is the answer. Context supplies the reason it was needed: "
        "two accepted risks had rested on a premise that went void and nothing was watching.",
    ),
    (
        "q-0241",
        "why is the release baseline re-blessed once per release instead of whenever it drifts",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#decision/0",
                3,
            ),
            (
                "docs/adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md#context/what-the-drift-actually-is/0",
                2,
            ),
        ),
        "Decision gives the rule and the reason for its cadence: dating the bless to a release is "
        "what keeps the reported delta meaningful. The drift subsection carries the measurement "
        "underneath it - what moved, and that most of the movement is the incumbent's.",
    ),
    (
        "q-0242",
        "why is the number of cases a slice needs derived rather than chosen",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md#decision/0",
                3,
            ),
            (
                "docs/adr/0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md#what-the-measurement-said/0",
                2,
            ),
        ),
        "Decision states the principle: a slice is enforced when no single case can trip it on "
        "its own, so the count follows from the blessed mean and a typical case rather than from "
        "a round number. The measurement section shows the derived requirement against the guess.",
    ),
    (
        "q-0243",
        "why is the entry point scan cached for the whole process but the config file not",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md#decision/0",
                3,
            ),
            (
                "docs/adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md#alternatives-considered/0",
                2,
            ),
        ),
        "Decision answers it directly - the environment is cached and the repository is not, "
        "because a running process cannot honour a change to what is installed while a build may "
        "rewrite mycelium.toml. Alternatives records the second cache being refused on its cost.",
    ),
    (
        "q-0244",
        "why are the agent tasks judged on documentation this project did not write",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md#decision/0",
                3,
            ),
            (
                "docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md#context/0",
                2,
            ),
        ),
        "Decision describes the second suite authored over a corpus we do not control, which is "
        "the answer. Context names the principle it inherits: a verdict read on a corpus we wrote "
        "measures the author as much as the retriever.",
    ),
    (
        "q-0245",
        "why does the performance gate time the tool call rather than the retriever",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/adr/0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md#decision/0",
                3,
            ),
            (
                "docs/adr/0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md#context/0",
                2,
            ),
        ),
        "Decision states what the harness times and what the gate reads, keeping the retriever as "
        "a floor beside it. Context explains why it had to change: the spec states one end-to-end "
        "budget and the gate had been timing the part inside the harness instead.",
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
