#!/usr/bin/env python3
"""Generate the `/eados` command tree for whichever host you use (#375, ADR-0019 addendum).

Only Claude Code ever had adapters. `codex`, `gemini` and `opencode` are declared hosts of the
routing catalog and got none — so since M19 made provider-agnosticism an explicit commitment, the OS
resolved tier, effort and model for any host while the **command surface** stayed one host wide.

**Adapters are data.** Each host declares a `commands:` block in `os/routing/routing.yaml` — where
the files go, what format the host discovers, whether a subdirectory namespaces them, and what the
user actually types. One renderer reads that block and the canonical command list, so 14 commands
across 4 hosts is one generator instead of 56 hand-maintained files and guaranteed drift.

**Three scopes, and the middle one is a constraint rather than an omission:**
  * `project` — EADOS writes the tree into the repository (Claude Code, Gemini, OpenCode).
  * `home`    — the host reads them from OUTSIDE the project (Codex: `~/.codex/prompts`, documented
                as *"not shared through your repository"*). EADOS renders them **inside** the
                project and prints the one command to install them. It never writes outside the
                target, which is the same containment posture the installer is built on.
  * `none`    — no verified mechanism. Stated, never guessed: shipping a directory a host does not
                read looks like support.

Every adapter is a **pointer** (ADR-0019 class 4 — surfacing, never semantics): it names the
canonical procedure and instructs the agent to read it. No procedure body is copied, so the markdown
in `orchestrator/commands/` stays the single source of truth for every host.

    python .eados-core/tools/adapter_render.py --host gemini [--out DIR] [--list] [--dry-run]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import command_registry   # noqa: E402  — the canonical verb list (#373)
import route_advice       # noqa: E402  — the host catalog + its loud-rejecting loader
import sandbox            # noqa: E402  — the ONE write-containment path (ADR-0007)

CLASS_NOTE = ("cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing: it never "
              "writes `delivery_state`, proposes no transition, and drafts nothing without the "
              "human's confirmation.")


def host_commands(spec, host_id):
    """The `commands:` block a host declares, or `{}`. Data, so a new host needs no code here."""
    for h in (spec.get("catalog") or {}).get("hosts") or []:
        if isinstance(h, dict) and h.get("id") == host_id:
            block = h.get("commands")
            return block if isinstance(block, dict) else {}
    raise KeyError(host_id)


def adapter_name(entry, block):
    """The file stem the host will turn into a command name. `nest: false` hosts cannot namespace
    via a subdirectory, so the prefix goes into the name itself — recorded per host rather than
    assumed, because getting it wrong produces a tree the host silently ignores."""
    return entry["name"] if block.get("nest") else f"eados-{entry['name']}"


def render_adapter(entry, block, host_name):
    """One adapter, in the format its host discovers. A POINTER: it names the procedure and says to
    read it. Copying the body would fork the procedure per host — the drift this design exists to
    prevent."""
    desc = f"EADOS {entry['name']} — {entry['summary']}"
    body = (f"Run the governed EADOS command **`/eados {entry['name']}`**.\n\n"
            f"This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, "
            f"never adds behavior). The canonical procedure is the single source of truth — read it "
            f"and follow it exactly; do not improvise or reproduce it from memory.\n\n"
            f"- **Procedure:** `{entry['procedure']}`\n"
            f"- **Class:** {CLASS_NOTE}\n"
            f"- **Contract:** `AGENTS.md`.\n\n"
            f"Generated for {host_name} by EADOS (#375). Do not edit by hand — regenerate with "
            f"`adapter_render.py`.")
    fmt = block.get("format")
    if fmt == "toml":
        # Gemini: `prompt` is the only required key; `description` shows in /help. TOML basic
        # strings would need escaping, so both values use multi-line literal (''') strings, which
        # take the body verbatim.
        return (f"description = '''{desc}'''\n\n"
                f"prompt = '''\n{body}\n\n{{{{args}}}}\n'''\n")
    if fmt == "md-yaml-frontmatter":
        # OpenCode: YAML frontmatter; the prompt template is the body after it.
        return f"---\ndescription: {desc}\n---\n\n{body}\n\n$ARGUMENTS\n"
    # Claude Code / Codex: markdown with a `description` frontmatter key.
    return f"---\ndescription: {desc}\n---\n\n{body}\n\nUser arguments (may be empty): $ARGUMENTS\n"


def plan(host_id, spec=None, registry=None):
    """`(block, [(relpath, text)])` — everything the tree would contain, without writing anything.
    Pure enough to test, and it is what `--dry-run` prints."""
    spec = spec or route_advice.load_routing()
    registry = registry or command_registry.load()
    block = host_commands(spec, host_id)
    if not block or block.get("scope") == "none":
        return block, []
    name = next((h.get("name", host_id) for h in (spec.get("catalog") or {}).get("hosts") or []
                 if isinstance(h, dict) and h.get("id") == host_id), host_id)
    ext = block.get("ext") or ".md"
    files = []
    for entry in registry:
        rel = f"{block['dir']}/{adapter_name(entry, block)}{ext}"
        files.append((rel, render_adapter(entry, block, name)))
    return block, files


def main(argv=None):
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="Generate the /eados command tree for a host.")
    ap.add_argument("--host", help="a host id from os/routing/routing.yaml (see --list)")
    ap.add_argument("--out", default=".", help="target repository (default: .)")
    ap.add_argument("--list", action="store_true", help="what each declared host supports")
    ap.add_argument("--dry-run", action="store_true", help="print the tree, write nothing")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing adapters (default: additive, never clobber)")
    args = ap.parse_args(argv)

    try:
        spec = route_advice.load_routing()
    except (OSError, ValueError) as exc:
        print(f"adapter-render: ERROR — cannot read os/routing/routing.yaml: {exc}",
              file=sys.stderr)
        return 2

    if args.list or not args.host:
        print("hosts and their command surfaces (os/routing/routing.yaml `commands:`):")
        for h in (spec.get("catalog") or {}).get("hosts") or []:
            block = h.get("commands") if isinstance(h.get("commands"), dict) else {}
            scope = block.get("scope", "none")
            where = block.get("dir", "—")
            print(f"  {h.get('id'):<12} scope={scope:<8} {where:<26} "
                  f"{block.get('invocation', 'no verified command mechanism')}")
        print("\n  project = generated into the repo · home = generated here, you install it · "
              "none = no verified mechanism")
        if not args.host:
            print("\nusage: adapter_render.py --host <id> [--out DIR] [--dry-run]")
        return 0

    try:
        block, files = plan(args.host, spec)
    except KeyError:
        print(f"adapter-render: unknown host {args.host!r} — see --list", file=sys.stderr)
        return 2
    if not files:
        # Never a silent no-op: a host with no verified mechanism must SAY so, or the caller
        # cannot tell "nothing to do" from "it worked".
        print(f"adapter-render: {args.host} declares no verified command mechanism "
              f"(scope={block.get('scope', 'none')}). Its surface is AGENTS.md §13 plus "
              f"`eados.py commands`.")
        return 0

    if args.dry_run:
        for rel, _text in files:
            print(rel)
        return 0

    written, skipped = [], []
    for rel, text in files:
        target = os.path.join(args.out, rel.replace("/", os.sep))
        if os.path.exists(target) and not args.force:
            skipped.append(rel)      # additive by default, like the installer
            continue
        try:
            sandbox.safe_write(args.out, rel, text, overwrite=args.force)
        except Exception as exc:     # noqa: BLE001 — containment refusal is sandbox's to raise
            print(f"adapter-render: refused to write {rel}: {exc}", file=sys.stderr)
            return 2
        written.append(rel)
    print(f"adapter-render: {args.host} — {len(written)} adapter(s) written to "
          f"{block['dir']}/" + (f", {len(skipped)} left alone (already present; --force to "
                                f"overwrite)" if skipped else ""))
    if block.get("scope") == "home":
        print(f"  {args.host} reads its commands from {block.get('install_to')}, which is OUTSIDE "
              f"this project — EADOS does not write there. Install them yourself:")
        print(f"    cp {block['dir']}/*{block.get('ext', '.md')} "
              f"{block.get('install_to')}/    # macOS/Linux")
        print(f"    Copy-Item {block['dir']}\\*{block.get('ext', '.md')} "
              f"{block.get('install_to')}\\   # Windows")
    print(f"  invoke with: {block.get('invocation')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
