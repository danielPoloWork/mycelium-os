# ADR-0089: Put content identity in the citation, and make the grammar extensible first

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §2, spec 02 §10
- **Related:** [ADR-0078](0078-report-a-moved-citation-rather-than-serving-it-in-silence.md) (the
  positional check, and the blind spot it named), [ADR-0005](0005-adopt-in-repo-identity-library.md)
  (the URI grammar and its deliberate departure from RFC 3986),
  [ADR-0009](0009-adopt-build-publication-semantics.md) (pinned identity, which is what makes a
  citation outlive a rename), [ADR-0011](0011-implement-mcp-stdio-in-repo.md) (the tool surface),
  [ADR-0014](0014-adopt-partial-strict-configuration.md) (the strictness this one deliberately
  inverts), [ADR-0007](0007-adopt-structure-first-chunking.md) (anchor survival as best-effort);
  spec 02 §§10, 11, spec 03 §§1, 2, 3.1, spec 05 §3.2; NFR-8; roadmap 5.6, 5.17

## Context

ADR-0078 made `mycelium_fetch` honour the `?lines=a-b` it had always minted and then ignored, so
a citation whose passage had moved came back annotated rather than in silence. It closed five of
the six drifts the roadmap 5.6 proof corpus produces and stated the sixth as a limit:

> It cannot see an edit that rewrites a passage in place without changing its length: same
> anchor, same range, different words.

That case was pinned by `test_an_in_place_edit_is_the_blind_spot` — a test written to fail the day
the limit was lifted, and to be the receipt whoever lifted it had to collect. Roadmap 5.17 is that
day, and the item was filed with three questions attached, because the fix touches the citation
URI and the URI is part of the identity rules, one of the five contracts NFR-8 freezes at 1.0:

> what an old client does with a URI carrying an unknown query key, whether the digest is
> truncated and to what, and whether `mycelium_search` mints it too — it must, because a citation
> is *born* there and a digest only reachable from `mycelium_fetch` is a tool nobody can pick up
> when they need it.

## Decision

**The grammar becomes extensible before anything is added to it, and that is the first decision
rather than a side effect.** `parse_citation_uri` refused any query key but `lines=`. That made
the grammar unextendable in the only direction it ever needed to grow: a URI carrying `digest=`
would have been rejected *outright* by every earlier client — not degraded, not ignored, but
refused, along with the anchor it plainly names. So an unrecognised query key is now **ignored**.

This is the opposite of how `mycelium.toml` is read, and ADR-0014 was right there and is still
right: an operator who mistypes a config key must be told, because the file is theirs and silence
would be a lie about their intent. **A citation's author is usually another program, often a newer
one, and there is nobody at the terminal to tell.** A citation travels between versions inside
agents' transcripts — outside anything this product can reach or migrate (ADR-0078 established
that when it declined spec 02 §11's "validate stored citations"). Forward compatibility is the
property that matters for an identifier in that position.

The cost is real and is named rather than discovered later: `?line=1-9` — a typo — is ignored
rather than refused, so the citation carries no evidence of what it pointed at. It then degrades
to exactly the hand-written case ADR-0078 already defined, where absent evidence means silence
rather than a guess. A citation that checks nothing is worse than a refusal; a citation last
year's client cannot resolve at all is worse than both.

**Minting is strict; parsing is forgiving.** `citation_uri` refuses a digest it cannot write, and
`parse_citation_uri` never refuses one it cannot read. A minting bug is this product getting its
own grammar wrong and must fail loudly; an unreadable value in an incoming URI must not take the
anchor down with it. The asymmetry is the one every durable format needs, and it is stated in both
functions.

**A malformed *known* key is still an error.** `lines=5` and `lines=9-4` raise as they always did.
Leniency is for keys this parser has never heard of, not for the ones it defines — otherwise the
grammar has no shape at all.

**Every minted URI carries `&digest=<hex>`**, twelve characters of the chunk's own
`chunk_digest`, untagged. That answers the item's third question by construction: there is exactly
one mint point (`mycelium.citations.chunk_uri`, the single implementation ADR-0078 consolidated),
so `mycelium_search`, `mycelium_fetch`, `mycelium show` and `mycelium_neighbors` all mint it or
none do. ADR-0078 rejected a digest reachable only from `mycelium_fetch` as a half-mechanism; this
avoids the shape rather than resisting it.

**Twelve characters, and the number is smaller than it looks** because the comparison is *not* a
birthday problem. The digest never finds a chunk — the anchor does that — it only asks whether the
chunk the anchor resolved to is the one that was cited. A miss therefore needs one specific
rewritten passage to share a prefix with one specific old one: about 1 in 2.8e14. Git has run on
seven characters for twenty years at a harder job. The `sha256:` tag is dropped because spec 03 §1
fixes the algorithm for every digest in the system, so spelling it in every citation would be
seven characters restating what the grammar already says.

**The parser accepts 8 to 64 hex characters and the check compares on the shorter.** A URI
assembled by hand from an exported `chunk_digest` — all sixty-four of it — works beside one this
product minted, because the current value is cut down to the cited length rather than the cited
one padded out. Eight is the floor: below it the check stops being one.

**The two signals are checked independently, and the report says which fired.** `lines` is *where*
the passage sat and `digest` is *what it said*, and a passage can move without changing or change
without moving. So `Drift` carries a `kind` — `moved`, `rewritten`, `moved_and_rewritten` — with
its own sentence for each, because they call for different reading: a moved passage is the text
that was cited at a new address, so the remedy is the corrected URI; a rewritten one is different
text at the same address, so the remedy is to read it again. ADR-0078 had one sentence for both
and had to say *"has moved"* even when the words were what differed.

