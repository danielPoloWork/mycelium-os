# ADR-0085: Let a callout bound a chunk rather than atomise one

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §3.1
- **Related:** [ADR-0007](0007-adopt-structure-first-chunking.md) (heading-bounded chunking,
  and what `atomic` protects), [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md) and
  [ADR-0047](0047-pack-atomic-blocks-by-default.md) (atomicity means indivisible, not
  solitary — the distinction this turns on), [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the `chats` module, whose workaround this retires), [ADR-0012](0012-adopt-the-g6-determinism-gate.md)
  (the golden this re-blesses), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (which corpora a number is gated on); spec 03 §§3.1, 5, doc 08 §7; D-022; roadmap 5.5, 5.13

## Context

Spec 03 §3.1's profile table has promised one thing since it was written:

> | Callouts `> [!note]` | full | KIR `callout` nodes; atomic chunks like tables |

The chunker implements atomicity for two node kinds — `_ATOMIC_KINDS` maps `table` and
`code_block` and nothing else (ADR-0007) — so a callout has always been packed as ordinary
prose. Two consecutive callouts land in one chunk, and so does the paragraph after them.

Roadmap 5.5 met the consequence immediately. Doc 08 §7 makes the **message** the chunking
unit for a projected conversation and the obvious rendering is one callout per message, which
would have put several turns in one chunk. The module worked around it by opening every
message with its own heading, which the chunker already bounds, and filed the divergence
(roadmap 5.13) rather than absorbing it.

Two measurements shaped this change before any code was written.

**Nothing in the judged corpora has a callout.** Counted across all three: this repository's
144 documents, the vendored `uv` documentation's 81, and its ingested twin's 81 — **zero**
callout nodes. The one callout anywhere in the repository is in the gate G6 fixture. So the
cost the item forecast — *"every corpus with a callout moves every boundary after it, so a G6
re-bless and three baseline re-blesses with the per-slice diff in the PR body"* — is almost
entirely absent: **no baseline moves at all**, and there is no per-slice diff to report,
because there is nothing to move. That makes this the cheapest moment this change will ever
have, and it gets more expensive with every corpus that adopts the profile.

**The promise is wrong in one half, and doc 08 §7 already said so.** `atomic` for a table
means *never split*, because half a table is not a table and half a fence is not runnable. A
callout is not that shape: it is a *container of blocks*, and the adapter emits its paragraphs
as children. Half a callout is still readable prose. Doc 08 §7 knows it and asks for the
opposite of never-split — *"oversize messages split at paragraph boundaries per the standard
chunker rules"* — which the literal promise would have forbidden. So the two specifications
disagreed with each other, and implementing either one literally would have broken the other.

## Decision

**A callout *bounds* a chunk; it does not atomise one.** Its blocks pack with each other and
never with anything outside it. Concretely, `_sections` turns a callout into one `_Unit` per
block inside it, all carrying the callout's node id as their `group`, and `_pack` closes
whatever has accumulated whenever the group changes. Three consequences follow, and they are
the three things the two specifications between them asked for:

- two consecutive callouts are two chunks, and a callout never merges with the prose beside
  it — spec 03 §3.1's intent, and what doc 08 §7 needs the chunking unit to be;
- an oversize callout splits at *its own* paragraph boundaries under the ordinary target and
  ceiling — doc 08 §7's last clause, which the literal reading forbade;
- a callout containing a table keeps that table atomic, because the two rules compose rather
  than compete.

**Spec 03 §3.1's cell is amended rather than the code bent to it**, which AGENTS.md §7 allows
explicitly and which is the honest disposition here: the cell was right about the merging and
wrong about the splitting, and it now says so with the reason. Spec 03 §5 gains the same
paragraph, next to the atomicity rule it sits beside.

**The `kind` stays `prose`.** `ChunkKind` has three members because `kind` describes *content*
— a table is not prose, a fence is not prose — and a callout's content is prose in a box.
Adding a fourth member would change the `Chunk` contract, one of the five that freeze at 1.0,
in exchange for a distinction no consumer makes: nothing filters or ranks on `kind`.

