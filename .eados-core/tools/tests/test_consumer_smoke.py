#!/usr/bin/env python3
"""Every shipped tool, run inside a rendered repo, judged by THAT repo's contract (#359).

Seven consecutive issues — #306, #313, #346, #347, #350, #353, #358 — were found by a downstream
consumer, six naming `egl-utils-java`/`egl-utils-js`. **Zero** were found by CI. That is not seven
unrelated misses; it is one structural gap: **no test ran a factory tool inside a rendered
repository**, so a "correct in the factory, wrong in a generated repo" defect could only surface in
the field.

A hand-built fixture is written by whoever wrote the tool and encodes the same assumptions. A
rendered repo is produced by the *renderer*, from a *manifest*, and carries the *project's*
contract — the only artifact that can contradict them. `workflow.yaml` even declares the git gate as
`runs: python .eados-core/tools/git_check.py`, a path that resolves **only inside a consumer repo**.

So this builds a faithful consumer and drives the real CLIs at it:

    render -> git init + a commit using a MANIFEST scope -> the manifest where a consumer keeps it

Four properties, and the third is the one that would have caught #358 no matter which tool carried
the bug:

  1. every tool runs there without crashing (the #347 root-discovery class);
  2. the read-only tools leave the tree byte-identical;
  3. when a tool rejects something, the vocabulary it names is the PROJECT's, not the factory's;
  4. the defect can be resurrected on demand — so property 3 is not passing vacuously.

    python .eados-core/tools/tests/test_consumer_smoke.py
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
HAVE_GIT = shutil.which("git") is not None
sys.path.insert(0, TOOLS)
import git_check   # noqa: E402
import render      # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(args, cwd=None):
    """One shipped CLI, invoked the way a consumer's procedure invokes it."""
    proc = subprocess.run([sys.executable, os.path.join(TOOLS, args[0]), *args[1:]],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def tree_hash(root):
    h = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for fn in sorted(files):
            p = os.path.join(base, fn)
            h.update(os.path.relpath(p, root).replace("\\", "/").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def build_consumer(tmp):
    """A repo as a maintainer actually has it: the rendered project, under git, with the manifest
    where the vendored `.eados-core/` keeps it. Returns (path, manifest_path)."""
    out = os.path.join(tmp, "consumer")
    rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE, "--out", out],
                        capture_output=True, text=True, timeout=240)
    if rc.returncode != 0:
        return None, (rc.stderr or "")[-400:]
    manifest = os.path.join(out, ".eados-core", "orchestrator", "project.yaml")
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    shutil.copyfile(REFERENCE, manifest)
    for cmd in (["init", "-q", "."], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                ["add", "-A"], ["commit", "-qm", "docs(api): first spec pass"],
                ["checkout", "-q", "-b", "docs/first-spec"]):
        subprocess.run(["git", *cmd], cwd=out, capture_output=True, timeout=120)
    return out, manifest


