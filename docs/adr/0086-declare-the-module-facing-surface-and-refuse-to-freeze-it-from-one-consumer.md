# ADR-0086: Declare the module-facing surface — and refuse to freeze it from one consumer

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §10
- **Related:** [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the module that found this, and the gate that reports it),
  [ADR-0010](0010-adopt-cli-output-conventions.md) (the output doctrine a module reuses),
  [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md) and
  [ADR-0037](0037-record-what-was-refused-and-redact-what-was-found.md) (custody, secret
  scanning and redaction — the doctrine a module must not reimplement),
  [ADR-0007](0007-adopt-structure-first-chunking.md) (the token estimate a budget is counted
  in), [ADR-0014](0014-adopt-partial-strict-configuration.md) (the one configuration file a
  module reads its own section from), [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md)
  and [ADR-0005](0005-adopt-in-repo-identity-library.md) (two of the three frozen contracts a
  module builds on); spec 02 §10, spec 05 §§4.1, 4.3, doc 08 §10; D-012, D-017, D-023, D-025;
  roadmap 5.5, 5.14, 6.1

## Context

Spec 02 §10 names five contracts v1 may not change casually — identity rules, the KIR schema,
the snapshot manifest, the MCP tool contracts, and the plugin protocols. Everything else is
"an implementation detail, deliberately replaceable, and documented as such."

Roadmap 5.5 built the first module against that promise and gate 6 produced the finding it
exists for: a module needs more than the plugin API. The measurement, taken from the module's
sources rather than from its documentation:

| component | names imported | frozen by spec 02 §10? |
|---|---|---|
| `mycelium.sdk.types` | 6 | yes — records and identity formats |
| `mycelium.sdk.identity` | 4 | yes — identity rules |
| `mycelium.sdk.protocols` | 2 | yes — plugin protocols |
| `mycelium.cli.output` | 6 | **no** |
| `mycelium.ingest` | 4 | **no** |
| `mycelium.config` | 3 | **no** |
| `mycelium.modules` | 2 | **no** |
| `mycelium.chunking` | 1 | **no** |

Twenty-eight names across eight components; sixteen of them in five components the freeze does
not cover. And each of those five is there because a module that reimplemented it would be
*wrong* rather than merely different: a second configuration parser would make `mycelium.toml`
mean two things, a second secret scanner would be a second security posture (D-017), a second
token estimate would make `--budget-tokens 4000` a different number in two places, and a
second output convention would break ADR-0010's promise that every command exits 0/1/2 and
emits one JSON document. The coupling is not laziness; it is the product being one product.

So the risk is real: **every module that takes input into custody, scans it for secrets,
reports fidelity and prints like the core depends on surfaces that may move**, and the next
module will either reimplement them badly or depend on them too.

The item names three candidate decisions — a `mycelium.sdk` façade re-exporting the doctrine
and then freezing it; a documented statement that these components are public; or a narrower
module contract that does not need them — and then says what makes this hard: *"designing an
API from a sample of one is how the first real user contradicts it."*

## Decision

**The surface is declared, and it is not frozen.** `mycelium.modules.MODULE_SURFACE` maps each
module-facing component to the one-line reason it is unavoidable, and states the terms: an
installed module may import these and nothing else, and the surface within each one is its
`__all__`. That is the item's second option taken in the narrowest form that asserts no API
shape — it says *what* a module may reach for and *why*, and says nothing about how it will
eventually be spelled.

**The declaration lives in the core, and the module's gate reads it.** Until now the allowlist
was restated in `contrib/chats/tests/test_acceptance.py`: the module's claim about itself. A
core author who moved one of those surfaces met a failing test in somebody else's
distribution, which reads as the module's problem. Declared in the core, it is the core's claim
about what it offers, and the difference is who the failure is addressed to. One list, two
readers — the same discipline `tools/verify.py` and CI hold for the verification mode.

**The gate is strengthened while it moves.** It used to reject a name beginning with an
underscore; it now requires every imported name to be in its component's `__all__`. Every name
the module already imports passes today, so this pins a property rather than demanding a fix —
and it closes the gap where a public-looking name that a component never exported would have
slipped through.

**The shape is refused, explicitly, with a trigger.** A `mycelium.sdk` façade re-exporting the
doctrine would freeze a module-facing API against a sample of one, which is exactly the refusal
`mycelium.modules` already makes for pipeline stages, lifecycle hooks and MCP tools: three of
D-023's four mechanisms are unbuilt because building them would freeze three contracts against
no consumer. The same reasoning applies to the fourth thing a module needs, and it is not
weakened by the fact that this one has a consumer — it has *one*. The trigger is a second
module, or the 1.0 freeze review (roadmap 6.1), whichever comes first, and it is written into
the constant rather than left to memory.

