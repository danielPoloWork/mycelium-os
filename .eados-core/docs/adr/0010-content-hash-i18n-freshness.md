# ADR-0010: Content-hash i18n freshness (squash-merge-proof)

- **Status:** Accepted
- **Date:** 2026-06-19
- **Deciders:** Maintainer, Enterprise Project Architect
- **Related:** `tools/eados_lint.py` (`i18n-freshness`), `docs/i18n/translation-status.md`,
  the repository's squash-only merge policy (`AGENTS.md` §6)

## Context

The `i18n-freshness` check (added with the factory's own translations) pinned each
translation to the **commit SHA** of the English source at translation time, and flagged a
translation stale when `git log <recorded-sha>..HEAD -- <source>` was non-empty.

When the repository adopted an **owner-governed, squash-merge-only** policy (`AGENTS.md` §6),
this broke. A squash-merge replaces a PR's commits with a single new commit on `main`; the
original commit the manifest recorded is **orphaned** (not reachable from `main`). The check
then either errors ("commit not in history") or, because the squash commit also touched the
source, reports a false **STALE** — even though the translation is perfectly in sync. This is
not hypothetical: it turned the gate red on `main` immediately after the first squash-merge,
and it recurs on *every* PR that touches a translated source — including the gate-fixing PR
itself. A merge policy and a freshness gate that fight each other is a broken design.

## Decision

Record the **SHA-256 content hash** of the English source (first 12 hex of the digest of the
file's bytes) instead of its commit SHA. The check recomputes the current source's hash and
flags the translation stale when it differs from the recorded one.

- The manifest column becomes `Source hash`; banners drop the fragile `as of commit <sha>`
  line (freshness lives in `translation-status.md`).
- The check is **git-independent** — no history walk, no `fetch-depth: 0` requirement — so it
  is deterministic and works on any checkout (shallow, archive, worktree).

## Alternatives Considered

- **Keep commit SHA, record the squash commit post-merge.** Rejected — the squash SHA is
  unknown until after merge, so it always lands one merge behind; a follow-up push to `main`
  to fix it is itself blocked by the PR-only policy. Self-defeating.
- **Compare `git show <sha>:<file>` to the working tree.** Rejected — still needs the orphaned
  commit object, which may be gc'd; reintroduces the git dependency content-hashing removes.
- **Disable the gate under squash policy.** Rejected — staleness detection is the whole point
  of tracked translations; we fix the mechanism, not drop the guarantee.

## Consequences

- Squash-merges (and rebases, and any history rewrite) never falsely trip the gate: a
  translation is stale **iff** the source bytes changed, which is exactly the intent.
- Refreshing a translation now means: re-translate, then update the row's `Source hash`. The
  workflow doc and `docs/i18n/README.md` are updated accordingly.
- `fetch-depth: 0` on the self-lint CI job (added only for the old git-based check) is removed.
- This concerns EADOS's *own* i18n. The generated-project i18n gate
  (`templates/tools/consistency_lint.py`) is governed separately; aligning it the same way is
  follow-up work when a generated repo adopts squash-only.

## References

- `tools/eados_lint.py` (`check_i18n_freshness`, `_source_hash`),
  `docs/i18n/translation-status.md`, `docs/i18n/README.md` §Staleness gate, `AGENTS.md` §6.
