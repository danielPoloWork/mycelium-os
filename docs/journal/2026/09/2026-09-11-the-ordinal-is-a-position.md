# 2026-09-11 — the ordinal is a position (roadmap 5.6)

- **Session scope:** roadmap 5.6 — prove stale-anchor handling on a heavily refactored corpus
  (`ANCHOR_GONE` semantics), a Milestone 5 exit gate (spec 03 §3.1, spec 02 §11).
- **PR:** #105 (`fix/report-a-moved-citation`). Follows #104, merged as `ff043e4`.
- **Milestone 5:** 5.6 done; 5.17 filed. Remaining open: 5.7, 5.9–5.17.
- **ADR:** [ADR-0078](../../../adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md).

## The item said "proven", so the deliverable is a proof

Not a test of a function — a corpus of *changes*. Three documents, every citation a consumer
could be holding minted before each change, one of eleven named refactorings applied, rebuild,
and classify every citation into survived / moved / gone / missing. The outcome map is pinned
per refactoring **by citation name**, so a future change to the chunker, the anchor scheme or
the slug rule reports itself as `architecture.md#event-bus/0 moved from GONE to MOVED` rather
than as a count that nobody reads.

Most of the promise held, and two rows are worth stating because they are the design working:
a **renamed file** and a **`verified/` → `candidate/` move** cost nothing at all. That is D-021
— citations key on the pinned `doc_id`, not on a path — and it is the case the whole
identity-pinning apparatus was built for.

## What the proof found

An anchor is `(path, heading-slug-path, ordinal)`. The heading path is stable under everything
except a rename, which is the designed death. **The ordinal is a position**, and that is the
part nobody had tested:

| refactoring | the held citation resolved to |
|---|---|
| delete a paragraph mid-section | the next passage in the section |
| insert a paragraph mid-section | the previous one |
| reorder two sections | the other section |
| rename the first of two headings that slugify alike | the second section |

Six citations across five refactorings, every one of them served with no indication that
anything had happened. The last row is the one that should worry a reader: two `## Event bus`
headings, rename the first, and a citation to the first now returns the second, because the
second inherits the unsuffixed slug when the first stops claiming it. An agent re-quoting that
has fabricated an attribution — the exact failure this product exists to prevent, produced by a
routine edit.

Spec 03 §3.1's sentence is *"rather than silently wrong content"*. That clause was not true.

## The fix was already in the URI, unused

Every citation this product mints carries `?lines=a-b` — `mycelium_search`, `mycelium show`,
and `mycelium_fetch` itself have written it since the citation format existed. `mycelium_fetch`
parsed it on the way back in and then ignored it entirely.

Honouring it is the whole change. If the cited range is not where the anchor sits now, the
passage moved, and the response says so: what was cited, where it is, the URI to cite instead,
and one sentence telling the reader to re-read before re-quoting. The content still comes back.
Refusing to serve it would break every consumer holding a citation into a document being
edited, which is every consumer, and `ANCHOR_GONE` would be a lie — the anchor is precisely
what did not go.

Minting and checking now live in one module, `mycelium.citations`, because the CLI and the MCP
server hand out the *same* citation and had two private copies of the minting function. They
agreed by coincidence. Now that the range they write is load-bearing, coincidence is not the
standard.

## The half I did not ship, and why it is a separate item

The line range is positional. It catches every drift that moves a passage — five of the six —
and cannot catch an edit that rewrites a passage in place without changing its length: same
anchor, same range, new words.

The exact fix is content identity in the citation: a chunk digest, which the store already
holds per chunk. I did not ship it, and the reason is not that it is hard. The URI grammar is
part of the identity contract that freezes at 1.0, so extending it needs a compatibility
argument — what an old client does with an unknown query key, whether the digest is truncated,
and whether `mycelium_search` mints it too. It must, because a citation is *born* in search,
and a digest reachable only from `fetch` is a tool nobody can pick up at the moment they need
it. Shipping half of that inside a size-S item would have made the other half harder to argue.

So it is roadmap 5.17, with the measurement attached — and the blind spot is not merely filed.
It is a row in the proof table, a test whose docstring says it is 5.17's receipt, and a
sentence in the `mycelium_fetch` tool description, which is the only documentation an agent
reads. An undocumented blind spot is worse than a known one.

## Design discipline worth recording

My first outcome model had one axis and was wrong. It called a citation `MOVED` when its text
changed, and the first run failed on three refactorings — because deleting a paragraph at the
top of a document moves every section below it *without changing a word of them*. Moved and
changed are different questions, and conflating them made the table lie in both directions.

The model that survived keeps them apart, and the contract is stated on the second axis: **no
citation may resolve to changed content without saying so**, with exactly one listed exception.
Reporting a move whose content is intact is a deliberate false alarm — the consumer's line
range really is out of date and the block hands back the corrected URI. A false alarm costs a
re-read; a missed drift costs a fabricated quotation.

## Noted, not fixed

`mycelium show` reports an unknown document behind a `mycelium://` URI as exit 2 (usage) with a
doubled message — *"not a citation URI or anchor: no document …"* — where the same document
behind a path anchor is exit 1 (failed). Found while writing the CLI test, which initially
overwrote the seeded file and destroyed its pinned `mycelium_id`, so the rebuild minted a new
document and the citation pointed at nothing. Cosmetic, one line in `_resolve`, and out of this
item's scope; recorded here for whoever next touches that function.

## Lesson

"Survives edits that keep the heading path" is what the spec says about an anchor, and it is
true of the heading path and false of the ordinal beside it. The clause was accurate about the
part someone had thought about and silent about the part they had not — and it stayed that way
for four milestones because every test of `ANCHOR_GONE` asked *does a dead anchor report
correctly* and none asked *does a live one still mean what it meant*.
