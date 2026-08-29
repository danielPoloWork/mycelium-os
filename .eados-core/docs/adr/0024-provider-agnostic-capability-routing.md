# ADR-0024: Provider-agnostic, capability-driven model & effort routing

## Status

Accepted (2026-07-26)

Extends [ADR-0017](0017-model-effort-routing.md). Everything ADR-0017 decided stays in force —
tiers-not-names, advisory-first, the OS-neutral effort vocabulary, and the downward-only
application boundary are reaffirmed here, not revisited.

## Context

ADR-0017 made model & effort routing a policy-as-data layer and got the central abstraction right:
the rules speak **capability tiers**, concrete model names live only in a dated catalog, and model
churn is a catalog edit rather than a code change. It also anticipated growth — *"a future host (or
a re-ranked market) is one catalog entry, not a schema change."*

That promise was never exercised, and the distance between it and the shipped state became
material once EADOS started being used under agents other than Claude Code. The maintainer stated
the requirement on 2026-07-26: EADOS will not always run under Claude — GPT, Gemini, Mistral, Qwen,
Kimi, Sakana and others are all plausible — and the OS must determine, **from whichever LLM it is
actually running under**, the best model and effort for each step of a milestone, using the best
available combination while treating tokens as a real but secondary constraint.

Four gaps block that, all verified in-tree at v2.11.0 with every gate green:

