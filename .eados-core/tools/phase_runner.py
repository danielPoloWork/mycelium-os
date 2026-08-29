#!/usr/bin/env python3
"""EADOS phase runner — the deterministic, state-driven checker behind `/eados <phase>`.

Given a project manifest, it reads `delivery_state.phase` and the workflow spec
(`orchestrator/os/workflow/workflow.yaml`) and prints the **legal next transitions** — each with
its entry gates and whether it needs human confirmation. It is the thin "engine" the RFC calls
for: a pure function over data. It **never advances state** — it reports what is legal; the agent
proposes a transition, the gates validate it, and the human confirms every human-gated step
(`AGENTS.md` §6).

At every boundary it re-grounds the runtime non-negotiables (#221) — the acting role, the terminal
human gate, one-PR — each line derived from the workflow / authority / git specs, so a long run can
no longer let them drift out of view. Past a checkpoint-depth threshold it adds a compact reminder.

Dependency-free: the Python standard library plus the sibling renderer's YAML loader.

    python .eados-core/tools/phase_runner.py <manifest>     # report the legal next transitions
"""

import copy
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader (sibling tool)

WORKFLOW = os.path.join(ROOT, "orchestrator", "os", "workflow", "workflow.yaml")
AUTHORITY = os.path.join(ROOT, "orchestrator", "os", "authority", "authority.yaml")
GIT = os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")
INTERACTION = os.path.join(ROOT, "orchestrator", "os", "interaction", "interaction.yaml")
ROUTING = os.path.join(ROOT, "orchestrator", "os", "routing", "routing.yaml")

# #221: a project this many recorded transitions deep re-grounds the core non-negotiables — a
# deterministic proxy for a "long run" (there is no session in a one-shot CLI). Data, not magic.
LONG_RUN_CHECKPOINTS = 3


def load_workflow(path=WORKFLOW):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read())


def _load_optional(path):
    """A spec loaded as data, or `{}` when it is absent/unreadable. The re-grounding preamble (#221)
    reads the authority + git specs; a missing one must degrade the preamble, never crash the primary
    report (unlike the workflow, which is load-bearing and left unguarded)."""
    try:
        with open(path, encoding="utf-8") as handle:
            return render.load_yaml(handle.read()) or {}
    except OSError:
        return {}


def load_authority(path=AUTHORITY):
    return _load_optional(path)


def load_git(path=GIT):
    return _load_optional(path)


def load_interaction(path=INTERACTION):
    """The interaction policy, or `{}` when absent — the re-grounding preamble re-reads it (M17 17.4,
    #280) to re-inject the how-you-communicate posture at each boundary. Optional like authority/git:
    a project without the spec loses the interaction line, never the report."""
    return _load_optional(path)


def load_routing(path=ROUTING):
    """The model/effort routing policy, or `{}` when absent — the preamble re-states the advisory
    routing posture at each boundary (M18 18.2, #297). Optional: a project without the spec loses
    the routing line, never the report."""
    return _load_optional(path)


def _read_text(path):
    """File contents, or None when the path is absent — for the optional --rfc / --roadmap inputs
    the live gate evaluation (#213) reads; a missing input leaves that gate unevaluated, not fatal."""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return None


def state_ids(workflow):
    return [s.get("id") for s in (workflow.get("states") or []) if isinstance(s, dict)]


# Back-compat: the brownfield phase was renamed `refactor` -> `migrate` (ADR-0020, #236), which
# freed `refactor` for the code-quality command (#243). An existing manifest that still records
# `delivery_state.phase: refactor` (or a checkpoint into it) is mapped to the canonical name for
# one minor version, with a deprecation warning at the CLI boundary — so old manifests keep working.
PHASE_ALIASES = {"refactor": "migrate"}


def canonical_phase(phase):
    """Map a deprecated phase alias to its canonical name (`refactor` -> `migrate`, #236); any other
    value (including None) passes through unchanged. Pure."""
    return PHASE_ALIASES.get(phase, phase)


def current_phase(manifest):
    """The manifest's current phase (canonicalized through PHASE_ALIASES); defaults to `init` when
    there is no delivery_state yet (a legacy / freshly-initialized manifest)."""
    ds = manifest.get("delivery_state") if isinstance(manifest, dict) else None
    return canonical_phase(ds.get("phase", "init")) if isinstance(ds, dict) else "init"


