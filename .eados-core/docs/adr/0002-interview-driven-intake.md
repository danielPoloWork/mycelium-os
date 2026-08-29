# ADR-0002: Interview-driven intake before generation

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Maintainer, Enterprise Project Architect
- **Related:** ADR-0001, `orchestrator/interview.md`, `orchestrator/questionnaire.yaml`

## Context

To generate a correct repository, EADOS needs facts it cannot infer: the language and
standard, frameworks, toolchain overrides, governance choices, and — most importantly — the
functional specification. The maintainer explicitly wants to be **asked** for these
("dovrò chiedere linguaggi, framework, tool, e le specifiche di progetto"). At the same
time, an interrogation that asks everything would be slow and annoying, and most toolchain
facts have a sensible default in the language profile.

## Decision

Generation is preceded by a **structured intake interview**
([`orchestrator/interview.md`](../../orchestrator/interview.md), backed by
[`questionnaire.yaml`](../../orchestrator/questionnaire.yaml)) organised in six phases:
Frame, Languages, Frameworks, Tools, Governance, Specification. The architect:

- conducts it in the maintainer's language (answers transcribed to English);
- **asks only what it cannot safely default**, stating each assumed default for confirmation;
- treats Phase 5 (the spec) as the substantive conversation, pushing every requirement to a
  testable, CI-checkable form;
- opens Phase 5 with a **provenance branch** (`Q5.0`): a maintainer who already has a technical
  spec / PRD / SRS takes an **import-and-validate** path — the document is mapped onto the six-section
  shape and run through a **gap audit** (each section/requirement gets the testability follow-up),
  and only the gaps are asked — instead of re-narrating a finished spec through Q5.1–Q5.7; both paths
  converge on the same frozen `docs/specs/01_spec_<slug>.md` (`spec.provenance` records which);
- ends by writing `project.yaml` and **getting explicit confirmation before rendering**.

## Alternatives Considered

- **A single up-front form.** Rejected — forces the maintainer to answer toolchain
  questions the profile already knows, and front-loads the spec before context exists.
- **Infer everything from a one-line brief.** Rejected — the spec and governance choices are
  not inferable; guessing them produces a confidently-wrong repository.
- **Generate first, fix later.** Rejected — rendering from an unconfirmed manifest wastes
  effort and erodes trust; the manifest is the cheap checkpoint.

## Consequences

- The interview is the single intake path; `generate.md` refuses to run without a confirmed
  manifest.
- Defaults live in the profiles, so the interview shrinks as profiles improve.
- The "every requirement maps to a mechanical check" discipline (Phase 5 follow-ups) is what
  keeps the generated quality bar real rather than aspirational.

## References

- `orchestrator/interview.md`; `orchestrator/questionnaire.yaml`; `orchestrator/generate.md`.
