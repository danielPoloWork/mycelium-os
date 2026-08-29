# ADR-0006: Spec-correct manifest loader and a real-parser gate for emitted YAML

## Status

Accepted

## Context

The renderer's bundled, dependency-free YAML loader (`tools/render.py:load_yaml`) reads every
`project.yaml` — the single source of truth for a generation run. An audit found it diverged
from standard YAML on the two most common block styles, and one failure mode was **silent**:

- A block sequence whose `-` items sit at the **same** indentation as the parent key (idiomatic
  YAML, and what most formatters emit) parsed to `null`. The affected section rendered empty and
  the tool still printed `Render: OK` — a generated repo could silently lose its functional
  requirements, public API, or milestone items with no error.
- A **block-style list of maps** (a CI `matrix:` written as `- os: x` / `  toolchain: y`) kept
  only the first line of the first item as a string and dropped the rest.

The reference manifest only worked because it happened to use deeper-indent block lists and
flow-style maps. Worse, the render-smoke gate only renders that one hand-tuned reference, so
the 19 shipped profiles were never rendered in CI; a malformed CI fragment in a profile (the
audit found `run: { CC: clang, ... } && cmake` in `cpp.yaml`, which emits invalid GitHub
Actions YAML) passed every existing check.

This contradicts EADOS's core promise: *measurable correctness over assertion*, and "unresolved
placeholder = hard error". An empty section is not an unresolved placeholder, so nothing caught it.

## Decision

1. **Make the loader spec-correct for block sequences**, staying dependency-free: accept a
   block sequence at the same indent as its key, and parse block-style mapping items
   (`- key: value` plus aligned continuation lines) into real maps. Flow style still works, so
   the reference render is byte-for-byte unchanged.
2. **Validate the manifest before rendering**: reject an unknown/misspelled top-level section
   (which would otherwise blank every field under it) and a non-numeric `start_version` (the
   classic `start_version` ↔ `version_start` swap). These are hard render failures.
3. **Add an emitted-YAML gate** (`tools/profile_ci_lint.py`): a real-parser (PyYAML) check that
   every profile's `setup_steps`/`extra_jobs`/`race_job` fragment and every `*.yml` in a
   rendered repo actually parses. To keep the tools dependency-free for everyday use it degrades
   to a no-op skip when PyYAML is absent; CI installs PyYAML so the gate is enforced there.
4. Fix `cpp.yaml`'s malformed `tidy` step (`env:` at step level, `run:` the command).

## Consequences

- The most-used component no longer loses data silently; correctness is enforced where it was
  only asserted. The render-smoke now also renders/validates from the raw profiles, not just the
  reference.
- A new, optional dependency (PyYAML) exists **only** in CI and only for the validation gate;
  the rendering path and all other tools remain standard-library-only. We deliberately keep the
  hand-rolled loader (no third-party dep on the hot path) rather than vendoring a full parser —
  re-evaluate if its surface grows.
- New profiles are now CI-proven to emit parseable YAML, not just schema-complete.
