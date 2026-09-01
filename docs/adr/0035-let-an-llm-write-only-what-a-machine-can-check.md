# ADR-0035: Let an LLM write only what a machine can check

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.4; RFC-0001; spec 02 §5; spec 03 §§3, 6; spec 05 §§2, 4; D-013,
  D-017, D-020, D-021, D-026; NFR-1, NFR-6; [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0024](0024-serve-what-the-configuration-admits.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)

## Context

D-020 makes ingestion dual-lane. The **evidence lane** — acquire, parse, project, account
(roadmap 4.1–4.3) — is deterministic and always runs. The **synthesis lane** additionally
lets an LLM author *readable* documentation from that evidence, and it is the one place in
this project where a model writes something a human will later read as knowledge.

The decision's whole difficulty is that D-020 does not permit this because LLM prose is
good. It permits it because the prose can be **checked**: "synthesized docs are born
`candidate` and must cite the evidence layer per statement", and the reason recorded beside
the decision is that *"100 % source truth can only be proven against a deterministic
extraction"*. So the question this ADR answers is not "which model" or "what prompt". It is:
**what exactly is checked, how exactly is it measured, and what happens when the check
fails?**

Three project constraints shape the rest. **D-013/NFR-6**: no network call unless
configured — a default install must synthesize nothing. **NFR-1/gate G6**: identical inputs
produce byte-identical artifacts, so a non-deterministic stage has to be *declared* and kept
out of the golden, the way the embedder was (ADR-0017). **D-021**: verification status is
the folder and nothing else, so nothing in this lane may produce a `verified` document.

## Decision

**An LLM may write a document only if every claim in it cites evidence that exists, and the
lane refuses to write anything else.**

Concretely:

1. **A `Synthesizer` Protocol** joins `Connector` and `Parser` in `mycelium.sdk.protocols`
   (spec 05 §4.1). It returns a `Synthesis` record — markdown *plus* provider, model, prompt
   digest, parameters and attempt count — rather than the bare string the spec sketches:
   a stage declared non-deterministic must record what produced it, and a string cannot.
2. **The `wiki` plugin** (D-026) is the default synthesizer, and it owns three things, none
   of which is the model: a **closed citable vocabulary** (the prompt hands over the exact
   `[[document#Heading]]` strings that exist), **one repair round-trip** (a rejected draft is
   answered with its violations, once), and **the refusal** (a second failure writes nothing).
3. **The citation contract** (`mycelium.synthesis.citations`) is pure, deterministic, and
   the only thing that decides whether a document is written:
   - *No fabricated citation.* Every wikilink resolves to a document in the evidence set and,
     with a fragment, to a heading it has. Always fatal — prose that merely *looks* grounded
     is the most dangerous artifact this project could ship.
   - *Something is cited.* A candidate that cites nothing is prose with a provenance stamp.
   - *Claim-bearing blocks are covered*, measured against `[synthesis]
     min_citation_coverage`, which **defaults to 1.0**.
4. **A claim-bearing statement is a KIR `paragraph` or `list_item` node of at least five
   words** — a *block*, not a sentence. This is the measure gate G7 (roadmap 4.5) will be
   applied to.
5. **The lane is off unless a provider is named.** `enabled = "auto"` means *on when a
   provider is configured*; naming one is the operator's consent to a network call, and it is
   the only way this project makes one (D-013/D-017). The provider seam lives in
   `mycelium.synthesis.provider`, beside its subsystem — not in the SDK, whose protocol list
   spec 05 §4.1 fixes.
6. **A candidate lands in `knowledge/candidate/`** with `origin: synthesized`,
   `generated_by`, and a `source_digest` pointing at a **synthesis record in tier-1 custody**
   — the one-key mechanism ADR-0034 established, aimed at a different kind of record. The
   compiler recovers provider, model, prompt digest and parameters from it into
   `provenance.synthesizer`.
7. **A citation is a typed edge.** A wikilink from anywhere outside `knowledge/evidence/`
   into it resolves to `cites` rather than `links_to` (spec 03 §6). Folder-derived, because
   the folder *is* the status (D-021), so no store migration and no new field are needed.
8. **A synthesis failure never fails the ingestion that carried it.** Missing provider,
   declined request, ungrounded draft — each is reported and the evidence lane's output
   stands, because D-020 makes synthesis the *additional* lane.

## Alternatives Considered

- **Measure coverage per sentence rather than per block.** Closer to gate G7's wording, and
  finer. Rejected because KIR states block boundaries exactly and says *nothing* about
  sentence boundaries: a sentence-level measure would be this module inventing a structure
  the compiler does not have, and a grounding number is worth nothing unless two runs of it
  agree. The block measure is what G7's threshold will be applied to; moving to sentences
  later changes what the number *means* and has to be re-judged, not patched.
