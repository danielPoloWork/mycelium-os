# Language Profile Schema

A language profile (`profiles/<lang>.yaml`) is the toolchain knowledge for one language,
expressed as data. The templates never name a specific tool — they reference *roles*
(build tool, test runner, formatter). The profile binds those roles to concrete tools and
commands. This is what lets EADOS generate the same enterprise structure in any language.

Every profile **must** define every key below. A profile missing a key is incomplete and
the generator must refuse it (quality bar, `AGENTS.md` §8).

```yaml
lang:            <source-tree segment, e.g. cpp | python | typescript | java | go | rust>
display_name:    <human name, e.g. "C++">
default_standard: <default standard/edition string, e.g. "C++17">
src_ext:         <primary source file extension without the dot, e.g. cpp>

# How the native namespace/package is formed from group_dotted + project_slug.
# Use the tokens {group_dotted} and {project_slug}; describe the idiom precisely.
namespace_pattern: "{group_dotted}::{project_slug}"        # e.g. it::d4np::memorypool
import_idiom:      "#include <{group_path}/{project_slug}/<header>.h>"

toolchain:
  build_tool:      <e.g. "CMake + Ninja">
  pkg_manager:     <e.g. "vcpkg / Conan">
  test_framework:  <e.g. "doctest">
  formatter:       <e.g. "clang-format">
  linter:          <e.g. "clang-tidy">
  sanitizers:      <comma list, e.g. "ASan, UBSan, TSan, Valgrind">
  coverage_tool:   <e.g. "llvm-cov / gcovr">
  doc_tool:        <e.g. "Doxygen">
  version_file:    <relative path under src_main holding the version constant>
  version_const_hint: <how the version constant is named/expressed>
  package_ecosystem: <Dependabot ecosystem id, e.g. cargo|pip|npm|gomod|gradle|maven; "" if the language has none>

# Canonical commands. Keep them copy-pasteable; CI and the local-build doc reuse them.
commands:
  build:        <e.g. "cmake --build --preset debug">
  test:         <e.g. "ctest --preset debug --output-on-failure">
  format_check: <e.g. "clang-format --dry-run --Werror <files>">
  lint:         <e.g. "clang-tidy --warnings-as-errors='*' <files>">
  bench:        <e.g. "cmake --build --preset bench"  | "" if N/A>

# The ONE config file whose presence proves the build system exists (#313). Roadmap item 1.1 is
# what creates it, so on a freshly rendered repo it is absent by design — and the rendered CI uses
# this name to SKIP the toolchain jobs until then, instead of failing them. Normally one of the
# `config_files` below. A glob is legal (the probe uses `compgen -G`).
build_manifest: <e.g. CMakeLists.txt | package.json | pyproject.toml | "*.rockspec">

# Repo-root config files this language expects (formatter/linter configs, build manifests).
# The generator creates stubs for these so day-one tooling is wired.
config_files:
  - <e.g. .clang-format>
  - <e.g. .clang-tidy>
  - <e.g. CMakeLists.txt>

ci:
  tier1_platforms: <human description, e.g. "Linux x86_64, Windows x86_64, macOS arm64">
  # The build matrix cells rendered into ci.yml.
  matrix:
    - { os: <runner>, toolchain: <name>, preset: <name> }
  # A YAML snippet (as a literal block) that sets up the language toolchain in a job.
  setup_steps: |
    - name: ...
      uses: ...
  # A YAML snippet (literal block) of extra jobs unique to this language's quality bar
  # (sanitizers, leak check, ABI compat, etc.). May reference {{PROJECT_SLUG}} etc.
  extra_jobs: |
    <job-yaml or "">
  # A YAML snippet (literal block) for the data-race / concurrency-verification job. Rendered
  # ONLY when the project sets capabilities.threading. "" if the language has no race tooling.
  race_job: |
    <race-job-yaml or "">

# Which capability flags this language can satisfy out of the box (informational; the
# project's own answers in project.yaml still decide what is enabled).
supports:
  threading_sanitizer: <true|false>
  bench: <true|false>
  abi_stability: <true|false>
notes: <free text — gotchas, idioms, why a tool was chosen>
```

## Authoring guidance

- **Mirror the reference.** `cpp.yaml` is the ground truth, reverse-engineered from
  `pbr-cpp-memory-pool`. New profiles should match its *shape* and *rigor*, not copy its
  tools.
- **Commands must be real.** Every command must run unmodified on a freshly generated repo
  (after Milestone 1). If a command needs a preset/config file, list that file in
  `config_files`.
- **Prefer the ecosystem's standard.** Choose the de-facto enterprise tool for each role
  (e.g. `ruff` + `mypy` for Python lint/type, `pytest` for tests) rather than a niche pick.
- **Sanitizers map to the language's equivalent.** Where ASan/UBSan/Valgrind do not apply
  (managed languages), substitute the moral equivalent (race detector, leak detector, type
  checker) and say so in `notes`.
