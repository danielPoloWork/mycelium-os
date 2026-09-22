# 2026-09-22 — a convention with no reader (roadmap 6.34)

- **Session scope:** roadmap 6.34 — an item can announce a merged pull request and still
  read as open. PR #163 merged on 2026-09-18 and wrote a full delivery record onto item
  6.18 while leaving its checkbox at `- [ ]`. Nothing mechanical caught it for two days.
- **PR:** #PRNUM (`test/lint-the-delivered-checkbox-convention`). Follows #183, merged as
  `ae2792e`.
- **Milestone 6:** 6.34 closed. 6.35–6.37 remain open.
- **Decision it records:**
  [ADR-0149](../../../adr/0149-lint-the-delivered-checkbox-convention.md).

## The convention already had a phrase; it just had no reader

Every closed roadmap item since M1 writes `delivered by PR #<N>` somewhere in its own
prose. That's not a rule anyone wrote down — it's just what closing an item looks like,
the same way every ADR has a Status line. `tools/consistency_lint.py` already leans on
conventions like this elsewhere (`roadmap-numbering` reads the `- [x]`/`- [ ]` state
directly), so the fix here isn't a new mechanism, it's pointing the same kind of lint at
a phrase that was already load-bearing and simply unread.

The rule ended up being one regex: an unchecked item whose text matches
`delivered by PR #\d` is a defect. The item's own filing text is a small trap for that
regex — it quotes the convention as `delivered by PR #N` while describing the bug, and a
naive match on `PR #` would fail on the very item that names the rule. Requiring an actual
digit after `#` sidesteps it for free, and it's checked directly: the check passes against
the committed roadmap with the item still unchecked, because `#N` isn't `#163`.

## The mirror rule earns its rejection by counting, not by asserting it

The item asked to consider the reverse — a checked item with no delivery phrase — and to
reject it if it can't be made unambiguous. Rather than reason about this from priors, I
grepped: 31 of the roadmap's 160 checked items have no `delivered by PR #<digits>` in
their text at all. Reading a sample of them shows why: `1.6`/`1.7` close on an owner
action taken outside any PR, `1.4` closes on a sibling item's CI run rather than new code
of its own, `1.5` was "delivered alongside" `1.1` in the same PR, `2.1` is "reconciled"
into `1.1`–`1.5`'s delivery entirely. Four different shapes, no single phrase covers them,
and inventing one to satisfy a lint would mean rewriting 31 legitimate closures to make a
tool happy — which is exactly the "reasoning backward from a check" trap this same item's
own filing text warned against. The forward rule doesn't have that problem: nothing
legitimately claims `delivered by PR #163` while remaining unmerged, so there's no
population of exceptions to reconcile.

## What shipped

`check_roadmap_delivery_checkbox` is the twelfth check in `tools/consistency_lint.py`'s
`CHECKS` tuple, following the same fail-and-name-it, never-repair-it posture every other
check there already takes — a ROADMAP.md edit is a human's to make. A new test file,
`tests/test_consistency_lint_delivery_checkbox.py`, mirrors `test_consistency_lint.py`'s
existing fixture pattern for `roadmap-numbering`: a synthetic two-item roadmap, a `run()`
fixture that monkeypatches `lint.read`, and cases for a well-formed roadmap, an unchecked
delivery, a checked non-delivery, the `#N`-placeholder trap, multiple simultaneous
failures, and the check's own registration in `CHECKS`.

Nothing published moves. The committed `ROADMAP.md` passes the new check as written — this
item's own line is the sole "delivered by PR #" text without real digits anywhere in the
file, which is exactly what the digit requirement was built to allow.
