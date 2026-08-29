# Placeholder Dictionary

The authoritative list of every `{{PLACEHOLDER}}` that may appear in `templates/**`. A
template may only use placeholders defined here; a placeholder defined here should be
resolvable from `orchestrator/project.yaml` (which merges the interview answers with the
chosen language profile).

**Conventions.** Placeholders are `{{UPPER_SNAKE}}` wrapped in double braces. Optional
blocks use `{{#IF_KEY}} ... {{/IF_KEY}}` (render only when the key is truthy); the
**inverted** form `{{^IF_KEY}} ... {{/IF_KEY}}` renders only when the key is falsy.
List expansion uses `{{#EACH_KEY}} ... {{/EACH_KEY}}`, with `{{.}}` for the current scalar
item or `{{field}}` for a field of the current object. Keep substitution literal and dumb —
all intelligence lives in the manifest, not the renderer. This is the Mustache subset; any
Mustache-compatible renderer (or a careful manual pass) works.

---

## 1. Identity

| Placeholder | Meaning | Example |
|---|---|---|
| `{{PROJECT_NAME}}` | Repository / package name (kebab) | `pbr-cpp-memory-pool` |
| `{{PROJECT_SLUG}}` | Short single-word slug used in the source path & namespace leaf | `memorypool` |
| `{{PROJECT_TITLE}}` | Human-facing title | `High-Performance Memory Pool` |
| `{{PROJECT_TAGLINE}}` | One-sentence description | `Fixed-block O(1) memory pool` |
| `{{PROJECT_SERIES}}` | Optional umbrella/series name, blank if none | `Purpose-Built References (PBR)` |

## 2. Ownership & governance

| Placeholder | Meaning | Example |
|---|---|---|
| `{{OWNER}}` | GitHub owner/org login | `danielPoloWork` |
| `{{MAINTAINER}}` | Maintainer display name | `Daniel Polo` |
| `{{AUTHOR}}` | Copyright holder | `Daniel Polo` |
| `{{YEAR}}` | Copyright year | `2026` |
| `{{LICENSE_ID}}` | SPDX license id | `MIT` |
| `{{DEFAULT_BRANCH}}` | Mainline branch | `main` |
| `{{ASSIGNEE}}` | PR assignee handle — the repository **owner** by default (a blank manifest `assignee` resolves to `{{OWNER}}`); never `@me`, which would resolve to whichever actor drafts the PR | `danielPoloWork` |
| `{{PROJECT_KIND}}` | `library` \| `service` \| `cli` \| `app` | `library` |
| `{{POSTURE}}` | Governance/compliance posture (Q0.5, ADR-0015): `standard` (default) or `enterprise` — a raised bar orthogonal to the domain | `standard` |
| `{{START_VERSION}}` | Numeric start version (drives the README badge + day-zero version constant) | `0.0.0` |
| `{{VERSION_START}}` | Versioning-start descriptor (prose) | `pre-1.0 milestone-driven` |

## 3. Source tree & language

| Placeholder | Meaning | Example |
|---|---|---|
| `{{LANG}}` | Source-tree language segment | `cpp` |
| `{{LANG_NAME}}` | Display language + standard | `C++17` |
| `{{LANG_STANDARD}}` | Standard/edition string | `C++17 (ISO/IEC 14882:2017)` |
| `{{GROUP_PATH}}` | Reverse-domain path segment | `it/d4np` |
| `{{GROUP_DOTTED}}` | Same, dotted | `it.d4np` |
| `{{NAMESPACE}}` | Language-native namespace/package for the project | `it::d4np::memorypool` |
| `{{SRC_MAIN}}` | Production source root | `src/main/cpp/it/d4np/memorypool` |
| `{{SRC_TEST}}` | Test source root | `src/test/cpp/it/d4np/memorypool` |
| `{{SRC_BENCH}}` | Benchmark source root (blank if N/A) | `src/bench/cpp/it/d4np/memorypool` |
| `{{SRC_EXT}}` | Primary source file extension | `cpp` |
| `{{PUBLIC_INCLUDE_HINT}}` | How a consumer imports the public surface | `#include <it/d4np/memorypool/memory_pool.h>` |

