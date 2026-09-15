# 2026-09-15 — the premise went void (roadmap 6.16)

- **Session scope:** roadmap 6.16, which did not exist when the session opened. It came out
  of the maintainer asking whether 6.6's three absent settings deserved corrective items.
- **PR:** `feat/watch-expired-deferrals`. Follows #152 (6.6), merged 2026-09-15T04:59Z.
- **Milestone 6:** 6.1, 6.2, 6.6, 6.11 and now 6.16 delivered. Open: 6.3, 6.4, 6.5, 6.7–6.10,
  6.12, 6.13, 6.14, 6.15.
- **Decision it records:**
  [ADR-0118](../../../adr/0118-make-a-deferral-name-the-condition-that-ends-it.md).

## The question was better than the answer I was about to give

6.6 reported three documented repository settings that had never been installed, and the
obvious next move was three corrective roadmap items. The maintainer asked whether that made
sense. Looking for the reason it did not produced the actual finding.

**Two of the three were never oversights.** The bootstrap audit accepted them on 2026-08-29,
in the risk register, each with a severity, an owner and an explicit condition:

- **F2** — no branch protection, accepted because it is unavailable on a private free-plan
  repository. Revisit *"at public/Pro"*.
- **F3** — the disclosure channel is dead, accepted because *"today there are no external
  reporters (private repo), so exposure is nil; at public launch a reporter would find a dead
  door"*. Revisit *"the day the repo goes public, before any announcement"*.

Both conditions came true. The repository is public. The first external fork appeared on
**2026-09-14T20:17:33Z**. F3's recorded impact — *exposure is nil* — had been void for weeks,
and the dead door it predicted at public launch is the door that is there now.

## Why nothing noticed, which is the part worth keeping

Three records each held a piece of the condition and none of them could tell it had fired.

- **A risk register is a document, and nobody re-reads a document.** It was written once and
  has been referenced only by things pointing into it.
- **The roadmap item carrying the trigger was ticked and closed.** Item 1.8's own text reads
  *"activate the repo feature at public launch — register F3"*. It shipped at v0.1.0 with the
  trigger inside it, and a closed item is not a place anyone looks.
- **The threat model recorded the premise as an assumption and never moved.** B1 still read
  *"repo currently private (no external contributors yet)"*, against AGENTS.md §7's obligation
  to move this file with a trust boundary. Going public was such a change.

## The rule

> A deferral must name the condition that ends it in a form a machine can evaluate. One that
> cannot be written that way has no expiry, and is not granted.

`DEFERRALS` in `tools/check_repo_settings.py` is that, and the design's load-bearing part is
the split **by what a question costs to ask**. Evaluating a condition reads only the
repository object, which any token can fetch; verifying a remedy needs administrative rights.
So `Finding.installed` is three-valued and a caller without those rights is told the remedy is
*unverifiable*, never absent and never installed. `--triggers-only` runs the cheap half alone.

An unverifiable remedy counts as unremedied. In a security record, "I could not check" is not
a pass.

The list is self-limiting: it holds what the register still calls deferred, so the owner
installs the remedy, the register records the closure, and the row leaves in the same change.
That is why a fired condition is a failure even where the remedy is unknown — what is being
asked for is not the setting, it is the register entry closed by someone who looked.

## Where it runs, and why not in CI

Not in CI, and that is a decision about credentials rather than convenience. Reading these
settings unattended needs a long-lived token, which is the one thing ADR-0116 and ADR-0117
removed from every other part of this supply chain. A release is the one moment a maintainer
with their own authenticated `gh` is already in the loop, so `release.md` gains it as step 0b.
Release cadence is not continuous; the ADR says so rather than implying otherwise.

## What landed with the mechanism

All three records, in the same change, because a re-assessment that arrives later is the
failure repeating: F3 re-rated **low → medium**, F2's deferral marked expired with its plan
constraint gone, B1 corrected and the fork recorded.

And one thing I nearly got wrong. The changelog entry I drafted told a reporter to email the
maintainer instead. `SECURITY.md` offers exactly one channel and it is the disabled one, so
there is currently **no working private route for an outsider at all** — and I do not get to
publish somebody's personal address to invent one. The interim note now says: open an issue
whose entire content is a request for a private channel, with nothing about the problem in it.
That needs no email and is honest about what exists.

## Lesson

An accepted risk is a promise to look again, and a promise with no owner at the moment it
comes due is a promise nobody keeps. Three documents held three pieces of one condition and
not one of them could answer whether it had fired. If a deferral's condition cannot be written
as code, the honest move is to refuse the deferral rather than to write the condition down
more carefully.
