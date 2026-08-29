# The delegation routing hook — applying a routed model + effort to delegated subagent work

Routing is **advisory-first** ([`_schema.md`](./_schema.md), ADR-0017): the OS recommends a
capability tier + effort and states it at its read-points (Step-0 triage, `/eados status`, the
`.issues/` planning docs — M16 16.1–16.3). This document defines the **one place the advice is
*applied* rather than merely printed**: when a governed command **delegates a sub-task** to a host
that supports **per-delegation model selection**, the adapter resolves the sub-task's route and
passes the concrete **model + effort** to the delegation call (M16 16.4, #255). Everywhere else,
and for hosts without that control, the hook **degrades to advisory-only** — it states the route
and proceeds at the session model, never attempting a switch.

## The hard limit — the session model is the human's (RFC-0001 human-in-the-loop)

No host lets an agent change its own **top-level session model**; that is a human action (e.g.
Claude Code's `/model`). The hook **never** tries to. It only ever sets the model of **work the
run spawns beneath itself** — a delegated subagent. If the route computed for the *whole run*
(the top-level unit of work) differs from the current session model, the OS **prints the advice
and stops** — the human re-invokes under the right model or accepts the mismatch. This is the same
only-recommend-never-switch boundary the milestone lists as an invariant, and the same
agent-drafts / human-decides posture as `AGENTS.md` §6. Auto-application is *downward only*: a run
may route the work it delegates; it may not re-route itself.

## The hook contract

For each delegated sub-task, deterministically and with no model in the loop:

1. **Signals** — the sub-task's own tracker labels plus any asserted flags (`sets-pattern`,
   `decision-heavy`). A sub-task is a *unit of work*; it carries its own signals, so different
   delegations of one run route differently (a design sub-task and its follow-up implementation do
   not share a tier by default — each earns its own).
2. **Resolve** — evaluate the policy for the target host:
   ```bash
   python .eados-core/tools/route_advice.py --labels "<sub-task labels>" \
     [--flags <asserted flags>] [--host <host>] --json
   ```
   `route_advice.py` ([tool](../../../tools/route_advice.py)) returns `{tier, effort, model, host,
   …}` by the policy's monotonic escalation — the model name comes only from the dated
   `catalog:` in [`routing.yaml`](./routing.yaml), never from the adapter.
3. **Apply** — pass the resolved **model** and **effort** to the host's delegation mechanism (the
   matrix below), translating effort through the host's `effort_aliases` at the edge. On a host
   without per-delegation model control, **skip step 3** and state the route instead (advisory
   fallback).

The advice never overrides an **explicit human choice**: if the operator pinned a model/effort for
the delegation, that wins — the hook fills the gap, it does not seize the wheel.

## Host application matrix

| Host | Reaches (providers) | Per-delegation model control | Hook behaviour |
|---|---|---|---|
| **claude-code** | anthropic | **yes** — Agent-tool `model:` parameter per spawn; `model:` frontmatter on a persisted subagent definition; effort via the `ultracode` alias (→ `max`) | **applied** — resolve → pass `model` + effort to each delegation |
| **codex** | openai | not today | **advisory-only** — state the route for the sub-task; proceed at the session model |
| **gemini** (Antigravity) | google | not today | **advisory-only** — state the route for the sub-task; proceed at the session model |
| **opencode** (model-agnostic) | anthropic, openai, google, mistral, alibaba-qwen, moonshot, sakana | not today | **advisory-only** — state the route for the sub-task; proceed at the session model |

The matrix tracks the `catalog.hosts` in [`routing.yaml`](./routing.yaml): **every** catalog host
appears here as either *applied* or *advisory-only*, so a host added to the catalog cannot be
silently left without a stated delegation posture (enforced by the `routing-delegation` self-lint).
A host graduates from advisory-only to applied the day it ships per-delegation model control — a
one-row edit here, no policy or tool change.