## 4. Toolchain (from the language profile)

| Placeholder | Meaning | Example |
|---|---|---|
| `{{BUILD_TOOL}}` | Build system | `CMake + Ninja` |
| `{{PKG_MANAGER}}` | Dependency/package manager | `vcpkg / Conan` |
| `{{TEST_FRAMEWORK}}` | Test framework | `doctest` |
| `{{FORMATTER}}` | Code formatter | `clang-format` |
| `{{LINTER}}` | Static analyzer / linter | `clang-tidy` |
| `{{SANITIZERS}}` | Runtime checkers, comma list | `ASan, UBSan, TSan, Valgrind` |
| `{{COVERAGE_TOOL}}` | Coverage tool | `llvm-cov / gcovr` |
| `{{COVERAGE_TARGET}}` | Minimum line-coverage percentage gate | `80` |
| `{{DOC_TOOL}}` | API docs generator | `Doxygen` |
| `{{CMD_BUILD}}` | Canonical build command | `cmake --build --preset debug` |
| `{{CMD_TEST}}` | Canonical test command | `ctest --preset debug` |
| `{{CMD_FORMAT_CHECK}}` | Format-check command | `clang-format --dry-run --Werror` |
| `{{CMD_LINT}}` | Lint command | `clang-tidy --warnings-as-errors='*'` |
| `{{CMD_BENCH}}` | Benchmark command (blank if N/A) | `cmake --build --preset bench` |
| `{{VERSION_FILE}}` | File holding the version constant | `src/main/cpp/it/d4np/memorypool/version.hpp` |
| `{{VERSION_CONST_HINT}}` | How the version constant is named | `PBR_MEMORY_POOL_VERSION_*` |
| `{{PKG_ECOSYSTEM}}` | Dependabot package ecosystem id (blank if none) | `cargo` |

## 5. CI matrix (from the language profile)