def legacy_phase_aliases(manifest):
    """The deprecated phase aliases actually present in a manifest's delivery_state (its `phase` and
    every checkpoint `from`/`to`) — the input to the one-time deprecation warning. Empty when the
    manifest is already canonical. Pure — no I/O."""
    ds = manifest.get("delivery_state") if isinstance(manifest, dict) else None
    if not isinstance(ds, dict):
        return []
    raw = [ds.get("phase")]
    for cp in (ds.get("checkpoints") or []):
        if isinstance(cp, dict):
            raw += [cp.get("from"), cp.get("to")]
    return sorted({p for p in raw if p in PHASE_ALIASES})


def warn_legacy_phases(manifest, out=sys.stderr):
    """Emit a deprecation line for each legacy phase alias the manifest still uses (ADR-0020, #236).
    Thin I/O over legacy_phase_aliases; called at the CLI boundary (report / report_propose)."""
    for alias in legacy_phase_aliases(manifest):
        print(f"DEPRECATION: delivery_state uses phase '{alias}', renamed to "
              f"'{PHASE_ALIASES[alias]}' (ADR-0020, #236); accepted for one minor version — update "
              f"the manifest to '{PHASE_ALIASES[alias]}'.", file=out)


def legal_transitions(workflow, phase):
    """The transitions whose `from` == phase, in declared order (deterministic)."""
    return [t for t in (workflow.get("transitions") or [])
            if isinstance(t, dict) and t.get("from") == phase]


def manifest_domain(manifest):
    """The manifest's target domain (the top-level `domain` scalar); `software` when absent."""
    dom = manifest.get("domain") if isinstance(manifest, dict) else None
    return dom.strip() if isinstance(dom, str) and dom.strip() else "software"


def manifest_rev(manifest):
    """The manifest's optimistic-concurrency counter (#214); 0 when absent (a legacy manifest is
    unlocked). A non-int/negative value reads as 0 here — validate_manifest is what rejects it."""
    rev = manifest.get("manifest_rev") if isinstance(manifest, dict) else None
    return rev if isinstance(rev, int) and not isinstance(rev, bool) and rev >= 0 else 0


def apply_overlay(workflow, domain):
    """The workflow adapted to `domain` (#165): `domain_overlays[<domain>]` merged into a deep
    copy. `insert_states` are appended as human-owner states (no automated role exists for them),
    and each `add_gates` id joins the entry_gates of every transition into a state its REGISTRY
    entry names in `required_for` — the registry, not code, says where a domain gate bites
    (cross-spec lint guarantees every add_gates id has an entry). The merge is recorded under
    `applied_overlay` so the doctor can surface it. A domain with no overlay effects (`software`,
    absent, unknown) returns the SAME object, so the base machine stays byte-identical."""
    overlays = workflow.get("domain_overlays") if isinstance(workflow, dict) else None
    ov = overlays.get(domain) if isinstance(overlays, dict) else None
    if not isinstance(ov, dict) or not (ov.get("insert_states") or ov.get("add_gates")):
        return workflow
    merged = copy.deepcopy(workflow)
    inserted = [s for s in (ov.get("insert_states") or []) if isinstance(s, str)]
    added = [g for g in (ov.get("add_gates") or []) if isinstance(g, str)]
    for sid in inserted:
        merged.setdefault("states", []).append(
            {"id": sid, "role": "human-owner", "produces": [], "overlay": domain})
    required = {g.get("id"): (g.get("required_for") or [])
                for g in (merged.get("gates") or []) if isinstance(g, dict)}
    for gid in added:
        for t in (merged.get("transitions") or []):
            if isinstance(t, dict) and t.get("to") in required.get(gid, []):
                entry = t.setdefault("entry_gates", [])
                if gid not in entry:
                    entry.append(gid)
    merged["applied_overlay"] = {"domain": domain, "insert_states": inserted, "add_gates": added}
    return merged


# --- #221: re-ground the runtime non-negotiables at a phase boundary. -----------------------------
# The insight: over a long run the hard invariants drift out of the effective attention window, so
# re-inject them at each boundary rather than trusting recall (the checkpoint records history; this
# re-grounds the agent). Every derivable FACT is read from a spec — the acting role and human-gate
# status from the workflow, the terminal decider + ownership from authority, one-PR + who-merges from
# git — so the runner holds no hardcoded copy of a rule that could drift from its source of truth.
# English-on-disk is the one invariant with no machine-readable field; it is cited to AGENTS.md §2,
# the same way every file in the tree cites its governing section.