The **Reaches** column is the schema-v2 half (ADR-0024 D1): a host declares which *providers* it
can drive, and the model for a tier is selected from those providers' catalogued models rather than
stored per host. `opencode` is the case the flat v1 shape could not express at all — one runtime,
seven vendors, one entry. A host whose reachable providers have **no assessed model** for a tier
resolves tier and effort but no model name, and says so: the recommendation is vendor-neutral, so
only the name is lost (ADR-0024 D4/D6). That is today's state for `gemini`.

## Worked example (claude-code) — the four-role relay

The governed form of the "four elite agents" relay: **architect → engineer → reviewer →
optimizer**, expressed as EADOS roles ([`authority.yaml`](../authority/authority.yaml)). One run
delegates four sub-tasks; each delegation carries the route its **own** signals earn, not a
per-role constant — the point of routing is that the *work*, not the *seat*, sets the tier.

| # | Role (persona) | Sub-task | Signals | Route → model / effort |
|---|---|---|---|---|
| 1 | **architect** — `enterprise-architect` | Decide the architecture / author the ADR | `flag:decision-heavy`, `label:adr` | **frontier-reasoning / high** → Fable 5 |
| 2 | **engineer** — `tech-lead` | Implement the RFC the architect set (`src/**`) | `label:severity:high` (pattern-following) | **standard / high** → Opus 5 |
| 3 | **reviewer** — `reviewer` | Return structured findings on the change | `label:severity:high` | **standard / high** → Opus 5 |
| 4 | **optimizer** — `tech-lead` under [`/eados optimize`](../../commands/optimize.md) | Measure-first tune to a numeric NFR budget | `label:severity:medium` | **standard / medium** → Opus 5 |

Since 19.7 each seat is also a **step**, so the relay can be resolved without hand-assigning
anything: `--step design` for the architect, `--step review` for the reviewer, `--step optimize`
for the optimizer. A step **raises** the route and can never lower it, so the architect's seat
earns depth on a cheap item while a *protected* item keeps its floor in every seat — including the
mechanical ones.

Each row's route is exactly what `route_advice.py --labels … [--flags …] [--step …]` returns for
that row's signals — the table is not hand-assigned. On claude-code the run **applies** it: delegation 1 is
spawned with `model:` = the frontier-reasoning name and effort `high`; delegations 2–4 at their
resolved model + effort. The **architect's decision surface earns the top tier and every follower
inherits a cheaper route** — the `sets-pattern` economics, now mechanical. Note the honest mapping:
EADOS has no distinct "optimizer" role — the fourth seat is the `tech-lead` acting under the
measure-first `/eados optimize` discipline; the reviewer holds **no** final authority (it returns
findings, it does not approve), exactly as the relay's reviewer recommends but never merges.

Run the same relay on codex or gemini and step 3 is skipped: the run **states** each sub-task's
route ("architect sub-task → frontier-reasoning / high → GPT Sol (advisory — this host has no
per-delegation model control; proceeding at the session model)") and delegates at the session
model. Same advice, no bypass.

## Invariants

- **Downward only.** The hook sets the model of *delegated* work; it never switches the top-level
  session model — that action does not exist below the human (RFC-0001, ADR-0017, `AGENTS.md` §6).
- **Deterministic.** The route is `route_advice.py` over [`routing.yaml`](./routing.yaml) — same
  signals, same model, no LLM in the routing loop. Model names live only in the dated `catalog:`.
- **Explicit human choice wins.** A delegation the operator pinned is left untouched; the hook only
  fills an unset model/effort.
- **Advisory fallback is not a downgrade of governance.** On an advisory-only host the work is
  still fully governed (ownership, one-PR, human-gated merge); only the *model selection* reverts
  to the session default.
- **Every catalog host is accounted for** in the application matrix — applied or advisory-only —
  so adding a host forces a stated delegation posture (`routing-delegation` self-lint).