| Placeholder | Meaning | Example |
|---|---|---|
| `{{TIER1_PLATFORMS}}` | Human description of CI-gated platforms | `Linux x86_64, Windows x86_64, macOS arm64` |
| `{{#EACH_CI_CELL}}` | Loop over CI matrix cells (`os`, `toolchain`, `preset`) | — |
| `{{CI_SETUP_STEPS}}` | Profile-provided "set up the toolchain" YAML steps | — |
| `{{EADOS_PROVENANCE}}` | Which factory produced this repo — version + commit + date, from the manifest's `generated_by:` when recorded, else derived from the CHANGELOG and git (#319) | `EADOS v2.12.0 (commit f6d487c) on 2026-07-27` |
| `{{CI_BUILD_MANIFEST}}` | The file whose presence proves the build system exists (`ci.build_manifest`); a glob is legal (#313) | `CMakeLists.txt`, `package.json`, `*.rockspec` |
| `{{CI_EXTRA_JOBS}}` | Profile-provided extra jobs (sanitizers, valgrind, …) | — |
| `{{CI_RACE_JOB}}` | Profile-provided data-race/concurrency job (rendered only under `IF_THREADING`; blank if N/A) | — |

## 6. Conventional-commit scopes

| Placeholder | Meaning | Example |
|---|---|---|
| `{{#EACH_SCOPE}}` | Loop over the project's commit scopes | `api`, `build`, `tests`, `docs`, `ci` |
| `{{EADOS_COMMANDS}}` | The `/eados` command table rendered into the generated `AGENTS.md` §13 — name, class and one-line description, from the canonical registry `orchestrator/commands/README.md` (#374). Never retyped: a stale command table sends an agent at a command that no longer exists | `\| `/eados init` \| phase \| Frame a new project… \|` |
| `{{GIT_COMMIT_SCOPES}}` | The same scopes as a single-line YAML flow body, for the rendered `docs/workflow/git-policy.yaml` the checks read (#358) | `api, build, tests, docs, ci` |
| `{{GIT_SUBJECT_MAX}}` | Max length of the commit subject the author writes — from the factory's `os/git/git.yaml` `commit.subject_max`; the squash-merge's trailing ` (#PR)` is excluded before measuring (#363) | `80` |
| `{{GIT_BRANCH_TYPES}}` | The Conventional Commit branch/commit types as a single-line YAML flow body — derived from the factory's `os/git/git.yaml`, **not** the manifest: the vocabulary is identical in every contract, so deriving it keeps the rendered policy in lockstep by construction | `feat, fix, refactor, perf, docs, test, build, chore, ci` |

## 7. Spec (from the interview)

| Placeholder | Meaning | Example |
|---|---|---|
| `{{SPEC_OBJECTIVE}}` | Objective & business context paragraph | — |
| `{{#EACH_FUNCTIONAL_REQ}}` | Functional requirements list | — |
| `{{#EACH_NONFUNCTIONAL_REQ}}` | Non-functional requirements list | — |
| `{{SPEC_ARCHITECTURE}}` | Logical architecture prose + diagram block | — |
| `{{ARCHITECTURE_STYLE}}` | Structured architecture style from `design-patterns.md` §5 (blank if none, e.g. a library) | `Hexagonal (Ports & Adapters)` |
| `{{PATTERN_DISCIPLINE}}` | Pattern-discipline posture: `advisory` (default) or `enforced` | `advisory` |
| `{{#EACH_PATTERN}}` | Expected first-class patterns named at intake; per-item fields: `name`, `why` | `Repository`/`decouple domain from persistence` |
| `{{#EACH_LAYER}}` | Layered package skeleton (when `capabilities.layered`); each item is a package-name string, referenced with `{{.}}` | `controller`, `service`, `repository`, `dto`, `mapper` |
| `{{#EACH_PUBLIC_API}}` | Public surface entries | — |
| `{{SPEC_VERIFICATION}}` | Verification & test strategy paragraph | — |
| `{{#EACH_MILESTONE1_ITEM}}` | Extra Milestone-1 roadmap items (beyond the universal bootstrap 1.1–1.5); each entry is a plain string or a `{text, signals[]}` object (#306 — an object renders with its derived advisory route) | — |
| `{{#EACH_MILESTONE}}` | The project's milestones beyond bootstrap, defined up front; per-item fields: `number`, `title`, `goal`, `items` | — |
| `{{#ITEMS}}` | A milestone's checklist items — nested loop **inside** `{{#EACH_MILESTONE}}`; `{{.}}` is one pre-numbered item string. A manifest item in the `{text, signals[]}` object form arrives here already route-suffixed (`<text> — route: <tier> / <effort> (<signals>)`, ADR-0023) | — |
| `{{ROUTE_TIERS}}` | The `os/routing` capability-tier ladder, cheapest → most capable (derived from `os/routing/routing.yaml`, never the manifest) | `fast → standard → frontier-reasoning` |
| `{{ROUTE_EFFORTS}}` | The `os/routing` effort ladder, lowest → highest (derived from `os/routing/routing.yaml`) | `low → medium → high → max` |
| `{{ROUTE_FLOOR}}` | The routing floor — the route an unsignalled/unrouted item takes (derived from `os/routing` `defaults:`) | `fast / low` |
| `{{ROUTE_CATALOG}}` | The dated catalog snapshot, one bullet per host mapping each tier to its current model name (the ONLY place model names surface — ADR-0017) | `- **claude-code**: fast → Sonnet 5 · …` |
| `{{ROUTE_CATALOG_AS_OF}}` | The catalog's `as_of:` date — the staleness/review cue for the rendered snapshot | `2026-07-09` |

## 8. Conditional capability flags

These gate optional sections so a CLI does not ship a library's packaging docs, etc.

| Flag | True when |
|---|---|
| `{{#IF_BOOTSTRAP_GUARD}}` | The manifest declares a `ci.build_manifest`, so the rendered CI skips the toolchain jobs until the build system lands (#313); absent, nothing is rendered and a pre-existing manifest is byte-identical |
| `{{#IF_BENCH}}` | The project has a benchmark suite |
| `{{#IF_THREADING}}` | The project exposes concurrency (renders the profile's race/TSan CI job + the thread-safety convention) |
| `{{#IF_PUBLIC_API}}` | The project publishes a stable API/ABI (enables SemVer-ABR notes) |
| `{{#IF_I18N}}` | Docs are translated (enables the i18n manifest + lint check) |
| `{{#IF_PACKAGING}}` | The project is distributed via a package registry (renders `docs/workflow/packaging.md`) |
| `{{#IF_SERVICE}}` | The project is a long-running service (renders `docs/workflow/operations.md`) |
| `{{#IF_SERIES}}` | The project belongs to an umbrella series (`PROJECT_SERIES` non-empty) |
| `{{#IF_ANNOUNCE}}` | Releases/news are announced on social channels (enables the announcements workflow) |
| `{{#IF_LAYERED}}` | The project opts into a layered package skeleton (`capabilities.layered`; renders the layout ADR note + seeds the layer directories) |
| `{{#IF_API_SPEC}}` | The project opts into an API contract stub (`capabilities.api_spec`; renders `docs/api/` OpenAPI/IDL + the AGENTS §review row — service/web, #240) |
| `{{#IF_COMMENT_LANG_NONEN}}` | A non-English code-comment language was chosen (derived: `CODE_COMMENT_LANG` ≠ `en`; renders the recorded exception in `AGENTS.md` §2) |
| `{{#IF_DOC_LANG_NONEN}}` | A non-English documentation language was chosen (derived: `DOC_DEFAULT_LANG` ≠ `en`; renders the recorded exception in `AGENTS.md` §2) |
| `{{#IF_PKG_ECOSYSTEM}}` | The language has a Dependabot ecosystem (derived: `PKG_ECOSYSTEM` non-empty) |
| `{{#IF_HOUSE_RULES}}` | An organization house-rules overlay is present (derived: `HOUSE_RULES` non-empty) |
| `{{#IF_ARCHITECTURE_STYLE}}` | A structured architecture style was committed (derived: `ARCHITECTURE_STYLE` non-empty) |
| `{{#IF_ENTERPRISE}}` | The enterprise governance posture is set (derived: `POSTURE` == `enterprise`, Q0.5/ADR-0015; renders the raised-bar clauses in `AGENTS.md` §3/§7/§10 + seeds the `docs/compliance/` index) |

## 9. Documentation i18n, announcements & customization

| Placeholder | Meaning | Example |
|---|---|---|
| `{{DOC_DEFAULT_LANG}}` | Canonical on-disk doc language (confirmed at Q4.7, default `en`) | `en` |
| `{{CODE_COMMENT_LANG}}` | Natural language for source comments (confirmed at Q4.7, default `en`; identifiers/API stay English — ADR-0016) | `en` |
| `{{I18N_ENABLED}}` | Python literal for the lint's CONFIG (`True`/`False`, capitalized) | `False` |
| `{{#EACH_DOC_LANG}}` | Loop over translation target languages (`code`, `name`) | `it`/`Italian`, `es`/`Spanish` |
| `{{#EACH_ANNOUNCE_CHANNEL}}` | Loop over announcement channels (`name`, `handle`, `mode`) | `X`/`@d4np`/`draft` |
| `{{HOUSE_RULES}}` | Organization house-rules block injected into the generated `AGENTS.md` §15 | — |

---

## Rendering rules

1. **Unresolved placeholder = hard error.** If a placeholder used in a template has no
   value in `project.yaml`, the render aborts; do not emit `{{...}}` literals to disk.
2. **Blank is intentional.** A key may resolve to empty string (e.g. `{{SRC_BENCH}}` for a
   project with no benchmarks); empty resolution is valid, missing key is not.
3. **`.tmpl` suffix is stripped** on output (`AGENTS.md.tmpl` → `AGENTS.md`). Files without
   `.tmpl` (e.g. `tools/consistency_lint.py`, `docs/adr/template.md`) are copied verbatim
   but still parameterized at their documented `{{...}}` config points.
4. **Path placeholders too.** Directory names in the source tree are produced by expanding
   `{{LANG}}` / `{{GROUP_PATH}}` / `{{PROJECT_SLUG}}`, not copied literally.
