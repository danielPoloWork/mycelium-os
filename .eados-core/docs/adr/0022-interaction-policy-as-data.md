# ADR-0022: Interaction policy as data — calibrated confidence, suppressed sycophancy, structured dissent

## Status

Accepted (2026-07-11)

## Context

*Numbering note:* the M17 plan and issue #277 reserved "ADR-0019" for this decision; that number
was consumed by the command-surface taxonomy (ADR-0019, M15) after the milestone was drafted.
Numbering is sequential and never reused (`docs/adr/README.md`), so the decision lands as
ADR-0022; the milestone plan is corrected in the same PR.

EADOS governs *what* the agent may do — workflow, authority, git, contribution, routing — but said
nothing about **how it communicates while doing it**. No spec, persona, or contract section covered
confidence calibration (when the agent must say it is guessing), sycophancy (courtesy openers,
reflexive agreement), or how to disagree with the maintainer — verified 2026-07-11: zero hits
across `os/`, `agent/`, and both contracts. The result was host-default behavior: agreeable,
uncalibrated, warm-up prose — exactly the posture the enterprise system is supposed to prevent.

The owner provided an interaction ruleset (2026-07-11, 7 rules: anti-sycophancy, confidence tags,
structured disagreement, don't-fold) — the third input of the prompt-pack family (11-prompts doc →
M15 / ADR-0018; routing table → M16 / ADR-0017). It names the gap precisely, but two of its rules
are counterproductive if adopted verbatim: rule 1 forces contrarianism, rule 7 entrenches errors
and collides with the human terminal gate. ADR-0017 set the precedent for this situation: adopt an
owner-provided ruleset as the seed, record every transformation, ship the result as data.

## Decision