**Adding an entry stays the reviewable event**, and it now happens in the core. It means a
module needed something the core did not offer as module-facing, which is either an API gap to
fix or a coupling to record before the freeze.

## Alternatives Considered

- **Build the `mycelium.sdk` façade now and freeze it at 1.0.** The tidiest-looking option and
  the one this ADR exists to refuse. A façade's value is that it hides which internals move;
  its cost is that it fixes, permanently, which of one consumer's needs were essential. Of the
  sixteen unfrozen names, the module's own usage already shows one that is almost certainly
  accidental — it imports `ChunkingPolicy` to read a single default attribute, where
  `estimate_tokens` is what it actually depends on — and a façade built today would have
  re-exported the class. One consumer cannot tell you which of its imports are doctrine and
  which are habit; a second one can, by disagreeing.
- **Declare the five components *frozen*, joining spec 02 §10's five contracts.** Rejected for
  the same reason at higher stakes: spec 02 §10's list is what the Phase-5 platform must not
  break, and adding `mycelium.config` and `mycelium.cli.output` to it on the evidence of one
  in-repo module would bind the platform phase to a CLI's colour policy.
- **Narrow the module contract so these are not needed** (the item's third option). Rejected
  on the reasons in the table above: each of the five is a place where two implementations
  would make the *product* inconsistent, not merely the module. The one place narrowing is
  available — the token estimate — is recorded here as evidence for the eventual shape rather
  than acted on, because changing another distribution's code for a marginal gain is churn
  while the shape is undecided.
- **Leave the allowlist in the module and change nothing.** Genuinely arguable: the item calls
  the existing guard "the current answer, which keeps the coupling honest meanwhile", and it
  does. Rejected because it leaves the statement in the wrong place — the core can move a
  module-facing surface and the only signal is somebody else's test — and because "which
  components are module-facing" is answerable now, on evidence, without touching the question
  that needs a second consumer.
- **Write the statement in prose only, with no guard.** Rejected on this project's standing
  rule: a claim without a check is a claim. Two guards now hold it, one on each side.

## Consequences

- **The decision that needed a second consumer is still open, and now has a trigger and a
  measurement waiting for it.** Whoever takes it at roadmap 6.1 starts from the table above
  rather than from a re-reading of the module's sources.
- **A core author changing `cli.output`, `config`, `ingest`, `chunking` or `modules` meets a
  named list saying modules import this.** That is the whole behavioural change, and it is the
  one the item asked for: the coupling stops being implicit.
- **Two guards, one on each side.** `tests/test_modules.py` holds the core to its declaration —
  every entry importable, exporting a curated `__all__` whose names all resolve, with its
  reason, and the frozen/unfrozen split pinned so a quiet promotion is a decision rather than a
  diff. `contrib/chats/tests/test_acceptance.py` holds the module to it. Neither restates the
  other.
- **Nothing about the product's behaviour changes.** No runtime code path moved: the
  declaration is a constant and the rest is tests and documentation. No baseline, golden, gate
  or corpus is touched.
- **Spec 05 §4.3 gains the statement**, next to the stability tiers it belongs beside — those
  tiers say where a *plugin* lives and what SemVer covers it, and said nothing about what the
  core promises a module that imports it.
- **A limitation, stated.** The declaration says which components are module-facing, not which
  *names* within them will survive. A module pinned to `mycelium.cli.output.detail` can still
  be broken by a rename inside a declared component — caught by CI because the in-repo module
  is tested, and not caught at all for a community module until the freeze review settles the
  shape. That is the residual risk this ADR does not remove, and naming it is the point.

## References

- Spec: `.draft-specs/02-architecture.md` §10 (the five frozen contracts);
  `.draft-specs/05-interfaces-and-plugins.md` §4.1 (the plugin API), §4.3 (stability tiers,
  amended here); `.draft-specs/08-module-chats.md` §10 (the sixth acceptance gate).
- Decision log: D-012 (a plugin is installed code), D-017 (one doctrine for untrusted input),
  D-023 (extension mechanisms built against consumers, not in advance), D-025 (modules).
- Re-runnable: `python -c "from mycelium.modules import MODULE_SURFACE; print(*MODULE_SURFACE)"`,
  and the two guards in `tests/test_modules.py` and `contrib/chats/tests/test_acceptance.py`.
