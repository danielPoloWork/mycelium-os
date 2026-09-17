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

**Amendments are not a status.** When a later decision changes *part* of a record that still
stands, say so on one line, as close to what moved as possible — in the `Status:` field when the
whole record is qualified, or in a blockquote note at the paragraph itself:

```text
- **Status:** Accepted — the `target_tokens` ruling is amended by [ADR-0023](0023-….md)

> **Narrowed at roadmap 4.26 ([ADR-0056](0056-….md)).** …what no longer holds, and what does.
```

Pick the verb: *corrected* when the evidence was wrong, *amended* when a decision moved,
*narrowed* when a rule still holds in a smaller scope. The amender must be a **link**, and it
must mention the record it amends — `consistency_lint.py` enforces both. There is deliberately
no `amends` edge type: the relation points at a clause rather than a document, so the graph
cannot state it truthfully ([ADR-0092](0092-leave-the-amendment-relation-in-prose-and-check-the-prose.md)).

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
| [0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md) | Look a name up exactly — and report that the table points at naming sites, not documenting ones | Accepted |
| [0081](0081-check-the-incumbents-reach-not-its-ranking.md) | Check the incumbent's reach, not its ranking | Accepted |
| [0082](0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md) | Open the frontmatter contract by one key, and make the drift unlandable | Accepted |
| [0083](0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md) | Route the query — and report that routing cannot save a lost ablation | Accepted |
| [0084](0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md) | Fingerprint the index a ranking reads, not the store it lives in | Accepted |
| [0085](0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md) | Let a callout bound a chunk rather than atomise one | Accepted |
| [0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md) | Declare the module-facing surface — and refuse to freeze it from one consumer | Accepted |
| [0087](0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md) | Distil a conversation at authoring time, and make it cite the message | Accepted |
| [0088](0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md) | Let a model propose line numbers, and slice the paste ourselves | Accepted |
| [0089](0089-put-content-identity-in-the-citation-and-make-the-grammar-extensible.md) | Put content identity in the citation, and make the grammar extensible first | Accepted |
| [0090](0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-asserted-them.md) | Project a source's links as links, now that the compiler knows who asserted them | Accepted |
| [0091](0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md) | Widen the heading rule, and refuse to guess which section documents a name | Accepted |
| [0092](0092-leave-the-amendment-relation-in-prose-and-check-the-prose.md) | Leave the amendment relation in prose, and check the prose | Accepted |
| [0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md) | Escape the prose that would open a block, and report what that costs | Accepted |
| [0094](0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md) | Mint a command the corpus both demonstrates and names, and report what promotion can and cannot reorder | Accepted |
| [0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md) | Read the corpus in the dialect it is written in, and let the generator check that it did | Accepted |
| [0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md) | Write the code span back where the source named it, and pin the arm that judges the leg | Accepted |
| [0097](0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md) | A twin case that outscores its source is the defect, not the fall that corrects it | Accepted |
| [0098](0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md) | Declare the renderer, pin it to what the artifacts already say, and keep it out of the default sync | Accepted |
| [0099](0099-ask-the-compiler-whether-the-prose-survived.md) | Ask the compiler whether the prose survived, and escape only where it did not | Accepted |
| [0100](0100-declare-what-a-lane-cannot-carry.md) | Declare what a lane cannot carry, per document, and report the split it creates | Accepted |
| [0101](0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md) | Let the `exact` slice name the section that documents the literal, because four of its five cases already do | Accepted |
| [0102](0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md) | Record whether the carried passage landed whole, and read a large negative with it | Accepted |
| [0103](0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md) | Generate the journal index, because every row it holds already lives in the file it links to | Accepted |
| [0104](0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md) | Merge what the projection could not tell apart, and record that it could not | Accepted |
| [0105](0105-pandoc-gets-a-floor-not-a-pin-because-nothing-it-writes-can-be-checked.md) | pandoc gets a floor, not a pin, because nothing it writes can be checked | Accepted |
| [0106](0106-escape-what-commonmark-will-see-and-keep-the-repairs-that-worked.md) | Escape what CommonMark will see, and keep the repairs that worked | Accepted |
| [0107](0107-refuse-to-model-emphasis-and-name-the-lane-the-disagreement-is-in.md) | Refuse to model emphasis, and name the lane the disagreement is actually in | Accepted |
| [0108](0108-put-the-repeated-anchor-rule-on-the-record-not-on-the-corpus-lint.md) | Put the repeated-anchor rule on the record, where no path can route around it | Accepted |
| [0109](0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md) | Print the grade beside the share, because a split anchor is only half the reading | Accepted |
| [0110](0110-drop-the-markup-and-keep-the-words-on-evidence-a-placeholder-cannot-forge.md) | Drop the markup and keep the words, on evidence a placeholder cannot forge | Accepted |
| [0111](0111-a-floor-can-reject-what-a-preference-must-not-choose.md) | A floor can reject what a preference must not choose | Accepted |
| [0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md) | Date the baseline to a release, because the drift it records is the incumbent's | Accepted |
| [0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md) | Close a milestone on its gates, and carry an unmet one by name | Accepted |
| [0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md) | Freeze the five contracts as goldens, and publish the promise before the tag that binds it | Accepted |
| [0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md) | Render the plugin cookiecutter to check it, and link the docs site out to canonical content instead of duplicating it | Accepted |
| [0116](0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md) | Publish under a name already decided, and let the artifact be a defined thing | Accepted |
| [0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md) | Sign and inventory the artifact, and reserve the rung a newcomer stands on | Accepted |
| [0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) | Make a deferral name the condition that ends it, in code | Accepted |
| [0119](0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-may-cost-to-read.md) | Derive the suite from the threat model, and bound what a document may cost to read | Accepted |
| [0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md) | Build the reference profile, publish what it says, and gate the instrument rather than the verdict | Accepted |
| [0121](0121-search-the-trademark-landscape-and-correct-what-d-024-assumed.md) | Search the trademark landscape, and correct what D-024 assumed | Accepted |
| [0122](0122-score-what-a-citation-names-and-read-it-from-the-chunk.md) | Score what a citation names, and read it from the chunk rather than the anchor | Accepted |