**An old client refuses a new URI, and pre-1.0 is exactly when that is allowed.** A 0.4.x parser
meets `&digest=` and raises `IdentityError`. There is no way to avoid that for clients already
shipped — which is the whole argument for doing this **now**: NFR-8 freezes the identity rules
*at 1.0*, and this is the last window in which the grammar can gain a field at all. It ships with a
CHANGELOG migration note rather than a version negotiation, because a citation URI has nowhere to
carry one.

## Alternatives Considered

- **Keep refusing unknown query keys and add `digest=` anyway.** Status quo plus the field.
  Rejected: it makes every *future* extension another breaking change, and it is the reason this
  one is breaking. Fixing the leniency is the durable half of the item.
- **Put the full 64-character digest in the URI.** No truncation argument to make. Rejected: a
  citation is a string a human pastes and an agent logs, and seventy-one characters of hex buys
  nothing — the digest is a comparison, never a lookup, so the tail is never read.
- **Keep the `sha256:` tag.** It names the algorithm, which a future change would need. Rejected:
  spec 03 §1 fixes SHA-256 for every digest in the system, and an algorithm change would move the
  whole grammar anyway. Seven characters on every citation to restate a constant.
- **Return the digest in the response and let consumers pin content themselves.** Additive, no
  grammar change, no compatibility question. Rejected by ADR-0078 already, for the reason that
  still holds: a citation is *born* in `mycelium_search`, so a mechanism reachable only from
  `mycelium_fetch` arrives after the consumer is already holding a URI that lacks it.
- **A second scheme or a version segment — `mycelium2://`, or `mycelium://v2/…`.** It would let old
  clients reject cleanly and by name. Rejected: it forks the one durable identifier this product
  hands out, and every consumer would have to learn both forever, to solve a problem that exists
  only for citations minted by one 0.x version and read by another.
- **Report drift only when the content changed**, now that the two can be told apart. Tempting: it
  removes ADR-0078's admitted false alarms. Rejected: the line range in the consumer's URI is
  *genuinely* out of date after a move, and the block hands back the corrected citation. The right
  fix for a noisy report is to say what happened, which is what `kind` does.
- **Make the ordinal content-derived so anchors cannot drift at all.** Rejected again for
  ADR-0078's reason, unchanged: it moves every anchor in every corpus, invalidates every judged
  case set and every baseline, and trades a detectable problem for a re-anchoring project.
- **Validate and rewrite stored citations at build time** (spec 02 §11's own phrasing). Still not
  applicable: this product stores no citations. The phrase becomes actionable at the Phase-5
  server.

## Consequences

- **The proof corpus now reports every drift it produces, with no exception.** Measured across all
  eleven refactorings: zero citations come back `SURVIVED` with changed content, where ADR-0078
  left exactly one. `test_a_changed_passage_is_never_served_in_silence` loses the branch that
  carried the exception, and the outcome table gains the column that was missing:

  | refactoring | citation | before | now |
  |---|---|---|---|
  | edit prose in place | `#retries/0` | silently served | `rewritten` |
  | insert a paragraph mid-section | `#retries/0`, `#storage/0` | `moved` | `moved`, text confirmed intact |
  | insert a paragraph mid-section | `#event-bus/0` | `moved` | `moved_and_rewritten` |
  | reorder two sections | both | `moved` | `moved_and_rewritten` |
  | rename the first of two alike headings | `#event-bus/0` | `moved` | `moved_and_rewritten` |

  The middle row is the one worth reading twice: those two citations were *always* reported, and
  the report could never say that their text was fine. Now it does.
- **`test_an_in_place_edit_is_the_blind_spot` is gone**, replaced by
  `test_an_in_place_edit_is_reported_by_its_content`. It was written to be the receipt for this
  item, and this is it being collected.
- **A citation grows by about twenty characters**, which is the honest price of the field.
- **The `stale` block gains `kind`, `cited_digest` and `current_digest`**, additively, and the
  `mycelium_fetch` description now tells an agent what each kind means and what to do about it.
  The tool's *input schema* is unchanged, so the MCP contract (spec 02 §10's fourth) is untouched.
- **Spec 03 §2 is amended**, per AGENTS.md §7's spec-or-ADR rule, taken as both: the grammar line
  gains `[&digest=<hex>]` and the cell states that both queries are evidence, that they are checked
  independently, and that an unknown key is ignored while a malformed `lines=` is not.
- **A citation minted before this item behaves exactly as ADR-0078 made it behave** — reported when
  it moves, silent when the words change under it — and that is its own test. A new field cannot
  retroactively improve an old citation and must not break one.
- **No golden and no baseline moves.** Checked rather than assumed: neither the G6 golden nor any
  judged case set embeds a citation URI — they name anchors — so nothing here is a re-bless.

## References

- Spec: `.draft-specs/03-data-model.md` §1 (SHA-256 for every digest), §2 (the citation URI, as
  amended), §3.1 (`ANCHOR_GONE`); `.draft-specs/02-architecture.md` §10 (the five contracts and
  the 1.0 freeze), §11 (failure modes).
- Measured: every refactoring's drift kind, from the roadmap 5.6 proof corpus — the table above,
  reproduced by `tests/test_stale_anchors.py`.
- Tests: `tests/test_stale_anchors.py` (the proof corpus, the closed blind spot, the
  moved-but-intact case, and the pre-5.17 citation), `tests/test_sdk_identity.py` (the grammar,
  the leniency, the mint/parse asymmetry, and the round-trip property).
