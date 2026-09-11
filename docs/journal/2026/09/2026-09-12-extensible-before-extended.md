# 2026-09-12 — extensible before extended (roadmap 5.17)

- **Session scope:** roadmap 5.17 — content identity in the citation URI, closing the blind
  spot ADR-0078 named and left pinned.
- **PR:** #116 (`feat/citation-content-identity`). Follows #115, merged as `d5819c7`.
- **Milestone 5:** 5.17 done. Nothing new filed.
- **ADR:** [ADR-0089](../../../adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-extensible.md).

## The item was about a field; the work was about the grammar

5.17 asked for a chunk digest in the citation URI, and listed three questions to answer
first: what an old client does with an unknown query key, whether the digest is truncated,
and whether `mycelium_search` mints it. The second and third turned out to be short. The
first turned out to be the item.

`parse_citation_uri` accepted `lines=` and raised on everything else. So adding `digest=`
would not have *degraded* on an earlier client — it would have been refused outright, along
with the anchor sitting plainly in front of it. Every future extension would have had the
same problem, for the same reason, forever. The field is one afternoon; the grammar's ability
to hold a field is the thing worth landing.

An unrecognised query key is now ignored. That is the opposite of how this project reads
`mycelium.toml`, and I had to be sure the difference was real rather than convenient.
ADR-0014 refuses an unknown config key because the file belongs to the operator and silence
would misrepresent what they asked for. A citation's author is usually another program, often
a newer one, and there is nobody at the terminal to tell — the URI is an identifier moving
between versions inside transcripts that nothing here can reach, which ADR-0078 had already
established when it declined the spec's "validate stored citations". Forward compatibility is
what matters in that position.

The cost is a typo: `?line=1-9` is now ignored rather than refused, so the citation carries no
evidence. It degrades to the hand-written case ADR-0078 already defined, where absent evidence
means silence rather than a guess. I wrote that down in the parser rather than leaving it to be
discovered, because it is the one place where the lenient direction is worse.

And the asymmetry, which I think is the part worth reusing: minting is strict, parsing is
forgiving. `citation_uri` refuses a digest it cannot write; `parse_citation_uri` never refuses
one it cannot read. A bug in our own minting must fail loudly. A bad value arriving from
elsewhere must not take the anchor down with it.

## The measurement paid twice

The obvious win was the blind spot. `edit prose in place, keeping every heading` had been
returning changed words under an unchanged citation in silence, and the digest sees it: same
lines, different content, `kind: rewritten`. The test that was written to fail on this day
failed on this day, and got replaced by its closed counterpart.

The gain I had not predicted is in the other direction. Under `insert a paragraph
mid-section`, two citations — `#retries/0` and `#storage/0` — were *already* being reported by
ADR-0078, correctly, because their line ranges had shifted. What the report could not say was
that their text was untouched. It had one sentence for every drift and that sentence was "has
moved", which for a rewritten passage was misleading and for an intact one was alarming. With
two independent signals the block can say *the words are unchanged, here is the corrected
URI*, which is a reassurance rather than a warning. ADR-0078 accepted its false alarms
explicitly and called the trade worth it; this did not remove them, it made them informative,
which is better than removing them would have been.

Twelve hex characters, and I want to record why that number is not nervous. The digest never
*finds* a chunk — the anchor does that — so a miss needs one specific rewritten passage to
share a prefix with one specific old one. That is a per-comparison probability, about 1 in
2.8e14, not the birthday bound a corpus-wide index would face. Git has run on seven for twenty
years at a harder job.

## What I checked rather than assumed

Whether anything judged embeds a citation URI. If the G6 golden or a case set carried one,
this would have been a re-bless and a much larger change. They carry *anchors*, so nothing
moved. Two greps, and they turned a suspicion into a line in the ADR.

## Lesson

When an item proposes adding something to a format, the first question is not what to add. It
is whether the format can be added to at all — and if the answer is no, that is the item, and
the field is the easy part that follows. A parser that refuses what it does not recognise is a
parser that has decided its grammar is finished.
