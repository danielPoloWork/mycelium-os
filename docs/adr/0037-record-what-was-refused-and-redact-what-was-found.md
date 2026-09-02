# ADR-0037: Record what was refused, and redact what was found

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.6; RFC-0001; spec 02 §5 (ingestion, quarantine), §8 (security
  posture); spec 03 §3 (`secret_flags`); spec 05 §2 (`[ingest] redact_secrets`); D-017;
  [ADR-0014](0014-adopt-partial-strict-configuration.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)

## Context

Two controls close out the ingestion milestone, and they are in one item because they are
the same sentence read from two ends: *what happens to a document that should not simply
pass through*.

**Quarantine.** Spec 02 §5 asks for three verbs — a malformed or hostile file is
*recorded, skipped, and reported*, and never aborts the build. Since roadmap 4.1
`mycelium ingest` has skipped and reported: each source is handled on its own, a failure
prints a warning, and the exit code is 1. The first verb was missing, and it is the one
that matters after the terminal scrolls. An operator ingests a directory, watches three
warnings go by, and an hour later cannot answer *which three, and why*. Worse, the answer
exists — ADR-0033 made ingestion store the acquired original **before** it tries to parse
it, precisely so a refused file can still be examined — and nothing pointed at it.

**Secret scanning.** Spec 02 §8: *ingestion runs a secret-pattern scan; hits are flagged in
the document record and excluded from indexing by default (`[ingest] redact_secrets`)*.
`Document.secret_flags` has been in the record contract since roadmap 2.2 and has been
empty ever since. The exposure is specific to the evidence lane and not hypothetical: an
ingested document is *somebody else's file*, and the lane's whole job is to write its
content into a Git working tree and then into an index. A credential in an exported wiki
page, a support ticket, or a PDF of a runbook becomes a credential in the repository, and
from there in every clone of it.

Both halves have one property that decides whether they survive contact with a real
corpus: **they must not cry wolf.** A quarantine that is red rather than amber, or a
scanner that fires on prose, is a control an operator switches off — which is strictly
worse than never having shipped it.

## Decision

**A refusal writes a record; the caller still decides what to do about it.**

`ingest_source` writes a `mycelium/quarantine/v0` record under `.mycelium/quarantine/` and
**re-raises**. Only the lane knows the media type and the custody digest at the moment
things went wrong, so only the lane can write them down; what to *do* about the failure
stays with the caller, as it was. One file per source, keyed by a digest of its URI, so
re-ingesting a failing source amends its record rather than accumulating another.
`first_seen` never moves and `last_seen` does, because "since when" and "just now" are
different questions. Nothing sweeps it — `mycelium gc` leaves the quarantine alone for the
reason it leaves custody alone (ADR-0033) — and nothing digests it, so the moving
timestamp cannot make anything non-reproducible.

**The stage is a type, not a sentence.** A record says which step refused the source —
`acquire`, `dispatch`, `guard`, `parse`, `budget` — because those are five different
operator actions, and `dispatch` (the bytes are readable, nothing pinned reads *that*) is
a configuration edit while `parse` is the file. To make that classification safe,
`GuardError` and `LossBudgetError` are split out of `ParseError` as subclasses: every
existing handler is unaffected, and the classifier reads the exception's type instead of
its prose.

**The scan always runs; `[ingest] redact_secrets` decides only whether it acts.** Flagging
is an observation, redaction is an action, and an operator who wants the verbatim text
should not silently also lose the record that a credential is in it. `secret_flags`
therefore reaches `Document` either way — through the **custody record**, ADR-0034's
mechanism: the projected document carries one link (`source_digest`) and every fact about
the evidence is read back from the record it points at, so the flags cannot drift from the
bytes they describe.

**Redaction happens before the KIR is stored**, which fixes where the credential lives:
**exactly one artifact.** The tier-1 original holds the bytes verbatim, because that is
what a citation is checked against and destroying it would destroy the evidence. Everything
derived from it — the KIR blob, the projection into `knowledge/evidence/`, the chunks, the
index, an export bundle — carries a self-describing placeholder, `[redacted: <rule-id>]`.
Redacting later would mean choosing which outputs to clean and remembering that list
forever.

**The rule set is closed, structural, and biased to precision.** Eleven rules, each
anchored on something that does not occur in prose: a vendor's fixed key prefix, PEM
armour, credentials in a URL's authority. **There is no entropy heuristic.** The negative
corpus is this repository's own `docs/` tree, asserted clean by a test, so documenting the
scanner cannot include a live-looking credential — the dogfooding is enforced rather than
intended.

## Alternatives Considered

- **Report failures to stderr only, as 4.1 did.** Cheapest, and it satisfies two of spec
  02 §5's three verbs. Rejected because the third verb is the one with lasting value, and
  the information it needs — the custody digest of the bytes that failed — is already
  being computed and thrown away.