def phase_role(workflow, phase):
    """The role that owns `phase` (workflow states[].role), or None."""
    for s in (workflow.get("states") or []):
        if isinstance(s, dict) and s.get("id") == phase:
            return s.get("role")
    return None


def _role_record(authority, role):
    for r in (authority.get("roles") or []):
        if isinstance(r, dict) and r.get("name") == role:
            return r
    return {}


def terminal_decider(authority):
    """The decider at the end of the escalation ladder — the human who holds the terminal gate."""
    ladder = authority.get("escalation") or []
    last = ladder[-1] if ladder and isinstance(ladder[-1], dict) else {}
    return last.get("decider")


def phase_invariants(workflow, authority, git, phase, transition=None, interaction=None,
                     routing=None):
    """The runtime non-negotiables for being AT `phase` — and, when `transition` is given, for TAKING
    that specific move — each line DERIVED from a spec field, never a hardcoded rule. Pure (no I/O).
    Returns a list of one-line strings suitable for a re-grounding preamble. When `interaction` is
    given (the interaction policy, #280), the preamble also re-reads the how-you-communicate contract
    — the *re-ground* tier of the ADR-0022 enforcement ceiling — so a long run cannot let the
    calibrated-confidence / no-sycophancy / structured-dissent posture drift out of view. When
    `routing` is given (the routing policy, #297), it re-states the advisory model/effort posture —
    check the route, never switch the session model (ADR-0017)."""
    lines = []
    role = phase_role(workflow, phase)
    if role:
        owns = ", ".join(_role_record(authority, role).get("owns") or []) or "—"
        lines.append(f"acting role for '{phase}': {role} (owns: {owns})")
    if transition is not None:
        edge = f"{transition.get('from')} -> {transition.get('to')}"
        if transition.get("human_gate"):
            lines.append(f"this move ({edge}) is human-gated: the owner confirms it before it is recorded")
        else:
            lines.append(f"this move ({edge}) is automatic (mechanical gates) — direction still lands "
                         "via a human-opened PR")
    decider = terminal_decider(authority)
    if decider:
        lines.append(f"the escalation ladder terminates at '{decider}' — the human holds the terminal "
                     "gate; an agent never crosses it")
    commit, prpol = (git.get("commit") or {}), (git.get("pr") or {})
    if commit.get("one_pr_at_a_time"):
        who = prpol.get("merged_by") or prpol.get("opened_by") or "human"
        squash = "squash-" if prpol.get("merge_method") == "squash" else ""
        lines.append(f"one PR at a time; the {who} opens and {squash}merges it (never the agent) — and "
                     "never a push to the default branch")
    if interaction:
        # #280: re-read the interaction contract at the boundary. The confidence tags are pulled from
        # the spec (not hardcoded) so the vocabulary can't rot; the operative rules live in §10.
        levels = "/".join((interaction.get("confidence") or {}).get("levels") or []) or "by evidence"
        lines.append(f"interaction contract: tag load-bearing claims ({levels}) by evidence, no "
                     "courtesy opener, structured dissent — a human decision is layer 1 (AGENTS.md §10)")
    if routing:
        # #297: re-state the advisory routing posture. Tiers are pulled from the spec (not hardcoded)
        # so the vocabulary can't rot; the checkpoint is route_advice.py --check.
        tiers = "/".join(routing.get("tiers") or []) or "by signals"
        lines.append(f"model routing (os/routing, ADR-0017): the route ({tiers}) is advisory — check "
                     "it with route_advice.py --check --current-model <id>; never switch the session "
                     "model, the human holds model authority")
    lines.append("on-disk values are English (AGENTS.md §2); the full contract is AGENTS.md")
    return lines


def checkpoint_count(manifest):
    ds = manifest.get("delivery_state") if isinstance(manifest, dict) else None
    cps = ds.get("checkpoints") if isinstance(ds, dict) else None
    return len(cps) if isinstance(cps, list) else 0