1. **The catalog is single-host.** `catalog.hosts` held one entry while `os/routing/delegation.md`
   documented three; `route_advice.py --host codex` failed with `unknown host` on a host the
   documentation said was supported. The `routing-delegation` self-lint checks only catalog→matrix,
   so it could not see the reverse. (#326 has since added `codex` as data; #327 covers the lint.)
2. **Nothing knows which host is running.** `_host_entry(spec, host=None)` returns `hosts[0]`, so a
   caller that does not pass `--host` silently receives the first host's model names — Anthropic
   names on any host.
3. **Resolution is a name lookup, not a capability match.** `tier → "Opus 5"` is a string per host.
   A model's context window, effort ceiling, cost and availability are unrepresentable, so they
   cannot participate in the decision.
4. **No cost dimension, and freshness is a suggestion.** `catalog.as_of` is documented as *"the
   review cue"* with nothing enforcing it. The cue was missed: until #326 the catalog routed every
   ADR, security and foundational-decision unit of work to a model all three READMEs described as
   not benchmarked for EADOS.

Per the L-0004 discipline, ADR-0017 was read first. It decides tiers-not-names, the advisory-first
posture, the effort vocabulary and the application boundary. It is **silent** on host identification,
multi-provider catalogs and cost as a resolution input. These are gaps, not rediscovered trade-offs.

## Decision

### D1 — Two-level catalog: providers describe capability, hosts declare reach

```
providers[] → models[]    # what exists, and what it can do (vendor-keyed)
hosts[]     → providers[] # what this runtime can actually reach
```

A **provider** is a vendor (`anthropic`, `openai`, `google`, `mistral`, `alibaba-qwen`,
`moonshot`, `sakana`, …). A **host** is a runtime (`claude-code`, `codex`, `gemini-antigravity`,
`opencode`, `cline`, `aider`, …). The split is what makes model-agnostic hosts representable: a
host reaching six providers is one entry listing six ids, not six fictitious hosts. Adding either
is configuration data; no code and no schema change.

*Rejected — a flat host→models map (the v1 shape) extended with more hosts.* It cannot express a
model-agnostic runtime at all, and the vendors the maintainer named are reached mostly through
exactly those runtimes. Representing them would require inventing one pseudo-host per
host×provider pair, duplicating every model record.

*Rejected — a provider-keyed catalog with hosts referencing models directly.* Normalized and
duplication-free, but it introduces a join the evaluator does not need: reach is a property of the
host, and expressing it as a provider list keeps resolution a filter rather than a graph walk.

### D2 — Resolve by capability, never by name

A model entry declares what it **meets**: the tier it satisfies, its effort ceiling, its context
window, a relative cost, and its own verification date. Resolution splits into two phases with
different jobs:

1. **Escalation → the floor.** Unchanged from ADR-0017. Start at `defaults`, every matched rule
   raises `min_tier`/`min_effort`, take the max. Pure quality; monotonic, deterministic and
   order-independent.
2. **Selection → the model.** Among models reachable by the resolved host that meet or exceed the
   floor, pick by the declared preference order.

The orchestrator never asks *"what is this host's frontier model called"*. It asks *"what is the
cheapest reachable thing that clears this bar"*. A market re-ranking becomes a catalog edit that
the evaluator absorbs without being told which name moved where.

### D3 — Quality-first with cost awareness, as a structural invariant

The maintainer's principle — *use the minimum model that satisfies the step's quality objectives;
raise when complexity, risk or criticality demand it; never downgrade in a way that compromises
quality, security or an ADR; treat tokens as a secondary constraint, not the objective* — is
implemented by constraining **where** cost may act, not by a weighting heuristic:

> **Cost may only choose among models that already clear the earned floor. It can never lower the
> floor.**

This is the reason phase 1 and phase 2 are separate. "Minimum sufficient model" is not new
behaviour to add: it is what the existing monotonic floor already computes. The floor *is* the
minimum that satisfies quality, and cost then picks the cheapest way to reach it. The escalation
invariant survives intact, and a security or ADR route cannot be quietly degraded to save tokens
because cost never operates on the floor at all.

`protected:` (`label:security`, `label:adr`, `flag:decision-heavy`) is declared in the policy so
the guarantee is data a gate can read, rather than a property of the code that happens to hold.
When no reachable model clears the floor, the answer is a loud failure naming the floor — never
the closest cheaper thing.

*Rejected — a budget posture that may cap the resolved tier.* More powerful, and it breaks the
only-add-never-relax property that makes resolution order-independent. Its safety would then rest
on a carve-out list being complete, which is precisely the kind of invariant that decays.

*Rejected — cost as a first-class rule input alongside labels and flags.* Maximum flexibility, at
the price of the determinism ADR-0017 lists as an invariant: rules that can resolve downward are
no longer monotonic, and the result becomes order-dependent.

### D4 — Host identity comes from evidence, never from self-report

**The OS must not derive its host by asking the agent what model it is.** Models misdescribe their
own identity, and most confidently right after a version change — exactly when routing most needs
to be right. A route computed from a hallucinated self-description is worse than no route: it is
wrong *and* it looks authoritative. The resolution ladder, in precedence order:

| Rung | Source | Why it wins |
|---|---|---|
| 1 | `--host` / `--model`, or `routing.host` in the manifest | An explicit human instruction; ADR-0017 keeps model authority with the human |
| 2 | `detect:` markers declared per host as data | Deterministic environment evidence |
| 3 | **unknown** | Loud. Never `hosts[0]`. |

Rung 3 is what makes this honest, and it costs less than it appears: because tiers and efforts are
vendor-neutral, an unresolved host loses the model **name** and nothing else. The recommendation —
`frontier-reasoning / high` — remains fully valid and actionable. Ambiguous evidence is reported as
ambiguous and falls to rung 3 rather than picking a winner.

**Reconciliation with M18.** M18 ratified that the consumer route checkpoint takes the session
model from `--current-model` and is honest that the provenance is self-report (L-0006). That stands
and is not reopened. The distinction drawn here is narrower and compatible: an explicitly *supplied*
model is authoritative input (rung 1); what the OS must never do is *derive* the host by
introspection. Where an agent fills that argument itself, the output labels the provenance as
self-reported — as M18 already requires.

### D5 — `extra` joins the effort scale

`efforts: [low, medium, high, extra, max]`, the maintainer's five-level vocabulary. Hosts continue
to map their own words through the catalog, and a model's declared effort ceiling bounds what may
be asked of it. Inserting a level changes what every existing `min_effort: high` rule means
relative to the ceiling, so the rule table gets a deliberate re-read rather than a mechanical
migration.

### D6 — Freshness becomes enforceable; the catalog stays hand-maintained

`catalog.as_of` gains a `max_age_days` companion, and per-model verification dates carry provenance
at the granularity that actually rots. A `catalog-freshness` self-lint turns the review cue into a
gate.

A model the maintainer has not assessed is **catalogued but not selectable**: recorded as
reachable, marked unassessed, and excluded from selection rather than given an invented capability
claim. This is the direct lesson of #326, where a confident claim nobody had verified routed the
factory's most consequential work for weeks.

*Rejected — refreshing the catalog from vendor APIs.* It requires network access plus per-vendor
authentication inside a gate, and it re-runs the reasoning ADR-0009 §3 used to decline
per-ecosystem SHA pinning: new per-vendor maintenance for a fact a dated human review already
captures. A network-dependent gate must also never fail closed on a missing network, which would
make it advisory anyway.

## Consequences

- Adding a provider, a model or a host is a data edit — no code, no schema change. The market may
  re-rank without the factory noticing structurally.
- Advice degrades honestly instead of silently: an unknown host yields tier and effort with the
  model name explicitly unresolved and the reason stated.
- `routing.yaml` moves to `version: 2`. The shape change is breaking for direct readers, so the
  schema, the instance and `_schema.md` ship together.
- Cost becomes visible in the output — the chosen model's relative cost and the alternatives that
  also cleared the floor — without becoming a lever on quality.
- The `protected:` guarantee and the "no model below the floor" property become testable
  invariants rather than review conventions.
- Two claims in this record are the ones most likely to be re-litigated later, and are written down
  with their reasoning for that reason: **D4** (no model self-report) and **D6** (no API-driven
  catalog refresh).
- The `examples:` decision surface and the worked delegation relay both speak tiers, so neither
  needs to change when the catalog does.

## References

- [ADR-0017](0017-model-effort-routing.md) — model & effort routing; extended, not superseded.
- [ADR-0009](0009-ci-supply-chain-pinning.md) §3 and its 2026-06-28 addendum — the precedent for
  declining per-vendor maintenance inside a gate, reused in D6.
- [ADR-0022](0022-interaction-policy-as-data.md) — policy-as-data; [ADR-0015](0015-web-domain-and-enterprise-posture.md) /
  [ADR-0016](0016-authoring-language-model.md) — the honesty posture behind D4's loud unknown.
- [ADR-0023](0023-scaffold-routing-surface.md) — the rendered catalog surface consumers see.
- `os/routing/_schema.md`, `os/routing/routing.yaml`, `os/routing/delegation.md`,
  `tools/route_advice.py`.
- Lessons: L-0003 (reject rather than guess), L-0004 (check the governing ADR first — applied
  above), L-0006 (state what was not verified), L-0008 (assert the classification, not a proxy).
- M19 plan: `.issues/M19-provider-agnostic-routing-milestone.md`; items #322–#328. The catalog
  contradiction that motivated the milestone: #326 / PR #330.
