---
id: BUG-0038
title: a plugin's adoption tally let this repository's owner count as a stranger to it, so a comment of theirs alone could fire the plugin-sandbox trigger
status: fixed
severity: low
reporter: internal
discovered: 2026-09-25
affected-versions: "main from 6334571 (PR #196) to the fixing commit; no tagged release"
fixed-in: "next release (main after the fixing PR; no tagged release carries the defect)"
---

# BUG-0038: a plugin's adoption tally let this repository's owner count as a stranger to it, so a comment of theirs alone could fire the plugin-sandbox trigger

## Summary

`tools/adoption_report.py` reads spec 06 §3's plugin-sandbox trigger as *one D-030 engaged
actor, on a third-party plugin's own repository, who is not that plugin's owner* (ADR-0155).
The reading reused `engaged_actors(slug, owner)`, which excludes `slug`'s own owner from its
tally — called as `engaged_actors(candidate.slug, candidate.owner)` for a plugin repository,
it excluded **the plugin's** owner and nobody else. D-030's own engaged-actor definition
excludes a repository's own owner as one half of a two-repository comparison this reuse
collapsed into one: this repository's owner was never excluded from a *plugin's* tally, so an
issue, a comment, a pull request or a fork by this repository's owner on somebody else's
plugin repository read as a stranger's engagement and could fire the trigger by itself —
closing the gate by counting ourselves, the mistake ADR-0138 found in a fork carrying our own
commits back to us, recurring at the one call site that reused its definition rather than its
lesson.

## Environment

- **Affected versions:** `main` from `6334571` (PR #196, roadmap 7.5, 2026-09-24) until the
  fixing commit. No tagged release carries the reader; the plugin-sandbox trigger existed on
  `main` only.
- **Toolchain / platform:** platform-independent.
- **Configuration:** none. Needs `gh`, authenticated, to reproduce against GitHub; the root
  cause is demonstrated without it, against the pure functions below.

## Reproduction

```text
$ python -c "
import sys; sys.path.insert(0, 'tools')
import adoption_report as r
print(r.is_external('danielPoloWork', 'acme'))"
True
```

`danielPoloWork` (this repository's owner) reads as external to `acme` (a plugin's owner) —
correctly, on its own; the defect is that nothing upstream of this call ever supplied the
second exclusion. Confirmed against the actual call site with `search_plugin_declarations`
and `engaged_actors` stood in for: a fake `engaged_actors(slug, owner)` matching the pre-fix
signature (no `also_exclude` parameter) is exactly what `third_party_plugins` called, and the
login recorded against `acme/mycelium-jira`'s tally in that call was never filtered against
`danielPoloWork`.

## Expected vs. actual

- **Expected:** an engaged actor on a plugin's repository excludes that plugin's owner *and*
  this repository's owner — D-030's rule, applied to both repositories the comparison names.
- **Actual:** only the plugin's own owner was excluded; this repository's owner counted as an
  adopter of any plugin they had ever opened an issue on, commented on, or forked with a
  commit.

## Root cause

`is_external(login, owner)` takes one exclusion. `tally`, `fork_acts` and `engaged_actors` all
built on it with a single `owner` parameter, which is correct for every caller that asks *"who
engaged with repository X, other than X's own owner"* — every caller until roadmap 7.5 added
one that asks a second question at the same time: *and other than the owner of the repository
asking.* Nothing in the call chain had a slot for a second exclusion, so the second question
went unanswered rather than raising an error, which is why it shipped without failing any
existing test: every prior caller's answer was still correct.

## Impact

Low, and not yet real: no plugin candidate exists (GitHub code search finds no repository
outside this one declaring `mycelium.plugins` or `mycelium.modules`), so the trigger has never
fired on this defect. Had one existed, the maintainer's own ordinary engagement — filing an
issue, leaving a review comment, starring a conversation — on a plugin they did not author
would have been indistinguishable from a stranger's adoption, firing an XL item's entry
trigger on an act that was never adoption.

## Fix / workaround

`is_external` gains an optional `also_exclude: str | None`, threaded through `tally`,
`external_commits`, `fork_acts` and `engaged_actors`; every existing call keeps its behaviour,
since the parameter defaults to `None`. `third_party_plugins` is the only caller that supplies
it, as `engaged_actors(candidate.slug, candidate.owner, also_exclude=owner)`. Pinned two ways
in `tests/test_adoption_report.py`: `is_external`/`tally` directly with `also_exclude`, and
`third_party_plugins`'s wiring, with a spy standing in for `engaged_actors` confirming it is
called with `also_exclude=owner` — the exact shape the pre-fix call lacked.

A second, related drift found while reading the same code was not a defect: `plugin_candidates`
has always excluded every repository this repository's owner holds, not only `mycelium-os` by
name, and ADR-0155's prose said the narrower thing. [ADR-0160](../../../adr/0160-exclude-this-repositorys-owner-from-a-plugins-own-adoption.md)
corrects the record to match the code, which was already right.

## References

- Fixing PR: #N (filled in once opened — never pre-written)
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: roadmap 7.11, 7.13
  ([ADR-0155](../../../adr/0155-read-7-2s-three-triggers-and-say-which-one-cannot-be-read.md),
  [ADR-0160](../../../adr/0160-exclude-this-repositorys-owner-from-a-plugins-own-adoption.md));
  [ADR-0138](../../../adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md) (the
  fork-carries-our-own-commits mistake this repeats at a different call site);
  [BUG-0036](BUG-0036-a-report-of-no-saving-is-refused-as-malformed.md) (the other defect
  found in this same tool by reading its own output rather than by a report)