def long_run_reminder(manifest, authority, git, threshold=LONG_RUN_CHECKPOINTS):
    """A compact re-statement of the two most critical non-negotiables, emitted only once a project is
    `threshold` recorded transitions deep — a deterministic proxy for a long run, where drift is
    likelier. Empty below the threshold. Derived from the same specs as phase_invariants. Pure."""
    if checkpoint_count(manifest) < threshold:
        return []
    out = []
    decider = terminal_decider(authority)
    if decider:
        out.append(f"the human ({decider}) still holds the terminal gate — do not cross a human_gate")
    if (git.get("commit") or {}).get("one_pr_at_a_time"):
        out.append("still one PR at a time; the human opens and merges")
    return out


def _emit_regrounding(out, workflow, authority, git, manifest, phase, transition=None, indent="",
                      interaction=None, routing=None):
    """Print the re-grounding preamble (#221): the phase invariants, then the long-run reminder when a
    project is deep enough to warrant it. Thin I/O over the pure builders above. `interaction` (#280)
    adds the how-you-communicate line; `routing` (#297) adds the advisory model/effort line — each
    when its policy is present."""
    invariants = phase_invariants(workflow, authority, git, phase, transition, interaction, routing)
    if invariants:
        print(f"{indent}runtime invariants (re-grounded at this boundary):", file=out)
        for line in invariants:
            print(f"{indent}  - {line}", file=out)
    reminder = long_run_reminder(manifest, authority, git)
    if reminder:
        print(f"{indent}long-run reminder — several transitions deep, the non-negotiables still hold:",
              file=out)
        for line in reminder:
            print(f"{indent}  - {line}", file=out)


def report(manifest_path, out=sys.stdout):
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = render.load_yaml(handle.read())
    warn_legacy_phases(manifest)
    workflow = apply_overlay(load_workflow(), manifest_domain(manifest))
    authority, git, interaction, routing = (load_authority(), load_git(), load_interaction(),
                                            load_routing())
    states = state_ids(workflow)
    phase = current_phase(manifest)
    print(f"current phase: {phase}  (manifest_rev {manifest_rev(manifest)})", file=out)
    if phase not in states:
        print(f"  ERROR: '{phase}' is not a declared workflow state {states}", file=out)
        return 1
    transitions = legal_transitions(workflow, phase)
    if not transitions:
        print("  (terminal phase — no outgoing transitions)", file=out)
    else:
        print("legal next transitions:", file=out)
        for t in transitions:
            gates = ", ".join(t.get("entry_gates") or []) or "—"
            human = "  [human-gated — the owner confirms]" if t.get("human_gate") else ""
            print(f"  -> {t.get('to')}   (gates: {gates}){human}", file=out)
    # #221: re-ground the invariants for the current phase at this boundary (transition-agnostic).
    _emit_regrounding(out, workflow, authority, git, manifest, phase, interaction=interaction,
                      routing=routing)
    return 0


def propose_transition(workflow, from_phase, to_phase):
    """The declared transition from_phase -> to_phase, or None if that move is not legal."""
    for t in legal_transitions(workflow, from_phase):
        if t.get("to") == to_phase:
            return t
    return None


def emit_checkpoint(from_phase, transition, at=None, confirmed_by=None, gate_results=None):
    """The delivery_state checkpoint the agent appends after a CONFIRMED transition: the transition
    edge (`from`/`to`), the declared `gates`, the date `at`, and — for a human-gated move —
    `confirmed_by` (who approved it; a `<owner>` placeholder the human fills in). `gate_results`
    (gate id -> OK/manual) is recorded only when the caller evaluated the gates; wiring that live
    evaluation lands with the audit-trail work (#203), and `checkpoint_chain_problems` already
    validates it when present. The runner returns the checkpoint; the agent writes it and the human
    confirms human-gated moves — the runner itself never writes state (reports, never advances)."""
    cp = {"from": from_phase, "to": transition.get("to"),
          "gates": transition.get("entry_gates") or [],
          "at": at or datetime.date.today().isoformat()}
    if transition.get("human_gate"):
        cp["confirmed_by"] = confirmed_by or "<owner>"
    if gate_results is not None:
        cp["gate_results"] = gate_results
    return cp


_CHECKPOINT_OK_MARKS = ("OK", "manual")

