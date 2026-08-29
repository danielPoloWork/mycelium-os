#!/usr/bin/env python3
"""EADOS model & effort routing advisor (M16 16.2) — the `os/routing` policy as a tool. Given a
unit of work's signals (tracker labels + asserted flags) it recommends a capability tier, an
effort level, and the current model for a host — by the spec's monotonic escalation: start at the
`defaults` floor, every matched rule raises to at least its `min_tier`/`min_effort`, final = max.
It recommends only; the human keeps final model authority (ADR-0017, AGENTS.md §6).

Everything is data-driven: the policy is `orchestrator/os/routing/routing.yaml`; model names come
from its dated `catalog:`, never from this file. The core (`advise`) is pure and fixture-tested;
the spec is loud-rejected on load when it breaks its own `_schema.md` invariants. Only the
optional `--issue N` / `--milestone T` fetches shell out to `gh`, degrading cleanly (clear
message, exit 2) when `gh` is missing, unauthenticated, or offline — like `pr_review.py`.

    python .eados-core/tools/route_advice.py --labels "adr,severity:high" [--flags decision-heavy]
    python .eados-core/tools/route_advice.py --issue 247 [--repo OWNER/REPO] [--json]
    python .eados-core/tools/route_advice.py --milestone "M15 — command surface & governed assistants"
    python .eados-core/tools/route_advice.py --labels "adr" --check --current-model "Opus 4.8"

The `--check` mode (M18 18.2) compares the resolved route against the model the session
self-reports (`--current-model`) and prints ROUTE-OK / ROUTE-MISMATCH — advisory, always exit 0;
it never switches the model (no host lets an agent re-route its own session — ADR-0017).
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render            # noqa: E402  — the dependency-free YAML loader

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound

ROUTING_SPEC = os.path.join(ROOT, "orchestrator", "os", "routing", "routing.yaml")


# --- spec integrity (the _schema.md invariants, loud-rejected) -------------
def spec_problems(spec):
    """Pure referential-integrity check of a parsed routing spec. Returns a list of problem
    strings (empty == every reference resolves). This is the loud enforcement ADR-0017 assigns
    to the evaluator: a policy that parses but points at an unknown tier/effort/flag must fail
    here, not silently misroute."""
    problems = []
    if not isinstance(spec, dict):
        return ["routing spec is not a mapping"]
    tiers = spec.get("tiers") or []
    efforts = spec.get("efforts") or []
    flags = spec.get("flags") if isinstance(spec.get("flags"), dict) else {}
    steps = spec.get("steps") if isinstance(spec.get("steps"), dict) else {}
    if not isinstance(tiers, list) or not tiers:
        problems.append("`tiers` must be a non-empty ordered list")
    if not isinstance(efforts, list) or not efforts:
        problems.append("`efforts` must be a non-empty ordered list")

    defaults = spec.get("defaults") if isinstance(spec.get("defaults"), dict) else {}
    if defaults.get("tier") not in tiers:
        problems.append(f"defaults.tier {defaults.get('tier')!r} is not a `tiers` entry")
    if defaults.get("effort") not in efforts:
        problems.append(f"defaults.effort {defaults.get('effort')!r} is not an `efforts` entry")

    for i, rule in enumerate(spec.get("rules") or []):
        label = f"rules[{i}]"
        if not isinstance(rule, dict):
            problems.append(f"{label} must be a mapping")
            continue
        label = f"rule '{rule.get('id') or i}'"
        if not str(rule.get("id", "")).strip():
            problems.append(f"rules[{i}] has no id")
        when = rule.get("when")
        if not isinstance(when, list) or not when:
            problems.append(f"{label}: `when` must be a non-empty list of signals")
            when = []
        for sig in when:
            problems += _signal_problems(str(sig), flags, where=label, steps=steps)
        if rule.get("min_tier") is None and rule.get("min_effort") is None:
            problems.append(f"{label}: declares neither min_tier nor min_effort — it can raise nothing")
        if rule.get("min_tier") is not None and rule.get("min_tier") not in tiers:
            problems.append(f"{label}: min_tier {rule.get('min_tier')!r} is not a `tiers` entry")
        if rule.get("min_effort") is not None and rule.get("min_effort") not in efforts:
            problems.append(f"{label}: min_effort {rule.get('min_effort')!r} is not an `efforts` entry")

    catalog = spec.get("catalog") if isinstance(spec.get("catalog"), dict) else {}
    hosts = catalog.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        problems.append("`catalog.hosts` must be a non-empty list")
        hosts = []
    if not str(catalog.get("as_of", "")).strip():
        problems.append("`catalog.as_of` is missing — the dated catalog is the review cue")
    # --- schema v2 (ADR-0024): providers describe capability, hosts declare reach ---
    provider_ids = set()
    for i, p in enumerate(catalog.get("providers") or []):
        if not isinstance(p, dict) or not str(p.get("id", "")).strip():
            problems.append(f"catalog.providers[{i}] needs an `id`")
            continue
        pid = p["id"]
        if pid in provider_ids:
            problems.append(f"catalog provider '{pid}' is declared twice")
        provider_ids.add(pid)
        models = p.get("models")
        if models is None:
            models = []
        if not isinstance(models, list):
            problems.append(f"provider '{pid}': `models` must be a list (use [] when none are "
                            "catalogued)")
            continue
        for j, m in enumerate(models):
            label = f"provider '{pid}' models[{j}]"
            if not isinstance(m, dict) or not str(m.get("id", "")).strip():
                problems.append(f"{label} needs an `id`")
                continue
            label = f"provider '{pid}' model '{m['id']}'"
            assessed = bool(m.get("assessed"))
            meets = m.get("meets_tier")
            if assessed:
                # An assessed model MUST say what it clears; an unassessed one must NOT claim it.
                if meets is None:
                    problems.append(f"{label}: assessed but declares no `meets_tier`")
                elif meets not in tiers:
                    problems.append(f"{label}: meets_tier {meets!r} is not a `tiers` entry")
            elif meets is not None:
                problems.append(f"{label}: not assessed, so it must not claim `meets_tier` "
                                f"{meets!r} — an unverified capability claim is what #326 was")
            if m.get("max_effort") is not None and m["max_effort"] not in efforts:
                problems.append(f"{label}: max_effort {m['max_effort']!r} is not an `efforts` entry")

    if not catalog.get("providers"):
        problems.append("`catalog.providers` must be a non-empty list (schema v2)")

    seen_hosts = set()
    for h in hosts:
        if not isinstance(h, dict) or not str(h.get("id", "")).strip():
            problems.append("every catalog host entry needs an `id`")
            continue
        hid = h["id"]
        if hid in seen_hosts:
            problems.append(f"catalog host '{hid}' is declared twice")
        seen_hosts.add(hid)
        reach = h.get("providers")
        if not isinstance(reach, list) or not reach:
            problems.append(f"catalog host '{hid}': `providers` must be a non-empty list of "
                            "provider ids — a host that reaches nothing can route nothing")
            reach = []
        for pid in reach:
            if pid not in provider_ids:
                problems.append(f"catalog host '{hid}' reaches unknown provider '{pid}'")
        aliases = h.get("effort_aliases") if isinstance(h.get("effort_aliases"), dict) else {}
        for alias, effort in aliases.items():
            if effort not in efforts:
                problems.append(f"catalog host '{hid}' alias '{alias}' -> {effort!r} is not an "
                                "`efforts` entry")

    # `protected` and `selection` are required structure in schema v2: they carry the cost
    # invariant, and absent they fail OPEN — an undeclared `selection` silently disables the cost
    # preference, and an undeclared `protected` silently drops the guarantee it encodes.
    if spec.get("protected") is None:
        problems.append("`protected` is missing — schema v2 requires the signals whose floor "
                        "nothing may reduce, declared as data (use [] to mean none)")
    for sig in spec.get("protected") or []:
        problems += _signal_problems(str(sig), flags, where="protected", steps=steps)
    if not isinstance(spec.get("selection"), dict):
        problems.append("`selection` is missing — schema v2 requires how selection chooses among "
                        "models that already clear the floor")
    sel = spec.get("selection") if isinstance(spec.get("selection"), dict) else {}
    for pref in sel.get("prefer") or []:
        if pref not in ("lowest_cost", "lowest_latency"):
            problems.append(f"selection.prefer '{pref}' is not a known criterion")

    ex = spec.get("examples") if isinstance(spec.get("examples"), dict) else {}
    for verdict in (ex.get("verdicts") or []):
        if verdict not in tiers:
            problems.append(f"examples verdict '{verdict}' is not a `tiers` entry — the decision "
                            "surface must speak the policy's own vocabulary")
    return problems


def _signal_problems(sig, flags, where, steps=None):
    """A signal is `label:<tracker label>`, `flag:<declared flags key>` or `step:<declared steps
    key>`. Unknown labels are fine (the tracker owns that vocabulary); an unknown FLAG or STEP is
    a typo the spec must catch — those vocabularies are closed and declared here."""
    steps = steps if isinstance(steps, dict) else {}
    if sig.startswith("label:"):
        return [] if sig[len("label:"):].strip() else [f"{where}: empty label signal"]
    for prefix, vocab, key in (("flag:", flags, "flags"), ("step:", steps, "steps")):
        if sig.startswith(prefix):
            sid = sig[len(prefix):].strip()
            if not sid:
                return [f"{where}: empty {prefix.rstrip(':')} signal"]
            if sid not in vocab:
                return [f"{where}: {prefix.rstrip(':')} signal '{sid}' is not declared "
                        f"under `{key}:`"]
            return []
    return [f"{where}: signal {sig!r} is not 'label:<name>', 'flag:<id>' or 'step:<id>'"]


def load_routing(path=ROUTING_SPEC):
    """Load + loud-reject: a spec that breaks its own invariants never reaches the core."""
    with open(path, encoding="utf-8") as handle:
        spec = render.load_yaml(handle.read())
    problems = spec_problems(spec)
    if problems:
        raise ValueError("routing spec invalid — " + "; ".join(problems))
    return spec


# --- the pure core ---------------------------------------------------------
def signals_for(labels=(), flags=(), spec=None, step=None):
    """Build the signal set from tracker label names, asserted flag ids, and an optional STEP
    within the unit of work (19.7). An asserted flag or step the spec does not declare is a typo,
    rejected loudly (same posture as spec_problems)."""
    known = (spec.get("flags") if isinstance(spec, dict) and isinstance(spec.get("flags"), dict)
             else {})
    known_steps = (spec.get("steps") if isinstance(spec, dict) and isinstance(spec.get("steps"), dict)
                   else {})
    sigs = ["label:" + str(l).strip() for l in labels if str(l).strip()]
    for f in flags:
        fid = str(f).strip()
        if not fid:
            continue
        if spec is not None and fid not in known:
            raise ValueError(f"unknown flag '{fid}' — declared flags: {', '.join(sorted(known)) or 'none'}")
        sigs.append("flag:" + fid)
    sid = str(step).strip() if step else ""
    if sid:
        if spec is not None and sid not in known_steps:
            raise ValueError(f"unknown step '{sid}' — declared steps: "
                             f"{', '.join(sorted(known_steps)) or 'none'}")
        sigs.append("step:" + sid)
    return sigs


def advise(signals, spec, host=None):
    """Pure evaluator: monotonic escalation over the matched rules. `signals` is an iterable of
    'label:<name>' / 'flag:<id>' strings. Returns {tier, effort, model, host, matched[], floor}.
    Deterministic and order-independent: final = max(defaults, matched mins) in spec order."""
    tier_rank = {t: i for i, t in enumerate(spec["tiers"])}
    effort_rank = {e: i for i, e in enumerate(spec["efforts"])}
    have = {str(s) for s in signals}

    tier = spec["defaults"]["tier"]
    effort = spec["defaults"]["effort"]
    matched = []
    for rule in spec.get("rules") or []:
        if not all(str(sig) in have for sig in (rule.get("when") or [])):
            continue
        matched.append({"id": rule.get("id"), "why": rule.get("why")})
        mt, me = rule.get("min_tier"), rule.get("min_effort")
        if mt is not None and tier_rank[mt] > tier_rank[tier]:
            tier = mt
        if me is not None and effort_rank[me] > effort_rank[effort]:
            effort = me

    # --- phase 2: SELECTION — the cheapest reachable model that CLEARS the floor -------------
    # The floor above is quality, and nothing below decides it. Selection only ever chooses AMONG
    # models that already clear it, so cost can never lower the floor (ADR-0024 D3). There is
    # deliberately no branch here that can return a model below `tier`.
    entry = _host_entry(spec, host)
    ranked = candidates_for(spec, tier, effort, host)
    best = ranked[0] if ranked else None
    protected = [str(s) for s in (spec.get("protected") or []) if str(s) in have]

    unresolved = None
    if best is None and entry is None:
        unresolved = ("the host is unresolved, so no model name can be given — name one with "
                      "--host or `routing.host` in the manifest. The tier and effort above are "
                      "vendor-neutral and stand on their own.")
    elif best is None:
        reachable = ", ".join(entry.get("providers") or []) or "nothing"
        unresolved = (f"no reachable model clears {tier}/{effort} on host '{entry['id']}' "
                      f"(providers: {reachable}) — catalogue and assess one, or run this work on a "
                      "host that reaches one. The tier and effort above still stand.")

    return {
        "tier": tier,
        "effort": effort,
        # None when nothing reachable clears the floor. The tier/effort advice is vendor-neutral
        # and still stands; only the name is unresolved, and `unresolved_reason` says why. Never a
        # cheaper substitute — that would be the floor quietly lowered.
        "model": best["model"] if best else None,
        "provider": best["provider"] if best else None,
        "relative_cost": best["relative_cost"] if best else None,
        "alternatives": ranked[1:],
        "unresolved_reason": unresolved,
        "protected": protected,
        "host": entry["id"] if entry else None,
        "catalog_as_of": (spec.get("catalog") or {}).get("as_of"),
        "matched": matched,
        "floor": dict(spec["defaults"]),
        "boundary": "advisory only — the human keeps final model authority (ADR-0017)",
    }


def format_selection(advice, spec):
    """`--explain`: why the chosen model won, and what the runners-up would have cost. Selection is
    phase 2 only — every model listed here already clears the floor, so this shows a COST choice,
    never a quality one."""
    prefer = (spec.get("selection") or {}).get("prefer") or []
    alts = advice.get("alternatives") or []
    out = [f"  selection: among models that already clear {advice['tier']}/{advice['effort']} "
           f"(prefer: {', '.join(prefer) or 'declaration order'})"]
    if advice.get("model"):
        costed = advice.get("relative_cost")
        basis = (f"cheapest at cost {costed}" if costed is not None
                 else "least capable that still clears the floor (no cost recorded, so the tier "
                      "ladder decides)")
        out.append(f"    chosen: {advice['model']} ({advice['provider']}, "
                   f"clears {advice['tier']}) — {basis}")
    for a in alts:
        cost = f"cost {a['relative_cost']}" if a.get("relative_cost") is not None else "cost unrecorded"
        out.append(f"    also cleared: {a['model']} ({a['provider']}, {a['meets_tier']}, {cost})")
    if not alts:
        out.append("    no runner-up — it was the only reachable model clearing the floor"
                   if advice.get("model") else "    no candidate cleared the floor")
    return "\n".join(out)


def _host_entry(spec, host=None):
    """The catalog entry for `host`, or None when the host is UNRESOLVED.

    There is deliberately no default (#325, ADR-0024 D4). Returning the first catalog entry for an
    unknown caller is how every non-Claude host silently received Anthropic model names; the
    absence of that fallback is asserted by a test, because it is exactly the kind of convenience
    that gets helpfully re-added. A host that was *named* but does not exist is a different case —
    that is a typo or a stale config, and it raises."""
    hosts = (spec.get("catalog") or {}).get("hosts") or []
    if host is None:
        return None
    for h in hosts:
        if h.get("id") == host:
            return h
    known = ", ".join(str(h.get("id")) for h in hosts)
    raise ValueError(f"unknown host '{host}' — catalog hosts: {known}")


# --- host detection (19.4 / ADR-0024 D4) -----------------------------------------------------
# The OS works out which RUNTIME it is in from the environment. It never asks the agent which
# MODEL it is: models misdescribe their own identity, most confidently right after a version
# change — exactly when routing most needs to be right — and a route computed from a hallucinated
# self-description is worse than no route, because it is wrong AND it looks authoritative.
#
# Marker vocabulary (data, so a new host is a catalog edit):
#   - env: NAME              presence of an environment variable
#   - env: NAME + matches: R presence AND its value matching regex R

def _marker_hit(rule, environ):
    if not isinstance(rule, dict):
        return None
    name = rule.get("env")
    if not name or name not in environ:
        return None
    pattern = rule.get("matches")
    if pattern is None:
        return f"env {name} is set"
    if re.search(str(pattern), str(environ.get(name) or "")):
        return f"env {name} matches /{pattern}/"
    return None


def detect_host(spec, environ=None):
    """`(host_id, evidence)` from environment markers.

    Returns `(None, reason)` when nothing matches, and — importantly — also when MORE THAN ONE
    host matches. Ambiguity is not resolved by guessing: two runtimes claiming the same session is
    a state the OS cannot honestly settle, so it says so and lets the explicit rungs decide."""
    environ = os.environ if environ is None else environ
    hits = []
    for h in (spec.get("catalog") or {}).get("hosts") or []:
        if not isinstance(h, dict):
            continue
        found = [ev for rule in (h.get("detect") or []) if (ev := _marker_hit(rule, environ))]
        if found:
            hits.append((h.get("id"), found))
    if not hits:
        return None, "no host declared a marker present in this environment"
    if len(hits) > 1:
        names = ", ".join(str(h) for h, _ in hits)
        return None, (f"ambiguous — {names} all match this environment; name one explicitly "
                      "(--host, or `routing.host` in the manifest)")
    host, evidence = hits[0]
    return host, "; ".join(evidence)


MANIFEST = os.path.join(os.path.dirname(ROOT), "orchestrator", "project.yaml")


def manifest_routing_host(path=None):
    """`routing.host` from the project manifest, or None. Additive: a manifest without the block
    (or without a manifest at all) is entirely legal and simply contributes nothing to the ladder."""
    path = MANIFEST if path is None else path
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = render.load_yaml(handle.read())
    except (OSError, ValueError):
        return None                      # a broken manifest is another gate's problem, not ours
    routing = data.get("routing") if isinstance(data, dict) else None
    host = routing.get("host") if isinstance(routing, dict) else None
    return str(host).strip() or None if host else None


def resolve_host(spec, explicit=None, manifest_host=None, environ=None):
    """The precedence ladder (ADR-0024 D4). Returns `{host, source, evidence}` where `host` is None
    when unresolved — never a default.

      1. explicit      a `--host` flag: a direct human instruction
      2. manifest      `routing.host`: a recorded human declaration
      3. evidence      environment markers the host declares as data
      4. unresolved    stated, with the reason

    Rung 4 costs less than it looks: tiers and efforts are vendor-neutral, so an unresolved host
    loses the model NAME and nothing else — the recommendation stays fully actionable."""
    if explicit:
        _host_entry(spec, explicit)          # raises on a named host that does not exist
        return {"host": explicit, "source": "explicit", "evidence": "--host was given"}
    if manifest_host:
        _host_entry(spec, manifest_host)
        return {"host": manifest_host, "source": "manifest",
                "evidence": "`routing.host` in the manifest"}
    host, why = detect_host(spec, environ)
    if host:
        return {"host": host, "source": "evidence", "evidence": why}
    return {"host": None, "source": "unresolved", "evidence": why}


def candidates_for(spec, floor_tier, floor_effort, host=None):
    """Every model that CLEARS the floor and is reachable from `host`, best-first (ADR-0024 D2
    phase 2). A candidate is a dict: {model, model_id, provider, meets_tier, relative_cost}.

    Admission — a model is a candidate only when all of these hold:
      * it belongs to a provider the host declares it reaches;
      * it is `assessed` (an unverified capability claim never routes work — #326);
      * its `meets_tier` is at or ABOVE the floor tier (meets-or-exceeds, not exact match);
      * its `max_effort`, where declared, admits the floor effort. An absent ceiling is
        unrecorded, not unlimited — it is treated as no constraint, which is how every other
        optional field in this catalog reads.

    Ordering — `selection.prefer`. `lowest_cost` applies only when EVERY candidate records a
    `relative_cost`: partial cost data cannot produce a fair ranking, and a model with a recorded
    cost of 100 must not outrank one whose cost is simply unknown. With cost unusable, the fallback
    is the tier ladder itself, which `tiers` declares as cheapest -> most capable — so the answer is
    the LEAST capable model that still clears the floor. That is "minimum sufficient model"
    computed rather than asserted (ADR-0024 D3). Remaining ties break on the host's provider order
    then declaration order, so the result never depends on a missing figure.
    """
    tier_rank = {t: i for i, t in enumerate(spec.get("tiers") or [])}
    effort_rank = {e: i for i, e in enumerate(spec.get("efforts") or [])}
    entry = _host_entry(spec, host)
    if entry is None:
        return []          # unresolved host reaches nothing — never fall back to a default host
    by_id = {p.get("id"): p for p in (spec.get("catalog") or {}).get("providers") or []
             if isinstance(p, dict)}

    rows = []
    for order, pid in enumerate(entry.get("providers") or []):
        for decl, m in enumerate((by_id.get(pid) or {}).get("models") or []):
            if not isinstance(m, dict) or not m.get("assessed"):
                continue
            meets = m.get("meets_tier")
            if meets not in tier_rank or tier_rank[meets] < tier_rank.get(floor_tier, 0):
                continue
            ceiling = m.get("max_effort")
            if ceiling in effort_rank and effort_rank[ceiling] < effort_rank.get(floor_effort, 0):
                continue
            rows.append({"model": str(m.get("name") or m.get("id")),
                         "model_id": m.get("id"), "provider": pid, "meets_tier": meets,
                         "relative_cost": m.get("relative_cost"),
                         "_order": order, "_decl": decl})

    prefer = (spec.get("selection") or {}).get("prefer") or []
    costed = bool(rows) and all(r["relative_cost"] is not None for r in rows)
    if "lowest_cost" in prefer and costed:
        rows.sort(key=lambda r: (r["relative_cost"], tier_rank[r["meets_tier"]],
                                 r["_order"], r["_decl"]))
    else:
        rows.sort(key=lambda r: (tier_rank[r["meets_tier"]], r["_order"], r["_decl"]))
    for r in rows:
        r.pop("_order", None)
        r.pop("_decl", None)
    return rows


def models_by_tier(spec, host=None):
    """`{tier: model name}` — the model each tier resolves to for `host`, exact-tier floor.

    A thin view over `candidates_for` kept for the surfaces that show a tier→model legend (the
    rendered ROADMAP, `tier_of_model`). A tier with no reachable assessed candidate is absent,
    which is the honest answer: the tier advice stands, the name does not.
    """
    out = {}
    for tier in spec.get("tiers") or []:
        rows = candidates_for(spec, tier, (spec.get("defaults") or {}).get("effort"), host)
        exact = [r for r in rows if r["meets_tier"] == tier]
        if exact:
            out[tier] = exact[0]["model"]
    return out


def normalize_effort(word, spec, host=None):
    """Map a host-vocabulary effort word (e.g. Claude Code's 'ultracode') to the OS scale via the
    host's `effort_aliases`; an OS-scale word passes through. Unknown words are rejected loudly."""
    word = str(word).strip()
    if word in (spec.get("efforts") or []):
        return word
    aliases = (_host_entry(spec, host) or {}).get("effort_aliases") or {}
    if word in aliases:
        return aliases[word]
    raise ValueError(f"unknown effort '{word}' — OS scale: {', '.join(spec.get('efforts') or [])}"
                     + (f"; host aliases: {', '.join(sorted(aliases))}" if aliases else ""))


def format_advice(advice, heading=None, host_info=None):
    """One human-readable advice block (the line the triage/status surfaces print)."""
    out = []
    if heading:
        out.append(heading)
    # An unresolved model is stated, never printed as a bare None: the tier/effort half of the
    # advice is vendor-neutral and fully actionable on its own (ADR-0024 D4).
    model = advice["model"] or "<unresolved>"
    cost = advice.get("relative_cost")
    provider = f", {advice['provider']}" if advice.get("provider") else ""
    cost_note = f", cost {cost}" if cost is not None else ""
    out.append(f"  route: tier={advice['tier']}  effort={advice['effort']}  "
               f"-> {model} (host: {advice['host'] or 'unresolved'}{provider}{cost_note}, "
               f"catalog as of {advice['catalog_as_of']})")
    if host_info:
        # State WHAT decided the host, not just which one — an inferred answer whose basis is
        # invisible is indistinguishable from a guess (ADR-0024 D4).
        out.append(f"    host {host_info['source']}: {host_info['evidence']}")
    if advice.get("unresolved_reason"):
        out.append(f"    unresolved: {advice['unresolved_reason']}")
    if advice.get("protected"):
        out.append(f"    protected ({', '.join(advice['protected'])}) — this floor may not be "
                   "lowered to save cost")
    if advice["matched"]:
        for m in advice["matched"]:
            out.append(f"    matched {m['id']}: {m['why']}")
    else:
        out.append(f"    no rule matched — the floor applies "
                   f"(tier={advice['floor']['tier']}, effort={advice['floor']['effort']})")
    out.append(f"  {advice['boundary']}")
    return "\n".join(out)


# --- the route checkpoint (M18 18.2, #297) --------------------------------
# Compare a resolved route against the model the session self-reports it is running on. The
# session model is NOT introspectable by any host's agent, so the tool trusts its
# `--current-model` argument (stated in the output). Effort is likewise unobservable — the
# checkpoint verifies the model->tier half only and says so. Advisory always: the caller exits 0
# regardless of the verdict (ADR-0017 — a blocking model gate would claim authority the OS lacks).
def _norm_model(name):
    """Lowercase, alphanumerics only — so 'Opus 4.8' / 'claude-opus-4-8' / 'opus-4.8' compare equal."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def tier_of_model(model, spec, host=None):
    """The catalog tier whose model matches `model` for `host`, or `None` when no *single* tier
    matches. Normalized match with containment tolerance; zero or ambiguous (>1) hits return `None`
    — the honest 'cannot compare' signal the checkpoint degrades on rather than guessing."""
    target = _norm_model(model)
    if not target:
        return None
    models = models_by_tier(spec, host)
    hits = [tier for tier, name in models.items()
            if (n := _norm_model(name)) and (n == target or n in target or target in n)]
    return hits[0] if len(hits) == 1 else None


def check_route(advice, current_model, spec, host=None):
    """Pure: compare a resolved route (`advise(...)`) against the session's self-reported model.
    Returns {status, routed_tier, routed_effort, routed_model, current_model, current_tier,
    direction}. `status` is 'ok' (tiers match), 'mismatch' (differ — `direction` is 'below'/'above'
    the routed tier), or 'unknown-model' (current model not in the dated catalog → cannot compare).
    Effort is never compared: no host exposes the session's effort, so only the model->tier half is
    verified (the output states this)."""
    tier_rank = {t: i for i, t in enumerate(spec["tiers"])}
    routed_tier = advice["tier"]
    current_tier = tier_of_model(current_model, spec, host)
    if current_tier is None:
        status, direction = "unknown-model", None
    elif current_tier == routed_tier:
        status, direction = "ok", None
    else:
        status = "mismatch"
        direction = "below" if tier_rank[current_tier] < tier_rank[routed_tier] else "above"
    return {"status": status, "routed_tier": routed_tier, "routed_effort": advice["effort"],
            "routed_model": advice["model"], "current_model": str(current_model),
            "current_tier": current_tier, "direction": direction}


def format_check(check, host=None, heading=None):
    """The human-readable checkpoint block. Advisory always — the caller exits 0 whatever the verdict."""
    routed = f"{check['routed_tier']}/{check['routed_effort']} (-> {check['routed_model']})"
    out = [heading] if heading else []
    if check["status"] == "ok":
        out.append(f"ROUTE-OK — routed {routed}; session model '{check['current_model']}' is the "
                   f"{check['routed_tier']} tier. Match.")
    elif check["status"] == "mismatch":
        out.append(f"ROUTE-MISMATCH — routed {routed}; session '{check['current_model']}' is the "
                   f"{check['current_tier']} tier ({check['direction']} the route). Switch with your "
                   "host's model control, or proceed to accept the mismatch and record it: "
                   f"record_run.py --route-mismatch "
                   f"\"{check['routed_tier']}/{check['routed_effort']}={check['current_tier']}\".")
    else:  # unknown-model
        out.append(f"ROUTE-CHECK — routed {routed}; session model '{check['current_model']}' is not "
                   f"in the dated catalog (host: {host or 'default'}) — cannot compare tiers (advisory).")
    out.append("  effort is recommended, not verifiable (no host exposes the session effort); only "
               "the model half is checked. Advisory — the human keeps final model authority (ADR-0017).")
    return "\n".join(out)


# --- the thin `gh` shell (best-effort; degrades cleanly) ------------------
def _gh_json(args):
    import json
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh {' '.join(args)}` timed out after {GH_TIMEOUT}s — the network "
                           "stalled, the API is rate-limiting, or it is waiting on an auth prompt "
                           "that will never be answered")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh {' '.join(args)}` failed (authenticated? online?): "
                           f"{(proc.stderr or proc.stdout or '').strip()}")
    try:
        return json.loads(proc.stdout or "null")
    except ValueError as exc:
        raise RuntimeError(f"could not parse `gh` JSON output: {exc}")


def fetch_issue(number, repo=None):
    """{number, title, labels[]} for one issue. Raises RuntimeError when gh is unavailable."""
    args = ["issue", "view", str(number), "--json", "number,title,labels"]
    if repo:
        args += ["--repo", repo]
    data = _gh_json(args) or {}
    return {"number": data.get("number"), "title": data.get("title") or "",
            "labels": [l.get("name") for l in (data.get("labels") or []) if isinstance(l, dict)]}


def fetch_milestone_issues(milestone, repo=None):
    """Open issues of a milestone (by title), oldest first — the batch surface 16.3 prints."""
    args = ["issue", "list", "--state", "open", "--milestone", milestone,
            "--json", "number,title,labels", "--limit", "200"]
    if repo:
        args += ["--repo", repo]
    items = _gh_json(args) or []
    return sorted(({"number": it.get("number"), "title": it.get("title") or "",
                    "labels": [l.get("name") for l in (it.get("labels") or [])
                               if isinstance(l, dict)]}
                   for it in items if isinstance(it, dict)),
                  key=lambda it: it["number"] or 0)


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Recommend a model tier + effort for a unit of work "
                                             "(advisory only — os/routing policy, ADR-0017).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--labels", help="comma-separated tracker labels (offline mode)")
    src.add_argument("--issue", type=int, help="fetch one issue's labels via gh")
    src.add_argument("--milestone", help="batch: one advice line per open issue of this milestone")
    ap.add_argument("--flags", default="", help="comma-separated asserted flags "
                                                "(e.g. sets-pattern,decision-heavy)")
    ap.add_argument("--repo", help="OWNER/REPO (default: the repo gh infers)")
    ap.add_argument("--step", default=None,
                    help="the step within the unit of work (design|implement|test|review|optimize)"
                         " — steps only ever RAISE a route, never lower it")
    ap.add_argument("--host", default=None, help="catalog host (default: the first catalog entry)")
    ap.add_argument("--json", action="store_true", help="emit structured advice as JSON")
    ap.add_argument("--explain", action="store_true",
                    help="show why the chosen model won and what the runners-up would have cost")
    ap.add_argument("--require-model", action="store_true",
                    help="exit non-zero when no reachable model clears the floor (for automation "
                         "that needs a name; the default reports it and still exits 0, because the "
                         "tier/effort advice is valid on its own)")
    ap.add_argument("--check", action="store_true",
                    help="compare the resolved route against the session model (--current-model); "
                         "prints ROUTE-OK / ROUTE-MISMATCH, advisory — always exits 0")
    ap.add_argument("--current-model",
                    help="the model the session is running on, self-reported (required with --check)")
    args = ap.parse_args(argv)

    if args.check and args.milestone is not None:
        print("route-advice: --check compares one session model to one unit of work — use --labels "
              "or --issue, not --milestone", file=sys.stderr)
        return 2
    if args.check and not args.current_model:
        print("route-advice: --check requires --current-model <id>", file=sys.stderr)
        return 2

    try:
        spec = load_routing()
    except (OSError, ValueError) as exc:
        print(f"route-advice: ERROR — {exc}", file=sys.stderr)
        return 1
    flags = [f for f in (args.flags or "").split(",") if f.strip()]

    # 19.4: the precedence ladder replaces the silent `hosts[0]` default. An unresolved host is
    # reported, never guessed — the tier/effort advice is vendor-neutral and stands regardless.
    try:
        resolved = resolve_host(spec, explicit=args.host, manifest_host=manifest_routing_host())
    except ValueError as exc:
        print(f"route-advice: ERROR — {exc}", file=sys.stderr)
        return 1
    host = resolved["host"]

    try:
        if args.milestone is not None:
            if flags:
                print("route-advice: note — flags apply to every issue in the batch; per-issue "
                      "flags may raise individual routes further", file=sys.stderr)
            issues = fetch_milestone_issues(args.milestone, repo=args.repo)
            batch = [dict(advise(signals_for(it["labels"], flags, spec, step=args.step), spec, host=host),
                          issue=it["number"], title=it["title"]) for it in issues]
            if args.json:
                print(json.dumps({"milestone": args.milestone, "advice": batch}, indent=2))
            else:
                if not batch:
                    print(f"route-advice: no open issues in milestone '{args.milestone}'")
                for adv in batch:
                    print(f"#{adv['issue']} -> {adv['tier']}/{adv['effort']} ({adv['model']})  "
                          f"{adv['title']}")
                if batch:
                    print(f"advisory only — the human keeps final model authority (ADR-0017); "
                          f"asserted flags (sets-pattern, decision-heavy) may raise a route")
            return 0
        if args.issue is not None:
            it = fetch_issue(args.issue, repo=args.repo)
            advice = advise(signals_for(it["labels"], flags, spec, step=args.step), spec, host=host)
            heading = f"#{it['number']}  {it['title']}"
        else:
            labels = [l for l in args.labels.split(",") if l.strip()]
            advice = advise(signals_for(labels, flags, spec, step=args.step), spec, host=host)
            heading = f"labels: {', '.join(l.strip() for l in labels) or 'none'}" \
                      + (f"  flags: {', '.join(f.strip() for f in flags)}" if flags else "")
    except RuntimeError as exc:
        print(f"route-advice: SKIP — {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"route-advice: ERROR — {exc}", file=sys.stderr)
        return 1
    if args.check:
        # #297: advisory checkpoint — compare the route to the session model, always exit 0.
        check = check_route(advice, args.current_model, spec, host=host)
        print(json.dumps(check, indent=2) if args.json
              else format_check(check, host=host, heading=heading))
        return 0
    if args.json:
        print(json.dumps(advice, indent=2))
    else:
        print(format_advice(advice, heading=heading, host_info=resolved))
        if args.explain:
            print(format_selection(advice, spec))
    # An unresolved model does NOT fail by default: the tier/effort half of the advice is
    # vendor-neutral and fully valid on its own (ADR-0024 D4), and the reason is printed. Automation
    # that genuinely needs a name asks for it explicitly.
    if args.require_model and not advice.get("model"):
        print(f"route-advice: ERROR — {advice.get('unresolved_reason')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