**The boundary holds whatever `pack_atomic` says.** That flag decides whether a *table* may
share a chunk with the prose around it (ADR-0042, ADR-0047) — a packing question about an
indivisible block. A callout's boundary is a structural claim its author made by writing one,
and it is not the same question.

**The `chats` module keeps its heading, for the reason it also had.** With the core
implementing the promise, the workaround is no longer load-bearing — but an anchor has to be
stable across a re-read, and a section slug is the only thing that gives a message one.
Without its own heading a conversation's messages would share one slug and be told apart by
ordinal, so inserting or re-reading a message would move every anchor after it. The module's
docstring now says which of its two reasons survived, and records that the cost it stated —
an oversize message staying one chunk — is closed.

## Alternatives Considered

- **Make callouts atomic exactly like tables**, the literal promise. Rejected: it would
  forbid doc 08 §7's *"oversize messages split at paragraph boundaries"* by construction, and
  it is the wrong analogy — a table cannot be split without ceasing to be a table, and a
  callout can. Implementing a specification sentence that another specification contradicts
  is not fidelity, it is picking one without saying so.
- **Delete the promise from spec 03 §3.1**, which the item offers as the other option.
  Genuinely arguable and the cheapest thing to do. Rejected on the measurement: the promise is
  *right* about the merging, doc 08 §7 depends on that half, and the module had already paid
  for its absence with a workaround. Removing it would have made a shipped module's core
  dependency permanently a coincidence of heading placement.
- **Add `ChunkKind.CALLOUT`.** Rejected: a contract change to one of the five stable records
  for a distinction nothing reads. If a consumer ever needs it, the `kir_nodes` on the chunk
  already say a callout node is in there.
- **Tie the boundary to `pack_atomic`**, so the old behaviour stays one flag away as the
  v0.3 chunk boundaries do. Rejected: `pack_atomic` answers "may an indivisible block share",
  and this answers "does an author's box bound". Overloading one flag with two questions is
  how a knob stops meaning anything, and the second question has no measured case for being
  configurable.
- **Do it later, when a corpus actually has callouts.** Rejected on the arithmetic above:
  today it costs one golden re-bless and no baseline at all, and every later day costs more.

## Consequences

- **No baseline moves, and no judged set is touched**, because no judged corpus contains a
  callout. Gate G3 has nothing to re-run and `tools/check_frozen_release_sets.py` has no
  conjunction to refuse — the conjunction the item warned about never arises.
- **Gate G6's golden moves, and the fixture is widened on purpose.** `retries.md` had one
  callout; it gains a second, consecutive one with two paragraphs, so the gate now covers the
  rule rather than the syntax. Chunks 27 → 29: the prose before the callouts, and each callout,
  are three chunks where they were one. Every other document and chunk is byte-identical, and
  `tests/test_determinism.py` pins the three anchors and their line spans so a later edit
  cannot quietly narrow the coverage — the same guard ADR-0047 added for the solitary code
  chunk.
- **The `chats` module's stated cost is closed** without touching the module's behaviour: its
  tests pass unchanged, because a message inside the ceiling was one chunk before and is one
  chunk now. What changed is what happens when a message exceeds the ceiling.
- **KIR accounting is unchanged.** The callout node's own id and its title ride with the
  first unit, so no node lands outside a chunk: an id in no chunk is an anchor nothing can
  cite and a symbol extraction cannot reach (ADR-0073).
- **A callout with a title and no body is still a chunk**, which is the shape
  `> [!note] Heads up` produces and the shape that would otherwise have vanished.
- **Performance is unchanged**: one extra field on an internal dataclass and one comparison
  per unit in the packer.

## References

- Spec: `.draft-specs/03-data-model.md` §3.1 (the profile table, amended here) and §5 (the
  chunking policy, amended here); `.draft-specs/08-module-chats.md` §7 (the message as the
  chunking unit, and the splitting clause this honours).
- Decision log: D-022 (the Obsidian-flavoured profile that has callouts at all).
- Tests: `tests/test_chunking.py` (six callout tests), `tests/test_determinism.py` (the
  fixture's pinned coverage), `contrib/chats/tests/` (unchanged, and passing).