# Gates that are PURE FUNCTIONS of the manifest (no ctx files) — re-runnable at validation time
# to flag divergence (#250). manifest-valid is deliberately absent: its evaluator CALLS
# checkpoint_chain_problems (via validate_manifest), so re-running it here would recurse.
_CTX_FREE_GATES = ("adoption-recorded", "nfr-budgets")


def _gate_results_divergence(manifest, results):
    """Re-run the ctx-free in-process gates recorded in `results` against the CURRENT manifest
    and flag divergence (#250): a mark recorded OK whose gate now FAILs means the manifest
    changed after the transition was recorded — the record is stale, not evidence. Lazy eados
    import: eados imports phase_runner at module level, so importing it here (at call time,
    never during module load) resolves from sys.modules in every eados-driven flow."""
    try:
        import eados  # noqa: E402 — lazy: breaks the phase_runner<->eados import cycle
    except Exception:
        return []      # a partial checkout without the orchestrator CLI — divergence unchecked
    problems = []
    for gate in _CTX_FREE_GATES:
        recorded = str(results.get(gate) or "").strip()
        evaluator = eados.GATE_EVALUATORS.get(gate)
        if recorded not in _CHECKPOINT_OK_MARKS or evaluator is None:
            continue
        mark, detail = evaluator(manifest, {})
        if mark == "FAIL":
            problems.append(f"delivery_state.checkpoints[-1] records gate '{gate}' as "
                            f"'{recorded}' but it now FAILs ({detail}) — the manifest changed "
                            "after the transition was recorded; re-run the propose (#250)")
        elif mark == "skipped" and recorded == "OK":
            # An OK was recorded, so the gate's subject EXISTED at transition time; `skipped`
            # now means it was removed (the adoption block, the domain) — the strongest tamper,
            # flagged exactly like a FAIL (#250).
            problems.append(f"delivery_state.checkpoints[-1] records gate '{gate}' as 'OK' but "
                            f"it is now skipped ({detail}) — what the gate checked was removed "
                            "after the transition was recorded (#250)")
    return problems


