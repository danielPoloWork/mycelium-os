# 2026-09-24 — a promise is not an act (roadmap 7.5)

- **Session scope:** roadmap 7.5 — give 7.2's three spec 06 §3 triggers a reading, as 7.4
  gave 7.1's, and where a row cannot be read, say so and put the re-cut to the owner.
- **PR:** #N (`feat/give-7-2s-triggers-a-reading`). Follows #195, merged as `9b5c0e9`.
- **Milestone 7:** 7.5 closed. 7.1 and 7.2 remain held at their triggers; 7.3, 7.6, 7.7 open.
- **Decision it records:**
  [ADR-0155](../../../adr/0155-read-7-2s-three-triggers-and-say-which-one-cannot-be-read.md).

## Two readings were the owner's, and asking first was cheaper than designing

The item left two of the three rows genuinely open, and both were readings of the spec's
words rather than engineering: whether a *commitment* can be read off anything, and whether
*meaningful adoption* means anything without telemetry. Both went to the maintainer in one
batched round with a recommendation each, before a line of code, and both recommendations
were taken. The alternative — building an instrument for the RBAC row and then asking — would
have spent the session on the one row whose honest answer was *no instrument*.

## The row that cannot be read is the finding

*An organization commits to deploying the server profile* is unreadable twice over: a
commitment is a promise, and the server profile does not exist to be deployed until 7.2
ships. So as an *entry* trigger it can never fire before the item it gates — it is not a
deferral with an expiry, it is a condition that belongs inside 7.2's RFC. Reporting it
`UNREADABLE` by decision is the ADR-0118 third value used as designed: not a pass, not a
finding, never the exit code. The tempting proxy — public organisation membership of the
requester — would have quietly rewritten *commits to deploying* as *asks on behalf of*.

## Match the form, not the label

The consumer row's instrument is an issue form, and the first design recognised requests by
the label the form applies. A label is a triage act: anyone with rights adds or removes one,
and anyone at all can type the word into a title. The form's own rendered field headings are
the filer's act — they cannot appear without answering the required fields — so the reader
matches those, and a test holds the reader's tuple to the YAML. The label stays, for humans.

## Code search finds our own declarations first

The plugin row's search for the entry-point groups returned exactly two hits, both ours:
`contrib/chats` and the plugin cookiecutter's template. A fork of this repository would carry
both back as a "third-party plugin" — the same shape as ADR-0138's fork that reflected our own
branch — so forks are excluded by flag and the owner by login, and one repository declaring
both groups is one plugin. Adoption reuses D-030's engaged-actor tally on the plugin's own
repository rather than inventing a second definition of adoption.

## What the next session should know

- **All four M7 triggers are now evaluated by one command**, and all hold; 7.3 is the only M7
  item that enters without one.
- **The `surface-request` label was created on GitHub** by the agent in this session, as the
  type labels were on 2026-09-11; the form is recognised whether or not the label exists.
- **Touching `.github/` derives `full`** — the form and the label file did here, on top of a
  tooling change that would have derived `code`.