- **Classify the quarantine stage by matching the error message.** It would have worked on
  the day it was written. Rejected: a classifier that reads sentences is one reworded
  message away from silently mislabelling, and nothing would catch it. Two exception
  subclasses cost eight lines and make the classification a type check.
- **Fail `doctor` when anything is quarantined.** Rejected. A quarantined source is the
  system working as designed; a repository whose health check goes red for one unreadable
  PDF teaches an operator to stop running it. `warn`, with the stage and the remedy in the
  line.
- **Add a `mycelium quarantine` command.** Rejected: spec 05 §1's command table is a
  permanent compatibility surface and this needs no verb of its own. Reporting belongs to
  `doctor`, which is already the diagnostic surface, and the one action that cannot happen
  by itself — forgetting a source that is never coming back — is `--forget` on the command
  that already takes sources as arguments.
- **Sweep quarantine records in `mycelium gc`.** Rejected for ADR-0033's reason, one level
  further out: the sweep an operator reaches for is the one they run when the store feels
  too large, which is the worst possible moment to lose the list of what never made it in.
- **Add an entropy/high-randomness rule so the scanner catches unprefixed secrets.**
  Rejected, and this is the decision the whole design turns on. High-entropy heuristics
  fire on base64 images, digests, UUIDs and minified code — all of which this project's own
  corpora contain. What it costs is stated rather than hidden: a bare password or a
  home-grown token goes through unflagged, and **this is not a substitute for a repository
  secret scanner**.
- **Redact only at projection time, leaving the KIR verbatim.** Simpler to write, and no
  additional exposure today, since the KIR blob sits under the same gitignored
  `.mycelium/`. Rejected because it makes the redaction a property of one output rather
  than of the compiled document: the next consumer of a KIR blob — a re-projection, an
  export, a future stage — would have to remember, and one day would not.
- **Quarantine a document whose secrets were found while `redact_secrets = false`.**
  Rejected: an operator who switched redaction off asked for the content, and refusing it
  instead would be a second, unrequested behaviour hiding behind one setting.
- **Scan authored Markdown at build time too.** Out of scope by the spec's own words
  ("secret scan at *ingestion*") and by the trust model: an authored document is the
  operator's own writing in their own repository, and a compiler that redacted it would be
  editing tier 2. Worth an RFC if it is ever wanted; not worth assuming.

## Consequences

- **`mycelium ingest` gains a durable failure trail.** Five stages, the reason, the
  message, and the custody digest of the bytes — so "quarantined" now means the file can
  be *opened again*, which is what distinguishes it from "dropped".
- **`[ingest]` is honoured in full.** `redact_secrets` was the last accepted-and-inert key,
  so `unhonoured_keys` is empty and `eval` is the only unhonoured section left (ADR-0014's
  promise, discharged for this section).
- **`mycelium doctor` gains two conditional checks.** `quarantine` appears only when
  something is quarantined; `secrets` appears only when redaction is *off*, because the
  default configuration needs no line and the other one is a deliberate choice that should
  be visible somewhere other than a config file nobody re-reads.
- **A new stable-ish artifact.** `mycelium/quarantine/v0` joins the exported JSON Schemas
  beside `custody` and `fidelity` — an operator-facing file on disk that another tool may
  read. It is not a snapshot artifact class: a quarantine is a fact about a *machine's
  attempt to ingest*, not about a published snapshot.
- **`Dead Letter Channel` is catalogued** (EIP): undeliverable messages diverted for
  inspection rather than dropped or blocking the pipeline. It fits without being pushed,
  which is the test §8 sets.
- **The verbatim credential still exists in tier-1 custody**, and must. `.mycelium/` is
  gitignored, so it does not reach a clone — but an operator who needs the credential gone
  from a machine entirely has to delete the original, and doing so is the loss of the
  evidence behind that document's citations. The threat model records this as the residual.
- **Recall is deliberately incomplete**, and the README says so rather than implying
  coverage the eleven rules do not have.
- **No golden re-bless.** `redact_secrets` was already part of the config digest, and a
  document with no credentials is returned by the scan *identically* — not merely equal —
  so gate G6's corpus is untouched. The scan costs one linear pass per node text.

## References

- Spec 02 §5 (recorded/skipped/reported; quarantine never aborts a build), §8 (secret scan
  at ingestion, `redact_secrets`); spec 03 §3 (`Document.secret_flags`); spec 05 §2.
- D-017 (all source content untrusted, including the user's own).
- [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md) — storing the original before
  parsing, which is what a quarantine record points at, and the "custody is never swept"
  rule this extends to the quarantine.
- [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) — one frontmatter key,
  every other fact read back from the custody record; the mechanism `secret_flags` reuses.
- `docs/patterns/design-patterns.md` §EIP — Dead Letter Channel.
