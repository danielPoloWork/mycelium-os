#!/usr/bin/env python3
"""EADOS thin phase orchestrator (roadmap 6.5 / G3) — the executable counterpart to `/eados <phase>`.

`/eados <phase>` is a markdown *procedure* an agent reads ([`commands/`](../orchestrator/commands/)).
This is the deterministic spine underneath it: `eados.py <phase> <manifest>` runs that phase's
**outgoing-transition entry gates** — the gates you must satisfy to leave the phase, read straight
from [`workflow.yaml`](../orchestrator/os/workflow/workflow.yaml) (knowledge as data, no hardcoded
chain) — evaluating the ones it can compute from the project (`manifest-valid`, `rfc-approved`,
`roadmap-covers-rfcs`, `adoption-recorded`, `nfr-budgets`, `traceability-lint`) and marking the
rest `[manual]` / `[needs-input]`. It then prints the legal
next transitions and points at the procedure for the authoring + human-gated steps. `eados.py status`
is the read-only doctor ([`doctor.py`](doctor.py)).

It reports and gates; it never authors an artifact, advances state, or runs a phase tool that writes.
Exit 0 unless a deterministic gate FAILs (or the phase is undeclared). Dependency-free (stdlib + the
sibling tools — one source of truth, never a re-implementation).

    python .eados-core/tools/eados.py <phase|status> <manifest> [--rfc P] [--roadmap P] [--links P] [--strict] [--root D]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render          # noqa: E402  — YAML loader + manifest validation (manifest-valid)
import phase_runner    # noqa: E402  — workflow + legal transitions (the deterministic engine)
import traceability    # noqa: E402  — roadmap-covers-rfcs
import rfc_check        # noqa: E402  — rfc-approved
import doctor          # noqa: E402  — the `status` readout (reused, not re-implemented)
import command_registry  # noqa: E402  — the canonical verb list (#373), parsed once

PHASES = ("init", "design", "plan", "scaffold", "audit", "migrate")

# The host-independent command surface (#373). Only `claude-code` ships slash-command adapters, so
# for every other host — and for a model driven through a plain API, which has no command mechanism
# at all — THIS is the command surface. It exposed 7 of the registry's 14 verbs.
#
# Commands split into two kinds, and the split is the design rather than an omission:
#   * DELEGATES  — a tool does the work; the CLI forwards the remaining argv to it, so each tool's
#                  flags stay declared in ONE place (re-stating them here would be a second copy of
#                  every signature, which is how the surface fell behind in the first place);
#   * the rest   — `debug`/`refactor`/`optimize`/`testcases` AUTHOR code and tests. A CLI cannot run
#                  them; an agent does. So they are *addressable*: the CLI prints the procedure, its
#                  owning role and its class, and stops. For a host with no slash commands that
#                  turns "find the right file inside a vendored bundle" into one command.
DELEGATES = {
    "adopt":   ("brownfield", "<repo-dir>"),
    "review":  ("pr_review", "--pr N [--repo OWNER/REPO]"),
    "upgrade": ("upgrade_advice", "[<repo-path>]"),
}
# Declared, not inferred. Falling back to "agent-authored" for anything unrecognised would let a NEW
# command that *should* be runnable land silently in the weakest bucket — the CLI would keep looking
# complete while quietly demoting it. A command must be classified on purpose, so an unlisted verb
# is reported as unclassified and `test_cli_command_parity` fails until someone decides.
AGENT_AUTHORED = ("debug", "refactor", "optimize", "testcases")


def _rfcs(manifest):
    ds = manifest.get("delivery_state") if isinstance(manifest, dict) else None
    refs = (ds.get("refs") or {}) if isinstance(ds, dict) else {}
    return list(refs.get("rfcs") or [])


# --- gate evaluators: each returns (mark, detail). mark ∈ {OK, FAIL, skipped, needs-input}. -----
#     skipped     = the input is genuinely not applicable (nothing to check yet).
#     needs-input = a CHECKABLE input is missing — the project HAS something to verify, but the
#                   caller withheld the file/refs. Under --strict it fails the phase (#200), so a
#                   gate can no longer be satisfied by omission (EADOS's fail-closed posture).
def _ev_manifest_valid(manifest, ctx):
    scalars, _f, _s = render.build_context(manifest)
    problems = render.validate_manifest(manifest, scalars)
    return ("FAIL", f"{len(problems)} problem(s) (e.g. {problems[0]})") if problems else ("OK", "")


def _ev_rfc_approved(manifest, ctx):
    if ctx.get("rfc_text") is None:
        if _rfcs(manifest):
            return ("needs-input", "delivery_state records RFC refs but no --rfc <path> was given — "
                    "the rfc-approved check cannot run (withholding the file must not pass the gate)")
        return ("skipped", "no RFC refs recorded yet; provide --rfc <path> once an RFC exists")
    problems = rfc_check.check_rfc(ctx["rfc_text"], rfc_check.load_protocol())
    return ("FAIL", problems[0]) if problems else ("OK", "")


def _ev_roadmap_covers(manifest, ctx):
    rfcs = _rfcs(manifest)
    if not rfcs:
        return ("needs-input", "no RFC refs recorded in delivery_state — record them so coverage "
                "can be checked (withholding refs must not silently satisfy the gate)")
    if ctx.get("roadmap_text") is None:
        return ("needs-input", "no ROADMAP.md found — coverage of the recorded RFCs cannot be checked")
    uncovered = traceability.uncovered_rfcs(ctx["roadmap_text"], rfcs)
    return ("FAIL", f"uncovered: {', '.join(uncovered)}") if uncovered else ("OK", "")


def _ev_adoption_recorded(manifest, ctx):
    """The brownfield adoption gate (#247, ADR-0021). Absent block -> `skipped` (a greenfield
    project is genuinely not applicable — `eados.py init` must stay green for every ordinary
    manifest, since run_phase unions the gates of ALL outgoing init edges); present-but-malformed
    -> FAIL (render.adoption_problems owns the shape rules); valid -> OK."""
    adoption = manifest.get("adoption") if isinstance(manifest, dict) else None
    if adoption is None:
        return ("skipped", "no adoption block — a greenfield project; /eados adopt records one")
    problems = render.adoption_problems(adoption)
    if problems:
        return ("FAIL", f"{len(problems)} problem(s) (e.g. {problems[0]})")
    return ("OK", "")


def _ev_nfr_budgets(manifest, ctx):
    """The numeric NFR-budget gate (#249). Every HARD axis of the manifest's domain
    (domains/<domain>.yaml `nfr_axes[].hard_budget: true`, typed with unit/direction/scale/
    metrics) must carry a recorded budget in spec.nfr_budgets, well-formed
    (render.nfr_budget_problems owns the entry shape; render.budget_number coerces the
    yamlmini string-decimals), typed right (numeric, or on the axis's scale; one entry per
    declared composite metric), and — when a `measured` value is recorded — satisfied per the
    axis's direction. No hard axes declared -> `skipped` (the software baseline). A GREENFIELD
    manifest still at phase `init` (no adoption block) -> `skipped`: budgets are elicited at
    Q5.3 (Phase 5), and without an adoption record the audit edges this gate rides are not
    takeable anyway — `eados.py init` must stay green, exactly like `adoption-recorded`. An
    ADOPTED manifest at init IS held to the bar (the ADR-0021 same-bar consequence). An
    unreadable domain profile -> `needs-input` (a checkable input is missing, #200)."""
    adoption = manifest.get("adoption") if isinstance(manifest, dict) else None
    if phase_runner.current_phase(manifest) == "init" and not adoption:
        return ("skipped", "greenfield manifest at init — budgets arrive with the Phase-5 "
                "interview; the audit edges are not takeable from here without adoption")
    domain = phase_runner.manifest_domain(manifest)
    path = os.path.join(os.path.dirname(HERE), "orchestrator", "domains", f"{domain}.yaml")
    try:
        with open(path, encoding="utf-8") as fh:
            axes = render.load_yaml(fh.read()).get("nfr_axes") or []
    except (OSError, ValueError):
        return ("needs-input", f"domain profile domains/{domain}.yaml is missing or unreadable — "
                "the hard-axis budgets cannot be checked")
    hard = [a for a in axes if isinstance(a, dict) and a.get("hard_budget")]
    if not hard:
        return ("skipped", f"domain '{domain}' declares no hard NFR axes — nothing to budget")
    spec = manifest.get("spec") if isinstance(manifest, dict) else None
    budgets = (spec or {}).get("nfr_budgets") if isinstance(spec, dict) else None
    problems = render.nfr_budget_problems(budgets if budgets is not None else [])
    by_axis = {}
    for entry in (budgets if isinstance(budgets, list) else []):
        if isinstance(entry, dict) and str(entry.get("axis") or "").strip():
            by_axis.setdefault(entry["axis"], []).append(entry)
    for axis in hard:
        name, unit = axis.get("axis"), axis.get("unit") or "a number"
        entries = by_axis.get(name) or []
        if not entries:
            problems.append(f"hard axis '{name}' ({unit}) has no recorded budget in "
                            "spec.nfr_budgets — a hard budget is a number, not a promise")
            continue
        scale = str(axis.get("scale") or "").strip()
        direction = str(axis.get("direction") or "max").strip()
        for entry in entries:
            target = entry.get("target")
            tgt_num = render.budget_number(target)
            if scale:
                allowed = [s.strip() for s in scale.split("|")]
                if str(target).strip() not in allowed:
                    problems.append(f"hard axis '{name}': target {target!r} is not on the "
                                    f"scale {scale}")
            elif tgt_num is None:
                problems.append(f"hard axis '{name}': target must be numeric ({unit}), "
                                f"got {target!r}")
            measured_num = render.budget_number(entry.get("measured"))
            if tgt_num is not None and measured_num is not None:
                satisfied = (measured_num >= tgt_num if direction == "min"
                             else measured_num <= tgt_num)
                if not satisfied:
                    problems.append(f"hard axis '{name}': measured {entry.get('measured')} "
                                    f"violates the {direction} budget of {target} "
                                    f"{axis.get('unit') or ''}".rstrip())
        # composite axis (#249): the declared metrics must EACH carry an entry, and an entry's
        # metric must be one the axis declares — the _schema.md one-entry-per-metric promise.
        metrics = [m.strip() for m in str(axis.get("metrics") or "").split("|") if m.strip()]
        if metrics:
            seen = {str(e.get("metric") or "").strip() for e in entries}
            for metric in metrics:
                if metric not in seen:
                    problems.append(f"hard axis '{name}': composite metric '{metric}' has no "
                                    "recorded budget entry")
            for e in entries:
                em = str(e.get("metric") or "").strip()
                if em and em not in metrics:
                    problems.append(f"hard axis '{name}': unknown metric '{em}' (declared: "
                                    f"{axis.get('metrics')})")
    if problems:
        return ("FAIL", f"{len(problems)} problem(s) (e.g. {problems[0]})")
    return ("OK", "")


def _ev_traceability_lint(manifest, ctx):
    """The cross-cutting traceability gate (#250) — the graph `RFC -> milestone -> PR -> commit ->
    release` must have no dangling edge. Needs the roadmap AND the links file (derive it:
    `derive_links.py --out links.yaml`); a recorded RFC set with either input withheld is
    `needs-input` (fail-closed under --strict, #200); no RFC refs recorded yet -> `skipped`."""
    rfcs = _rfcs(manifest)
    if not rfcs:
        return ("skipped", "no RFC refs recorded yet — the graph has no roots to trace")
    if ctx.get("roadmap_text") is None:
        return ("needs-input", "no ROADMAP.md found — the RFC -> milestone edges cannot be traced")
    if ctx.get("links") is None:
        return ("needs-input", "no links file — derive it (`derive_links.py --out links.yaml`) "
                "and pass --links; withholding the edges must not pass the gate")
    problems = traceability.traceability_lint(ctx["roadmap_text"], rfcs, ctx["links"])
    if problems:
        kind, detail = problems[0]
        return ("FAIL", f"{len(problems)} dangling edge(s) (e.g. {kind}: {detail})")
    return ("OK", "")


GATE_EVALUATORS = {
    "manifest-valid": _ev_manifest_valid,
    "rfc-approved": _ev_rfc_approved,
    "roadmap-covers-rfcs": _ev_roadmap_covers,
    "adoption-recorded": _ev_adoption_recorded,   # brownfield adoption (#247, ADR-0021)
    "nfr-budgets": _ev_nfr_budgets,               # numeric hard-axis budgets (#249)
    "traceability-lint": _ev_traceability_lint,   # dangling-edge lint (#250)
}

# The procedure a phase points at for its authoring + human-gated steps.
PROCEDURE = {p: f"orchestrator/commands/{p}.md" for p in PHASES}
PROCEDURE["scaffold"] = "orchestrator/generate.md"


def evaluate_gates(gate_ids, manifest, ctx):
    """{gate id -> mark} for `gate_ids`: the in-process gates (GATE_EVALUATORS) evaluated over the
    project, the rest marked `manual` (run by the phase procedure / CI / a human). One source of
    truth for the deterministic marks — run_phase's display and the checkpoint's LIVE gate_results
    (#213) both resolve a gate through GATE_EVALUATORS, so the two can never diverge."""
    out = {}
    for g in gate_ids:
        evaluator = GATE_EVALUATORS.get(g)
        out[g] = evaluator(manifest, ctx or {})[0] if evaluator else "manual"
    return out


def run_phase(phase, manifest, workflow, roadmap_text=None, rfc_text=None, strict=False,
              links=None):
    """Run `phase`'s deterministic outgoing gates over the project. Returns (lines, ok): `ok` is
    False when a gate the orchestrator can evaluate FAILs (manual/skipped never fail), or — under
    `strict` (#200) — when a gate is `needs-input` (a checkable input was withheld), so a gate can
    no longer be satisfied by omission. The phase not being a declared state is also not-ok."""
    ctx = {"roadmap_text": roadmap_text, "rfc_text": rfc_text, "links": links}
    states = phase_runner.state_ids(workflow)
    if phase not in states:
        return [f"'{phase}' is not a declared workflow state {states}"], False

    lines, ok = [], True
    transitions = phase_runner.legal_transitions(workflow, phase)
    gates = []
    for t in transitions:
        for g in t.get("entry_gates") or []:
            if g not in gates:
                gates.append(g)

    if gates:
        lines.append(f"gates to leave '{phase}':")
        for g in gates:
            evaluator = GATE_EVALUATORS.get(g)
            if evaluator is None:
                lines.append(f"  [manual] {g} (run it in the procedure; needs a rendered repo or a "
                             "human decision)")
                continue
            mark, detail = evaluator(manifest, ctx)
            lines.append(f"  [{mark}] {g}" + (f" - {detail}" if detail else ""))
            if mark == "FAIL" or (mark == "needs-input" and strict):
                ok = False
    else:
        lines.append(f"phase '{phase}': terminal — no outgoing gates")

    if transitions:
        lines.append("legal next transitions:")
        for t in transitions:
            gs = ", ".join(t.get("entry_gates") or []) or "-"
            human = "  [human-gated]" if t.get("human_gate") else ""
            lines.append(f"  -> {t.get('to')}   (gates: {gs}){human}")
    else:
        lines.append("(terminal phase — no outgoing transitions)")

    lines.append(f"next: {PROCEDURE.get(phase, '?')} — the authoring + human-gated steps.")
    return lines, ok


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _procedure_card(name, registry):
    """What the CLI can honestly offer for a command it cannot run: where the procedure is, who owns
    it, and what it does. `debug`/`refactor`/`optimize`/`testcases` author code and tests — an agent
    does that. Saying so beats a command that appears to work and does nothing."""
    entry = next((c for c in registry if c["name"] == name), None)
    if entry is None:
        print(f"eados: unknown command {name!r}", file=sys.stderr)
        return 2
    print(f"EADOS {name} - agent-authored (this CLI cannot run it)")
    print(f"  {entry['summary']}")
    print(f"  procedure: {entry['procedure']}")
    print("  class:     cross-cutting - advisory, never advances delivery_state (ADR-0019 class 3)")
    # The owning role is stated in the procedure's own prose, not a parseable field. A
    # regex over it would fire for some commands and not others, and a reader could not
    # tell "no owner" from "could not find one" - so the card points at the file instead.
    print("  It produces code, tests or a ledger entry, so an AGENT follows the procedure above.")
    print("  Open this repository with your agent and ask for it by name; the contract "
          "(AGENTS.md) points at the same file.")
    return 0


def _command_list(registry):
    """Every command the registry declares, with how this CLI treats it. The list an agent or a
    human reads on a host that ships no slash commands."""
    lines = ["EADOS commands (from orchestrator/commands/README.md):"]
    for c in registry:
        if c["name"] in PHASES or c["name"] == "status":
            how = "runs gates"
        elif c["name"] in DELEGATES:
            how = f"runs {DELEGATES[c['name']][0]}.py"
        elif c["name"] in AGENT_AUTHORED:
            how = "agent-authored"
        else:
            how = "UNCLASSIFIED"
        lines.append(f"  {c['name']:<10} [{how:<20}] {c['summary'][:78]}")
    lines.append("")
    lines.append("  eados.py <phase|status> <manifest>      run a phase's deterministic gates")
    for name, (_mod, usage) in sorted(DELEGATES.items()):
        lines.append(f"  eados.py {name} {usage}".ljust(42) + " delegate to its tool")
    return lines


def completion_script(shell, registry, tool=None):
    """A shell snippet defining an `eados` command and completing the registry's verbs.

    **Generated, never hand-written.** A checked-in completion file is a second copy of the verb
    list, and a stale completion is worse than none — it offers a command that no longer exists and
    hides one that does. This is the same reasoning that put the registry parser in one module.

    Emitted to stdout for the caller to `eval` or append; nothing is written to disk, so there is no
    file to fall out of date between releases."""
    verbs = " ".join(c["name"] for c in registry) + " commands"
    tool = (tool or os.path.join(HERE, "eados.py")).replace("\\", "/")
    if shell == "bash":
        return (f'# eval "$(python {tool} completion bash)"\n'
                f'eados() {{ python "{tool}" "$@"; }}\n'
                f'_eados_complete() {{\n'
                f'  local cur="${{COMP_WORDS[COMP_CWORD]}}"\n'
                f'  if [ "$COMP_CWORD" -eq 1 ]; then\n'
                f'    COMPREPLY=( $(compgen -W "{verbs}" -- "$cur") )\n'
                f'  else\n'
                f'    COMPREPLY=( $(compgen -f -- "$cur") )\n'
                f'  fi\n'
                f'}}\n'
                f'complete -F _eados_complete eados\n')
    if shell == "zsh":
        return (f'# eval "$(python {tool} completion zsh)"\n'
                f'eados() {{ python "{tool}" "$@"; }}\n'
                f'_eados_complete() {{\n'
                f'  if (( CURRENT == 2 )); then\n'
                f'    compadd -- {verbs}\n'
                f'  else\n'
                f'    _files\n'
                f'  fi\n'
                f'}}\n'
                f'compdef _eados_complete eados\n')
    if shell == "powershell":
        quoted = ", ".join(f"'{c['name']}'" for c in registry) + ", 'commands'"
        return (f'# python {tool} completion powershell | Out-String | Invoke-Expression\n'
                f'function eados {{ python "{tool}" @args }}\n'
                f'Register-ArgumentCompleter -CommandName eados -Native -ScriptBlock {{\n'
                f'  param($wordToComplete, $commandAst, $cursorPosition)\n'
                f'  @({quoted}) |\n'
                f'    Where-Object {{ $_ -like "$wordToComplete*" }} |\n'
                f'    ForEach-Object {{ [System.Management.Automation.CompletionResult]::new('
                f'$_, $_, "ParameterValue", $_) }}\n'
                f'}}\n')
    return ""


COMPLETION_SHELLS = ("bash", "zsh", "powershell")


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else list(argv)
    registry = command_registry.load()
    known = [c["name"] for c in registry]
    # The command set comes from the REGISTRY, never a tuple maintained here — a surface that keeps
    # its own copy of the verb list is a surface that falls behind it (#373).
    if argv and argv[0] in DELEGATES:
        module, _usage = DELEGATES[argv[0]]
        return __import__(module).main(argv[1:])
    if argv and argv[0] in known and argv[0] not in PHASES + ("status",):
        return _procedure_card(argv[0], registry)
    if argv and argv[0] in ("--commands", "commands"):
        for line in _command_list(registry):
            print(line)
        return 0
    if argv and argv[0] == "completion":
        shell = argv[1] if len(argv) > 1 else ""
        if shell not in COMPLETION_SHELLS:
            print(f"eados: completion needs a shell ({'|'.join(COMPLETION_SHELLS)})",
                  file=sys.stderr)
            return 2
        sys.stdout.write(completion_script(shell, registry))
        return 0

    import argparse
    ap = argparse.ArgumentParser(
        description="EADOS command surface - run a phase's deterministic gates, delegate to a "
                    "command's tool, or print a procedure. `eados.py commands` lists every verb.",
        epilog="every /eados command is accepted; see `eados.py commands`")
    ap.add_argument("command", choices=PHASES + ("status",),
                    help="a phase (init|design|plan|scaffold|audit|migrate) or 'status'")
    ap.add_argument("manifest", help="path to a project manifest (project.yaml)")
    ap.add_argument("--root", help="project root for ROADMAP.md / links "
                         "(default: the nearest ancestor with .eados-core/ or .git/)")
    ap.add_argument("--roadmap", help="path to ROADMAP.md (default: <root>/ROADMAP.md)")
    ap.add_argument("--links", help="traceability links file (default: <root>/links.yaml if present)")
    ap.add_argument("--rfc", help="an RFC file to check for the rfc-approved gate (design)")
    ap.add_argument("--strict", action="store_true",
                    help="fail the phase on a needs-input gate too (a checkable input was withheld) "
                         "— the fail-closed posture for CI; skipped (not applicable) still passes")
    args = ap.parse_args(argv)

    try:
        manifest = render.load_yaml(_read(args.manifest))
    except (OSError, ValueError) as exc:
        print(f"eados: cannot read manifest {args.manifest!r}: {exc}", file=sys.stderr)
        return 2
    workflow = phase_runner.apply_overlay(phase_runner.load_workflow(),
                                          phase_runner.manifest_domain(manifest))
    # #347: the project root, not the manifest's own directory — the prescribed manifest
    # lives in orchestrator/ while ROADMAP.md and links.yaml live at the repo root.
    root = args.root or render.project_root(args.manifest)
    roadmap_path = args.roadmap or os.path.join(root, "ROADMAP.md")
    roadmap_text = _read(roadmap_path) if os.path.isfile(roadmap_path) else None
    links_path = args.links or os.path.join(root, "links.yaml")
    links = (render.load_yaml(_read(links_path)) or {}).get("links") if os.path.isfile(links_path) else None
    rfc_text = _read(args.rfc) if args.rfc else None

    if args.command == "status":
        lines, ok = doctor.status_report(manifest, workflow, roadmap_text, links)
    else:
        lines, ok = run_phase(args.command, manifest, workflow, roadmap_text, rfc_text,
                              strict=args.strict, links=links)

    # #214: surface the optimistic-concurrency counter the readout validated against, so a caller
    # can pass it to `phase_runner --propose --expect-rev N` before writing.
    print(f"EADOS {args.command} - {args.manifest}  (manifest_rev {phase_runner.manifest_rev(manifest)})")
    for line in lines:
        print(f"  {line}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
