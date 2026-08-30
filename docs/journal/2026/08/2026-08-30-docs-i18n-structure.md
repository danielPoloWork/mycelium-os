# 2026-08-30 — docs i18n subsystem, structure only (roadmap 2.13)

- **Session scope:** roadmap item 2.13 — enable the documentation i18n subsystem with zero
  translations (RFC-0001, D-028; L-0002).
- **PR:** #26 (`docs/i18n-structure`), one item, one PR. Follows #25 (2.12), merged.
- **This closes Milestone 2's original scope (2.1–2.13);** 2.14 (configuration loading),
  filed during 2.8, is the remaining item in the milestone.

## What got done

The flag and its artifacts ship together, which is the whole point of L-0002:

- `docs/i18n/README.md` — the subsystem: the derived-copy layout and why the symmetric
  `en/it/zh/ja` alternative was rejected, the three target languages, what is tracked and
  what deliberately is not, how freshness gating works, and the step-by-step procedure for
  translating a page.
- `docs/i18n/translation-status.md` — twelve rows (4 pages × 3 languages), all `pending`.
- `tools/consistency_lint.py` — `i18n_enabled: True`.
- `orchestrator/project.yaml` — `capabilities.i18n: true`, `i18n.targets: [it, zh-Hans,
  ja]`, and the interview provenance moved from `defaulted` to `asked` (the owner asked;
  that is what D-028 records).
- Root README — the language selector's labels became links, which is what 2.12 deferred
  to this item because it is the one that creates their targets.

## The contract gap the flag exposed

`AGENTS.md` §2 read: *"anything that lands on disk or in Git is English-only"* — no
exception. Enabling i18n would have put Italian, Chinese, and Japanese pages on disk in
direct contradiction of the contract every agent in this repo reads first. §2 now carries
the narrow carve-out (only `docs/i18n/`, never replacing a canonical source), and the
`CLAUDE.md` / `GEMINI.md` TL;DR lines carry the same clause. `docs/workflow/documentation.md`
gains a *Translations* section with the two rules that make this safe: translate *after*
never *instead*, and never update a recorded SHA without re-translating.

Worth noting because it generalises: turning a capability flag on is rarely just a flag. It
has a documentation contract, a lint check, and a manifest entry that must agree, and the
one that contradicted the others was the one no test reads.

## Scope call: which pages are tracked

Tracked are the four pages a **reader** needs — README, CONTRIBUTING, CODE_OF_CONDUCT,
SECURITY. Nobody should need English to read the rules they are held to, or to report a
vulnerability.

Not tracked, with reasons recorded in `docs/i18n/README.md`: ROADMAP and CHANGELOG (they
change nearly every PR, so a translation would be stale more often than not and the gate
would fail permanently), ADRs / RFCs / specs / journal (the working record of an
English-language engineering contract), and the agent instruction files (they are
instructions to tools, not prose for readers).

## Verifying the gate rather than trusting it

A lint that passes on an all-`pending` table proves nothing. So the gate was made to fail
on purpose: one row was temporarily marked `` `translated` `` against the README's *first*
commit, and the lint reported

```text
[i18n-freshness] i18n translation of README.md is STALE (7 commit(s) after the recorded source commit)
```

then returned to OK once restored. The gate bites, names the page, and counts the drift.

## Where the project stands

- Milestone 2: 2.1–2.13 ✅ · **2.14 open** (configuration loading — `mycelium.toml` is
  scaffolded by `init` but nothing reads it yet).
- Gates green locally: `python tools/consistency_lint.py` (now including `i18n-freshness`),
  and the full suite unchanged — this item touches documentation and configuration only.

## How the next session resumes

- Wait for PR #26 to merge, then start **2.14** — configuration loading. The note from 2.8
  still stands: the determinism golden pins the *default* chunking policy and namespace, so
  making `mycelium.toml` readable must not move it. If it does, the config is being applied
  where the defaults used to be, and that is the bug.
- When translation *content* starts (README first, per D-028), remember the procedure in
  `docs/i18n/README.md`: record the source SHA in the same PR, and never refresh a SHA
  without re-translating — that silently defeats the gate this item built.