def main():
    failures = []
    if not HAVE_GIT:
        print("test-consumer-smoke: SKIP — git not on PATH")
        return 0

    with open(REFERENCE, encoding="utf-8") as fh:
        manifest_data = render.load_yaml(fh.read())
    project_scopes = [str(s) for s in ((manifest_data.get("governance") or {}).get("scopes") or [])]
    factory_scopes = [str(s) for s in ((git_check.load_policy().get("commit") or {})
                                       .get("scopes") or [])]
    factory_only = [s for s in factory_scopes if s not in project_scopes]
    check(f"the two vocabularies differ, so the assertions below can fail "
          f"({len(project_scopes)} vs {len(factory_scopes)})", factory_only, failures)

    with tempfile.TemporaryDirectory() as tmp:
        consumer, manifest = build_consumer(tmp)
        if consumer is None:
            print(f"test-consumer-smoke: FAIL\n  render failed: {manifest}")
            return 1

        # --- 1. every tool runs there, and 2. the read-only ones write nothing ---------------
        before = tree_hash(consumer)
        invocations = [
            ("git_check", ["git_check.py", "--repo", consumer, "--advisory"], None),
            ("doctor", ["doctor.py", manifest, "--root", consumer], None),
            ("phase_runner", ["phase_runner.py", manifest], None),
            ("eados status", ["eados.py", "status", manifest], None),
            ("traceability", ["traceability.py", os.path.join(consumer, "ROADMAP.md")], None),
            ("risk_score", ["risk_score.py", os.path.join(consumer, "src", "main")], None),
            ("self_check", ["self_check.py"], consumer),
            ("self_review", ["self_review.py", consumer], None),
        ]
        for label, args, cwd in invocations:
            rc, out = run(args, cwd=cwd)
            check(f"{label}: runs inside a rendered repo without crashing\n{out[-400:]}",
                  "Traceback (most recent call last)" not in out, failures)
            for scope in factory_only:
                # A broad net, not the primary assertion: on a clean consumer these tools succeed
                # and print no vocabulary, so it is usually silent. Its job is the tools whose
                # failure modes nobody has enumerated yet — if any of them ever starts echoing the
                # factory's vocabulary at a consumer, that is the #358 signature and this catches it
                # without someone first suspecting that particular tool. The sharp assertions are
                # properties 3 and 4 below.
                if f"'{scope}'" in out or f"`{scope}`" in out:
                    failures.append(f"{label}: names the factory-only scope '{scope}' while "
                                    f"inspecting a consumer repo — it is reading EADOS's contract, "
                                    f"not the project's (#358 class)\n{out[-300:]}")
                    break
        check("the read-only tools left the repository byte-identical",
              tree_hash(consumer) == before, failures)

        # --- 3. the contract it judges by is the PROJECT's -----------------------------------
        good = project_scopes[0]
        rc, out = run(["git_check.py", "--repo", consumer, "--branch", "docs/x",
                       "--message", f"docs({good}): ok"])
        check(f"a manifest-declared scope '{good}' is accepted\n{out}",
              "is not a declared scope" not in out, failures)

        rc, out = run(["git_check.py", "--repo", consumer, "--branch", "fix/x",
                       "--message", f"fix({factory_only[0]}): sneaks in"])
        check(f"a factory-only scope '{factory_only[0]}' is rejected", rc != 0, failures)
        check(f"...and the vocabulary NAMED in the rejection is the project's, not the factory's"
              f"\n{out}",
              all(f"{s}," in out or f"{s})" in out for s in project_scopes)
              and not any(f"{s}," in out for s in factory_only[1:]), failures)

        # --- 4. resurrect the defect, so property 3 is not vacuous ---------------------------
        rc, out = run(["git_check.py", "--repo", consumer, "--branch", "docs/x",
                       "--message", f"docs({good}): ok", "--policy", git_check.GIT_POLICY])
        check(f"THE DEFECT ON DEMAND: judged by the factory's policy, the project's own valid "
              f"commit is rejected\n{out}", "is not a declared scope" in out and rc != 0, failures)
        check("...and that rejection DOES name the factory vocabulary — so the detector above "
              "is real, not vacuous", any(s in out for s in factory_only), failures)

        # --- the consumer-side fixes of #350 hold in a rendered repo -------------------------
        dependabot = render.load_yaml(
            open(os.path.join(consumer, ".github", "dependabot.yml"), encoding="utf-8").read())
        for eco in (dependabot or {}).get("updates") or []:
            name = (eco or {}).get("package-ecosystem")
            check(f"dependabot '{name}' is capped and grouped, so a fresh repo does not open a "
                  f"queue of bot PRs against its own one-PR policy",
                  eco.get("open-pull-requests-limit") == 1 and isinstance(eco.get("groups"), dict),
                  failures)
        policy = git_check.load_policy(os.path.join(consumer, git_check.PROJECT_POLICY))
        for key, holder in (("one_pr_counts", policy.get("commit")),
                            ("metadata_applies_to", policy.get("pr"))):
            check(f"the rendered policy scopes '{key}' to authored PRs",
                  (holder or {}).get(key) == "authored", failures)

        # --- self_check front-runs the gate that will actually run (#368) --------------------
        # It read the factory spec unconditionally, so inside a generated repo it described EADOS's
        # PR contract. The fix is a MERGE, not a swap: the rendered policy carries only what varies
        # per project, so replacing would have dropped every item it does not mention — a
        # pre-flight that quietly stops asking about PR metadata is worse than one asking with the
        # wrong repo's values, and both look identical from the outside.
        import self_check
        rc, here = run(["self_check.py"], cwd=os.path.dirname(ROOT))
        rc, there = run(["self_check.py"], cwd=consumer)
        check(f"self_check names the policy it used\n{there[-200:]}",
              "docs/workflow/git-policy.yaml" in there, failures)
        check("...the project's, merged over the vendored spec — not instead of it",
              "merged over" in there, failures)
        n_here = here.count("  [ ] ")
        n_there = there.count("  [ ] ")
        check(f"...and the checklist does NOT get shorter in a consumer ({n_here} vs {n_there})",
              n_here == n_there and n_there >= 7, failures)

        merged, _ = self_check.resolve_git_policy(consumer)
        check("the merge takes the PROJECT's value where it declares one",
              [str(s) for s in ((merged.get("commit") or {}).get("scopes") or [])]
              == project_scopes, failures)
        check("...and keeps the factory's where the project is silent (the four items a naive "
              "swap would have dropped)",
              all((merged.get("pr") or {}).get(k) for k in
                  ("metadata", "required_crosslinks", "opened_by", "merged_by")), failures)
        # The merge itself: a project declaring PART of a block keeps the rest.
        part = self_check._merge({"pr": {"metadata": {"a": 1, "b": 2}, "x": 9}},
                                 {"pr": {"metadata": {"b": 3}}})
        check(f"a partial block override keeps its siblings ({part})",
              part == {"pr": {"metadata": {"a": 1, "b": 3}, "x": 9}}, failures)
        check("a list replaces rather than concatenates",
              self_check._merge({"s": [1, 2]}, {"s": [3]}) == {"s": [3]}, failures)

        # --- a WRITING tool is exercised separately, and only where it is meant to write -----
        rc, out = run(["record_run.py", manifest, "--phase", "init", "--outcome", "success",
                       "--note", "consumer smoke"], cwd=consumer)
        check(f"record_run writes its record inside the consumer, not the factory\n{out[-300:]}",
              "Traceback (most recent call last)" not in out, failures)
        stray = os.path.join(ROOT, "learning", "runs")
        check("...and nothing landed in the FACTORY's run-record directory",
              not any("consumer smoke" in open(os.path.join(stray, f), encoding="utf-8").read()
                      for f in (os.listdir(stray) if os.path.isdir(stray) else [])
                      if f.endswith(".yaml")), failures)

    if failures:
        print("test-consumer-smoke: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-consumer-smoke: OK — every shipped tool runs inside a rendered repo, the read-only "
          "ones leave it byte-identical, the vocabulary they judge by is the project's (asserted "
          "against the defect resurrected on demand, so it is not vacuous), and the consumer-side "
          "bot-policy fixes hold in a real render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
