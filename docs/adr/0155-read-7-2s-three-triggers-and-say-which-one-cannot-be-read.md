# ADR-0155: Read 7.2's three triggers, and say which one cannot be read

- **Status:** Accepted
- **Date:** 2026-09-24
- **Deciders:** the maintainer (the two readings below, 2026-09-24) with the tech-lead (EADOS
  delivery agent), per RFC-0001 / spec 06 §3
- **Related:**
  [ADR-0154](0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)
  (7.1's trigger given a reading — the shape this repeats, and the item that filed this one),
  [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (a deferral whose
  condition cannot be written as code is not granted; *could not evaluate* is a third value),
  [ADR-0138](0138-recut-the-adoption-gates-onto-acts-we-can-observe.md) (the engaged-actor
  definition reused here for a plugin's adoption, and the fork lesson repeated),
  [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (the issue forms this adds one to); D-011 (CLI + MCP only), D-012 (a plugin is installed
  code; sandboxing deferred with a trigger), D-017 (no telemetry), D-019 (the server profile is
  Phase 5), D-029 (topology), D-030; spec 06 §3 and Phase 5; spec 02 §10; roadmap 7.2, 7.4, 7.5

## Context

Roadmap 7.2 is the server profile — HTTP API, authn/z, tenancy and RBAC, Postgres and object
store, OpenSearch/Qdrant, out-of-process plugin isolation, OTel — and the Milestone 7 heading
lets each part in only through its spec 06 §3 trigger and its own RFC. Three rows of that table
gate it:

| Decision | Trigger, as written |
|---|---|
| HTTP API + SDKs | a consumer that cannot use MCP/CLI actually appears |
| Multi-tenancy, policy engine, RBAC | an organization commits to deploying the server profile |
| Plugin sandboxing + signed registry | ≥ 1 third-party plugin with meaningful adoption exists |

Roadmap 7.4 found 7.1's row to be a sentence nothing could evaluate, and filed 7.5 because these
three are the same kind of sentence: each names something real and nothing observable, so each
could only be asserted — the defect ADR-0138 found in the adoption gates, and the case ADR-0118
refuses (*a deferral whose condition cannot be written as code has no expiry, and is not
granted*). Two shapes of answer existed: re-cut a row onto acts GitHub reports (ADR-0138), or
give its words a reading and an instrument that fires it (ADR-0154). 7.5's instruction was to
decide row by row, and where nothing can evaluate a row, to say so and put the re-cut to the
owner rather than invent an instrument.

## Decision

**Row by row; two get an instrument, one gets the honest answer that it has none.** All three
join `tools/adoption_report.py`'s *Deferred decisions* section with ADR-0154's polarity: a fired
trigger is a decision owed to the owner, never a decision taken, and it fails the report until
the owner takes it.

### HTTP API + SDKs — a consumer appears by saying so

*A consumer that cannot use MCP/CLI actually appears* is observable the moment it is made an
act: a new issue form, **I cannot use MCP or the CLI** (`.github/ISSUE_TEMPLATE/surface_request.yml`),
asks which client it is and why each of the two surfaces does not fit it — required fields, so
a filer cannot leave the reason out. The trigger fires on **one** such issue by an external
login that nobody closed as *not planned* (`SURFACE_REQUESTS_BAR`), the spec's indefinite
article read literally. Whether *cannot* holds, or means *would rather not*, is the owner's
reading of the issue; the trigger puts the issue in front of them.

The reader recognises the form by **its field headings**, which GitHub renders as `### <label>`
over each answer — never by the label the form applies. A label is one click for anyone with
triage rights and a hand-typed word for anyone else, and a request under the label with no form
behind it would be a claim. The label (`surface-request`) exists for the humans reading the
tracker and is declared in `.github/labels.yml`; a test holds the reader's heading tuple to the
form's YAML, so renaming a field is caught. As with the cache reports, nothing the filer typed is
printed — the login and the issue number are GitHub's.

### Multi-tenancy, policy engine, RBAC — not evaluable as written, and reported so

*An organization commits to deploying the server profile* fails twice as an entry trigger. A
commitment is a promise, and no endpoint reports one; and the thing to be deployed does not
exist until 7.2 does, so the sentence cannot fire before the item it gates. The two candidate
instruments were both refused: a requester's public membership of a GitHub organisation would
turn *commits to deploy* into *asks on behalf of*, a re-cut of the meaning and not a reading of
it; and counting an organisation's word is the assertion ADR-0138 exists to replace.

The owner's decision (2026-09-24): **the row is read as a condition inside 7.2's own RFC**,
which must name its deployer, and not as an entry trigger. The tool reports it `UNREADABLE`
with that reason — ADR-0118's third value, which is neither a pass nor a finding and never moves
the exit code — and points at the HTTP API trigger as the door a deployer would come through
first. No number is invented and no D-0NN is spent on a threshold that cannot be read.

### Plugin sandboxing + signed registry — exists, and somebody else touched it

*≥ 1 third-party plugin with meaningful adoption exists.* The number is the spec's. Its three
words get readings a command can check, and the fourth is left where only a person can weigh it:

- **exists** — a repository that is not this one and **not a fork of it**, whose
  `pyproject.toml` declares a `mycelium.plugins` or `mycelium.modules` entry point, found by
  GitHub code search. Forks are excluded by flag because a fork of this repository carries
  `contrib/chats` and the plugin cookiecutter back to us — the mirror of ADR-0138's finding that
  a fork's copy of our own branch counted as a contribution.
- **adoption** — D-030's *engaged actor*, turned on the plugin's repository: at least one login
  that is neither the plugin's owner nor a bot opened an issue or a pull request there,
  commented, or holds a fork with a commit of their own (`PLUGIN_ADOPTERS_BAR`). A plugin nobody
  but its author has touched is listed and not counted.
- **meaningful** — the owner's judgement at the moment the trigger fires. There is no telemetry
  and there will be none (D-017), so nothing here can say how much a plugin is used; what it can
  say is that somebody other than its author cared enough to act.

### What a fired trigger is not

None of the three decides anything. The HTTP API row fires on a form that anyone with a GitHub
account can fill in, and the plugin row on a public repository anyone can create — so both can be
fired on purpose, and a fired trigger's whole effect is to put a decision in front of the owner
and hold the exit code until it is taken. The owner withdraws a request by closing its issue as
*not planned*; a plugin repository that is not a plugin is the owner's to disregard when they
decide. The magnitude that would justify an XL item with a new trust boundary is the decision
each trigger defers, and it is written nowhere in code.

## Alternatives Considered

- **Re-cut the RBAC row onto public organisation membership.** Offered to the owner and not
  chosen: observable, but a different sentence — *asks on behalf of an organisation* is not
  *commits to deploying*, and a trigger that fires on a proxy of its meaning is the assertion
  with a number on it.
- **Leave the RBAC row as written.** Rejected by ADR-0118: a deferral with no expiry.
- **Read plugin adoption as existence alone.** Offered and not chosen: it drops *adoption*
  rather than reading it, when D-030 already defines an observable act of adoption this tool can
  count on any repository.
- **Read plugin adoption from PyPI downloads.** Rejected: download counts are not exposed by the
  index's JSON API, the third-party services that publish them include mirrors and CI, and a
  plugin need not be on an index to exist — the cookiecutter's output is a repository first.
- **Recognise a surface request by its label.** Rejected: a label is a triage act, not the
  filer's, and can be added by hand to any issue. The form's rendered headings are the filer's
  own act and cannot be produced without answering the required fields.
- **Recognise a surface request by a hidden marker in the form's markdown.** Rejected: an
  invisible token is exactly the kind of thing a reader cannot audit; the headings are visible to
  everyone who opens the issue.
- **One trigger for the whole of 7.2.** Rejected: the spec wrote three rows because the three
  parts have three different consumers, and one of them turned out to have no reading at all —
  a single trigger would have hidden that.

## Consequences

- **`tools/adoption_report.py` evaluates four deferrals** — 7.1's and 7.2's three — and exits 1
  when any has fired, as before. Today it reads: HTTP API *holding* (no form filed), RBAC
  *unreadable* (by decision), plugin sandbox *holding* — code search finds no `pyproject.toml`
  outside this repository naming either group. Code search is a second GitHub API
  with its own rate limit and permissions; a refusal there is reported as an unreadable trigger,
  not a failed report.
- **The issue chooser gains a form**, and the tracker a label. The label has to exist on GitHub
  to be applied — `docs/workflow/github-setup.md` §2's import, or one `gh label create` — and
  the form is recognised whether or not it does. Filing the form is the first thing this
  repository asks a consumer to do that is neither a bug nor a feature request.
- **Spec 06 §3's three rows change by a parenthesis each**, none by a number; the RBAC row's
  parenthesis says it is read inside 7.2's RFC. `docs/workflow/adoption.md` gains the three;
  `docs/security/threat-model.md` §3 records the two new inputs to a maintainer-run tool — issue
  bodies matched on headings, and code-search results — and that neither is ever echoed beyond a
  login, an issue number and a repository slug.
- **What this does not do.** It builds none of 7.2 and writes none of its RFC. It cannot see a
  consumer that never files the form, a plugin whose repository is private or that code search
  has not indexed, or adoption that leaves no trace on GitHub; each is a reason a *holding*
  trigger is not proof of absence, and the report says *holding*, never *nobody*.

## References

- `tools/adoption_report.py`, `tests/test_adoption_report.py`,
  `.github/ISSUE_TEMPLATE/surface_request.yml`, `.github/labels.yml`.
- `docs/workflow/adoption.md` § *The deferred decisions it also watches*;
  `docs/security/threat-model.md` §3.
- Re-runnable: `python tools/adoption_report.py`.
