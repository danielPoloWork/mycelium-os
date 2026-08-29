# Customization Overlays

How a maintainer or organization tunes EADOS **without editing the core**. Overlays are read
by the architect at interview/generate time and layered on top of the built-ins.

**Precedence (highest wins):** user overlay (this folder) → language profile → built-in
default. A blank/omitted overlay value falls through to the next layer.

## What you can override

| File | Effect |
|---|---|
| [`defaults.yaml`](defaults.yaml) | Pre-fills the interview's answers — default branch, license, group path, coverage target, commit scopes, i18n defaults. The architect uses these instead of the built-in defaults and still echoes them back for confirmation. |
| [`house-rules.md`](house-rules.md) | Organization-specific rules **injected into every generated `AGENTS.md`** as §14 (via `{{HOUSE_RULES}}`). Where a house rule conflicts with a default, the house rule wins. Empty by default (no §14 is emitted). |
| `agents/` | Drop custom role agents here, or a file overriding a shipped one (same name). They take precedence over [`../agent/`](../agent/README.md). Worked example: [`agents/example-role.md`](agents/example-role.md) — copy its shape, fill it in, and register it with a two-line `authority.yaml` record; no tool source reading required. |
| `interaction.yaml` | Tunes the [interaction policy](../orchestrator/os/interaction/_schema.md) (ADR-0022) — same-name overlay over `orchestrator/os/interaction/interaction.yaml` for the `sycophancy:` denylist and `confidence:` wording (e.g. your organization's own banned-opener list). The `dissent:`/`pushback:` protocol blocks are the contract, not overlay surface — and `pushback.human_decision` never relaxes (precedence layer 1 sits above every spec). Not shipped; create it the day you need it. |

## How it flows into a generated repo

1. The architect loads `defaults.yaml` and uses it to pre-fill the interview.
2. It copies the body of `house-rules.md` (if non-empty) into the manifest's
   `governance.house_rules`, which the renderer emits as `AGENTS.md` §14.
3. Custom `agents/` are offered alongside the shipped registry.

Nothing here is secret — keep tokens/webhooks out of these files (use CI secrets). Overlays are
committed and version-controlled like everything else, so a change to house rules is reviewable.

## Roles the factory does not ship

A DBA/data-engineer, performance-engineer, or SRE persona is a real need for some
organizations but not a universal one — exactly the logic [ADR-0004](../docs/adr/0004-seed-language-profiles.md)
already applies to languages (a profile ships when it earns broad demand, not speculatively).
These stay **organization overlays** under `agents/` (see the worked
[`example-role.md`](agents/example-role.md), a filled-in `performance-engineer`) rather than
shipped roles — add one the day a domain profile or your organization's scale genuinely needs it,
and it composes with the shipped registry exactly like any other overlay.
