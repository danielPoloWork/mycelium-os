# 2026-09-10 — declared, not guessed (roadmap 5.4)

- **Session scope:** roadmap 5.4 — the entity extraction stage, optional and off by default
  (spec 02 §4.1's `entities°`, spec 03 §6). The last stage the compiler's DAG draws, and with
  it the last of D-014's eight edge types.
- **PR:** #103 (`feat/entity-extraction`). Follows #102 (5.3), merged as `cf24131`.
- **Milestone 5:** 5.4 done; 5.12 filed. Open: 5.5, 5.6, 5.7, 5.9, 5.10, 5.11, 5.12.
- **ADR:** [ADR-0076](../../../adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md).

## The measurement refused the obvious answer

"Entity extraction" in the field means an LLM reading prose and inventing nodes, which this
build cannot do and should not: it makes no network call, it is byte-identically reproducible,
and spec 06 §3 defers the ontology and the acceptance workflow to post-1.0 behind a trigger
that has not fired. So the question was what a deterministic, offline stage can honestly
extract, and the only way to answer it was to count what the corpora actually contain.

| candidate vocabulary | ours | uv | uv-ingested |
|---|---:|---:|---:|
| frontmatter `tags` | 0 | 0 | 0 |
| frontmatter `aliases` | 0 | 0 | 0 |
| inline `#tag` | 77 distinct, **1** with a letter | 6, **0** | 2, **0** |
| document titles | 134 | 81 | 81 |

Eighty-four of the eighty-five inline tags are GitHub issue references — `#1`, `#313`,
`#2252`. Titles were the only vocabulary with real numbers, and they are the trap: matching
them in prose gives 227, 197 and 163 hits whose most frequent members are `README` (42),
`Documentation` (41), `Changelog` (28), `Projects` (23) and `Tools` (21). Ordinary words. A
table built from those would have been the largest artifact in the PR and the least true, and
wrong in the way that reads as coverage.

So titles are refused, and an entity is a name the corpus *declares*: a tag, or an `aliases`
key saying the thing a document is about answers to other names. A title becomes a name only
when its own document says so — one keystroke for an author who means it, silence from every
author who does not. `mentions` then follows ADR-0074's rule exactly: resolve against the
declared vocabulary or emit nothing. Every entity is `authored` and every mention `extracted`,
which is the first time spec 03 §6's status discipline has had both halves in one place.

## What that yields here, which is almost nothing

With the stage switched on, this repository declares **one** entity: `ent:nnn`, from
`Fixing PR: <#NNN, once closed>` in the bug-ledger template. Zero mentions. uv and its ingested
twin declare nothing at all. The `entities` stage reports 0 ms in the manifest timings on all
three.

That is the evidence behind "off by default", and it is worth being precise about what it
means. It is a fact about *these* corpora — a Git repository's docs tree and a vendored
documentation site, neither of which uses tags or aliases — and not about the mechanism. An
Obsidian vault, which is the corpus D-022 shaped the profile for, uses both heavily. The
determinism fixture does use them, and yields 8 entities and 5 `mentions` edges, so the gate
carries real data even though the product's own corpus does not.

Publishing the number rather than implying it is the same move ADR-0073 made with three
symbols. A stage whose yield is one placeholder in a template is a stage whose default is
easy to argue.

## Two bugs the fixtures caught

The first golden had no `設計`. The multilingual fixture tags a document with it, and the
numeric-tag filter — there to drop `#2252` — was written `[^A-Za-z]*`, so it read a Japanese
word as an issue number. Replaced with `str.isalpha`. The corpus is multilingual by decision
(D-028) and the anchor slugger already keeps non-Latin scripts intact; an ASCII filter would
have made the whole stage quietly Latin-only. It also turned out `EntitySlug`'s pattern could
not accept `設計` either — ASCII-only since Milestone 2, never exercised because no entity had
ever been minted. Widened to what `heading_slug` actually produces, at no cost, because there
was no data under the narrower rule.

The second: `aliases: [Arch, the design]` produced *three* entities. Re-reading spec 03 §6 is
enough to see why that is wrong — the record has an `aliases` field precisely so it is one
entity with three names. The fix is that an alias takes the title's slug rather than one of
its own.

Both were visible in the first blessed golden and in nothing else. That is the argument for
having switched the stage on in the fixture at all: a golden blessed under the defaults could
never see a change to a stage the defaults leave off, so the gate would have been blind to a
whole stage of the compiler.

## The G2 false positive, named rather than absorbed

Adding the `entities` table bumped the store schema v5 → v6, which moved
`retrieval_identity()`, which made `eval/g2-verdict.json` stale — for a change that no query
can see. The fingerprint takes the store's whole `SCHEMA_VERSION` as its proxy for *what BM25
can see* (ADR-0068), and a new unrelated table trips it.

Re-recording proved the point instead of hiding it: all four `uv` and `uv-ingested` set
numbers reproduced **byte-identically**, and only our own corpus moved, by the growth this
repository's documentation produces on every PR. Worth doing carefully, too — the first
re-record happened against a working tree that still held the maintainer's uncommitted
Graphify analysis, so it was stashed and the record retaken against the committed corpus. A
committed verdict must describe a corpus a clone can reproduce.

Narrowing the fingerprint to the `chunks_fts` DDL is the right fix and is filed as 5.12, not
done here: changing a tuning path for one PR's convenience is the move this project refuses.
The friction is real, though, and the item says so — re-recording needs the embedding model,
which CI does not have.

## Lesson

The honest version of a feature is sometimes the one that produces nothing on the corpus in
front of you. Counting first is what turns that from a disappointment into a decision: the
vocabulary that would have filled the table was measured, found to be `README` and
`Documentation`, and refused — and the empty table is now the argument for the default rather
than an embarrassment to explain away.
