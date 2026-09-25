# ADR-0160: Exclude this repository's owner from a plugin's own adoption

- **Status:** Accepted
- **Date:** 2026-09-25
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 06 §3
- **Related:**
  [ADR-0155](0155-read-7-2s-three-triggers-and-say-which-one-cannot-be-read.md) (corrected —
  the plugin-sandbox trigger's *adoption* reading, and the *exists* wording this reconciles
  with the code it already matched), [ADR-0138](0138-recut-the-adoption-gates-onto-acts-we-can-observe.md)
  (the engaged-actor definition, and the fork-counts-ourselves mistake this repeats one call
  site over), [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (a fired
  trigger's polarity — unaffected here, since no candidate exists to move it); D-030; roadmap
  7.11, 7.13

## Context

Roadmap 7.11 audited item 7.2 as it stands and found one gap in ADR-0155's *adoption* reading,
filed as 7.13. ADR-0155 turns D-030's **engaged actor** — a login that is neither a
repository's own owner nor a bot — onto a plugin's repository, to read whether *"≥ 1
third-party plugin with meaningful adoption exists."* The reuse carried only half of D-030's
exclusion: `tools/adoption_report.py`'s `engaged_actors(slug, owner)` excludes `slug`'s own
owner from its tally, and calling it as `engaged_actors(candidate.slug, candidate.owner)` for
a plugin repository excluded **the plugin's** owner and nobody else. This repository's own
owner was a stranger to every plugin repository, so **one comment by this repository's owner
on somebody else's plugin would fire the plugin-sandbox trigger alone** — closing the gate by
counting ourselves, the exact mistake ADR-0138 found in a fork that carried our own commits
back to us, recurring at the one call site 7.5 added rather than the one it corrected.

A second, smaller drift sat beside it. ADR-0155's *exists* bullet reads a plugin candidate as
*"a repository that is not this one and not a fork of it,"* but `plugin_candidates` has always
excluded **every repository this owner holds**, not only `mycelium-os` itself
(`repo_owner.casefold() == owner.casefold()`). The stricter reading is the one roadmap 7.13
judged intended — a plugin authored by this repository's owner under a different name is not
third-party either — and the record should say what the code does rather than the reverse.

Neither defect has moved a verdict yet: GitHub code search finds no repository outside this
one declaring `mycelium.plugins` or `mycelium.modules`, so the plugin-sandbox trigger has read
*holding* regardless.

## Decision

**Exclude both owners from a plugin's tally, and correct the record to match the code it
already agreed with on the other half.**

`is_external` gains a second, optional exclusion — `also_exclude` — threaded through `tally`,
`external_commits`, `fork_acts` and `engaged_actors`. Every existing call keeps its old
behaviour, because the parameter defaults to `None`; only `third_party_plugins` supplies it,
passing this repository's own owner alongside the plugin's:

```python
adopters, _bookmarks, _issues, _comments = engaged_actors(
    candidate.slug, candidate.owner, also_exclude=owner
)
```

An engaged actor on a plugin's repository is now a login that is neither the plugin's owner,
nor this repository's owner, nor a bot — matching D-030's own rule applied twice, once per
owner that must not count as its own adopter.

ADR-0155's *exists* bullet is corrected in place to name the exclusion the code has always
enforced: every repository this repository's owner holds, not only this one by name. Its
*adoption* bullet is corrected to name both exclusions. Both carry an `> **Corrected**` note
naming this record, per `docs/workflow/documentation.md`'s amendment mechanism — the reading
moved, the number and the rest of ADR-0155's decision did not.

## Alternatives Considered

- **Leave the record as written and fix only the code.** Rejected: the item that found this
  asked for both, and a record that states a looser rule than the code enforces is the kind of
  drift `tools/consistency_lint.py`'s `amendments` check exists to make loud rather than quiet
  — here the loose half was prose, not a lint's business, but the principle is the same.
- **Give `is_external` a set of excluded logins instead of one more parameter.** Rejected for
  this call graph: every caller today excludes at most two logins (a repository's own owner,
  and — for a plugin — this repository's), and a set argument would cost every call site a
  wrapping `{owner}` for a generality nothing here uses.
- **Filter plugin candidates whose owner is a login this repository has ever seen contribute
  under, rather than excluding by count in the tally.** Rejected: `plugin_candidates` already
  excludes any repository this owner holds; the adoption tally is a different question — who
  engaged with a plugin that already passed that filter — and conflating the two would hide
  which rule caught what.

## Consequences

- **`tools/adoption_report.py`'s plugin-sandbox trigger reads correctly** the day a real
  candidate exists; today's verdict (*holding*, no candidate) is unchanged.
- **`is_external`, `tally`, `external_commits`, `fork_acts` and `engaged_actors` each carry an
  optional `also_exclude`**, unused by every call site but `third_party_plugins`'s. A future
  caller with the same shape — a tally taken on somebody else's repository that must still
  exclude ours — has the parameter rather than a fifth copy of the rule.
- **Pinned**: `tests/test_adoption_report.py` exercises `is_external` with `also_exclude`
  directly, and reproduces roadmap 7.13's own scenario — the maintainer's login commenting on
  a plugin repository whose owner is somebody else — through `third_party_plugins` with
  `engaged_actors` and `search_plugin_declarations` stood in for, confirming the comment does
  not appear among that plugin's adopters.
- **ADR-0155 is corrected, not superseded**: its trigger reading, its bars and its other two
  rows stand as decided on 2026-09-24.

## References

- `tools/adoption_report.py` (`is_external`, `tally`, `external_commits`, `fork_acts`,
  `engaged_actors`, `third_party_plugins`), `tests/test_adoption_report.py`.
- Re-runnable: `python tools/adoption_report.py`.
