# 2026-09-11 — name the surface, do not freeze it (roadmap 5.14)

- **Session scope:** roadmap 5.14 — decide what the module-facing surface is, given that the
  first module depends on five components the 1.0 freeze does not cover (spec 02 §10, spec 05
  §4.3; ADR-0077).
- **PR:** #113 (`docs/name-the-module-facing-surface`). Follows #112, merged as `b1647df`.
- **Milestone 5:** 5.14 done. 5.15–5.19 and 5.21 open.
- **ADR:** [ADR-0086](../../../adr/0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md).

## An item that tells you not to decide it

5.14 is unusual: it names three candidate decisions and then says 5.5 deliberately took none
of them, because *"designing an API from a sample of one is how the first real user
contradicts it"*, and that it wants a second consumer or the 1.0 freeze review. The existing
allowlist, it says, "is the current answer, which keeps the coupling honest meanwhile."

So the work was to separate the half that is decidable today from the half that is not, and
to do it on evidence rather than on the item's summary.

## Measuring the coupling the item describes in prose

The item says "five components". It does not say which *names*, and the difference between
"the module imports `mycelium.ingest`" and "the module imports four names from it" is the
difference between a vague risk and a reviewable surface. Parsed from the module's sources:

| component | names | frozen by spec 02 §10? |
|---|---:|---|
| `sdk.types`, `sdk.identity`, `sdk.protocols` | 12 | yes |
| `cli.output` | 6 | no |
| `ingest` | 4 | no |
| `config` | 3 | no |
| `modules` | 2 | no |
| `chunking` | 1 | no |

Twenty-eight names, sixteen of them unfrozen. And reading why each is there settles the
item's third option immediately: a narrower contract has nowhere to go, because every one of
the five is a place where a second implementation would make the **product** inconsistent
rather than the module. Two configuration parsers make `mycelium.toml` mean two things on one
machine. Two secret scanners are two security postures. Two token estimates make
`--budget-tokens 4000` a different number in two places. Two output conventions break
ADR-0010's promise about exit codes and JSON. The coupling is the product being one product.

## The decidable half

Which components are module-facing is answerable now, from evidence, and asserting it commits
to no API shape. `mycelium.modules.MODULE_SURFACE` names the eight with the one-line reason
each is unavoidable, and states the rule that the surface within a declared component is its
`__all__`.

The part that actually changes behaviour is **where the list lives**. It was in
`contrib/chats/tests/test_acceptance.py` — the module's claim about itself — so a core author
who moved one of those surfaces met a failing test in somebody else's distribution, which
reads as the module's problem. Declared in the core it is the core's claim about what it
offers, and the difference is who the failure is addressed to. One list, two readers, which is
the discipline `verify.py` and CI already hold for the verification mode.

The gate got stronger while it moved: it used to reject a leading underscore, and now requires
every imported name to be in its component's `__all__`. Every current import already passes,
so it pins a property rather than demanding a fix.

## The half that is refused, and the evidence for refusing it

A `mycelium.sdk` façade re-exporting the doctrine is the tidiest-looking option and it is the
one to refuse. `mycelium.modules` already refuses three of D-023's four extension mechanisms
on the grounds that building them would freeze three contracts against no consumer; the fourth
thing a module needs is not exempt because it has *one*.

The sample contains its own warning. The module imports `ChunkingPolicy` — a whole policy
class — to read one default attribute, where `estimate_tokens` is what it actually depends on.
A façade built today would have re-exported the class, and that accident would have been the
API. One consumer cannot tell you which of its imports are doctrine and which are habit; a
second one can, by disagreeing. So the trigger is written into the constant rather than left
to memory: a second module, or the 1.0 freeze review at 6.1, whichever comes first.

I left that import alone rather than narrowing it. Changing another distribution's code for a
marginal gain, while the shape it should take is undecided, is churn — and as evidence for the
eventual decision it is worth more where it is.

## What did not change

Any runtime code path. The declaration is a constant; everything else is tests and
documentation. No gate, golden, baseline or corpus is touched.

## Lesson

When an item says the decision needs input you do not have, the work is not to wait and not to
guess — it is to find which part of the decision the missing input does not bear on. Here that
was *which* components are module-facing, answerable from the sources, versus *what shape* they
should eventually take, answerable only by a second consumer. Splitting the two took a parse of
the module's imports, and it turned an item that reads as "defer this" into one that ships a
declaration, two guards, a spec statement and a named trigger — while still refusing the part
that would have been a guess.