- **Write the document with a warning when coverage is short.** The friendly option, and the
  one that voids the permission: D-020 allows the lane *because* the citations are checked,
  so a lane that writes unchecked prose has kept the cost and dropped the justification. The
  floor is configurable — relaxing it is an operator's explicit act, and easier than
  un-publishing a claim.
- **Retry until the contract passes.** Rejected: an unbounded loop spends an operator's money
  converging on a document that the evidence may not support. Two attempts, and the second
  failure is *information* — it says this document cannot be written from this evidence.
- **A hand-rolled HTTPS client instead of the `anthropic` SDK** (the ADR-0011 precedent,
  where the MCP protocol was implemented in-repo rather than taking seventeen packages).
  Rejected here: the SDK is four packages, and what it owns — credential resolution order,
  retry policy for 429/5xx, a typed error hierarchy — is exactly what a hand-rolled client
  would reimplement and get subtly wrong. ADR-0011's arithmetic came out the other way
  because its dependency was seventeen packages including an HTTP server and JWT.
- **Add a `synthesized` member to the `trust_class` vocabulary.** Rejected: spec 03 §3's v1
  enum has none, deliberately. A synthesized document's authority *layer* is tier 2 like any
  authored one; what makes it untrustworthy is its **status**, which is folder-derived
  (D-021) and already what retrieval filters on (ADR-0024). A vocabulary member would put
  one fact in two places, where they can disagree. If evaluation shows retrieval must weight
  synthesized prose separately, that is an RFC — the same anti-sprawl valve the edge
  vocabulary uses (F-9).
- **Emit `derived_from` edges alongside `cites`,** as spec 03 §6 pairs them. Rejected for
  now: at document granularity it is the deduplicated projection of the `cites` edges
  already emitted — the same assertion at lower resolution — and the distinction the spec
  actually wants (synthesized documents versus authored ones citing evidence) is not
  expressible until the graph's per-document state carries `origin`. Filed with roadmap 4.5,
  which needs the same field.
- **Default `model_id` to the Sonnet id in spec 05 §2's sample file.** Rejected: the sample
  is an illustration dated 2026-07, not a contract, and the failure this lane exists to
  prevent — an unsupported claim in `knowledge/candidate/` — is a reasoning failure. The
  default is the most capable model of the family; an operator trades capability for cost in
  one line.

## Consequences

- **A fourth stable contract member.** `Synthesizer`, `SynthesisContext`, `EvidenceDocument`
  and `Synthesis` join the SDK's frozen surface. `Synthesis` deviates from spec 05 §4.1's
  sketched `-> str`, recorded above.
- **A new record and a new custody kind.** `mycelium/synthesis/v0` and
  `CustodyKind.SYNTHESIS`. It is the synthesized lane's counterpart to `FidelityReport`:
  where that accounts for what an ingested document *lost*, this accounts for what a written
  document *rests on*.
- **The lane is testable without a network, and it is tested that way.** Everything the lane
  decides — prompt, contract, repair, refusal, record, candidate — is exercised against a
  scripted provider. One test calls the real API; it needs a credential, is marked `llm`, and
  skips without one. That is the honest boundary of what CI can assert, and it is the same
  shape ADR-0017 used for the model files.
- **The claim is proved end to end.** A synthesized document is written, compiled by
  `mycelium build` like any authored file, and comes out labelled `candidate`, carrying the
  identity of the model that wrote it, with its citations as `cites` edges in the graph.
- **`[synthesis]` leaves the unhonoured set**, and `[synthesis] min_citation_coverage` makes
  "mandatory wikilink citations" a number rather than an adjective.
- **The config digest changed**, so the G6 golden is re-blessed — again with a **one-line
  diff** (`config_digest` only), which is the evidence that a new section reached the
  manifest and no chunk moved.
- **The `synthesis` extra pulls four packages** (`anthropic`, `docstring-parser`, `jiter`,
  `sniffio`). Nothing imports them unless a provider is configured.
- **Known limits, stated rather than discovered.** Coverage is per block, so a paragraph with
  five claims and one citation counts as covered — the floor bounds *how many blocks* cite,
  never *how well*. The contract checks that a citation **resolves**, not that the cited text
  **supports** the claim; sampled entailment is gate G7's half of the job (roadmap 4.5), and
  until it lands a grounded-looking document can still misread its evidence. One document is
  synthesized per source; multi-source synthesis is a topic-selection problem this item does
  not open.

## References

- Spec 02 §5 (dual-lane ingestion); spec 03 §3 (frontmatter ownership, trust vocabulary),
  §6 (edge vocabulary); spec 05 §2 (configuration), §4.1 (plugin protocols), §4.4 (naming).
- D-020 (dual-lane ingestion), D-021 (verification is a workflow), D-026 (`wiki` is the
  default synthesizer; the `-llm` suffix is refused and llm-wiki credited in the
  description), D-013/D-017 (offline default, untrusted content).
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the
  declared-non-determinism and optional-extra precedents.
- [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) — the one-frontmatter-key
  link into custody, reused here for a different record.
