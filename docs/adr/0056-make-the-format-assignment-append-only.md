# ADR-0056: Make the format assignment append-only, and let the regeneration check replace the rule it made impossible

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.26; RFC-0001; spec 04 §§7.1, 7.3, 7.6; D-010;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0039](0039-measure-what-projection-costs.md),
  [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md),
  [ADR-0051](0051-hold-the-judgements-fixed-too.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md);
  [BUG-0018](../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)

## Context

ADR-0052 gave gate G3 a rule it needed — enforce a slice only when it holds at least four
judged cases and a baseline above zero — and the honest consequence was that `uv/release`,
the set G3 *does* enforce (ADR-0053), read **`1 of 6 slice(s) enforced`**. One row. Four of
the other five held one, two or three cases; the sixth is `unanswerable`, whose correct score
is zero and which G4 gates instead.

Eight cases had been written to fix that at roadmap 4.20 and could not land. Two couplings
stopped them, and neither was about the judgements:

**The format rotation was position-dependent.** The third corpus is the second one rendered
into DOCX, HTML and PDF and put back through the ingestion lane. The documents a judgement
points at, *sorted by path*, took the three formats in rotation. Three of the new cases newly
judge `projects/run.md`, `projects/sync.md` and `getting-started/features.md`, which sort
*between* documents already judged — so every index after them shifted and the format of
already-rendered documents changed. Those renderings are committed provenance that cannot be
re-derived: typst embeds a build identifier, measured at ADR-0039. Landing the cases would
have re-rendered the corpus and moved ADR-0039's per-format cost table with it, for no reason
connected to the cases.

**A derived set could not follow its source.** `tools/check_frozen_release_sets.py` forbade a
derived set moving in the same change as the judged set it is carried from. But a derived set
*is a function of* that source: growing the source must regenerate the carry, CI byte-checks
the carry, and a regeneration on its own has nothing to regenerate from. The rule and the
requirement could not both be satisfied, and no ordering of two PRs helped. Roadmap 4.15 met
the same deadlock from the chunking side.

The tempting escape was to rewrite the offending cases so they only touch documents already
judged. That is the one option that is certainly wrong: it lets the tooling decide what gets
judged, which is a quieter version of what the frozen-set discipline exists to prevent.

## Decision

**The format assignment is append-only, over a recorded order.** A new committed file,
`eval/corpora/uv-docs-ingested/format-rotation.json`, holds the order in which judged
documents took their formats. The rotation runs over *that list*, not over the judged paths
re-sorted on every run. A newly judged document appends and takes the next format in the
cycle; nothing already rendered moves. A document that stops being judged keeps its slot,
because the file on disk is the evidence and the order is the record of how it got there.
`--render` becomes incremental to match: it writes what the plan asks for and disk does not
have, and removes a stale rendering of the same document in another format.

The assignment therefore stops being derivable from the case sets alone. That is the trade,
and it is the same one ADR-0039 already made about the renderings themselves: a corpus whose
inputs cannot be re-derived byte-for-byte has to *keep* them, and the assignment is one of
those inputs.

**The derived-set rule is retired, and the regeneration check is what replaces it.**
`tools/build_ingested_cases.py --check` regenerates the carry from the source set and the
corpus and byte-compares it, in CI, on every run that touches either (roadmap 4.16,
BUG-0018). That is a *direct* check of the property the retired rule was a proxy for — "this
file was not hand-written" — and it holds whichever commit the file arrived in. `DERIVED_SETS`
is kept as an empty mapping rather than deleted, so the shape of the rule stays visible and
re-arming it is one line if the reproduction check ever stops running.

**Nine cases land, not eight.** Eight were drafted; `symbol` needed a third to reach four, so
`uv export` joins `uv lock --check` and `uv python pin`. The result is `conceptual` 4,
`exact` 5, `fact` 7, `relationship` 4, `symbol` 4, `unanswerable` 2 — and G3 goes from
**1 of 6 slices enforced to 5 of 6** on both frozen sets.

**Both frozen baselines are re-blessed in this change, and ADR-0053's rule is narrowed to
say so.** That ADR wrote "a re-bless is its own PR … and it never rides along with a
retrieval or a judgement change". The first half is right and stays. The second half was
over-general — it was reasoned about our own *reported* baseline, where nothing is disarmed
because nothing was armed. On an **enforced** set the opposite holds: a case-set change moves
`cases_digest`, which disarms G3 by design (ADR-0051), and a PR that grows a set without
re-blessing leaves the only enforcing gate switched off with nobody accountable for switching
it back. So: a bless must never ride with a **retrieval** change — that conjunction is what
could fit the retriever to the set, and `check_frozen_release_sets.py` still refuses it — and
a bless **must** ride with a judgement change on an enforced set. Roadmap 4.12 already worked
this way; this states why.

## Alternatives Considered

