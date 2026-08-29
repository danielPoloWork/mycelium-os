#!/usr/bin/env python3
"""Negative-path tests for the renderer's guards — they must FAIL on bad input.

The render-smoke proves the *happy path* (the reference manifest renders cleanly). This proves
the inverse, which is where the security/correctness value lives: a path-unsafe identifier, a
missing required field, an unknown section, or a bad version must each be a hard failure, and a
write can never escape --out. Dependency-free (no PyYAML): runnable in the self-lint job.

    python .eados-core/tools/tests/test_render_guards.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import render  # noqa: E402  (the module under test)
import sandbox  # noqa: E402  (write_file now delegates here — one containment/clobber path)

RENDER_PY = os.path.join(TOOLS, "render.py")

# A minimal manifest with every required field present and valid — the positive control.
# The spec block is the minimum the #170 substance floor accepts: an objective, one
# functional requirement, a verification strategy, and one forward milestone.
VALID = """
identity: { project_name: Acme, project_slug: acme, project_kind: library }
ownership: { owner: o, license_id: MIT, default_branch: main }
language: { lang: go, group_path: it/d4np }
governance: { start_version: "0.0.0" }
spec:
  objective: A demo library.
  functional_reqs: [do one thing]
  verification: unit tests
  milestones:
    - { number: 2, title: Harden, goal: Stable API, items: ["2.1 freeze the API"] }
