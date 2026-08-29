#!/usr/bin/env python3
"""Every host gets a command tree, generated from data (#375, ADR-0019 addendum).

Only Claude Code ever had adapters. `codex`, `gemini` and `opencode` are declared hosts of the
routing catalog and got **none** — so while M19 made provider-agnosticism an explicit commitment and
the OS resolves tier, effort and model for any host, the *command surface* stayed one host wide.

Adapters are now data: each host declares `commands:` (scope, dir, ext, format, nest, invocation)
and one renderer emits the tree. The property that matters is **no per-host copies** — 14 commands
across 4 hosts by hand is 56 files and guaranteed drift, the failure #365 and #366 each closed with
a gate. Here it is closed by not creating the copies at all, so the test asserts every tree is
derived from the one registry and that a new command appears in all of them at once.

The formats were verified against each host's current documentation; the generated TOML is parsed
with `tomllib` rather than eyeballed, because a file a host cannot read is worse than none — it
looks like support and fails silently.

    python .eados-core/tools/tests/test_adapter_render.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import adapter_render     # noqa: E402
import command_registry   # noqa: E402
import eados_lint as lint  # noqa: E402
import route_advice       # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(args, cwd=None):
    proc = subprocess.run([sys.executable, os.path.join(TOOLS, "adapter_render.py"), *args],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main():
    failures = []
    spec = route_advice.load_routing()
    registry = command_registry.load()
    hosts = [h.get("id") for h in (spec.get("catalog") or {}).get("hosts") or []]
    check(f"the catalog declares its hosts ({hosts})", len(hosts) >= 4, failures)

    # --- every host declares a commands block, and the scopes are the three we support -------
    for host in hosts:
        block = adapter_render.host_commands(spec, host)
        check(f"{host}: declares a commands block", bool(block), failures)
        check(f"{host}: scope is one of project|home|none (got {block.get('scope')!r})",
              block.get("scope") in ("project", "home", "none"), failures)
        if block.get("scope") != "none":
            check(f"{host}: declares where and how", block.get("dir") and block.get("format")
                  and block.get("invocation"), failures)
        if block.get("scope") == "home":
            # The constraint that makes this scope exist: EADOS renders inside the project and the
            # USER installs it. A home host that did not say where would be unusable.
            check(f"{host}: home scope names install_to, and renders INSIDE the project",
                  block.get("install_to") and not block["dir"].startswith("~"), failures)

    # --- one registry, every tree ------------------------------------------------------------
    trees = {}
    for host in hosts:
        block, files = adapter_render.plan(host, spec, registry)
        if block.get("scope") == "none":
            check(f"{host}: an unverified host emits nothing rather than a guess", files == [],
                  failures)
            continue
        trees[host] = files
        check(f"{host}: one adapter per command ({len(files)} vs {len(registry)})",
              len(files) == len(registry), failures)
        for (rel, text), entry in zip(files, registry):
            check(f"{host}/{entry['name']}: lands under the declared dir",
                  rel.startswith(block["dir"] + "/") and rel.endswith(block["ext"]), failures)
            check(f"{host}/{entry['name']}: is a POINTER at the canonical procedure — no host may "
                  "carry its own copy of the body", entry["procedure"] in text, failures)
            check(f"{host}/{entry['name']}: carries its description", entry["summary"][:30] in text,
                  failures)

    # A new command must appear in EVERY tree from the one registry, with no per-host edit.
    extended = registry + [{"name": "brandnew", "phase": "— (any)",
                            "procedure": ".eados-core/orchestrator/commands/brandnew.md",
                            "summary": "A new verb."}]
    for host in trees:
        _b, files = adapter_render.plan(host, spec, extended)
        check(f"{host}: a new registry command flows through with no per-host change",
              any("brandnew" in rel for rel, _t in files), failures)

    # --- nest:false hosts must not rely on undocumented namespacing --------------------------
    for host, files in trees.items():
        block = adapter_render.host_commands(spec, host)
        if not block.get("nest"):
            check(f"{host}: flat names carry the prefix, since subdirectory namespacing is not "
                  "documented for it", all("/eados-" in rel for rel, _t in files), failures)

    with tempfile.TemporaryDirectory() as tmp:
        # --- the generated files are readable BY THEIR HOST ----------------------------------
        for host in hosts:
            rc, out = run(["--host", host, "--out", tmp])
            check(f"{host}: renders ({out.strip()[-160:]})", rc == 0, failures)
        try:
            import tomllib
            gem = adapter_render.host_commands(spec, "gemini")
            n = 0
            for fn in sorted(os.listdir(os.path.join(tmp, *gem["dir"].split("/")))):
                with open(os.path.join(tmp, *gem["dir"].split("/"), fn), "rb") as fh:
                    data = tomllib.load(fh)
                check(f"gemini/{fn}: `prompt` is required by the host and non-empty",
                      str(data.get("prompt") or "").strip(), failures)
                check(f"gemini/{fn}: carries a description for /help",
                      str(data.get("description") or "").strip(), failures)
                n += 1
            check(f"every gemini adapter is valid TOML ({n}) — parsed, not eyeballed",
                  n == len(registry), failures)
        except ImportError:
            pass          # tomllib is 3.11+; the rest of the assertions still hold

        # --- additive by default, like the installer -----------------------------------------
        rc, out = run(["--host", "gemini", "--out", tmp])
        check(f"a second run does not clobber ({out.strip()[-120:]})",
              "left alone" in out or "0 adapter(s)" in out, failures)

        # --- a home-scoped host renders INSIDE the project and says who installs it ----------
        rc, out = run(["--host", "codex", "--out", tmp])
        check("codex renders into the project, never into the user's home",
              os.path.isdir(os.path.join(tmp, ".eados", "adapters", "codex")), failures)
        check(f"...and states that EADOS does not write there, with the command to run\n{out}",
              "OUTSIDE this project" in out and "~/.codex/prompts" in out, failures)

        rc, out = run(["--host", "nope", "--out", tmp])
        check("an unknown host is refused, not silently skipped", rc == 2 and "unknown host" in out,
              failures)
        rc, out = run(["--list"])
        check("--list shows every host's surface", rc == 0 and all(h in out for h in hosts),
              failures)

    # --- the gate now covers every project-scoped host ---------------------------------------
    gated = [h for h, _b in lint._adapter_hosts()]
    project_hosts = [h for h in hosts
                     if adapter_render.host_commands(spec, h).get("scope") == "project"]
    check(f"command-adapters covers every project-scoped host ({gated} vs {project_hosts})",
          sorted(gated) == sorted(project_hosts), failures)
    # ...and its messages name the host's OWN path — a gemini finding pointing at a .claude file
    # sends the reader to a file that does not exist.
    readme = lint.read(os.path.join(ROOT, "orchestrator", "commands", "README.md"))
    problems = lint.command_adapter_problems(readme, {}, where=".gemini/commands/eados",
                                             ext=".toml", host="gemini")
    check(f"a gemini finding names a gemini path ({problems[:1]})",
          problems and ".gemini/commands/eados/" in problems[0] and ".toml" in problems[0],
          failures)

    if failures:
        print("test-adapter-render: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-adapter-render: OK — every declared host's tree is generated from the one registry "
          "(a new command reaches all of them with no per-host edit), the Gemini TOML parses, a "
          "home-scoped host renders inside the project and says who installs it, and the gate "
          "covers every project-scoped host in its own path vocabulary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