def checkpoint_chain_problems(manifest, workflow):
    """Validate `delivery_state.checkpoints` as a legal, contiguous transition chain through the
    (overlay-applied) `workflow`, ending at the current `phase`. This closes the honor-system gap
    (#199): a hallucinating or shortcut-taking agent can no longer set `phase: scaffold` without the
    intervening `init -> design -> plan -> scaffold` checkpoints. Rules:

      * a legacy manifest with no `delivery_state` is exempt (backward-compat, M1-B);
      * `checkpoints` must be a list; each item a `{from, to}` mapping;
      * every `{from, to}` must be a declared transition, and each must continue from the previous
        checkpoint's `to` (the chain is contiguous, rooted at `init`);
      * a human-gated transition (`human_gate: true`) must carry a `confirmed_by:` — mechanical
        evidence a human approved it, not the agent's narrative;
      * a human-gated transition must also RECORD `gate_results` covering its entry gates (#250)
        — an unrecorded gate outcome on a direction-changing move is the honor system;
      * a recorded `gate_results` (when present) must be all `OK`/`manual` — a transition taken over
        a failing gate is illegal;
      * the LAST checkpoint's recorded marks must still hold for the ctx-free gates (#250):
        a mark recorded OK whose gate now FAILs is stale, not evidence (divergence);
      * the last checkpoint's `to` must equal the current `phase`; with no checkpoints the phase
        must still be `init`.

    No writes; the divergence re-run reads the domain profile the gate evaluator needs.
    Returns a list of problem strings (empty == consistent)."""
    ds = manifest.get("delivery_state") if isinstance(manifest, dict) else None
    if not isinstance(ds, dict):
        return []                                # no delivery_state — nothing to enforce (legacy)
    phase = canonical_phase(ds.get("phase", "init"))
    checkpoints = ds.get("checkpoints")
    if checkpoints is None:
        checkpoints = []
    if not isinstance(checkpoints, list):
        return ["delivery_state.checkpoints must be a list of {from, to} transitions"]

    problems, prev_to = [], "init"
    for i, cp in enumerate(checkpoints):
        if not isinstance(cp, dict):
            problems.append(f"delivery_state.checkpoints[{i}] must be a {{from, to}} mapping")
            continue
        frm, to = canonical_phase(cp.get("from")), canonical_phase(cp.get("to"))
        if frm != prev_to:
            problems.append(f"delivery_state.checkpoints[{i}] starts at '{frm}' but the previous "
                            f"state is '{prev_to}' — the checkpoint chain is not contiguous")
        transition = propose_transition(workflow, frm, to)
        if transition is None:
            problems.append(f"delivery_state.checkpoints[{i}] '{frm} -> {to}' is not a legal "
                            "transition in the workflow")
        else:
            if transition.get("human_gate") and not str(cp.get("confirmed_by") or "").strip():
                problems.append(f"delivery_state.checkpoints[{i}] '{frm} -> {to}' is human-gated "
                                "and needs a 'confirmed_by:' entry (who approved the move)")
            results = cp.get("gate_results")
            if transition.get("human_gate"):
                # #250: a direction-changing move must RECORD what its gates said — an absent
                # gate_results block was the honor system (`--propose` evaluates live and emits
                # the marks; recording the checkpoint without them drops the evidence).
                recorded = results if isinstance(results, dict) else {}
                missing = [g for g in (transition.get("entry_gates") or []) if g not in recorded]
                if missing:
                    problems.append(f"delivery_state.checkpoints[{i}] '{frm} -> {to}' is "
                                    "human-gated and must record gate_results for its entry "
                                    f"gates — missing: {', '.join(missing)} (#250)")
            if isinstance(results, dict):
                for gate, mark in results.items():
                    if str(mark).strip() not in _CHECKPOINT_OK_MARKS:
                        problems.append(f"delivery_state.checkpoints[{i}] '{frm} -> {to}' records "
                                        f"gate '{gate}' as {mark!r} — a transition may not be taken "
                                        f"over a gate that is not {' / '.join(_CHECKPOINT_OK_MARKS)}")
        if to is not None:
            prev_to = to
    if checkpoints:
        if prev_to != phase:
            problems.append(f"delivery_state.phase is '{phase}' but the checkpoint chain ends at "
                            f"'{prev_to}' — the current phase must be the last transition's target")
        # #250: divergence — only the LAST checkpoint is re-checked (earlier marks legitimately
        # reflect earlier manifest states), and only when the chain is otherwise clean (one
        # problem class at a time keeps the report actionable).
        if not problems and isinstance(checkpoints[-1], dict):
            results = checkpoints[-1].get("gate_results")
            if isinstance(results, dict):
                problems += _gate_results_divergence(manifest, results)
    elif phase != "init":
        problems.append(f"delivery_state.phase is '{phase}' but there are no checkpoints — a "
                        "non-init phase must record the transitions that reached it (no phase-skip)")
    return problems


