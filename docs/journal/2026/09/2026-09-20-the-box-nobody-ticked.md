# 2026-09-20 — the box nobody ticked (roadmap 6.18)

- **Session scope:** roadmap 6.18 — picked up as though it were unstarted, and it was not.
- **PR:** #173 (`docs/close-6-18`). Follows #172, merged as `54caf4b`.
- **Milestone 6:** 6.18 closed. 6.34 filed. Open: 6.24–6.33.
- **Decision it records:** none — the decision is
  [ADR-0128](../../../adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md),
  taken at PR #163 on 2026-09-18.

## The work was done; the list said otherwise

`ROADMAP.md` carried, on one line: `- [ ] 6.18 … — delivered by PR #163: **one cache, one
declaration, and the second cache refused on its own measurement** (ADR-0128)`, followed by
nine hundred words of before-and-after numbers. The record is complete. The checkbox is
unticked. PR #163 merged on 2026-09-18 and wrote both.

Three things that exist to prevent exactly this all declined to:

- the PR template's **ROADMAP.md checkbox flipped** is a box a human ticks beside a box a
  human forgot to tick;
- `tools/consistency_lint.py` asserts the two roadmap invariants that are mechanical —
  numbers unique, item under the milestone it names (4.27) — and has no opinion about an
  item announcing a merged pull request while reading as open;
- the session's own journal entry is missing its `Milestone 6:` line, which is the same slip
  from the other side, and the one place a reader might have noticed.

## Verified, not assumed

A record is a claim, and this one had already proved it could be half-written, so the tick
rests on a re-run rather than on the prose:

| check | result |
|---|---|
| `test_config.py`, `test_modules.py`, `test_mcp.py` | **142 passed** (320 s) |
| `test_config_bench.py` | `load_config` **1.88 ms mean**, against the 2.1 ms the record claims |
| `forget_installed`, `BUILTIN_PARSER_IDS` | present in `config.py` / `modules.py`, with their guards |

The constant 6.4 found is gone and has stayed gone. ADR-0128 is in the index, the CHANGELOG
entry landed with #163, and the two follow-ups that item filed — 6.24 and 6.25 — are
where it left them.

## What is actually new here

One item: **6.34**, the rule that would have caught this on the day. *An item whose text
records a delivery is checked.* It is a lint on a convention every closed item since M1 has
followed (`delivered by PR #N`), it fails naming the item rather than repairing it — a
roadmap edit is never a tool's to make — and it belongs beside `check_roadmap_numbering`,
which was filed at 4.27 for the same reason: cheap to prevent, dear to repair.

The general shape is one this project keeps finding: the journal index that stopped being
written and nothing noticed (5.32), the setup steps nobody read back (6.6), the labels that
were never imported. **A convention with no reader is a convention with no force**, and this
repository's answer has consistently been to give it one.

Not fixed here, because it is a second item: the lint itself. This change closes 6.18 and
files it.
