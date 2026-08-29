# ADR-0005: Seed Scala, Kotlin, Swift, Dart, Ruby, and legacy COBOL & Pascal

## Status

Accepted

## Context

After the first six general-purpose seeds (ADR-0004), the maintainer asked for additional
modern languages (Scala, Kotlin, Swift, Dart, Ruby) and legacy languages (COBOL, Pascal,
QBasic, "etc"). The genericity rules (data, not code) make adding any language additive, but
each seed must meet the ground-truth bar of `cpp.yaml` and be proven by the render-smoke — a
hollow profile is worse than authoring on demand.

The legacy request raises a real toolchain-maturity question: COBOL and Pascal have usable,
CI-able toolchains (GnuCOBOL `cobc` + cobol-check; Free Pascal `fpc` + FPCUnit), but with no
standard formatter / doc / package manager in COBOL's case. **QBasic/QuickBASIC has
essentially no enterprise toolchain** — no standard test framework, formatter, linter,
coverage, package manager, or CI runner — so a QBasic profile would be hollow and would
generate degraded "enterprise" output, contradicting EADOS's value.

## Decision

Ship seven new seeds, each schema-complete and render-smoke-verified:

- **Modern:** `scala`, `kotlin`, `swift`, `dart`, `ruby` — full enterprise toolchains.
- **Legacy:** `cobol` (GnuCOBOL) and `pascal` (Free Pascal) — build/test/CI are real; roles
  with no standard tool (notably COBOL's formatter/doc/package-manager) are filled honestly as
  `none (...)` and flagged in the profile `notes`. The enterprise bar is explicitly **degraded**
  for these, not pretended.

**Do not** ship a QBasic profile: it cannot meet the bar. It remains available on demand if a
maintainer accepts the limitations. Likewise, unspecified "etc" legacy languages are authored
on demand (or seeded later) once named.

This brings the shipped seeds to **nineteen**; any other language is still authored on demand
from `_template.yaml`.

## Consequences

- Nineteen languages generate with zero friction, including mobile (Kotlin/Swift/Dart) and
  big-data (Scala); the language-fit advisory now reasons over all of them.
- COBOL/Pascal set an honest precedent for "degraded-bar" legacy profiles: real where tooling
  exists, explicit `none` where it does not — never a fake tool name.
- The seven new seeds join the stay-current maintenance surface.
- Authoring the legacy COBOL profile surfaced and fixed a real bug in `eados_lint`'s schema
  parser (it had treated block-scalar example content as required keys).
