# ADR-0088: Let a model propose line numbers, and slice the paste ourselves

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec doc 08 §6
- **Related:** [ADR-0035](0035-let-an-llm-write-only-what-a-machine-can-check.md) (an LLM may
  write only what a machine can check — the rule this applies to structure),
  [ADR-0037](0037-record-what-was-refused-and-redact-what-was-found.md) (the secret doctrine
  this extends to egress), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (the degradable-failure shape), [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the module and its `[chats]` table), [ADR-0087](0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md)
  (the module's other LLM lane, and the surface entry it added); spec 02 §5, doc 08 §§4, 6,
  10; D-013, D-017, D-020; roadmap 5.5, 5.16

## Context

Doc 08 §6's import table has four rows and the module shipped three. The fourth:
*"Optional LLM-assisted segmentation | Off by default; when enabled, it may propose
**boundaries/roles only** — content stays verbatim — and the record is labeled
(`segmenter: llm/<model>`) in provenance"*.

Roadmap 5.5 built the floor underneath it instead, and the floor is a real refusal rather
than an unfinished feature. A paste with no turn labels becomes **one fragment** with
`structure_inferred: true`, because doc 08 §4's second invariant permits inferring structure
and forbids inventing a speaker — and the obvious heuristic, alternating `user`/`assistant`
by paragraph, invents one on every other block. A fabricated attribution reaching the index
is a false statement about who said what, and the projection makes it citable.

The floor costs something specific, and 5.16 was filed to name it: an unlabelled paste gets
**no message anchors at all**. Every other conversation in the archive is one section per
message, so a search result cites a conversation *and a turn*; this one is a single chunk and
a single citation for the whole thing. The `segmenter` field on the record and the `inferred`
counter on the fidelity report have existed since 5.5, both unexercised, waiting for this.

## Decision

**The model returns line numbers. It never returns content.** A proposal is a JSON object
holding a list of `{line, role}` boundaries, and this module slices the segments out of the
operator's own text. That is what makes *"content stays verbatim"* a property of the shape
rather than a promise checked afterwards: a model that hallucinated a sentence has nowhere to
put it, and a model that rewrote a turn could not, because it was never asked for one. The
test for it passes an invented `content` key alongside a boundary and asserts the invention
does not reach the record.

This is ADR-0035's rule applied to structure rather than prose. The synthesis lane lets an
LLM write *because* the citations can be checked; here the output is small enough that it
does not need checking against the source — it cannot express the failure.

**A proposal partitions the paste exactly, or it is refused by name.** First boundary at
line 0, strictly increasing, every index inside the text, every role from the record's closed
four. A violation is quoted back for **one** repair attempt — the synthesis lane's number, for
its reason: a loop that retried until it passed would spend an operator's money converging on
a partition of a text that may have no turns in it, and the second failure is information.
Every refusal names the offending value, because *"the proposal is invalid"* would spend the
repair attempt without improving its odds.

**Two failures leave the floor, and so does every other failure.** An unreachable provider, a
paste over the line ceiling, a paste that must not be sent, a model that honestly answered
`{"turns": []}` — each returns the conversation the reader read, with a warning saying which
it was. Doc 08 §6 calls this row *optional*; the floor is a correct record and this is an
improvement on it, never a precondition for it.

**The paste is redacted before it leaves the machine, and a paste holding a private key is
not sent at all.** Doc 08 §6 redacts a secret in the projection and the index and keeps the
record's original text by default, because the record is the archive. Neither rule says
anything about *egress*, and this is the module's first — so what reaches the provider is the
redacted copy while the record is sliced from the original.

That works because the core replaces a finding **in place**, so line indices survive the
substitution. One rule does not: `private-key-block` spans lines, and redacting it collapses
them — measured, an 8-line paste becomes 5, so every index after the key would name the wrong
line. A paste whose redaction moves its line count is therefore not sent, and stays one
fragment. The guard and the instinct agree, which is the part worth keeping: nobody should be
clever about a pasted private key.

**Injection has a bounded blast radius, and it is worth stating rather than assuming.** The
paste is untrusted content (D-017) and the model reads it, so it may contain something shaped
like an instruction. The output contract is a list of integers and four role words, validated
against the text's own length — so the most a successful injection achieves is a *differently
wrong partition of the operator's own paste*, which is visible in the record and which the
fidelity report already calls `inferred`.

**Off by default, behind `[chats] segmenter = "llm"`, using `[synthesis]`'s provider.** A
fresh install makes no network call (D-013) and naming a provider is the operator's consent
(D-017). The module does not get a provider setting of its own: one repository has one LLM,
and a second way to name it is a second thing to keep in agreement.

**A reader says it gave up; it does not say what happens next.** `ReadConversation` gains a
typed `unsegmented` flag — narrower than `structure_inferred`, which every paste sets —
because the archive asks this on every import and an answer read out of a `meta` string is an
answer nobody pinned. Readers stay pure functions of `(text, context)`: segmentation happens
in the import path, where the provider already is, so no reader acquires a network call.

## Alternatives Considered

- **Let the model return the segmented text.** The obvious shape, and every other tool's.
  Rejected: verbatim content then becomes something to verify rather than something that
  holds, and the verification is string comparison against a model that had every opportunity
  to normalise whitespace, fix a typo, or drop a line. Doc 08 §6 says *boundaries/roles only*
  and it says it for this reason.
- **Character offsets instead of line numbers.** More precise, and it would allow a turn
  boundary mid-line. Rejected: a model cannot count characters, so it would be guessing at the
  one value the contract validates — and a pasted conversation breaks at line boundaries
  anyway. Line numbers can be *shown* to the model, which is why the prompt numbers them.
- **Alternate `user`/`assistant` by paragraph, with no model at all.** Free, offline,
  deterministic. Rejected again, for 5.5's reason unchanged: it invents a speaker, which is
  the one thing invariant 2 forbids. This item does not lower that bar — a model proposing a
  boundary is still a reading, which is why `structure_inferred` stays true and every message
  keeps `meta.inferred`.
- **Send the raw paste.** Simpler, and the record keeps the secret anyway. Rejected: the
  record is on the operator's disk and the provider is not, and doc 08 §6's whole security
  posture is that a secret does not spread. Egress is spreading.
- **Pad a multi-line redaction with blank lines so the indices survive.** It would let a paste
  with a private key be segmented. Rejected: it is a second redaction implementation living in
  a module, diverging from the core's, to rescue the one case where the right answer is to
  stop. A pasted private key should be removed from the paste, not worked around.
- **Segment labelled pastes too, to improve on the label heuristic.** Rejected: the labels are
  what the source rendered, and replacing read structure with proposed structure is strictly
  worse. The segmenter answers one question — a paste with no turns at all.
- **Make it a reader** (`--provider llm`). It would fit the registry. Rejected: a reader is a
  pure function and the registry sniffs by shape, so an LLM reader would either sniff on
  nothing or be selected by a flag that duplicates the setting. Worse, `reader_for` would have
  to know which readers cost money.
- **Drop `[chats] segmenter` and switch on `[synthesis] provider` alone.** One fewer setting.
  Rejected: configuring a provider for the distillation lane (ADR-0087) would then silently
  start sending pastes to it. Two lanes, two consents.

## Consequences

- **An unlabelled paste can become a conversation with message anchors**, which is the whole
  of what 5.16 was filed for. The fidelity report reads `turns 3, recognised 0, inferred 3,
  fragments 0` — the `inferred` counter doc 08 §6 asked for, exercised for the first time, and
  `recognised 0` because nothing was *stated*.
- **The record says who read it.** `segmenter: "llm/<model>"` on the header, `meta.segmenter`
  on each message beside the `meta.inferred` the archive already adds. The two are not the
  same claim: inferred says the structure was read rather than stated, and this says what did
  the reading.
- **A defect found by building it.** The `pasted` reader emitted *"archived as a single
  fragment"* itself — true when it was written, and false the moment segmentation could turn
  that fragment into turns *after* the reader had spoken. An import that had just produced
  three messages would have reported producing one. The sentence moved to the archive, which
  is the only place that knows; the reader now sets a flag and says nothing.
- **Threat-model boundary B10 widens again**, one item after ADR-0087 widened it. Both lanes
  in this module now send content to a provider, and they send different things: distillation
  sends the projection, which doc 08 §6 has already redacted, and segmentation sends a paste
  this module redacts on the way out and refuses outright when redaction cannot preserve its
  shape.
- **No new CLI command and no change to `mycelium chats import`'s interface.** A setting and a
  configured provider are the whole of the operator-facing change, which is what doc 08 §6's
  *"off by default; when enabled"* describes.
- **The ceiling is a number this ADR chose**: 2000 lines, above which a paste is not offered
  to a model. It is not a guard against a known pathology — it is the statement that two
  thousand lines selected in a browser is a document rather than a conversation, and it bounds
  what a provider is asked to generate, since the proposal carries one entry per turn.
- **Nothing in the core changed.** The module reaches `mycelium.ingest` for the scan and the
  redaction and `mycelium.synthesis` for the provider, both already on the module-facing
  surface — the second added one item ago (ADR-0087). Doc 08 §10's sixth gate produced no new
  finding here, which is the first time it has not.

## References

- Spec: `.draft-specs/08-module-chats.md` §4 (the record, and invariant 2), §6 (the import
  table's fourth row, and the security defaults), §10 (the acceptance gates);
  `.draft-specs/02-architecture.md` §5 (quarantine, not abort).
- Decision log: D-013 (offline by default), D-017 (all source content untrusted), D-020 (the
  LLM lane is the additional one).
- Measured: `redact_text` on a paste holding an RSA private key returns 5 lines for 8 — the
  case `redacted_for_egress` exists to catch, asserted in
  `contrib/chats/tests/test_segment.py`.
- Tests: `contrib/chats/tests/test_segment.py`, and the reader's own change in
  `contrib/chats/tests/test_readers.py`.