def report_propose(manifest_path, to_phase, out=sys.stdout, evaluate=None, ctx=None, expect_rev=None):
    """Report and validate the transition frm -> to_phase, and emit its checkpoint. When an
    `evaluate` callable is supplied (`(gate_ids, manifest, ctx) -> {gate: mark}`, injected so the
    engine stays testable and free of an eados import cycle), the transition's deterministic gates
    are evaluated LIVE and their marks recorded in the checkpoint's `gate_results` (#213) — the
    audit trail becomes the runner's own observation, not a copy of workflow.yaml. A gate that is
    not OK/manual means the move is not ready to record (the same rule checkpoint_chain_problems
    enforces at manifest-valid time); the exit code stays 0 for a LEGAL move (legality, not gate
    satisfaction — `eados.py <phase> --strict` is the fail-closed gate check). `expect_rev` (#214) is
    the optimistic-concurrency guard: pass the rev you last read and the move is REFUSED if the file
    has moved since (another session wrote), so a parallel edit fails loud instead of clobbering."""
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = render.load_yaml(handle.read())
    warn_legacy_phases(manifest)
    rev = manifest_rev(manifest)
    if expect_rev is not None and expect_rev != rev:
        print(f"CONFLICT: manifest_rev is {rev}, but you expected {expect_rev} — another session "
              "changed the manifest since you read it. Re-read it and redo the transition (#214).",
              file=out)
        return 1
    workflow = apply_overlay(load_workflow(), manifest_domain(manifest))
    authority, git, interaction, routing = (load_authority(), load_git(), load_interaction(),
                                            load_routing())
    states = state_ids(workflow)
    frm = current_phase(manifest)
    print(f"proposed transition: {frm} -> {to_phase}  (read at manifest_rev {rev})", file=out)
    if to_phase not in states:
        print(f"  ILLEGAL: '{to_phase}' is not a declared workflow state {states}", file=out)
        return 1
    t = propose_transition(workflow, frm, to_phase)
    if t is None:
        legal = [x.get("to") for x in legal_transitions(workflow, frm)]
        print(f"  ILLEGAL: not a declared transition from '{frm}' (legal: {legal or 'none'})",
              file=out)
        return 1
    entry_gates = t.get("entry_gates") or []
    gates = ", ".join(entry_gates) or "—"
    print(f"  LEGAL — gates to satisfy: {gates}; "
          f"human-gated: {'yes' if t.get('human_gate') else 'no'}", file=out)
    # #221: re-ground the non-negotiables for THIS specific move before it is evaluated/recorded.
    _emit_regrounding(out, workflow, authority, git, manifest, to_phase, transition=t, indent="  ",
                      interaction=interaction, routing=routing)
    gate_results = evaluate(entry_gates, manifest, ctx or {}) if evaluate else None
    if gate_results:
        print("  gate results (live): "
              + ("; ".join(f"{g}={m}" for g, m in gate_results.items()) or "—"), file=out)
    cp = emit_checkpoint(frm, t, gate_results=gate_results)
    print("  emit — append to delivery_state.checkpoints, then set delivery_state.phase:", file=out)
    confirmed = f", confirmed_by: {cp['confirmed_by']}" if "confirmed_by" in cp else ""
    results = ""
    if "gate_results" in cp:
        results = ", gate_results: { " + ", ".join(f"{g}: {m}" for g, m in cp["gate_results"].items()) + " }"
    print(f"    - {{ from: {cp['from']}, to: {cp['to']}, gates: {cp['gates']}, "
          f"at: {cp['at']}{confirmed}{results} }}", file=out)
    print(f"    phase: {to_phase}", file=out)
    print(f"    (top-level) manifest_rev: {rev + 1}   # bump the optimistic-concurrency counter, and "
          f"re-run with --expect-rev {rev} before writing to catch a concurrent edit (#214)",
          file=out)
    if "confirmed_by" in cp:
        print("    (human-gated — replace <owner> in confirmed_by with who approved the move)",
              file=out)
    if gate_results:
        unmet = sorted(f"{g}={m}" for g, m in gate_results.items() if m not in ("OK", "manual"))
        if unmet:
            print(f"  NOT READY — resolve before recording this transition: {', '.join(unmet)} "
                  "(checkpoint_chain_problems rejects a checkpoint whose gate_results are not "
                  "all OK/manual)", file=out)
    return 0


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="EADOS phase runner — report or validate a transition.")
    ap.add_argument("manifest", help="path to a project manifest (project.yaml)")
    ap.add_argument("--propose", metavar="TO",
                    help="validate a proposed transition to phase TO and emit its checkpoint")
    ap.add_argument("--rfc", help="an RFC file to evaluate the rfc-approved gate live (design -> plan)")
    ap.add_argument("--roadmap", help="ROADMAP.md to evaluate roadmap-covers-rfcs live "
                                      "(default: <manifest-dir>/ROADMAP.md)")
    ap.add_argument("--expect-rev", type=int, dest="expect_rev", metavar="N",
                    help="optimistic-concurrency guard (#214): refuse if the manifest's manifest_rev "
                         "is not N (another session changed it since you read it)")
    args = ap.parse_args(argv)
    try:
        if args.propose:
            # Lazy import: eados owns GATE_EVALUATORS (the single source of the deterministic marks);
            # importing it here — not at module top — breaks the render<->phase_runner<->eados cycle.
            import eados  # noqa: E402
            root = os.path.dirname(os.path.abspath(args.manifest))
            roadmap_path = args.roadmap or os.path.join(root, "ROADMAP.md")
            ctx = {"roadmap_text": _read_text(roadmap_path),
                   "rfc_text": _read_text(args.rfc) if args.rfc else None}
            return report_propose(args.manifest, args.propose, evaluate=eados.evaluate_gates,
                                  ctx=ctx, expect_rev=args.expect_rev)
        return report(args.manifest)
    except (OSError, ValueError) as exc:
        print(f"phase-runner: cannot read manifest {args.manifest!r}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
