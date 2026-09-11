# ADR-0087: Distil a conversation at authoring time, and make it cite the message

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec doc 08 §7
- **Related:** [ADR-0035](0035-let-an-llm-write-only-what-a-machine-can-check.md) (the
  citation contract this extends), [ADR-0036](0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md)
  (gate G7, whose judge the granularity question is really about),
  [ADR-0077](0077-build-the-module-mechanism-and-report-what-the-first-module-found.md) (the
  module mechanism and the API-fix provision), [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)
  (the surface this adds an entry to), [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  and [ADR-0085](0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md) (the same
  refusal to freeze a contract against no consumer); spec 02 §§2, 4.1, 5, spec 05 §4.1.1,
  doc 08 §§7, 9, 10; D-020, D-021, D-023, D-025; roadmap 5.5, 5.15

## Context

Doc 08 §7's last paragraph is the `chats` module's one optional half: *"an LLM-authored
summary doc ("decisions and outcomes of this conversation") written to
`knowledge/candidate/…` with `cites` wikilinks into the transcript — subject to
`mycelium verify`/`promote` exactly like every synthesized doc"*. Roadmap 5.5 deferred it
and roadmap 5.15 carries it, with two things attached that turned out to pull in opposite
directions.

The first was a prediction. 5.15 was filed saying distillation *"is the one thing in the
module that would use D-023's **pipeline-stage** mechanism, which 5.5 did not build because
nothing else needed it — so this item carries both halves: the stage contract … and its
first consumer, which is the only order that avoids designing a contract against no user."*

The second was an open question, and it was the right one: *"what a distilled conversation
cites: a message anchor is stable and a conversation is long, so grounding may want the
message rather than the document, which is a question for gate G7's coverage rule."*

## Decision

**Distillation is an authoring-time command, and the pipeline-stage mechanism still has no
consumer.** The prediction does not survive contact with the authority model. A
distillation writes `knowledge/candidate/…`, which is tier 2, and spec 02 §2 admits no
exception: *"Ingestion (`mycelium ingest`) is an **authoring-time** operation: it may write
tiers 1–2. The build (`mycelium build`) remains a pure function and never writes tiers 1–2."*
A pipeline stage runs inside the build. So the only way distillation could have been a stage
is if the build wrote tier 2, which is the one thing the compiler's purity — and therefore
gate G6, and therefore every determinism claim this project makes — rests on not doing.

This is not a near miss on a technicality. A stage must also *participate in build keys*
(spec 05 §4.1.1), and what a stage contributes to a key is a statement that the same inputs
give the same artifact. The synthesis lane is non-deterministic by declaration (ADR-0035),
which the stage contract does allow — the embed stage already is — but a non-deterministic
stage that also writes into somebody's Git working tree on every build is not a stage, it is
a robot with commit access.

So `mycelium chats distil <conv_id>` is a seventh command beside doc 08 §9's six, and
D-023's pipeline-stage, lifecycle-hook and MCP-tool mechanisms remain unbuilt with no
consumer between them. That is the third time this milestone has ended in the same place —
5.1 for `Extractor`, 5.5 for three mechanisms, 5.14 for an SDK façade — and the pattern is
worth naming: the mechanisms spec 05 §4.1.1 lists are a *menu*, and a module that needs one
will arrive. Building it first would freeze a contract whose only reviewer is its author.

**One conversation per invocation, and never as a side effect of `import`.** `mycelium
ingest` synthesizes every source it takes, by default, when a provider is configured. A chat
import is bulk by nature — a provider export is a year of conversations in one file, and the
fixtures here hold two — so the same default would spend an operator's money on a decision
they did not make.

**A distilled conversation cites the message, not the conversation**, and the reason is
gate G7's judge rather than taste. When a citation names a section, `section_text` hands the
judge that section; when it names a document, it hands over all of it, and that function's
own docstring already says what that is worth: *"handing a model twenty pages and asking
whether one sentence is in there somewhere is not the question G7 asks, and it is the
question a model answers most charitably."* A transcript is the first evidence the lane has
met with that shape.

The good news, measured before anything was written, is that the precise citation already
existed: roadmap 5.5 gave every message its own heading so anchors would be stable, so
`[[conversation#12 · assistant]]` resolved through the ordinary contract with no core change
at all. The problem was the imprecise one, and it has **two spellings**. `[[conversation]]`
is the obvious one. The other is the projection's own title heading — measured on the
fixture corpus, `section_text(kir, "Anchor stability")` returns 724 characters and the whole
document returns 724 characters, the same bytes. A rule that closed only the first would have
left the second open under a section's name.

Both are closed, and closed the way the citation contract already works — by pairing the
vocabulary with the check. An `EvidenceDocument` may declare `cite_sections_only`, and then
`citable_names` stops *offering* the whole-document form while `review` stops *accepting*
it; the module hands the synthesizer evidence whose citable `headings` are the message
headings and nothing else. Offering without enforcing would be a suggestion; enforcing
without offering would be a trap. It is a general rule on a general field, not a chat
special case: any evidence too long to be checked whole can set it.

**`mycelium.synthesis` joins the module-facing surface** (ADR-0086). The module needs the
lane, the citation contract, the candidate folder and the custody receipt, and a module that
reimplemented any of them would be wrong rather than merely different. It is on the
*unfrozen* side of that declaration, so the module now depends on a component v1 may still
move — which is the fact ADR-0086 built the list to make visible, and `test_modules.py` made
adding it an edit somebody had to justify.

## Alternatives Considered

- **Build the pipeline-stage contract anyway, and let the stage emit a tier-3 artifact that
  something else writes to tier 2.** It would satisfy the roadmap item as written. Rejected:
  it invents a second lane for a job the first lane already does, and the "something else"
  is a build side effect on Git wearing one layer of indirection. Doc 08 §7 says the
  distillation *is* a synthesized document, which is a thing that already has a home.
- **Distil during `mycelium chats import`, like `mycelium ingest` does.** Symmetry, and one
  fewer command. Rejected on the measurement above: an export file is a bulk archive, and
  the symmetry is with the wrong command. `ingest` takes one document a person chose.
- **Leave the citation granularity alone and let coverage speak.** The cheapest option, and
  a document citing `[[conversation]]` for every claim scores coverage 1.0. Rejected: that
  number would be measuring nothing, which is worse than measuring badly. It is the exact
  failure the item anticipated.
- **Enforce section-level citation for *every* evidence document.** More honest in the
  abstract. Rejected: it would move gate G7 for every candidate already written from a short
  projection, where citing the document whole is genuinely checkable — a change with real
  consequences, made in passing, for evidence that does not have the problem.
- **Decide it by length — "a document over N sections must be cited by section".** Rejected:
  N is a number nobody in this repository chose, able to reclassify a corpus on a chunking
  change. The evidence declares its own shape instead.
- **Carry the rule in the document's frontmatter, so `mycelium verify` re-derives it.** It
  would close the asymmetry below. Rejected: the core would be reading a key a module writes,
  which is the coupling `[chats]` was designed to avoid (ADR-0077) — the core holds a
  module's table and knows nothing about what is in it.
- **A markdown-it plugin or a KIR marker so a transcript is structurally special.** Rejected
  for the reason ADR-0073 rejected one for code-span headings: spec 03 §4's node vocabulary
  is closed, and nothing here needs the parser to change its mind.

## Consequences

- **`mycelium chats distil <conv_id>`**, with `--dry-run` and `--json`. It refuses with exit
  2 when `[synthesis]` names no provider, saying so and saying that the conversation is
  archived, projected and searchable regardless; with exit 1 when the conversation is
  unknown, or when it has no projection because `[chats] retention_months` excluded it. The
  two refusals are **ordered** — the repository first, the argument second — so an operator
  whose real problem is configuration is not sent hunting for an id.
- **A refusal is a result, not a failure of the module.** Doc 08 §7 calls distillation
  optional, and a conversation that cannot be distilled keeps everything the module promised
  it before anybody asked for prose about it.
- **The citation contract gains a fourth rule** and `CitationReport` a
  `whole_document_citations` field. The field exists because the three failures need three
  sentences: a fabricated citation names something that does not exist, a coarse one names
  something real and too large to check, and a thin document cites too little. Classified
  by prefix alone, the coarse case would have been reported as *"cites 1 thing(s) that do not
  exist"* — a true-sounding sentence pointing at the wrong problem, and the repair round-trip
  would have been sent after it too.
- **A bug found by building this, in the prompt rather than the contract.** `wiki._render`
  annotated every KIR heading with a `cite as [[…#…]]`, and the document itself with
  `cite as [[…]]`, reading the citable set off the KIR — while `review` read it off
  `evidence.headings`. The two agreed only because `evidence_of` filled the second from the
  first, and the first evidence document to narrow its headings made them disagree: the
  prompt's Evidence block offered exactly what its CITABLE block forbade. Both now read
  `evidence.headings`, the field whose definition is *what a statement can cite*. No shipped
  behaviour changed, because no evidence document had ever narrowed them.
- **The system prompt is untouched, deliberately.** Its rule 2 offers `[[document]]` as a
  citation form, which is false for section-only evidence — but it is the cached prefix
  (ADR-0035), and the correction belongs where it can be *specific*. The CITABLE block in the
  user turn names the documents the exception applies to, instead of teaching a rule that is
  wrong for the rest.
- **Write time is stricter than verify time, and that is the established shape.**
  `mycelium verify` rebuilds its evidence set with `evidence_of`, which knows nothing about
  section-only evidence, so a hand-edited candidate could add `[[conversation]]` and pass G7
  where the lane would have refused it. This is the same asymmetry `[synthesis]
  min_citation_coverage` already has by design — it defaults to 1.0 against G7's 0.95,
  because *"G7 decides whether an existing candidate may be promoted, this decides whether one
  is written at all"*. It costs nothing for a document this lane wrote: those citations name
  messages, and verify re-checks exactly those.
- **Threat-model boundary B10 widens, and it is the sharpest content it has carried.** The
  LLM egress boundary was written for ingested documents; a transcript is a private
  conversation, and distillation sends one to a provider. The lane is still off unless a
  provider is named, the command is still one conversation at a time and never automatic, and
  the transcript reaching the model is the **redacted projection** rather than the record —
  doc 08 §6 redacts secrets in the projection unconditionally, so the copy that leaves the
  machine is the copy that was already scrubbed.
- **Nine entries on the module-facing surface**, six of them unfrozen. The chats module now
  imports five core components spec 02 §10 does not cover.
- **No new roadmap item is filed.** The pipeline-stage mechanism is not deferred work; it is
  a mechanism with no consumer, which is a state rather than a debt (spec 05 §4.1.1 lists
  four and v1 needs one). If a module arrives that wants one, that module's item builds it.

## References

- Spec: `.draft-specs/02-architecture.md` §2 (the authority model and the build's purity),
  §4.1 (the stage contract), §5 (dual-lane ingestion);
  `.draft-specs/05-interfaces-and-plugins.md` §4.1.1 (the four mechanisms);
  `.draft-specs/08-module-chats.md` §7 (distillation), §9 (the CLI), §10 (the acceptance
  gates, and gate 6's API-fix provision).
- Decision log: D-020 (the synthesis lane), D-021 (candidate → verified is a human act),
  D-023 (extension mechanisms), D-025 (`chats` is the first module).
- Measured: `section_text` on a projected conversation's title heading returns the whole
  document, byte for byte — `contrib/chats/tests/test_distil.py`'s own assertion.
- Tests: `contrib/chats/tests/test_distil.py`, `tests/test_synthesis_citations.py`'s
  *Rule 2* section, and the command-set pin in `contrib/chats/tests/test_acceptance.py`.
