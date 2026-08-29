# Agent Registry

The composable agent roles EADOS ships. Each file is a **portable agent definition** (a persona
+ an operating procedure + the agent-vs-human boundary). Drop one into a host that supports
subagents (`.claude/agents/`, a Codex/Gemini agent registry) or follow it inline. Every role
defers to the project's `AGENTS.md` as the source of truth and never crosses the human
boundary (draft/propose; the human opens, merges, publishes).

## Roles

| Role | Use it to… |
|---|---|
| [`enterprise-architect`](enterprise-architect.md) | Stand up and govern a project; drive the EADOS interview → generate loop. The orchestrating role. |
| [`reviewer`](reviewer.md) | Review a diff/PR against the spec, quality bar, and patterns policy; return structured findings. |
| [`security-auditor`](security-auditor.md) | Threat-model and audit for vulnerabilities, unsafe deps, and secret leaks; draft advisories. |
| [`contribution-reviewer`](contribution-reviewer.md) | Evaluate an inbound PR from a non-owner: provenance, the contribution policy, risk, and triage to a recommended disposition. Recommends; never merges. |
| [`release-manager`](release-manager.md) | Cut a SemVer release: bump, changelog, notes, tag, announcement draft. |
| [`profile-author`](profile-author.md) | Add or refresh a language profile (toolchain knowledge as data). |
| [`product-manager`](product-manager.md) | Own the "what"/"why": vision, priorities, the product spec (PRD/GDD). The Product pillar. |
| [`tech-lead`](tech-lead.md) | Lead a team technically: author RFCs, map requirements to tasks, approve RFCs/code. |
| [`qa-engineer`](qa-engineer.md) | Own the verification strategy end-to-end: negotiate the spec's §6 test strategy, author the test suite, enforce the coverage bar. |
| [`producer`](producer.md) | Guard delivery: negotiate the milestone roadmap, manage scope and dependencies. The Delivery pillar. |

## How they compose

A generation run is the **architect**; before the bootstrap PR it invokes the **reviewer** and
(for sensitive surfaces) the **security-auditor**; an inbound PR from a non-owner is the
**contribution-reviewer** (which composes those two and adds provenance + policy + triage); a
release is the **release-manager**; adding a language is the **profile-author**. The **tech-lead**
and the **qa-engineer** negotiate the verification strategy together at design time, and the
**qa-engineer** partners with the **reviewer** on the coverage bar at merge time — neither gatekeeps
alone. They share one contract, so handing off between them does not change the rules — only the
focus.

## Persona vs. authority (the separation is the point)

A role file here is the **persona** — behavior, procedure, boundary. A role's **authority** —
what it may *draft* / *approve* / *own* — lives separately, as data, in
[`../orchestrator/os/authority/authority.yaml`](../orchestrator/os/authority/authority.yaml)
(RFC-0001 §4). Keeping them apart is what lets a role act without holding approval authority over
an artifact (the `reviewer` comments on an RFC; only the `tech-lead` approves it).

The `authority-personas` self-lint enforces the pairing: every authority role has a persona here
**or** is declared in `pending_personas`, and every persona maps to a role. As of **M2**,
`product-manager`, `tech-lead`, and `producer` have landed, so `pending_personas` is now empty.

## Domain overlays

A persona can be **specialized per domain** without forking the role's authority. The default
persona is `agent/<role>.md`; an optional **overlay** at `agent/domains/<domain>/<role>.md` wins
for that domain. The manifest's `domain` (interview `Q0.4`) selects it, and the visible label comes
from the domain's `role_labels` — same authority role, domain-native behavior. So "Game Designer"
is the `game` overlay of `product-manager`, **not** a separate role (RFC-0001 §4; OQ4).

| Overlay | Specializes | Domain |
|---|---|---|
| [`domains/game/product-manager.md`](domains/game/product-manager.md) | `product-manager` → **Game Designer** (GDD, asset pipeline) | `game` |

Resolution: use `agent/domains/<domain>/<role>.md` if it exists, else `agent/<role>.md`. "Not yet
specialized" ≠ "unsupported" — add an overlay when a domain needs one.

## Customizing and adding roles

- **Override** a shipped role or **add** your own under
  [`../config/agents/`](../config/README.md) — overlays take precedence over these defaults, so
  you tune behavior without editing the core.
- A custom role should keep the same shape: frontmatter (`name`, `description`, `tools`), a
  persona, an operating procedure, and an explicit boundary. List it here (the self-lint checks
  that every role file is registered).

## Shared rules (all roles)

- **English on disk**, any language in chat (`AGENTS.md` §2).
- **Agent drafts; human opens/merges/publishes** (`AGENTS.md` §6.1 / §11).
- **Calibrated, non-sycophantic communication** — confidence tags earned by evidence, no
  courtesy openers, structured dissent, evidence-first pushback. One contract for every role
  ([`../orchestrator/os/interaction/interaction.yaml`](../orchestrator/os/interaction/interaction.yaml),
  ADR-0022; rendered into the governing `AGENTS.md`).
- **Measurable over asserted** — prove with tests/checks, not prose.
- **Learn** — record a generalizable lesson in [`../learning/lessons.yaml`](../learning/README.md).
