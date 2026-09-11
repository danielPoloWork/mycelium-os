# ADR-0084: Fingerprint the index a ranking reads, not the store it lives in

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.3
- **Related:** [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) (the verdict
  this dates, and the runner that checks it), [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)
  (a verdict is about the configuration it was measured under),
  [ADR-0076](0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md) (the
  table addition that exposed this), [ADR-0014](0014-adopt-partial-strict-configuration.md)
  (digest the resolved settings, not the file bytes — the same normalisation argument),
  [ADR-0048](0048-stem-the-index-and-weight-the-stem-below-the-surface.md) and
  [ADR-0063](0063-split-the-heading-path-into-the-leaf-and-its-ancestors.md) (the two changes
  to `chunks_fts` this must keep catching), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (gate G2 itself), [ADR-0083](0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md)
  (the most recent addition to the same fingerprint); spec 03 §8, spec 04 §7.3; D-013, D-016;
  roadmap 5.4, 5.12

## Context

`retrieval_identity()` exists so gate G2's recorded verdict can say what it was measured
under (ADR-0064, ADR-0068): the verdict compares hybrid against the lexical leg, and it is
only about the shipped product for as long as that lexical leg is the one that ships. One of
its fields has been wrong since it was written. The key is `fts_schema` and its value was
`mycelium.store.schema.SCHEMA_VERSION` — the version of the *whole store*, every table in it.

Roadmap 5.4 made the cost concrete. It added the `entities` table and nothing a query reads;
`SCHEMA_VERSION` went `v5 → v6` because the DDL policy bumps it on any schema change at all;
`retrieval_identity()` moved; `eval/g2-verdict.json` went stale; and `measure_hybrid_gate.py
--check` failed until the verdict was re-recorded. The re-record proved the point rather than
hiding it — all four `uv` and `uv-ingested` numbers reproduced byte-identically and only the
self-hosting corpus moved, by its own growth — but re-recording **needs the embedding model**,
which CI deliberately does not have (D-013). So adding a table became a task only a machine
with a 133 MB download could finish, for a ranking that had not changed.

The reason it was not fixed at 5.4 is worth keeping: narrowing a fingerprint inside the PR
whose CI it is inconveniencing is the move that turns a guard into a formality. It needed its
own change, with a check that the narrowing loses nothing.

## Decision

**The fingerprint reads the `chunks_fts` statement itself.**
`mycelium.store.schema.fts_schema()` extracts that one statement from the DDL and returns it
normalised, and `retrieval_identity()` digests that instead of the store's version. The
statement is what BM25 can see: which columns are indexed, in what order, which is
`UNINDEXED`, the tokenizer, the prefix settings.

**The store's version was strictly coarser, which is why this loses nothing.** The DDL policy
bumps `SCHEMA_VERSION` on *any* schema change, so nothing that moves the `chunks_fts`
statement can fail to move the store version — and much that does not move the statement moves
the version anyway. Narrowing to the statement removes false positives and creates no false
negatives. Both historical changes to this table — the stem columns (ADR-0048) and the
heading/ancestors split (ADR-0063) — move it, and a test mutates the statement four ways to
show it still does.

**Normalised, not verbatim**, for the reason ADR-0014 gives for digesting resolved settings
rather than file bytes: SQL comments explain *why* a column exists, and rewording the
paragraph above `chunks_fts` changes nothing about what BM25 reads. Comments are stripped and
whitespace collapsed; what remains is the statement.

**The bound of the claim is stated rather than implied.** The query path also reads `chunks`,
`documents`, `vectors`, `symbols` and `edges`, and their DDL is *not* fingerprinted. They
supply filter predicates and result fields, not term statistics, so their column lists decide
what a result carries and not what order results come in. A change to how a leg *uses* them is
a change to that leg, whose own constants sit in this same fingerprint (ADR-0075, ADR-0080,
ADR-0083). The tables the fingerprint now ignores entirely — `doc_state`, `snapshot_state`,
`build_cache`, `entities` — are build-side, which is the class `entities` belongs to and the
class this fix exists for.

## Alternatives Considered

- **Add an `FTS_SCHEMA_VERSION` constant beside the store's and bump it by hand.** Simple,
  and it is the same defect one level down: a hand-maintained number is a number someone
  forgets, and the failure is silent — a verdict that still looks current after the index
  moved. The whole point of `retrieval_identity()` is that every field is *read from the
  module that owns it at call time* (ADR-0068), and this is that rule applied to the one field
  that was breaking it.
- **Read the statement from the store's `sqlite_master` instead of the DDL constant.** More
  faithful — it is what the open database actually holds. Rejected: `retrieval_identity()` is
  a pure function with no store, called by a runner that must be able to date a verdict before
  opening anything, and adding a store dependency to it would make the fingerprint unavailable
  in exactly the places that check it.
- **Fingerprint every table a query reads** (`chunks`, `documents`, `vectors`, `symbols`,
  `edges` as well). Defensible, and it was the first design. Rejected because it re-creates the
  problem it fixes in a smaller form: adding a column to `documents` that nothing selects would
  stale a retrieval verdict again, and the honest statement is that those tables do not decide
  an order. The limit is recorded above rather than papered over with breadth.
- **Digest the statement verbatim, comments included.** Rejected: it would make rewording a
  comment a retrieval event, which is precisely the class of false positive this ADR is about.
- **Leave it, and accept a re-record per schema change.** Rejected on the cost the item
  names: the re-record needs a model CI does not have, so the burden falls on whoever happens
  to have one, for a ranking that did not move.

## Consequences

- **A build-side table addition no longer stales gate G2's verdict**, and that is a test
  rather than a claim: `tests/test_retrieval.py` appends a table to the DDL and asserts the
  identity is unchanged, and mutates `chunks_fts` four ways — a new indexed column, a
  different tokenizer, a different prefix index, an `UNINDEXED` column that starts being
  indexed — and asserts it moves each time.
- **The verdict is re-recorded once, in this change**, because the fingerprint's *value*
  changes even though nothing it describes did. The check asked for was that the four `uv` and
  `uv-ingested` rows reproduce byte-identically, and the result is stronger than that: **every
  score on all six sets reproduces byte-identically**, this repository's own included. The
  whole diff of `eval/g2-verdict.json` is three lines — the new fingerprint, and the
  self-hosting corpus's two digests, which moved because this change adds two documents to it
  (ADR-0053). Not one measured number moved.
- **`SCHEMA_VERSION` keeps its job**, which was never this one: it is the store's own
  compatibility marker, and D-016's rebuild policy still turns a foreign version into a
  recreated file.
- **Nothing else moves.** No baseline, no judged set, no golden — the shipped ranking is
  untouched, so gate G3 has nothing to re-run and `check_frozen_release_sets.py` no
  conjunction to refuse.
- **A future reader gets the reason at the point of use**: `fts_schema()`'s docstring says
  what it covers, what it does not, and why the store version was the wrong proxy.

## References

- Spec: `.draft-specs/03-data-model.md` §8 (the SQLite layout, an implementation detail);
  `.draft-specs/04-retrieval-and-evaluation.md` §7.3 (gate G2's bar).
- Decision log: D-013 (zero network by default — why CI has no model), D-016 (rebuild as the
  migration policy).
- Re-runnable: `python tools/measure_hybrid_gate.py --check`, and `--record` on a machine
  with the model.
- Tests: `tests/test_retrieval.py` (the four fingerprint tests), `tests/test_g2_verdict.py`.