- **Re-render the corpus and re-measure ADR-0039's per-format table.** The item's other
  option. Rejected on cost and on provenance: every PDF changes bytes for a build identifier
  rather than for content, the committed inputs a measurement was taken on are replaced by
  different inputs saying the same thing, and the cost table moves for a reason unrelated to
  the change that moved it. Append-only re-rendered **two** documents instead of eighty-one.
- **Assign the format from a hash of the path.** Stateless and stable under insertion, which
  is exactly what was wanted. Rejected because adopting it re-rolls all seventeen existing
  assignments on the first run — the same full re-render, arrived at more cleverly.
- **Keep the sorted rotation and confine new cases to documents already judged.** Rejected as
  the one clearly wrong answer: it makes the rendering tooling the arbiter of what may be
  judged, and a judged set shaped by what is convenient to render is not an independent
  measurement (ADR-0027).
- **Weaken the derived-set rule instead of retiring it** — for instance, allow the pair to
  move together only when the generator's check also runs. Rejected as the same guarantee
  written twice: if the check runs, the rule adds nothing; if it does not, the rule is the
  wrong control for the gap.
- **Land the cases without re-blessing, and re-bless in a follow-up.** Rejected: it ships a
  set that arms five rows together with a gate that enforces none of them, and it makes
  re-arming the only enforcing gate in the project somebody's future errand. The per-slice
  and per-case diff in the PR body is what makes the bless reviewable instead.

## Consequences

- **G3 enforces five rows on each frozen set instead of one.** `conceptual`, `exact`, `fact`,
  `relationship` and `symbol`; `unanswerable` stays reported, which is correct.
- **`symbol` stops being a row that cannot fail.** It was blessed at 0.0000 on a single case,
  so no relative threshold could ever trip it. It now reads **0.585** on `uv/release` over
  four cases — a row that can move, on a slice that could not.
- **The corpus grew by two renderings.** `projects/run.md` → PDF, `projects/sync.md` → DOCX;
  `getting-started/features.md` was already HTML and the plan agrees, so it was not touched.
  Seventy-nine renderings are byte-identical, and the per-format counts move from
  docx 6 / html 70 / pdf 5 to docx 7 / html 68 / pdf 6.
- **ADR-0039's per-format table is re-measured**, as the item required, and now rests on 8
  docx, 4 html and 7 pdf attributable cases. PDF still *gains* on projection (+0.195 nDCG@10)
  and the reason is in the same table: its judged passages are 5.4× the tokens of the
  Markdown original, so a hit is easier. Reported, never gated (ADR-0039).
- **Two of the nine new cases score 0.0000 under both shipped profiles**, and the reason is
  the same for both: `u-1023` and `u-1024` name documents that answer them in words the query
  does not use. Hybrid retrieval does not rescue either — measured, with vectors present —
  which is a sharper statement than "lexical cannot reach them" and points at ADR-0025's
  precondition: a vector leg that only re-ranks what the lexical leg found cannot introduce a
  document the lexical leg missed. Filed as roadmap **4.33**, not fixed here.
- **`u-1007` is still 0.0000** while the three new `symbol` cases score 0.63 to 1.00. The
  slice is armed with one member it has never served, which is now visible per case rather
  than hidden in a mean of one.
- **A re-bless of an enforced set now has a stated rule** rather than a precedent, and the
  rule differs from the one for the reported set — which is the distinction ADR-0053 collapsed.
- **The verification would not have run on this change.** `eval/corpora/**` matched
  `eval/` and derived `retrieval` (ADR-0055), which builds and gates *our* corpus — not the
  vendored ones, which only `full` gates and which are the sets G3 enforces on. So growing
  `uv/release` would have left `uv/release`'s own G3 unrun, locally and in CI. A corpus path
  now derives `full`. The wider question — whether every *retrieval* change should gate the
  vendored corpora, which is a change to ADR-0055's measured economy — is filed as roadmap
  4.35 rather than decided here.
- **The assignment is no longer a pure function of the case sets.** A reader checking it reads
  a committed list rather than re-deriving it, and the tests assert the list against the
  corpus on disk in both directions: every judged document has a slot, no slot repeats, and
  inserting a document that sorts first moves nothing.

## References

- Spec 04 §7.1 (frozen release sets), §7.3 (the gates), §7.6 (set size at 1.0).
- Measured this session: `uv/release` `1 of 6` → `5 of 6` slices enforced; mycelium
  0.5483 → 0.5858 and grep 0.5190 → 0.4849 on 25 cases; `uv-ingested/release` mycelium
  0.6469 → 0.6153, grep 0.5663 → 0.5046. Exactly three pre-existing cases moved on each
  corpus, all in `fact` — PR #75's retrieval gain, deliberately left unblessed there and
  booked here.
- [ADR-0039](0039-measure-what-projection-costs.md) — why the renderings are committed,
  and the build identifier that makes them irreproducible.
- [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) — the four-case rule this grows a
  set to satisfy.
- [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) — which
  sets a gate can live on, and the sentence this ADR narrows.