1. **Policy-as-data, the ninth spec.** `orchestrator/os/interaction/` ships
   [`_schema.md`](../../orchestrator/os/interaction/_schema.md) +
   [`interaction.yaml`](../../orchestrator/os/interaction/interaction.yaml) with four blocks —
   `confidence:`, `sycophancy:`, `dissent:`, `pushback:` — following the risk-weights (#79) and
   routing (ADR-0017) precedent: vocabulary and protocols are YAML the lint validates against a
   schema, never prose a contract paraphrases from memory. Registration is by discovery:
   `os-spec-completeness` auto-discovers the directory, `data-file-validity` parse-checks the
   instance, and the existing `.eados-core/orchestrator/os/**` gate-coverage row covers the files
   once tracked — no new lint entry is added: the existing row already covers the class (a second
   row would be redundant — one row per class by convention), and a row added ahead of its files
   would trip the stale-entry hygiene check. The acceptance's "untracked-file lint trap" resolves
   by commit, not by registry edit.
2. **Confidence: a vocabulary with evidence criteria and a scope rule.**
   `certain` / `likely` / `guessing`, each *earned* by an evidence criterion (certain = verified
   this session or an in-repo fact, cite it; likely = inference from named evidence, state it;
   guessing = gap-filling, flagged where it is made; a mostly-guessed reply says so first). The
   scope rule is the hardening that makes the vocabulary usable: tag **load-bearing claims** —
   recommendations, risk calls, decision-driving facts — not every sentence. Alignment with
   interview provenance (#169), stated precisely: `guessing` is the conversational analogue of a
   manifest answer whose provenance is `defaulted` (glossed *assumed*) — the milestone's shorthand
   "`guessing` ↔ `assumed`" resolves to the on-disk enum value `defaulted`, since the provenance
   vocabulary is `{asked, defaulted, imported}` (`render.py`).
3. **Sycophancy: a denylist as data, with its ceiling stated.** The banned-opener/phrase list
   ("Great question", "You're absolutely right", "That makes a lot of sense", "Absolutely",
   "Definitely", plus the praise-as-opener and reflexive-agreement classes) lives in
   `interaction.yaml`, overridable via a same-name `config/interaction.yaml` overlay — the first
   `os/` spec with a config overlay surface, registered in `config/README.md`'s "What you can
   override" table like the persona overlays. The spec says out loud what a denylist cannot do: a
   model can route around it; the list suppresses the worst offenders, the posture rules do the
   rest. The lint-registry row for a *committed* overlay lands with the first overlay file — it
   cannot be pre-added (stale-entry hygiene).
4. **Dissent: the ADR pattern applied to conversation.** The structured-disagreement template —
   reason / alternative / specific downside — plus uncomfortable-answer-first ordering and no
   warm-up prose. Escalation beyond the conversation follows the authority ladder; once the human
   decides, the dissent is recorded and never relitigated (a still-open claim stays governed by
   the pushback protocol).
5. **Pushback: claims vs decisions.** Replaces the source "don't fold" rule. A factual *claim*
   follows the evidence: on pushback, re-verify (never restate from memory), hold the claim only
   while the evidence still supports it, concede explicitly when wrong. A human *decision* is
   precedence layer 1 (`os/README.md`): comply and record the dissent. The precedence order is
   untouched.
6. **The enforcement ceiling, recorded honestly.** Three tiers: *instruct* (live chat — no gate
   can verify a conversation turn), *verify* (on-disk artifacts — lint; the 17.3
   `interaction-lockstep` gate keeps contract prose and this data congruent), *re-ground* (the
   M14 runtime hooks re-inject the posture, 17.4). One layer sits above all of it: a host's own
   system prompt constrains tone before `AGENTS.md` is read — the contract applies where the host
   permits (ADR-0015/0016 honesty posture). Never marketed as a guarantee.
7. **Scope boundary: generic interaction core only.** Per-activity interaction shapes (review /
   debug / optimize) stay in the commands and personas that own those activities (M8, M15).
   A parallel per-activity module catalog is declined — identity creep toward a prompt library
   (RFC-0001). Confidence calibration, uncertainty handling, challenge technique, and trade-off
   structure enter the generic core instead.

### Source ruleset → disposition (owner ruleset, 2026-07-11)

| # | Source rule | Disposition | As adopted |
|---|---|---|---|
| 1 | Never start with agreement; first sentence must challenge | **transformed** | "Open with the most informative statement; never a courtesy opener" (`sycophancy.opening_rule`). Forced contrarianism is as uncalibrated as flattery; manufactured challenges devalue real ones. |
| 2 | Tag every claim `[certain]` / `[likely]` / `[guessing]` | **adopted + hardened** | Vocabulary kept (`confidence.levels`), with an evidence criterion per level (`confidence.criteria`) and the scope rule: tag load-bearing claims, not every sentence. "Mostly guessing → say so first" kept (`confidence.mostly_guessing`). Aligns with #169 provenance: `guessing` ↔ `defaulted` (assumed). |
| 3 | Kill sycophantic phrases ("Great question", …) | **adopted as data** | `sycophancy.banned_openers` + `banned_classes` in `interaction.yaml`, overridable via `config/interaction.yaml`. Honest caveat in the spec: a denylist suppresses the worst offenders; the posture rules do the rest. |
| 4 | Structured disagreement: reason / alternative / specific risk | **adopted verbatim** | `dissent.template` — the ADR pattern applied to conversation; escalation wired to the authority ladder. |
| 5 | Uncomfortable answer first | **adopted verbatim** | `dissent.ordering` — first line, not paragraph three. |
| 6 | No warm-up paragraphs | **adopted verbatim** | `dissent.warm_up` — start with the most useful thing. |
| 7 | Don't fold on pushback without new information | **transformed** | `pushback:` — re-verify the evidence; hold a claim only while the evidence still supports it; concede explicitly when wrong. A human decision is precedence layer 1 — comply + record dissent, never relitigate. An absolute no-fold rule entrenches errors and collides with the human terminal gate. |
| — | Evolve into a framework with per-activity modules (architecture / research / code review) | **declined** | Identity creep toward a prompt library (RFC-0001); per-activity behavior stays in commands + personas (M8, M15); confidence calibration, uncertainty handling, challenge technique, and trade-off structure enter the generic core instead. |

## Consequences

- The vocabulary is now *set*: 17.2 renders it into every agent contract surface, 17.3 gates
  prose↔data congruence (`interaction-lockstep`), 17.4 re-grounds it at runtime, 17.5 documents it
  — every later item inherits this ADR's vocabulary instead of inventing its own.
- Manual registries touched in this PR: the `os/README.md` spec table (ninth row), the
  `config/README.md` override table (the `config/interaction.yaml` surface), the ADR index, the
  M17 plan's ADR-number correction. Everything else registers by discovery.
- `cross-spec-consistency` does not yet load the `interaction` spec (its spec set is hardcoded);
  wiring it in is part of 17.3's cross-spec refs, alongside the `interaction-lockstep` gate.
- No worked-example `examples:` surface (#224) yet — which confidence tag a real claim deserves is
  a natural few-shot surface once 17.4's runtime use accumulates judged cases; adding it later is
  a data edit plus one `EXAMPLE_SURFACES` registration.
- Live-chat behavior remains *instructed*, not enforced — the ceiling is permanent, not a TODO.
  What becomes mechanically checkable is exactly the artifact layer: the spec parses, defines its
  schema keys, and (from 17.3) stays congruent with the contracts rendered from it.
- Alternatives rejected: **(a) verbatim adoption** — rules 1 and 7 are counterproductive as
  written (forced contrarianism; entrenched error, terminal-gate collision); **(b) a per-activity
  interaction framework** — prompt-library identity drift, declined above; **(c) contract prose
  without a data spec** — unlintable, drifts per surface, and abandons the policy-as-data
  precedent (#79, ADR-0017); **(d) a blocking live-chat gate** — cannot exist; claiming it would
  violate the ADR-0015/0016 honesty posture.

## References

- Issue #277 (M17 17.1); milestone plan `.issues/M17-interaction-contract-milestone.md` — the
  ratified decisions and the source-ruleset disposition table this ADR records permanently.
- Owner-provided interaction ruleset (2026-07-11) — third input of the prompt-pack family
  (11-prompts doc → M15 / ADR-0018; routing table → M16 / ADR-0017).
- ADR-0017 (transformed adoption of an owner ruleset; policy-as-data); risk-weights-as-data
  (#79); worked-example decision surfaces (#224, M14); interview provenance (#169).
- ADR-0015 / ADR-0016 (the honesty posture the enforcement ceiling follows); ADR-0019
  (command-surface taxonomy — the numbering collision noted above); RFC-0001 (identity boundary:
  a delivery OS, not a prompt library).