"""


def _problems(yaml_text):
    m = render.load_yaml(yaml_text)
    scalars, _flags, _sections = render.build_context(m)
    return render.validate_manifest(m, scalars)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- validate_manifest: the positive control passes clean ---
    check("valid manifest yields no problems", _problems(VALID) == [], failures)

    # --- M1-B: the persistent delivery-state layer is accepted (schema_version scalar + the
    #     delivery_state section); a legacy manifest without it still passes (backward-compat,
    #     proven by the control above) ---
    WITH_STATE = VALID + (
        "\nschema_version: 1"
        "\ndelivery_state: { phase: init, checkpoints: [], "
        "refs: { rfcs: [], milestones: [], prs: [], releases: [] } }\n"
    )
    check("manifest with schema_version + delivery_state passes clean",
          _problems(WITH_STATE) == [], failures)

    # --- validate_manifest: each guard fires on the matching defect ---
    def has(yaml_text, needle):
        return any(needle in p for p in _problems(yaml_text))

    check("path-unsafe slug rejected",
          has(VALID.replace("project_slug: acme", 'project_slug: "../../evil"'),
              "not a safe path segment"), failures)
    check("path-unsafe lang rejected",
          has(VALID.replace("lang: go", 'lang: "../x"'), "not a safe path segment"), failures)
    check("missing required field rejected",
          has(VALID.replace("owner: o, ", ""), "required field"), failures)
    # #163: no silent it/d4np fallback — a manifest without language.group_path must trip the
    # GROUP_PATH required-field guard (the old build_context default made this guard dead code).
    check("missing group_path rejected (no it/d4np fallback)",
          has(VALID.replace(", group_path: it/d4np", ""),
              "required field for {{GROUP_PATH}}"), failures)

    # --- #170: the spec-substance floor — a hollow spec must FAIL with actionable messages
    #     (the deterministic path used to render "OK" on an empty spec); the positive control
    #     at the top proves the minimal honest spec passes ---
    check("empty spec.objective rejected",
          has(VALID.replace("objective: A demo library.", 'objective: ""'),
              "stated objective"), failures)
    check("empty spec.functional_reqs rejected",
          has(VALID.replace("functional_reqs: [do one thing]", "functional_reqs: []"),
              "at least one functional requirement"), failures)
    check("empty spec.verification rejected",
          has(VALID.replace("verification: unit tests", 'verification: ""'),
              "verification strategy"), failures)
    check("empty spec.milestones rejected",
          has(VALID.replace('milestones:\n    - { number: 2, title: Harden, goal: Stable API, '
                            'items: ["2.1 freeze the API"] }', "milestones: []"),
              "forward milestone"), failures)
    check("a manifest without a spec section trips the whole floor",
          sum(p.startswith("spec.") for p in _problems(VALID.split("spec:")[0])) == 4, failures)

    # --- #169: the interview provenance block — honest state passes; a wrong value, a
    #     dangling key, or a shapeless block is rejected; absence stays legal (the positive
    #     control at the top carries no block) ---
    # A COMPLETE block covers every answer-bearing section VALID carries (identity, ownership,
    # language, governance, spec) — #201 requires coverage, not just correct shape.
    WITH_PROV = VALID + (
        "\ninterview:\n  questionnaire_version: 1\n  provenance:\n"
        "    identity: asked\n    ownership: defaulted\n    language: asked\n"
        "    governance: asked\n    spec: asked\n"
    )
    check("manifest with a complete interview provenance block passes clean",
          _problems(WITH_PROV) == [], failures)
    check("invalid provenance value rejected",
          has(WITH_PROV.replace("ownership: defaulted", "ownership: guessed"),
              "asked|defaulted|imported"), failures)
    check("dangling provenance key rejected",
          has(WITH_PROV.replace("    language: asked\n", "    toolchain: asked\n"),
              "not a top-level key"), failures)
    check("shapeless interview block rejected (no provenance mapping)",
          has(VALID + "\ninterview:\n  questionnaire_version: 1\n",
              "non-empty mapping"), failures)
    # #201: a PARTIAL block (a present section missing from provenance) and a block without a
    # questionnaire_version are both rejected — coverage and version are now enforced, not just shape.
    check("an incomplete provenance block (a present section omitted) is rejected",
          has(WITH_PROV.replace("    governance: asked\n", ""), "no entry for governance"), failures)
    check("a present interview block without questionnaire_version is rejected",
          has(WITH_PROV.replace("  questionnaire_version: 1\n", ""), "questionnaire_version"),
          failures)
    check("unknown top-level section rejected",
          has(VALID + "\nbogus: { x: 1 }\n", "unknown top-level section"), failures)
    check("non-numeric start_version rejected",
          has(VALID.replace('start_version: "0.0.0"', 'start_version: "pre-1.0"'),
              "not a numeric"), failures)
    # #214: the optimistic-concurrency counter is a non-negative integer when present; absence is
    # legal (the VALID control carries none) — a legacy manifest stays unlocked.
    check("a valid manifest_rev passes", _problems(VALID + "\nmanifest_rev: 4\n") == [], failures)
    check("a negative manifest_rev is rejected",
          has(VALID + "\nmanifest_rev: -1\n", "non-negative integer"), failures)
    check("a non-integer manifest_rev is rejected",
          has(VALID + '\nmanifest_rev: "x"\n', "non-negative integer"), failures)
    # A known section given as a scalar must be reported, not crash build_context.
    check("section of wrong type rejected (no crash)",
          has(VALID.replace("language: { lang: go, group_path: it/d4np }", "language: nope"),
              "must be a mapping"), failures)

    # --- #199: delivery-state consistency reaches validate_manifest — a phase-skip and a
    #     human-gated move without confirmed_by are rejected; a legal chain passes; no
    #     delivery_state stays exempt (the VALID control above carries none) ---
    check("a phase-skip (scaffold, no checkpoints) is rejected",
          has(VALID + "\ndelivery_state: { phase: scaffold, checkpoints: [] }\n",
              "no checkpoints"), failures)
    check("a legal checkpoint chain ending at the current phase passes",
          _problems(VALID + "\ndelivery_state:\n  phase: plan\n  checkpoints:\n"
                    "    - from: init\n      to: design\n      confirmed_by: owner\n"
                    "      gate_results: { manifest-valid: OK }\n"
                    "    - from: design\n      to: plan\n      confirmed_by: owner\n"
                    "      gate_results: { rfc-approved: OK }\n") == [], failures)
    # #250: the honor-system closure — a human-gated move recorded WITHOUT its gate marks fails
    check("a human-gated move recorded without gate_results is rejected (#250)",
          has(VALID + "\ndelivery_state:\n  phase: design\n  checkpoints:\n"
              "    - { from: init, to: design, confirmed_by: owner }\n",
              "must record gate_results"), failures)
    check("a human-gated move recorded without confirmed_by is rejected",
          has(VALID + "\ndelivery_state:\n  phase: design\n  checkpoints:\n"
              "    - { from: init, to: design }\n", "confirmed_by"), failures)

    # --- _unsafe_path_value unit cases ---
    #     #196: `.git` is refused by EXACT segment at any depth (VCS-metadata write vector), while
    #     `.gitignore` and `foo.git` — which merely contain the substring — stay legal.
    for safe in ("acme", "memorypool", "it/d4np", "a.b-c_d", ".gitignore", "foo.git", "git"):
        check(f"_unsafe_path_value safe: {safe}", not render._unsafe_path_value(safe), failures)
    for bad in ("..", "a/../b", "", "/etc", "C:\\x", "a/..", "foo/./bar",
                ".git", ".git/hooks", "a/.git/b", "src/.git"):
        check(f"_unsafe_path_value unsafe: {bad!r}", render._unsafe_path_value(bad), failures)

    # --- _duplicate_top_level_keys: repeated section detected; nested dup not a false positive ---
    check("duplicate top-level key detected",
          render._duplicate_top_level_keys("identity:\n  a: 1\nidentity:\n  b: 2\n") == ["identity"],
          failures)
    check("nested duplicate is not a top-level duplicate",
          render._duplicate_top_level_keys("a:\n  x: 1\n  x: 2\nb: 3\n") == [], failures)

    # --- write_file containment + no-clobber: a normal rel writes, an escaping rel raises, and a
    #     second write over an existing file is refused unless overwrite=True (#195: write_file now
    #     delegates to sandbox.safe_write, so render and migrate share ONE containment/clobber path)
    with tempfile.TemporaryDirectory() as out:
        render.write_file(out, "docs/ok.md", "hi")
        check("normal write lands inside out_dir",
              os.path.exists(os.path.join(out, "docs", "ok.md")), failures)
        try:
            render.write_file(out, os.path.join("..", "..", "escape.md"), "x")
            check("escaping write must raise", False, failures)
        except sandbox.SandboxError:
            pass
        # additive by default: clobbering docs/ok.md without opt-in is refused, and the original
        # content survives; --force-equivalent overwrite=True is the only way through
        try:
            render.write_file(out, "docs/ok.md", "CLOBBERED")
            check("clobber without overwrite must raise", False, failures)
        except sandbox.SandboxError:
            pass
        with open(os.path.join(out, "docs", "ok.md"), encoding="utf-8") as fh:
            check("refused clobber left the original file intact", fh.read() == "hi", failures)
        render.write_file(out, "docs/ok.md", "CLOBBERED", overwrite=True)
        with open(os.path.join(out, "docs", "ok.md"), encoding="utf-8") as fh:
            check("overwrite=True regenerates over the existing file", fh.read() == "CLOBBERED",
                  failures)

    # --- end-to-end: render.py on a traversal manifest exits 1 and writes nothing outside ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "bad.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID.replace("project_slug: acme",
                                   'project_slug: "../../../../pwned"'))
        out = os.path.join(work, "out")
        proc = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", out],
                              capture_output=True, text=True)
        check("traversal manifest -> non-zero exit", proc.returncode == 1, failures)
        check("traversal manifest -> actionable message",
              "not a safe path segment" in (proc.stdout + proc.stderr), failures)
        check("traversal manifest wrote nothing outside out_dir",
              not os.path.exists(os.path.join(work, "pwned")) and
              not os.path.exists(os.path.join(os.path.dirname(work), "pwned")), failures)

    # --- end-to-end (#163): a manifest missing group_path fails naming GROUP_PATH — it must not
    #     render "OK" with the reference project's it/d4np namespace stamped in ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "nogroup.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID.replace(", group_path: it/d4np", ""))
        out = os.path.join(work, "out")
        proc = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", out],
                              capture_output=True, text=True)
        check("missing group_path -> non-zero exit", proc.returncode == 1, failures)
        check("missing group_path -> message names GROUP_PATH",
              "{{GROUP_PATH}}" in (proc.stdout + proc.stderr), failures)

    # --- #196: a `.git` segment in a path field is refused at VALIDATION time (--check), before
    #     write_file's sandbox backstop — so a manifest can never steer a .gitkeep into VCS
    #     metadata (`.git/hooks/` being the sharp case). Fails on --check and --out; writes nothing
    #     under a .git/ directory ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "dotgit.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID.replace("group_path: it/d4np", "group_path: .git/hooks"))
        chk = subprocess.run([sys.executable, RENDER_PY, manifest, "--check"],
                             capture_output=True, text=True)
        check("group_path .git/hooks -> --check exits non-zero", chk.returncode == 1, failures)
        check("group_path .git/hooks -> actionable 'not a safe path segment' message",
              "not a safe path segment" in (chk.stdout + chk.stderr), failures)
        out = os.path.join(work, "out")
        rnd = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", out],
                             capture_output=True, text=True)
        check("group_path .git/hooks -> --out exits non-zero", rnd.returncode == 1, failures)
        check("group_path .git/hooks -> nothing written under a .git/ directory",
              not os.path.exists(os.path.join(out, "src", "main", "go", ".git")), failures)

    # --- end-to-end: render.py refuses an --out inside the EADOS repo (self-overwrite guard) ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "ok.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID)
        inside = os.path.join(TOOLS, "__render_should_refuse__")
        proc = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", inside],
                              capture_output=True, text=True)
        check("render into EADOS repo -> non-zero exit", proc.returncode == 1, failures)
        check("render into EADOS repo -> actionable message",
              "OUTSIDE the EADOS repository" in (proc.stdout + proc.stderr), failures)
        check("render into EADOS repo wrote nothing", not os.path.exists(inside), failures)

    # --- --in-place refuses inside the EADOS development repo (the .eados-dev sentinel) ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "ok.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID)
        proc = subprocess.run([sys.executable, RENDER_PY, manifest, "--in-place"],
                              capture_output=True, text=True)
        check("--in-place in the EADOS dev repo -> non-zero exit", proc.returncode == 1, failures)
        check("--in-place in the EADOS dev repo -> .eados-dev message",
              ".eados-dev" in (proc.stdout + proc.stderr), failures)

    # --- the CLI requires exactly one of --out / --in-place / --check ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "ok.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID)
        neither = subprocess.run([sys.executable, RENDER_PY, manifest],
                                 capture_output=True, text=True)
        check("neither --out nor --in-place -> error exit", neither.returncode != 0, failures)
        both = subprocess.run([sys.executable, RENDER_PY, manifest,
                               "--out", os.path.join(work, "o"), "--in-place"],
                              capture_output=True, text=True)
        check("both --out and --in-place -> error exit", both.returncode != 0, failures)
        mixed = subprocess.run([sys.executable, RENDER_PY, manifest,
                                "--out", os.path.join(work, "o"), "--check"],
                               capture_output=True, text=True)
        check("--check with --out -> error exit", mixed.returncode != 0, failures)

    # --- #164: --check validates without writing — OK on a valid manifest, FAIL on a broken
    #     one, and the working tree stays untouched either way ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "ok.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID)
        ok = subprocess.run([sys.executable, RENDER_PY, manifest, "--check"],
                            capture_output=True, text=True, cwd=work)
        check("--check on a valid manifest -> exit 0", ok.returncode == 0, failures)
        check("--check reports Check: OK", "Check: OK" in ok.stdout, failures)
        bad = os.path.join(work, "bad.yaml")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write(VALID.replace("owner: o, ", ""))
        broken = subprocess.run([sys.executable, RENDER_PY, bad, "--check"],
                                capture_output=True, text=True, cwd=work)
        check("--check on a broken manifest -> exit 1", broken.returncode == 1, failures)
        check("--check failure labelled Check:", "Check: FAIL" in broken.stdout, failures)
        check("--check wrote nothing",
              sorted(os.listdir(work)) == ["bad.yaml", "ok.yaml"], failures)

    # --- #195: an --out render into a directory that already holds a file fails ALL-OR-NOTHING,
    #     names the collision, leaves the pre-existing file byte-for-byte intact, and writes nothing
    #     else; --force is the sole opt-in to regenerate over existing files ---
    with tempfile.TemporaryDirectory() as work:
        manifest = os.path.join(work, "ok.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write(VALID)
        out = os.path.join(work, "out")
        os.makedirs(out)
        sentinel = "PRE-EXISTING README — must not be clobbered\n"
        with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(sentinel)
        clobber = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", out],
                                 capture_output=True, text=True)
        check("clobbering render -> non-zero exit", clobber.returncode == 1, failures)
        check("clobbering render -> refuses and names the collision",
              "refusing to overwrite" in clobber.stdout and "README.md" in clobber.stdout, failures)
        with open(os.path.join(out, "README.md"), encoding="utf-8") as fh:
            check("pre-existing README.md is byte-for-byte unchanged after the refused render",
                  fh.read() == sentinel, failures)
        check("refused render wrote nothing else (only the pre-existing file remains)",
              os.listdir(out) == ["README.md"], failures)
        forced = subprocess.run([sys.executable, RENDER_PY, manifest, "--out", out, "--force"],
                                capture_output=True, text=True)
        check("--force render -> exit 0", forced.returncode == 0, failures)
        with open(os.path.join(out, "README.md"), encoding="utf-8") as fh:
            check("--force overwrote the pre-existing README.md", fh.read() != sentinel, failures)
        check("--force render produced the rest of the repo (LICENSE)",
              os.path.isfile(os.path.join(out, "LICENSE")), failures)

    if failures:
        print("test-render-guards: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} guard(s) did not fire as expected.")
        return 1
    print("test-render-guards: OK — validation, containment, and the CLI all reject bad input.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
