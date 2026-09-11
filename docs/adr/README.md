# Architecture Decision Records

One numbered Markdown file per decision, in the lightweight
[Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
format. Numbering is sequential and never reused or renumbered. Template:
[`template.md`](template.md).

Open an ADR when a choice affects the public surface or compatibility, when two reasonable
options exist and the rationale is non-obvious, when a **design pattern** is adopted, or
when superseding a prior decision. Do **not** open one for routine implementation details
or trivially reversible choices.

Status transitions: `Proposed` → `Accepted` → (`Superseded by ADR-XXXX` | `Deprecated`).

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-adopt-cross-language-source-layout.md) | Adopt the cross-language source layout | Superseded by ADR-0003 |
| [0003](0003-adopt-flat-python-src-layout.md) | Adopt the flat Python src-layout (D-024) | Accepted |
| [0004](0004-adopt-pydantic-v2-record-contracts.md) | Adopt pydantic v2 record contracts with JSON Schema 2020-12 export | Accepted |
| [0005](0005-adopt-in-repo-identity-library.md) | Implement the identity library in-repo, with an injectable monotonic ULID factory | Accepted |
| [0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) | Adapt Markdown to KIR over markdown-it, and give KIR nodes declared per-kind fields | Accepted |
| [0007](0007-adopt-structure-first-chunking.md) | Chunk on document structure, with a dependency-free token estimate | Accepted |
| [0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) | Keep SQLite behind a store protocol, and index lexically in a standalone FTS5 table | Accepted |
| [0009](0009-adopt-build-publication-semantics.md) | Fix the build's publication semantics — lock file, transaction-then-swap, identity pinned at first build | Accepted |
| [0010](0010-adopt-cli-output-conventions.md) | CLI output conventions — one JSON document on stdout, ASCII chrome, UTF-8 content | Accepted |
| [0011](0011-implement-mcp-stdio-in-repo.md) | Implement the MCP stdio server in-repo, and prove conformance with the reference client | Accepted |
| [0012](0012-adopt-the-g6-determinism-gate.md) | State what determinism claims, and gate it with a reviewable golden | Accepted |
| [0013](0013-adopt-the-evaluation-harness.md) | Evaluate against the grep incumbent, and publish the harness's limits with its numbers | Accepted |
| [0014](0014-adopt-partial-strict-configuration.md) | Load `mycelium.toml` strictly, honour it partially, and say which is which | Accepted |
| [0015](0015-adopt-content-addressed-incremental-builds.md) | Compile incrementally through a content-addressed stage cache | Accepted |
| [0016](0016-make-snapshots-restorable.md) | Make snapshots restorable, and give garbage collection a defined live set | Accepted |
| [0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) | Ship a local embedder and hybrid retrieval, and let gate G2 choose the default | Accepted |
| [0018](0018-build-the-graph-from-authored-links.md) | Build the graph from authored links, and resolve it globally on every build | Accepted |
| [0019](0019-adopt-watch-mode.md) | Let filesystem events decide *when* to build, never *what* to build | Accepted |
| [0020](0020-adopt-the-jsonl-interchange-bundle.md) | Make the export bundle a verifiable claim, not a directory of files | Accepted |
| [0021](0021-scope-the-corpus-and-gate-the-evaluation.md) | Scope the corpus, then let the gates run in CI | Accepted |
| [0022](0022-measure-the-agent-loop-without-an-agent.md) | Measure the agent loop without an agent, and say what that leaves out | Accepted |
| [0023](0023-make-the-chunk-target-steer-size.md) | Make `target_tokens` steer chunk size, and let the evaluation pick its default | Accepted |
| [0024](0024-serve-what-the-configuration-admits.md) | Make the vocabulary filters set-valued, and enforce the serving policy at one seam | Accepted |
| [0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) | Make lexical evidence the vector leg's precondition, and refuse every similarity floor | Accepted |
| [0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) | Pack the vectors into a memory-mapped matrix, and keep the SQL scan as the definition | Accepted |
| [0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) | Split dev from release, and judge a corpus we did not write | Accepted |
| [0028](0028-keep-the-vector-scan-exact.md) | Keep the vector scan exact, because every way of shortening it costs more than it saves | Accepted |
| [0029](0029-let-a-judgment-name-a-section.md) | Let a judgment name a section, and credit it once | Accepted |
| [0030](0030-correct-the-vector-scan-cost-model.md) | Correct the vector scan's cost model — the budget was met, and the benchmark was wrong | Accepted |
| [0031](0031-refuse-three-rerankings.md) | Refuse three re-rankings, and name what the ranking failure actually is | Accepted |
| [0032](0032-adapt-four-engines-and-pin-which-one-runs.md) | Adapt four engines behind two protocols, and pin which one runs | Accepted |
| [0033](0033-keep-the-original-and-bound-the-hostile.md) | Keep the original, and bound what an engine is asked to read | Accepted |
| [0034](0034-project-the-evidence-and-count-what-it-lost.md) | Project the evidence, and count what it lost | Accepted |
| [0035](0035-let-an-llm-write-only-what-a-machine-can-check.md) | Let an LLM write only what a machine can check | Accepted |
| [0036](0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md) | Measure what can be measured, and let a human outrank the gate | Accepted |
| [0037](0037-record-what-was-refused-and-redact-what-was-found.md) | Record what was refused, and redact what was found | Accepted |
| [0038](0038-declare-the-corpus-then-compare-it.md) | Declare what the corpus contains, then compare it — a report cannot corroborate itself | Accepted |
| [0039](0039-measure-what-projection-costs.md) | Measure what projection costs, by judging the same document twice | Accepted |
| [0040](0040-refuse-the-pdf-layout-pipeline-on-its-merits.md) | Refuse the PDF layout pipeline on its merits, not on its constraints | Accepted |
| [0041](0041-bound-the-section-unit-and-refuse-six-more.md) | Bound the section unit, and refuse six more re-rankings | Accepted |
| [0042](0042-let-an-atomic-block-share-its-chunk.md) | Let an atomic block share its chunk, and ship it switched off | Accepted |
| [0043](0043-judge-across-the-configurations-a-set-is-scored-under.md) | Judge across the configurations a set is scored under | Accepted |
| [0045](0045-ask-the-documents-whether-two-runs-are-comparable.md) | Ask the documents whether two runs are comparable, not the boundaries | Accepted |
| [0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) | Name what a two-case slice can and cannot say | Accepted |
| [0046](0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md) | Derive an identity rather than mint one, when a build may not write | Accepted |
| [0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md) | Flip the packed chunker on, and let the gate say so | Accepted |
| [0048](0048-index-the-stem-beside-the-surface-form.md) | Index the stem beside the surface form, and let the surface gate it | Accepted |
| [0049](0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md) | Close the grep gap, and keep the incumbent in the manifest | Accepted |
| [0050](0050-report-what-each-query-term-reached.md) | Report what each query term reached, surface and stem apart | Accepted |
| [0051](0051-hold-the-judgements-fixed-too.md) | Hold the judgements fixed too, and name a population change as one | Accepted |
| [0052](0052-give-a-slice-cases-or-stop-gating-it.md) | Give a slice cases, or stop gating it — and name the case that moved | Accepted |
| [0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) | Report on the corpus we author, gate on the one we do not | Accepted |
| [0054](0054-gate-the-query-not-the-documents.md) | Gate the query, not the documents | Accepted |
| [0055](0055-run-the-gates-the-change-implicates.md) | Run the gates the change implicates, and derive which those are | Accepted |
| [0056](0056-make-the-format-assignment-append-only.md) | Make the format assignment append-only, and let the regeneration check replace the rule it made impossible | Accepted |
| [0057](0057-drop-the-function-words-and-score-the-seam-that-ships.md) | Drop the function words, and score the seam that ships | Accepted |
| [0058](0058-decompose-a-conceded-slice-before-believing-it.md) | Decompose a conceded slice before believing what it says | Accepted |
| [0059](0059-make-the-plan-one-implementation-too.md) | Make the plan one implementation too, and let `retrieval` gate every corpus | Accepted |
| [0060](0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md) | Declare the property-test budget, and keep the falsifying example | Accepted |
| [0061](0061-count-the-population-before-decorating-it.md) | Count the population before decorating it, then guard the shape | Accepted |
| [0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) | A `symbol` judgment names where the thing is documented, not where it is framed | Accepted |
| [0063](0063-split-the-leaf-heading-from-its-ancestors.md) | Split the leaf heading from its ancestors, and take only the weight dev can see | Accepted |
| [0064](0064-measure-the-gate-that-decides-the-default.md) | Measure the gate that decides the default, and find it cannot decide | Accepted |
| [0065](0065-one-section-cannot-document-two-commands.md) | One section cannot be the documenting home of two commands | Accepted |
| [0066](0066-refuse-the-length-split-and-name-the-anti-correlation.md) | Refuse the length split, and name the anti-correlation it exposed | Accepted |
| [0067](0067-grow-the-dev-set-before-asking-it-a-question.md) | Grow the dev set before asking it a question, and keep the cases that embarrass it | Accepted |
| [0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) | Give gate G2 a runner by dating its verdict, not by re-running it everywhere | Accepted |
| [0069](0069-read-g2s-slices-case-by-case-and-keep-the-bar.md) | Read G2's slices case by case, and keep the bar they trip | Accepted |
| [0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) | Take the leaf heading weight on the third asking, because the dev set can now see it | Accepted |
| [0071](0071-advertise-the-types-and-check-the-tools.md) | Advertise the types, then check the tools with them | Accepted |
| [0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) | Keep our own restatements out of our own benchmark | Accepted |
| [0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md) | Take the grammar's word for what a definition is, and the heading's for what it names | Accepted |
| [0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md) | Give every edge type a derivation, or a reason it has none | Accepted |
| [0076](0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md) | Let the corpus declare its entities, and refuse to guess the rest | Accepted |
| [0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md) | Let the graph propose and the ranking dispose, and report that it lost the ablation | Accepted |
| [0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md) | Give a module an entry point, a section and a command — and report what it could not reach | Accepted |
| [0078](0078-report-a-moved-citation-rather-than-serving-it-in-silence.md) | Report a moved citation rather than serving it in silence | Accepted |
| [0079](0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md) | Resolve an ingested document's links through its source tree, and never call them authored | Accepted |
