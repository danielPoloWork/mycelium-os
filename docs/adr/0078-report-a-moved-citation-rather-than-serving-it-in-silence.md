# ADR-0078: Report a moved citation rather than serving it in silence

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §3.1, spec 02 §11
- **Related:** [ADR-0007](0007-adopt-structure-first-chunking.md) (structure-first chunking,
  where anchor survival is declared best-effort), [ADR-0009](0009-adopt-build-publication-semantics.md)
  (identity pinned at first build, which is what makes a citation outlive a rename),
  [ADR-0010](0010-adopt-cli-output-conventions.md) (the CLI's prose form of `ANCHOR_GONE`),
  [ADR-0011](0011-implement-mcp-stdio-in-repo.md) (the tool surface this changes),
  [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md) (which told consumers
  to *expect* `ANCHOR_GONE` after packing); spec 02 §§10, 11, spec 03 §§2, 3.1, spec 05 §3.2;
  D-021; roadmap 5.6, 5.17

## Context

Spec 03 §3.1 makes one promise about a citation into a document that has since been edited:

> the build validates all stored citations, and `mycelium_fetch` returns typed `ANCHOR_GONE`
> with the nearest ancestor **rather than silently wrong content**

Roadmap 5.6 is the Milestone 5 exit gate that asks for that to be *proven on a heavily
refactored corpus*. Proving it meant building the corpus the gate names: eleven named
refactorings, every citation a consumer could hold minted before each one, and every
citation classified after the rebuild. The result is `tests/test_stale_anchors.py`, and it
is the deliverable — a gate, not an anecdote, because each refactoring pins its whole
outcome map by citation name.

**Most of the promise held.** A renamed heading, a section re-nested one level deeper and a
section moved into a new document all produce `ANCHOR_GONE`, and the nearest ancestor each
one names really resolves. A deleted document produces `NOT_FOUND`. A *renamed file* and a
`verified/` → `candidate/` move cost nothing at all — which is D-021 working exactly as
designed, and worth stating, because keying citations on `doc_id` rather than on a path is
the reason.

**One part did not hold, and it is the part the sentence is about.** An anchor is
`(path, heading-slug-path, ordinal)`, and **the ordinal is a position**. Four refactorings
that leave the heading path intact move the passage underneath it:

| refactoring | what the consumer's citation resolved to |
|---|---|
| delete a paragraph mid-section | the *next* passage in that section |
| insert a paragraph mid-section | the *previous* passage |
| reorder two sections | the other section's passage |
| rename the first of two headings that slugify alike | the second section — it inherits the unsuffixed slug |

Six citations across five refactorings resolved to content they were never minted against,
and **not one of them said so**. The last row is the sharpest: rename `## Event bus` where a
second `## Event bus` follows it, and a citation to the first silently returns the second.
An agent that re-quotes it has fabricated an attribution, which is the failure this whole
product exists to prevent.

The mechanism to fix it was already present and unused. Every URI this product mints — from
`mycelium_search`, from `mycelium show`, from `mycelium_fetch` itself — carries `?lines=a-b`,
the spec's own optional query (spec 03 §2). `mycelium_fetch` parsed it and then ignored it
entirely.

## Decision

**`mycelium_fetch` and `mycelium show` honour the line range they have always minted, and a
citation whose passage has moved is served with a `stale` block rather than in silence.**
When the range in the caller's URI is not the range that anchor occupies now, the response
carries `cited_lines`, `current_lines`, the URI to cite instead, and one sentence saying the
passage has moved and must be re-read before being re-quoted. `mycelium show` prints that
sentence and puts the same block in its `--json`.

**Drift is not an error.** The anchor exists and its current content is the truth at that
anchor. Refusing to serve it would break every consumer holding a citation into a document
under active editing, which is every consumer; and `ANCHOR_GONE` would be a lie, because the
anchor is precisely what did *not* go. So the content is returned, annotated.

**A citation with no line range is not judged.** `?lines=` is optional, and a URI somebody
typed by hand carries no evidence of what it pointed at. Absent evidence, the honest answer
is silence rather than a guess.

**One implementation, in `mycelium.citations`.** The CLI and the MCP server hand out the
*same* citation and a consumer may hold one from either, so minting and drift-checking are
one module both import. They had two private copies of the minting function, agreeing by
coincidence; now that the range they write is load-bearing, coincidence is not good enough.

**The limit is stated, not papered over.** The line range is *positional*. It sees every
refactoring that moves a passage — five of the six drifts on the proof corpus — and it
cannot see an edit that rewrites a passage in place without changing its length: same
anchor, same range, different words. That case is pinned by
`test_an_in_place_edit_is_the_blind_spot`, named in the `mycelium_fetch` tool description so
an agent reads it, and filed as **roadmap 5.17**. Closing it needs *content* identity in the
citation, which changes one of the five contracts that freeze at 1.0 (spec 02 §10) and is
not a size-S item's to decide.

**Reporting a move is conservative, and that is deliberate.** A passage that shifted down
the file without changing a word is reported too: its text is intact, but the line range in
the consumer's URI is genuinely out of date, and the block hands back the corrected
citation. A false alarm costs a re-read; a missed drift costs a fabricated quotation.

## Alternatives Considered

- **Return `ANCHOR_GONE` for a moved passage.** Symmetrical with the existing error and
  needs no new field. Rejected: the anchor did not go. It would turn every edit above a
  cited section into a hard failure for a consumer whose citation is still perfectly usable,
  and it would make the error mean two different things.
- **Compare content instead of position, by putting a chunk digest in the citation URI.**
  The exact fix — no false alarms, no blind spot. Rejected *here*, not on its merits: the
  URI grammar is part of the identity contract that freezes at 1.0 (NFR-8), so extending it
  is a decision that deserves its own item and its own argument, with the compatibility
  question answered. Filed as roadmap 5.17 with this ADR's measurements in hand.
- **Return the chunk digest in the response so a consumer can pin content itself.** Additive
  and cheap. Rejected as a half-mechanism: a citation is *born* in `mycelium_search`, so a
  digest only in `mycelium_fetch` is a tool nobody can pick up at the moment they need it.
  Shipping half of 5.17 would make the whole of it harder to argue.
- **Validate and rewrite stored citations at build time**, which is spec 02 §11's own phrasing.
  Rejected as not applicable yet: this product stores no citations. They live in agents'
  transcripts, outside anything the build can reach. The phrase becomes actionable at the
  Phase-5 server, where sessions are stored, and is left to it.
- **Make the ordinal stable** — derive it from content rather than from position — so the
  anchor cannot drift at all. Rejected as the wrong layer and a much larger change: it moves
  every anchor in every corpus, invalidates every judged case set and every baseline, and
  trades a detectable problem for a re-anchoring project. The measurement says detection is
  enough.
- **Report drift only when the text also changed.** Cheaper to explain, and it removes the
  conservative false alarms. Rejected because `mycelium_fetch` cannot know the old text —
  only the old *position*, from the URI. Inferring "changed" from "moved" is exactly the
  guess this module refuses to make.

## Consequences

- **Six silent drifts become six reported ones**, and the proof that says so is a permanent
  gate. `tests/test_stale_anchors.py` pins eleven refactorings × every citation; a change to
  the chunker, the anchor scheme or the slug rule now shows up as a *named citation* moving
  between columns rather than as a number nobody reads.
- **The MCP response gains `stale`** (`null`, or the block), and `mycelium show --json` gains
  the same key. Additive and pre-1.0; the tool description states both what is detected and
  what is not, because an agent reads that description and nothing else.
- **`mycelium.citations` removes a duplicated minting function** from `mycelium/cli/app.py`
  and `mycelium/mcp/tools.py`. The two were identical; keeping them identical was nobody's
  job.
- **A known blind spot, with a receipt.** An in-place rewrite of identical length is not
  detected. It is one row in the proof table, one test whose docstring says it is roadmap
  5.17's receipt, and one sentence in the tool description. If 5.17 lands, that test fails
  and has to be updated, which is the point of writing it that way.
- **No store, schema, build or retrieval change.** Gate G6's golden is untouched, and no
  judged case, baseline or corpus moves — the change is in what two read surfaces *say*
  about what they return.
- **Found and stated, not fixed:** `mycelium show` reports an unknown document behind a
  `mycelium://` URI as exit 2 (usage) with a doubled message, where the same document behind
  a path anchor is exit 1 (failed). Cosmetic, out of this item's scope, and noted in the
  journal rather than filed — it is one line in `_resolve` for whoever next edits it.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (the citation URI and its `?lines=` query), §3.1
  (the promise this ADR keeps); `.draft-specs/02-architecture.md` §10 (the five contracts
  that freeze), §11 (the failure-mode table's stale-anchor row);
  `.draft-specs/05-interfaces-and-plugins.md` §3.2 (`mycelium_fetch`).
- Decision log: D-021 (folder-encoded status, and why a citation keys on `doc_id`).
- Tests: `tests/test_stale_anchors.py` (the proof corpus and its outcome table),
  `tests/test_cli.py::test_show_says_so_when_the_cited_passage_has_moved`.
- Re-runnable: `pytest tests/test_stale_anchors.py -v` prints one line per refactoring.
