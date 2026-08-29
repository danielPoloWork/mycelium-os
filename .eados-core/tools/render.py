#!/usr/bin/env python3
"""Deterministic template renderer for EADOS (the Mustache subset of placeholders.md).

Dependency-free (Python 3 standard library only). Turns a confirmed project manifest into a
rendered repository, replacing the "careful manual pass" with a reproducible one:

    python tools/render.py orchestrator/project.yaml --in-place   # or: --out <dir-outside-eados>

It implements exactly the substitution grammar the dictionary documents:
  - {{SCALAR}}                       a manifest-derived value
  - {{#IF_FLAG}}...{{/IF_FLAG}}      render when the flag is truthy
  - {{^IF_FLAG}}...{{/IF_FLAG}}      render when the flag is falsy
  - {{#EACH_LIST}}...{{/EACH_LIST}}  repeat per item; {{.}} is the scalar item, {{field}} a field
GitHub Actions ${{ ... }} expressions are left untouched. An unresolved {{UPPER}} placeholder
is a hard error (the render aborts and lists them), per placeholders.md rendering rule 1.

The YAML loader lives in the sibling `yamlmini.py` (#166) — extracted so the parser under
every gate cannot be perturbed by renderer changes. `render.load_yaml` stays a re-export, so
every existing caller works unchanged.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yamlmini import load_yaml  # noqa: E402,F401  — re-exported for every render.load_yaml caller
import sandbox  # noqa: E402  — the ONE write-containment path, shared with the migrate phase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")

SECTION_RE = re.compile(r"\{\{([#^])([A-Z][A-Z0-9_]*)\}\}(.*?)\{\{/\2\}\}", re.DOTALL)
VAR_RE = re.compile(r"(?<!\$)\{\{\s*([^{}]+?)\s*\}\}")
UPPER_RE = re.compile(r"[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# Manifest -> render context (scalars, boolean flags, list sections).
# ---------------------------------------------------------------------------
def _map(d, key):
    """A known section/sub-mapping must be a mapping; anything else degrades to {} so
    build_context never crashes on a mis-typed manifest (validate_manifest reports it)."""
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, dict) else {}


# ---------------------------------------------------------------------------
# Advisory model/effort routing surface (#306, ADR-0023) — template parity with os/routing.
# The generated ROADMAP carries a routing legend plus a per-item advisory route; both derive
# from orchestrator/os/routing/routing.yaml through route_advice's loud-rejecting loader and
# only-raise evaluator, so the policy has exactly one implementation and the templates carry
# tiers, never model names (ADR-0017 — names live only in the dated catalog).
# ---------------------------------------------------------------------------
_ITEM_KEYS = {"text", "signals"}   # the {text, signals[]} object form of a roadmap item


def _load_routing():
    """The parsed os/routing spec via route_advice's loud-rejecting loader. Imported lazily —
    route_advice imports this module for load_yaml, so a module-level import would be a cycle
    (the same break as validate_manifest's phase_runner import). Raises OSError/ValueError."""
    import route_advice   # noqa: E402 — lazy: breaks the route_advice <-> render import cycle
    return route_advice.load_routing()


def routing_scalars(routing):
    """The ROADMAP legend placeholders derived from the routing spec: the tier/effort ladders
    (cheapest/lowest first, the spec's own order), the floor, and the dated catalog snapshot.
    Model names flow from catalog VALUES only — a catalog refresh changes the next render's
    output, never a template or this code (ADR-0017)."""
    tiers = [str(t) for t in routing.get("tiers") or []]
    defaults = routing.get("defaults") or {}
    catalog = routing.get("catalog") or {}
    lines = []
    import route_advice   # noqa: E402 — lazy, same cycle-break as load_routing above
    for h in catalog.get("hosts") or []:
        # Schema v2 (ADR-0024): a host declares which providers it reaches, so the tier→model map
        # is projected from the catalog rather than stored per host. A tier with no assessed
        # reachable model renders as "—" — the honest answer, not a blank that reads as an omission.
        models = route_advice.models_by_tier(routing, (h or {}).get("id")) if isinstance(h, dict) else {}
        cells = " · ".join(f"{t} → {models.get(t) or '—'}" for t in tiers)
        lines.append(f"- **{(h or {}).get('id', '')}**: {cells}")
    return {
        "ROUTE_TIERS": " → ".join(tiers),
        "ROUTE_EFFORTS": " → ".join(str(e) for e in routing.get("efforts") or []),
        "ROUTE_FLOOR": f"{defaults.get('tier', '')} / {defaults.get('effort', '')}",
        "ROUTE_CATALOG": "\n".join(lines),
        "ROUTE_CATALOG_AS_OF": str(catalog.get("as_of", "")),
    }


GIT_SPEC = os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")


def commands_table(registry=None):
    """The `/eados` command table for the generated `AGENTS.md` (#374).

    Rendered from the canonical registry (`orchestrator/commands/README.md`) via
    `command_registry`, never retyped into the template — a hand-written copy is a second list to
    drift, and a *stale* command table is worse than none: it sends an agent at a command that no
    longer exists.

    It matters most where there are no slash commands. `AGENTS.md` is the one file every host
    auto-loads, and in a generated repo it carried no command list at all — while the registry that
    has one lives inside the gitignored `.eados-core/`, so the contract guaranteed to be read
    pointed at a file guaranteed not to be committed."""
    if registry is None:
        import command_registry   # noqa: E402 — lazy, matching the routing import's cycle-break
        registry = command_registry.load()
    if not registry:
        return ""
    # `agent-authored` is the CLI's own classification (eados.py), imported rather than restated so
    # the contract and the tool cannot disagree about which commands a CLI can run.
    try:
        import eados
        authored = set(eados.AGENT_AUTHORED)
    except Exception:                       # noqa: BLE001 — the table must render without the CLI
        authored = set()
    rows = ["| Command | Class | What it does |", "|---|---|---|"]
    for c in registry:
        phase = str(c.get("phase") or "")
        klass = ("phase" if phase and "any" not in phase and not phase.startswith("—")
                 else "agent-authored" if c["name"] in authored else "cross-cutting")
        rows.append(f"| `/eados {c['name']}` | {klass} | {c['summary']} |")
    return "\n".join(rows)


def git_policy_scalars(manifest, spec_path=GIT_SPEC):
    """The two lists a generated repo's `git-policy.yaml` needs, as single-line YAML flow bodies.

    The split is the point (#358). **Scopes are the project's** — they come from the manifest's
    `governance.scopes` and are what `git_check.py` was getting catastrophically wrong downstream,
    where it read EADOS's own 21 factory scopes instead (2 of 13 overlapping, so it rejected the
    project's valid scopes and waved through `fix(profiles):` in a Java library). **Branch/commit
    types are not** — they are the Conventional Commit set, identical in both contracts, so they
    are derived from the factory spec at render time rather than retyped into the template, which
    keeps them in lockstep with `os/git/git.yaml` by construction.

    Flow style on ONE line deliberately: the hand-rolled loader's multi-line flow support is
    untested, and this file exists to be read by that loader in a repo nobody will re-render."""
    types = []
    try:
        with open(spec_path, encoding="utf-8") as handle:
            spec = load_yaml(handle.read()) or {}
        types = [str(t) for t in ((spec.get("branch_naming") or {}).get("types") or [])]
    except (OSError, ValueError):
        types = []                 # absent -> the placeholder stays empty and render.py's
        # unresolved-placeholder guard turns it into a hard error, never a silent empty policy
    scopes = [str(s) for s in ((manifest.get("governance") or {}).get("scopes") or [])]
    subject_max = ""
    try:
        with open(spec_path, encoding="utf-8") as handle:
            cap = ((load_yaml(handle.read()) or {}).get("commit") or {}).get("subject_max")
        subject_max = str(cap) if str(cap or "").strip().isdigit() else ""
    except (OSError, ValueError):
        subject_max = ""
    return {"GIT_BRANCH_TYPES": ", ".join(types), "GIT_COMMIT_SCOPES": ", ".join(scopes),
            "GIT_SUBJECT_MAX": subject_max}


def routed_item(item, routing):
    """One roadmap item, route-suffixed. A plain string (the legacy form) passes through
    untouched; a `{text, signals[]}` object gains the advisory route its signals earn under the
    os/routing only-raise resolution — ` — route: <tier> / <effort>[ (<signals>)]`, the plan
    phase's own notation (tiers, never model names). An object with no signals still carries
    the explicit floor: opting into the object form is opting into a visible route."""
    if not isinstance(item, dict):
        return item
    import route_advice   # lazy — see _load_routing
    text = str(item.get("text") or "").strip()
    signals = [str(s).strip() for s in (item.get("signals") or [])
               if isinstance(s, (str, int, float)) and str(s).strip()]
    declared = routing.get("flags") if isinstance(routing.get("flags"), dict) else {}
    labels = [s for s in signals if s not in declared]
    flags = [s for s in signals if s in declared]
    adv = route_advice.advise(route_advice.signals_for(labels, flags, routing), routing)
    suffix = f" — route: {adv['tier']} / {adv['effort']}"
    if signals:
        suffix += f" ({', '.join(signals)})"
    return text + suffix


def _routing_signal_vocabulary(routing):
    """Every signal a roadmap item may usefully declare: the spec's asserted flags plus each
    tracker label its rules reference. Anything outside this set is INERT — no rule can ever
    match it, so declaring it is a typo (`set-pattern` for `sets-pattern`) that would silently
    route to the floor; validation rejects it loudly instead (#306 — the same posture as
    route_advice.signals_for's unknown-flag rejection)."""
    vocab = set(routing.get("flags") or {})
    for rule in routing.get("rules") or []:
        for sig in (rule.get("when") or []):
            s = str(sig)
            if s.startswith("label:"):
                vocab.add(s[len("label:"):].strip())
    return vocab


def milestone_item_problems(spec_section):
    """Shape problems of roadmap items in their #306 `{text, signals[]}` object form; plain
    strings — the legacy form — are always legal and acquire no routing dependency. Signals are
    checked against the routing spec's usable vocabulary; an unreadable routing spec is itself
    a problem only when an object item actually needs it to render."""
    problems, objects = [], []

    def walk(items, where):
        if items is None:
            return
        if not isinstance(items, list):
            problems.append(f"{where} must be a list of roadmap items")
            return
        for i, it in enumerate(items):
            if isinstance(it, dict):
                objects.append((f"{where}[{i}]", it))
            elif not isinstance(it, (str, int, float)):
                problems.append(f"{where}[{i}] must be a string or a {{text, signals}} mapping")

    walk(spec_section.get("milestone1_items"), "spec.milestone1_items")
    for j, ms in enumerate(spec_section.get("milestones") or []):
        if isinstance(ms, dict):
            walk(ms.get("items"), f"spec.milestones[{j}].items")
    if not objects:
        return problems
    try:
        routing = _load_routing()
    except (OSError, ValueError) as exc:
        problems.append("roadmap items use the {text, signals} object form but the os/routing "
                        f"spec is unreadable — {exc}")
        routing = None
    vocab = _routing_signal_vocabulary(routing) if routing is not None else None
    for where, it in objects:
        for key in sorted(it):
            if key not in _ITEM_KEYS:
                problems.append(f"{where}.{key} is not a recognized key (expected one of: "
                                f"{', '.join(sorted(_ITEM_KEYS))})")
        if not str(it.get("text") or "").strip():
            problems.append(f"{where}.text is missing or empty — the item's pre-numbered "
                            "task line")
        sigs = it.get("signals")
        if sigs is None:
            continue
        if not isinstance(sigs, list):
            problems.append(f"{where}.signals must be a list of routing signals")
            continue
        for s in sigs:
            sv = str(s).strip() if isinstance(s, (str, int, float)) else ""
            if not sv:
                problems.append(f"{where}.signals contains an empty or non-string entry")
            elif vocab is not None and sv not in vocab:
                problems.append(f"{where}.signals '{sv}' matches no os/routing rule or declared "
                                f"flag — it is inert (known signals: {', '.join(sorted(vocab))})")
    return problems


def build_context(m):
    if not isinstance(m, dict):
        m = {}
    ident = _map(m, "identity")
    own = _map(m, "ownership")
    lang = _map(m, "language")
    tool = _map(m, "toolchain")
    cmds = _map(tool, "commands")
    ci = _map(m, "ci")
    gov = _map(m, "governance")
    caps = _map(gov, "capabilities")
    spec = _map(m, "spec")
    i18n = _map(m, "i18n")
    ann = _map(m, "announce")

    slug = ident.get("project_slug", "")
    gpath = lang.get("group_path", "")  # no fallback: REQUIRED_SCALARS guards {{GROUP_PATH}} (#163)
    lng = lang.get("lang", "")
    bench = bool(caps.get("bench"))
    pkg_eco = tool.get("package_ecosystem", "") or ""
    series = ident.get("project_series", "") or ""

    scalars = {
        "PROJECT_NAME": ident.get("project_name", ""),
        "PROJECT_SLUG": slug,
        "PROJECT_TITLE": ident.get("project_title", ""),
        "PROJECT_TAGLINE": ident.get("project_tagline", ""),
        "PROJECT_SERIES": series,
        "PROJECT_KIND": ident.get("project_kind", ""),
        "OWNER": own.get("owner", ""),
        "MAINTAINER": own.get("maintainer", ""),
        "AUTHOR": own.get("author", ""),
        "YEAR": own.get("year", ""),
        "LICENSE_ID": own.get("license_id", ""),
        "DEFAULT_BRANCH": own.get("default_branch", ""),
        "ASSIGNEE": own.get("assignee") or own.get("owner", ""),   # #141: blank -> the owner, never "@me"
        "POSTURE": gov.get("posture") or "standard",   # standard (default) | enterprise (Q0.5, ADR-0015)
        "START_VERSION": gov.get("start_version", "0.0.0"),
        "VERSION_START": gov.get("version_start", ""),
        "LANG": lng,
        "LANG_NAME": lang.get("lang_name", ""),
        "LANG_STANDARD": lang.get("lang_standard", ""),
        "GROUP_PATH": gpath,
        "GROUP_DOTTED": lang.get("group_dotted", ""),
        "NAMESPACE": lang.get("namespace", ""),
        "SRC_EXT": lang.get("src_ext", ""),
        "PUBLIC_INCLUDE_HINT": lang.get("public_include_hint", ""),
        "SRC_MAIN": f"src/main/{lng}/{gpath}/{slug}",
        "SRC_TEST": f"src/test/{lng}/{gpath}/{slug}",
        "SRC_BENCH": f"src/bench/{lng}/{gpath}/{slug}" if bench else "",
        "BUILD_TOOL": tool.get("build_tool", ""),
        "PKG_MANAGER": tool.get("pkg_manager", ""),
        "TEST_FRAMEWORK": tool.get("test_framework", ""),
        "FORMATTER": tool.get("formatter", ""),
        "LINTER": tool.get("linter", ""),
        "SANITIZERS": tool.get("sanitizers", ""),
        "COVERAGE_TOOL": tool.get("coverage_tool", ""),
        "COVERAGE_TARGET": tool.get("coverage_target", ""),
        "DOC_TOOL": tool.get("doc_tool", ""),
        "VERSION_FILE": tool.get("version_file", ""),
        "VERSION_CONST_HINT": tool.get("version_const_hint", ""),
        "PKG_ECOSYSTEM": pkg_eco,
        "CMD_BUILD": cmds.get("build", ""),
        "CMD_TEST": cmds.get("test", ""),
        "CMD_FORMAT_CHECK": cmds.get("format_check", ""),
        "CMD_LINT": cmds.get("lint", ""),
        "CMD_BENCH": cmds.get("bench", ""),
        "TIER1_PLATFORMS": ci.get("tier1_platforms", ""),
        "CI_SETUP_STEPS": ci.get("setup_steps", ""),
        "CI_EXTRA_JOBS": ci.get("extra_jobs", ""),
        "CI_RACE_JOB": ci.get("race_job", ""),
        "SPEC_OBJECTIVE": spec.get("objective", ""),
        "SPEC_ARCHITECTURE": spec.get("architecture", ""),
        "ARCHITECTURE_STYLE": spec.get("architecture_style", ""),          # #151: structured §5 style
        "PATTERN_DISCIPLINE": spec.get("pattern_discipline") or "advisory",  # advisory (default) | enforced
        "SPEC_VERIFICATION": spec.get("verification", ""),
        "CODE_COMMENT_LANG": lang.get("comment_lang") or "en",   # #150: comment language, default en
        "DOC_DEFAULT_LANG": i18n.get("default_lang", "en"),
        "I18N_ENABLED": "True" if caps.get("i18n") else "False",
        "HOUSE_RULES": gov.get("house_rules", ""),
        # #319: which factory produced this repo. Derived from the CHANGELOG + git, or taken from
        # the manifest's `generated_by:` when it records one. ADR-0003 rightly refuses to
        # re-render a generated repo on every factory change — but "do not re-render" is not "do
        # not tell them what changed", and neither is possible without knowing where they started.
        "EADOS_PROVENANCE": provenance_line(factory_provenance(m)),
        # The file whose presence proves the build system exists (#313). A glob is legal —
        # the probe uses `compgen -G`, so lua's "*.rockspec" works without a special case.
        "CI_BUILD_MANIFEST": ci.get("build_manifest", ""),
    }
    scalars = {k: ("" if v is None else str(v)) for k, v in scalars.items()}

    flags = {
        "IF_BENCH": bench,
        "IF_THREADING": bool(caps.get("threading")),
        "IF_PUBLIC_API": bool(caps.get("public_api")),
        "IF_I18N": bool(caps.get("i18n")),
        "IF_PACKAGING": bool(caps.get("packaging")),
        "IF_SERVICE": bool(caps.get("service")),
        "IF_ANNOUNCE": bool(caps.get("announce")),
        "IF_SERIES": bool(series.strip()),
        "IF_PKG_ECOSYSTEM": bool(pkg_eco.strip()),
        "IF_HOUSE_RULES": bool(str(gov.get("house_rules", "") or "").strip()),
        # #313: the toolchain jobs SKIP until the build system exists. Absent a declared build
        # manifest the guard is not rendered at all, so a manifest written before this shipped
        # renders byte-identically — additive, like every other manifest field.
        "IF_BOOTSTRAP_GUARD": bool(str(ci.get("build_manifest", "") or "").strip()),
        "IF_ARCHITECTURE_STYLE": bool(str(spec.get("architecture_style", "") or "").strip()),  # #151
        "IF_ENTERPRISE": (gov.get("posture") or "standard").strip().lower() == "enterprise",  # #248, ADR-0015
        "IF_LAYERED": bool(caps.get("layered")),   # #152: opt-in layered package skeleton
        "IF_API_SPEC": bool(caps.get("api_spec")),  # #240: opt-in docs/api/ OpenAPI/IDL stub (service/web)
        # #150: recorded authoring-language exceptions (ADR-0016) — non-English choices render an
        # explicit exception block into the generated AGENTS.md §2 instead of silently deviating.
        "IF_COMMENT_LANG_NONEN": scalars["CODE_COMMENT_LANG"].strip().lower() not in ("", "en"),
        "IF_DOC_LANG_NONEN": scalars["DOC_DEFAULT_LANG"].strip().lower() not in ("", "en"),
    }

    # #306 (ADR-0023): the advisory routing surface. The legend placeholders and the per-item
    # route derivation both come from the os/routing spec. When it is unreadable, degradation is
    # LOUD, never silent: the ROUTE_* scalars stay absent (an unresolved-placeholder hard error
    # on any template that uses them) and object items stay raw (validate_manifest names the
    # real cause; a raw object renders empty only on a path that skipped validation).
    try:
        routing = _load_routing()
    except (OSError, ValueError):
        routing = None
    milestones = spec.get("milestones", []) or []
    m1_items = spec.get("milestone1_items", []) or []
    if routing is not None:
        scalars.update(routing_scalars(routing))
        milestones = [dict(ms, items=[routed_item(it, routing) for it in ms["items"]])
                      if isinstance(ms, dict) and isinstance(ms.get("items"), list) else ms
                      for ms in milestones]
        if isinstance(m1_items, list):
            m1_items = [routed_item(it, routing) for it in m1_items]
    # #358: the generated repo's own git policy as data. The manifest is gitignored downstream, so
    # `governance.scopes` survives a clone only if it is RENDERED somewhere committed.
    scalars.update(git_policy_scalars(m))
    # #374: the command table the generated contract carries, from the canonical registry.
    scalars["EADOS_COMMANDS"] = commands_table()

    sections = {
        "EACH_CI_CELL": ci.get("matrix", []) or [],
        "EACH_SCOPE": gov.get("scopes", []) or [],
        "EACH_FUNCTIONAL_REQ": spec.get("functional_reqs", []) or [],
        "EACH_NONFUNCTIONAL_REQ": spec.get("nonfunctional_reqs", []) or [],
        "EACH_PUBLIC_API": spec.get("public_api", []) or [],
        "EACH_MILESTONE1_ITEM": m1_items,
        "EACH_MILESTONE": milestones,
        "EACH_PATTERN": spec.get("patterns", []) or [],   # #151: expected first-class patterns (name, why)
        "EACH_LAYER": spec.get("layers", []) or [],       # #152: layered package skeleton (name, purpose)
        "EACH_DOC_LANG": i18n.get("targets", []) or [],
        "EACH_ANNOUNCE_CHANNEL": ann.get("channels", []) or [],
    }
    return scalars, flags, sections


# ---------------------------------------------------------------------------
# Manifest pre-render validation (catch silent mistakes the renderer would paper over).
# ---------------------------------------------------------------------------
KNOWN_SECTIONS = {
    "identity", "ownership", "language", "toolchain", "ci",
    "generated_by",     # which EADOS produced this repo (#319); recorded, never interviewed
    "governance", "i18n", "announce", "spec",
    "delivery_state",   # EADOS persistent delivery state (M1-B); state, not a placeholder source
    "interview",        # interview provenance — asked|defaulted|imported per answer key (#169);
                        # state for the confirmation step + the learning loop, never a placeholder source
    "adoption",         # brownfield adoption record — goals + gap_map_ref + its own provenance
                        # (#247, ADR-0021); state written by /eados adopt, never a placeholder source
}

# Known top-level SCALARS (not sections). `schema_version` versions the manifest schema for
# backward-compatible evolution (RFC-0001 §8 / OQ1); `domain` selects the target profile
# (orchestrator/domains/<domain>.yaml, M1-C); `manifest_rev` is the optimistic-concurrency counter
# (#214). All are metadata, not sections/placeholders.
KNOWN_SCALARS = {"schema_version", "domain", "manifest_rev"}

# How an interview answer got its value (#169): posed to the maintainer, assumed from the
# questionnaire default (and echoed back at confirmation), or carried in from an existing
# artifact (e.g. a validated PRD/SRS import, Q5.0).
_PROVENANCE_VALUES = {"asked", "defaulted", "imported"}

# Top-level keys that carry no interview answer, so need no provenance entry: the schema version
# (system metadata) and the state/meta sections. EVERY other top-level key present in the
# manifest must appear in interview.provenance (#201) — a partial block silently starves override
# derivation (derive_overrides treats an unrecorded key exactly like an explicitly `defaulted` one).
# `adoption` is exempt because its provenance lives INSIDE the block (#247, ADR-0021 §2).
# `routing` is exempt because it records the ENVIRONMENT the project is being run in (which host
# the OS should route for, #325), not an interview answer about the project itself.
PROVENANCE_EXEMPT = {"schema_version", "manifest_rev", "delivery_state", "interview", "adoption",
                     "routing", "generated_by"}

# The brownfield adoption goal menu (#247, ADR-0021): what a maintainer may ask of an adopted
# repository. Closed — extending it takes an ADR, like every command-surface class (ADR-0019).
_ADOPTION_GOALS = {"governance-docs", "retro-design", "audit", "migrate", "bugfix"}
_ADOPTION_KEYS = {"goals", "gap_map_ref", "provenance"}

# A spec.nfr_budgets entry (#249): the NUMERIC budget recorded for a domain NFR axis at intake
# (Q5.3). `axis` names the domain's nfr_axes entry; `target` is the committed number (or the
# level for a scale axis); `metric` qualifies a composite axis (Core Web Vitals: LCP/INP/CLS);
# `measured` is an optional recorded measurement the nfr-budgets gate compares against target.
_NFR_BUDGET_KEYS = {"axis", "target", "metric", "unit", "measured"}


def budget_number(value):
    """The numeric value of a budget field, or None. yamlmini deliberately keeps unquoted
    decimals as strings (#153 loader fidelity), so a manifest's `target: 2.5` arrives here as
    the string "2.5" — coerce the numeric-looking string ONCE, shared by the shape validator
    below and the `nfr-budgets` gate evaluator (eados.py, #249). Bools are not numbers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value if value is not None else "").strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def nfr_budget_problems(budgets):
    """Shape problems of a manifest's `spec.nfr_budgets` list (#249). Domain-aware semantics
    (hard-axis coverage, scale membership, direction comparison) live in eados.py's
    `nfr-budgets` gate evaluator — this validates only the manifest-local shape, so the two
    layers cannot disagree about what a well-formed entry is."""
    problems = []
    if not isinstance(budgets, list):
        return ["spec.nfr_budgets must be a list of {axis, target, ...} budget entries (#249)"]
    for i, entry in enumerate(budgets):
        if not isinstance(entry, dict):
            problems.append(f"spec.nfr_budgets[{i}] must be a mapping (axis, target, ...)")
            continue
        for key in sorted(entry):
            if key not in _NFR_BUDGET_KEYS:
                problems.append(f"spec.nfr_budgets[{i}].{key} is not a recognized key (expected "
                                f"one of: {', '.join(sorted(_NFR_BUDGET_KEYS))})")
        if not str(entry.get("axis") or "").strip():
            problems.append(f"spec.nfr_budgets[{i}].axis is missing or empty — name the domain "
                            "NFR axis this budget covers")
        target = entry.get("target")
        if isinstance(target, bool) or (budget_number(target) is None
                                        and not str(target or "").strip()):
            problems.append(f"spec.nfr_budgets[{i}].target must be a number — or the level, for "
                            f"a scale axis — that the design commits to; got {target!r}")
        measured = entry.get("measured")
        if measured is not None and budget_number(measured) is None:
            problems.append(f"spec.nfr_budgets[{i}].measured must be a number when present, "
                            f"got {measured!r}")
    return problems


def adoption_problems(adoption):
    """Shape problems of a manifest's `adoption:` block (#247, ADR-0021): `goals` (non-empty,
    from the closed menu), `gap_map_ref` (where the read-only brownfield.py report was captured),
    and its own `provenance` sub-block (the section is PROVENANCE_EXEMPT — its provenance lives
    here, like delivery_state's state lives inside delivery_state). One source of truth for the
    shape: validate_manifest calls it when the section is present, and eados.py's
    `adoption-recorded` gate evaluator calls it directly."""
    problems = []
    if not isinstance(adoption, dict):
        return ["adoption must be a mapping (goals, gap_map_ref, provenance)"]
    for key in sorted(adoption):
        if key not in _ADOPTION_KEYS:
            problems.append(f"adoption.{key} is not a recognized key (expected one of: "
                            f"{', '.join(sorted(_ADOPTION_KEYS))})")
    goals = adoption.get("goals")
    if not isinstance(goals, list) or not goals:
        problems.append("adoption.goals must be a non-empty list drawn from "
                        f"{'|'.join(sorted(_ADOPTION_GOALS))} (ADR-0021)")
    else:
        for goal in goals:
            # isinstance guard: a hand-edited nested mapping is unhashable — it must land as a
            # problem string, never a TypeError traceback (the gate's malformed -> FAIL contract).
            if not isinstance(goal, str) or goal not in _ADOPTION_GOALS:
                problems.append(f"adoption.goals contains {goal!r} — not in the closed menu "
                                f"{'|'.join(sorted(_ADOPTION_GOALS))} (ADR-0021)")
    if not str(adoption.get("gap_map_ref") or "").strip():
        problems.append("adoption.gap_map_ref is missing or empty — record where the "
                        "brownfield.py gap map was captured")
    prov = adoption.get("provenance")
    if not isinstance(prov, dict) or not prov:
        problems.append("adoption.provenance must be a non-empty mapping of adoption "
                        "answer key -> asked|defaulted|imported")
    else:
        for key in sorted(prov):
            if key not in _ADOPTION_KEYS - {"provenance"}:
                problems.append(f"adoption.provenance names '{key}' which is not an adoption "
                                "answer key (goals, gap_map_ref)")
            # isinstance guard: an unhashable (nested-mapping) value must be a problem, not a crash.
            if not isinstance(prov[key], str) or prov[key] not in _PROVENANCE_VALUES:
                problems.append(f"adoption.provenance['{key}'] must be one of "
                                f"asked|defaulted|imported, got {prov[key]!r}")
        if "goals" not in prov:
            problems.append("adoption.provenance has no entry for 'goals' — the elicited "
                            "goal-menu answer must record how it was settled (#201 discipline)")
    return problems

# Scalars without which the generated repo is structurally broken (blank title, no owner,
# no license, nowhere to put source). build_context defaults every scalar to "", so without
# this guard a manifest missing these would render a hollow repo and still print "Render: OK".
REQUIRED_SCALARS = (
    "PROJECT_NAME", "PROJECT_SLUG", "PROJECT_KIND",
    "OWNER", "LICENSE_ID", "DEFAULT_BRANCH",
    "LANG", "GROUP_PATH",
)

# Fields that become filesystem path segments (src tree, spec filename). Anything other than
# plain segments — a path separator beyond '/', '.', '..', or an absolute/drive-qualified
# value — would let the manifest steer writes outside --out. Rejected before any file is
# created; write_file enforces a second, defense-in-depth containment check.
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9._-]+\Z")


def _unsafe_path_value(value):
    """True if `value` cannot be used as one or more safe relative path segments. A `.git` segment
    at any depth is refused by EXACT match — it steers writes into VCS metadata (`.git/hooks/` is an
    execution vector on the next commit), the same corruption class sandbox.resolve refuses. The
    exact match keeps a `.gitignore` file and a `foo.git/` directory legal. Refusing it here makes
    the failure land at manifest validation (`--check`), before write_file's sandbox backstop."""
    for part in str(value).replace("\\", "/").split("/"):
        if part in ("", ".", "..", ".git") or not _SAFE_SEGMENT.match(part):
            return True
    return False


CHANGELOG = os.path.join(os.path.dirname(ROOT), "CHANGELOG.md")

# Markers that identify a project root, nearest-first. `.eados-core/` is the vendored factory —
# the same self-location convention AGENTS.md §4 already states the tooling uses — and `.git/`
# covers a repo that keeps the manifest elsewhere.
_ROOT_MARKERS = (".eados-core", ".git")


def project_root(manifest_path):
    """The project root a manifest belongs to (#347).

    The tools defaulted to `dirname(manifest)`, but the prescribed manifest location is
    `orchestrator/project.yaml` while `ROADMAP.md` and `links.yaml` live at the REPO ROOT — so on
    a correctly generated repo the default looked in `orchestrator/`, found neither, and reported
    them absent. Both lookups are `isfile`-guarded, so the miss was silent: `/eados status` said a
    roadmap that exists is missing, and two gates degraded to `needs-input` for a reason unrelated
    to the project.

    Ascend to the nearest ancestor carrying a root marker; fall back to the manifest's own
    directory when there is none, which is the previous behaviour and the right answer for a
    manifest sitting outside any project."""
    start = os.path.dirname(os.path.abspath(manifest_path))
    current = start
    while True:
        if any(os.path.isdir(os.path.join(current, m)) for m in _ROOT_MARKERS):
            return current
        parent = os.path.dirname(current)
        if parent == current:          # filesystem root — no marker anywhere above
            return start
        current = parent


def factory_provenance(manifest=None):
    """`{eados_version, eados_commit, rendered_at}` — which factory produced this render (#319).

    Derived, never hand-maintained: the version is the CHANGELOG's latest released heading, which
    is already the single source of truth the `version-lockstep` gate holds the READMEs to, so a
    stamp cannot drift from the release it claims. The commit comes from git and degrades to "" in
    a bundle install (no .git) rather than guessing.

    A manifest that RECORDS a `generated_by:` block wins over the derived values: a recorded fact
    beats one re-derived later, which is the whole point of a provenance stamp — a repo rendered by
    v2.11.0 must keep saying so after the factory moves on."""
    recorded = (manifest or {}).get("generated_by") if isinstance(manifest, dict) else None
    if isinstance(recorded, dict) and str(recorded.get("eados_version") or "").strip():
        return {k: str(recorded.get(k, "") or "") for k in
                ("eados_version", "eados_commit", "rendered_at")}
    version = ""
    try:
        with open(CHANGELOG, encoding="utf-8") as handle:
            found = re.findall(r"(?m)^##\s*\[(\d+\.\d+\.\d+)\]", handle.read())
        version = found[0] if found else ""
    except OSError:
        pass
    commit = ""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=os.path.dirname(ROOT), capture_output=True, text=True,
                             encoding="utf-8", timeout=15)
        if out.returncode == 0:
            commit = (out.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"eados_version": version, "eados_commit": commit,
            "rendered_at": datetime.date.today().isoformat()}


def provenance_line(prov):
    """The one human-readable sentence the generated contract carries. Says plainly what is not
    known rather than omitting it — an unstamped repo and a repo stamped by an unknown version are
    different situations, and a reader deserves to tell them apart."""
    ver = prov.get("eados_version") or "an unrecorded version"
    at = f" on {prov['rendered_at']}" if prov.get("rendered_at") else ""
    commit = f" (commit {prov['eados_commit']})" if prov.get("eados_commit") else ""
    return f"EADOS v{ver}{commit}{at}" if prov.get("eados_version") else f"EADOS {ver}{at}"


def validate_manifest(m, scalars):
    """Guards that turn quiet manifest mistakes into a hard, actionable failure: an
    unknown/misspelled top-level section (which would otherwise resolve to an empty mapping
    and blank every field under it), a missing required field, a path-unsafe identifier, and
    a non-numeric start version (the classic `start_version`/`version_start` swap)."""
    problems = []
    if not isinstance(m, dict):
        return [f"manifest root must be a mapping, got {type(m).__name__}"]
    for key, val in m.items():
        if key in KNOWN_SCALARS:
            continue  # a known top-level scalar (e.g. schema_version), not a section
        if key not in KNOWN_SECTIONS:
            problems.append(
                f"unknown top-level section '{key}' (typo? expected one of: "
                f"{', '.join(sorted(KNOWN_SECTIONS))})"
            )
        elif val is not None and not isinstance(val, dict):
            problems.append(f"section '{key}' must be a mapping, got {type(val).__name__}")
    for key in REQUIRED_SCALARS:
        if not str(scalars.get(key, "")).strip():
            problems.append(f"required field for {{{{{key}}}}} is missing or empty")
    # #313: `ci.extra_jobs` fragments gate themselves on the bootstrap job, which the CI template
    # only renders when `ci.build_manifest` is declared. Having one without the other emits a
    # workflow whose jobs `needs:` a job that does not exist — GitHub rejects it outright, and it
    # would be found at push time rather than here. Cheap to catch, expensive to debug.
    ci_block = m.get("ci") if isinstance(m.get("ci"), dict) else {}
    if "needs: bootstrap" in str(ci_block.get("extra_jobs") or "") \
            and not str(ci_block.get("build_manifest", "") or "").strip():
        problems.append("ci.extra_jobs gates on the `bootstrap` job but ci.build_manifest is not "
                        "set — the bootstrap job is only rendered when it is, so the emitted "
                        "workflow would reference a job that does not exist (#313)")
    for field, key in (("identity.project_slug", "PROJECT_SLUG"),
                       ("language.lang", "LANG"),
                       ("language.group_path", "GROUP_PATH")):
        val = str(scalars.get(key, "")).strip()
        if val and _unsafe_path_value(val):
            problems.append(
                f"{field} '{val}' is not a safe path segment "
                "(no path separators beyond '/', no '.', '..', '.git', or absolute paths)"
            )
    sv = scalars.get("START_VERSION", "")
    if sv and not re.fullmatch(r"\d+\.\d+\.\d+", sv):
        problems.append(
            f"governance.start_version '{sv}' is not a numeric X.Y.Z version "
            "(did you swap it with version_start?)"
        )
    # #248: the governance posture is a closed vocabulary (ADR-0015). A typo or wrong case
    # (`entrprise`, `Enterprise`) would silently degrade to a `standard` repo with the raised-bar
    # clauses missing — exactly the silently-defaulted-answer failure this materialization closes.
    # Fail loud at --check instead. Absent == the `standard` default (POSTURE handles the fallback).
    posture = _map(m, "governance").get("posture")
    if posture is not None and str(posture) not in ("standard", "enterprise"):
        problems.append(f"governance.posture '{posture}' is not one of standard|enterprise "
                        "(ADR-0015; a typo would silently render a standard repo)")
    # #214: the optimistic-concurrency counter is a non-negative integer when present (absent == 0).
    rev = m.get("manifest_rev")
    if rev is not None and not (isinstance(rev, int) and not isinstance(rev, bool) and rev >= 0):
        problems.append(f"manifest_rev must be a non-negative integer (the optimistic-concurrency "
                        f"counter, #214), got {rev!r}")
    # #170: the spec-substance floor. The deterministic (no-agent) path had no floor at all — a
    # manifest with an empty spec rendered "Render: OK" and a hollow repository (blank SPEC.md,
    # a roadmap with nothing beyond the bootstrap). A FLOOR, not a taste test: presence only;
    # measurability stays the rubric's job (eval/rubric.md). No library escape hatch — even a
    # library has an objective and one requirement.
    spec = _map(m, "spec")
    if not str(spec.get("objective") or "").strip():
        problems.append("spec.objective is empty — the spec floor requires a stated objective "
                        "(what the project exists to do)")
    freqs = spec.get("functional_reqs")
    if not [r for r in (freqs if isinstance(freqs, list) else []) if str(r or "").strip()]:
        problems.append("spec.functional_reqs is empty — the spec floor requires at least one "
                        "functional requirement")
    if not str(spec.get("verification") or "").strip():
        problems.append("spec.verification is empty — the spec floor requires a verification "
                        "strategy (how CI proves a requirement failed)")
    mss = spec.get("milestones")
    if not (isinstance(mss, list) and any(isinstance(e, dict) for e in mss)):
        problems.append("spec.milestones is empty — the roadmap is defined up front (interview "
                        "Phase 5): record at least one forward milestone (number, title, goal, "
                        "items)")
    # #306 / ADR-0023: roadmap items may take the {text, signals[]} object form — an item that
    # opts in gains a rendered advisory route, so a malformed object or an inert signal would
    # silently misroute the plan artifact it feeds. Fail loud at --check instead.
    problems += milestone_item_problems(spec)
    # #169: the interview provenance block is state with a fixed shape — a wrong value or a
    # dangling key would silently defeat the asked-vs-defaulted audit trail it exists to carry.
    # Optional (legacy manifests pass), but when present it must be honest.
    iv = m.get("interview")
    if isinstance(iv, dict):
        # #201: the block is mandated complete (interview.md) — questionnaire_version set and one
        # provenance entry per answer key. The #169 guard checked only the shape of what was
        # present, so a PARTIAL block passed and silently suppressed override derivation.
        if not str(iv.get("questionnaire_version") or "").strip():
            problems.append("interview.questionnaire_version is missing or empty — set it to "
                            "questionnaire.yaml's meta.version (#201)")
        prov = iv.get("provenance")
        if not isinstance(prov, dict) or not prov:
            problems.append("interview.provenance must be a non-empty mapping of "
                            "top-level manifest key -> asked|defaulted|imported")
        else:
            for key in sorted(prov):
                if prov[key] not in _PROVENANCE_VALUES:
                    problems.append(
                        f"interview.provenance['{key}'] must be one of "
                        f"asked|defaulted|imported, got {prov[key]!r}")
                if key not in m:
                    problems.append(
                        f"interview.provenance names '{key}' which is not a top-level key "
                        "of this manifest")
            # Coverage: an answer-bearing section present in the manifest but MISSING from
            # provenance is silently treated as `defaulted` and derives no override — the quiet,
            # compounding failure that starves autotune / lesson_audit. Require an entry for each.
            missing = sorted(k for k in m if k not in PROVENANCE_EXEMPT and k not in prov)
            if missing:
                problems.append(
                    "interview.provenance is incomplete — no entry for "
                    f"{', '.join(missing)}; record every answer key (an unrecorded section is "
                    "silently treated as defaulted and derives no override, #201)")
    # #247 / ADR-0021: the brownfield adoption block is state + elicited answers with a fixed
    # shape — a malformed block would silently defeat the `adoption-recorded` gate it feeds.
    # Optional (greenfield manifests pass); when present it must be honest. Non-dict values are
    # already rejected by the generic section-must-be-a-mapping check above.
    if isinstance(m.get("adoption"), dict):
        problems += adoption_problems(m["adoption"])
    # #249: recorded NFR budgets have a fixed shape — a malformed entry would silently defeat
    # the `nfr-budgets` gate it feeds. Optional (a domain with no hard axes records none).
    if spec.get("nfr_budgets") is not None:
        problems += nfr_budget_problems(spec.get("nfr_budgets"))
    # #199: delivery-state consistency. `delivery_state.checkpoints` must be a legal, contiguous
    # transition chain ending at the current phase, and a human-gated move must carry a
    # `confirmed_by:` — so `phase: scaffold` can no longer be asserted without the intervening
    # init->design->plan->scaffold checkpoints (the honor-system phase-skip). Optional (a legacy
    # manifest with no delivery_state passes). The chain logic + workflow live in phase_runner;
    # importing it here (lazily, to avoid a module-level import cycle — phase_runner imports render)
    # keeps ONE workflow engine. A missing/unreadable workflow.yaml degrades to "unchecked" rather
    # than blocking manifest validation on a factory-file problem.
    if isinstance(m.get("delivery_state"), dict):
        try:
            import phase_runner   # noqa: E402 — lazy: breaks the render<->phase_runner import cycle
            workflow = phase_runner.apply_overlay(phase_runner.load_workflow(),
                                                  phase_runner.manifest_domain(m))
            problems += phase_runner.checkpoint_chain_problems(m, workflow)
        except (OSError, ValueError):
            pass
    return problems


# ---------------------------------------------------------------------------
# Render engine.
# ---------------------------------------------------------------------------
def render(tmpl, scalars, flags, sections, local=None, where="", errors=None):
    # `errors` accumulates unresolved placeholders/fields. It is threaded explicitly (not a
    # module global) so render() is reentrant: standalone calls are self-contained, and one
    # run's failures never leak into the next. Callers that need the list pass their own.
    if errors is None:
        errors = []

    def repl_section(m):
        kind, name, body = m.group(1), m.group(2), m.group(3)
        # Nested loop over a list FIELD of the current item: {{#ITEMS}} inside {{#EACH_MILESTONE}}
        # iterates that milestone's `items`. The section name lowercased is the field, so a loop
        # item shadows a same-named global section (each milestone owns its own items).
        local_list = local.get(name.lower()) if isinstance(local, dict) else None
        if isinstance(local_list, list):
            if kind == "#":
                return "".join(
                    render(body, scalars, flags, sections, it, where, errors) for it in local_list
                )
            return render(body, scalars, flags, sections, local, where, errors) if not local_list else ""
        if name in sections:
            items = sections[name]
            if kind == "#":
                return "".join(
                    render(body, scalars, flags, sections, it, where, errors) for it in items
                )
            return render(body, scalars, flags, sections, local, where, errors) if not items else ""
        truthy = flags.get(name, False)
        keep = truthy if kind == "#" else not truthy
        return render(body, scalars, flags, sections, local, where, errors) if keep else ""

    out = SECTION_RE.sub(repl_section, tmpl)

    def block_indent(m, value):
        # If a multi-line value sits alone on an indented line, indent its continuation
        # lines to the same column (so injected YAML blocks nest correctly).
        if "\n" not in value:
            return value
        s = m.string
        line_start = s.rfind("\n", 0, m.start()) + 1
        prefix = s[line_start:m.start()]
        if prefix.strip():
            return value
        body = value[:-1] if value.endswith("\n") else value
        return body.replace("\n", "\n" + prefix)

    def repl_var(m):
        tok = m.group(1).strip()
        if tok == ".":
            return str(local) if isinstance(local, (str, int, float)) else ""
        if UPPER_RE.match(tok):
            if tok in scalars:
                return block_indent(m, scalars[tok])
            errors.append(f"{where}: unresolved placeholder {{{{{tok}}}}}")
            return ""
        if isinstance(local, dict) and tok in local:
            v = local[tok]
            return "" if v is None else str(v)
        errors.append(f"{where}: unresolved field {{{{{tok}}}}}")
        return ""

    return VAR_RE.sub(repl_var, out)


# ---------------------------------------------------------------------------
# File walking / output.
# ---------------------------------------------------------------------------
NOT_RENDERED = {"README.md"}  # templates/README.md is the templates-dir meta-doc


def out_relpath(rel, slug):
    if rel == "docs/specs/01_spec.md.tmpl":
        return f"docs/specs/01_spec_{slug}.md"
    if rel.endswith(".tmpl"):
        rel = rel[:-5]
    if rel == "gitignore":
        return ".gitignore"
    return rel


def write_file(out_dir, rel, text, overwrite=False):
    # One write path for the whole factory: delegate to sandbox.safe_write so containment
    # (realpath + commonpath), the `.git`-at-any-depth refusal, and the additive no-clobber guard
    # are a SINGLE implementation shared with the migrate phase (ADR-0007) — the renderer and the
    # sandbox can no longer drift. `overwrite=True` (via --force) is the only way to clobber; on a
    # violation sandbox raises SandboxError. The full-run pre-scan in main() is the all-or-nothing
    # gate; this is the per-file backstop underneath it.
    return sandbox.safe_write(out_dir, rel, text, overwrite=overwrite)


def _duplicate_top_level_keys(text):
    """Top-level keys repeated in the manifest (the loader silently keeps the last value).
    Best-effort, column-0 keys only — manifest sections live at the top level."""
    seen, dups = set(), []
    for raw in text.split("\n"):
        if not raw or raw[0] in " \t#-" or raw.lstrip() != raw:
            continue  # indented, comment, list item, or blank — not a top-level key
        m = re.match(r"([A-Za-z0-9_]+)\s*:", raw)
        if not m:
            continue
        key = m.group(1)
        if key in seen and key not in dups:
            dups.append(key)
        seen.add(key)
    return dups


def main():
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Render an EADOS manifest into a repository.")
    ap.add_argument("manifest", help="path to a filled project.yaml")
    ap.add_argument("--out", help="output directory, OUTSIDE the EADOS factory folder")
    ap.add_argument("--in-place", action="store_true",
                    help="render into the folder that holds .eados-core/ (a bundle copied into "
                         "your own repo): the project files land next to .eados-core/")
    ap.add_argument("--check", action="store_true",
                    help="validate the manifest and exit — nothing is written (the manifest-valid "
                         "gate command, workflow.yaml)")
    ap.add_argument("--force", "--overwrite", action="store_true", dest="force",
                    help="overwrite pre-existing files in the target (default: refuse to clobber, "
                         "like the migrate sandbox — a render is additive unless you pass this)")
    args = ap.parse_args()
    if sum((bool(args.out), args.in_place, args.check)) != 1:
        ap.error("provide exactly one of --out <dir>, --in-place, or --check")
    if args.force and args.check:
        ap.error("--force has no effect with --check (nothing is written)")
    mode = "Check" if args.check else "Render"

    with open(args.manifest, encoding="utf-8") as handle:
        raw = handle.read()
    if raw.startswith(chr(0xFEFF)):
        raw = raw[1:]   # Windows editors' UTF-8 BOM — load_yaml strips it too, but the raw
        #                 text also feeds _duplicate_top_level_keys, whose first-key regex
        #                 would silently skip a BOM-glued line
    manifest = load_yaml(raw)
    scalars, flags, sections = build_context(manifest)

    problems = validate_manifest(manifest, scalars)
    problems += [f"duplicate top-level key '{k}' (only the last value is kept)"
                 for k in _duplicate_top_level_keys(raw)]
    if problems:
        print(f"{mode}: FAIL — manifest validation\n")
        for p in sorted(set(problems)):
            print(f"  {p}")
        print(f"\n{len(set(problems))} manifest problem(s).")
        return 1
    if args.check:
        print("Check: OK — manifest is valid (nothing written).")
        return 0

    slug = scalars["PROJECT_SLUG"]
    eados_repo = os.path.realpath(os.path.dirname(ROOT))   # the folder that holds .eados-core/

    def _inside(child, parent):
        try:
            return child == parent or os.path.commonpath([child, parent]) == parent
        except ValueError:                                # different drives on Windows
            return False

    if args.in_place:
        # Generate INTO the folder that holds .eados-core/ — the bundle's intended home, copied
        # into the user's own repo (`<repo>/.eados-core/`), so the project files land in <repo>/
        # next to it. No template writes inside .eados-core/, so the factory stays intact, and the
        # generated .gitignore excludes it. Refuse only on the EADOS *development* repo, marked by
        # a root `.eados-dev` sentinel that never ships in a bundle — so a maintainer cannot
        # overwrite the factory's own source by running this from a clone.
        if os.path.exists(os.path.join(eados_repo, ".eados-dev")):
            print("Render: FAIL — refusing --in-place in the EADOS development repository "
                  "(the .eados-dev sentinel marks it). Use --out <dir> to render a separate copy.")
            return 1
        out_dir = eados_repo
    else:
        out_dir = os.path.abspath(args.out)
        # write_file confines writes within the output root, but nothing stops that root from
        # BEING the factory; `--out .` would overwrite EADOS's own AGENTS.md / CI / LICENSE. To
        # generate into a copied-in .eados-core/ on purpose, use --in-place instead.
        if _inside(os.path.realpath(out_dir), eados_repo):
            print("Render: FAIL — --out must be a directory OUTSIDE the EADOS repository "
                  f"(refusing {os.path.realpath(out_dir)}); use --in-place to generate into it).")
            return 1
    out_root = os.path.realpath(out_dir)

    # PLAN every write before touching disk. A render is all-or-nothing: an unresolved placeholder,
    # a path that escapes containment, or a clobber (absent --force) must abort the WHOLE run, so a
    # failed render never leaves the target repo half-written or half-overwritten.
    errors = []           # one accumulator for the whole run, threaded into every render()
    plan = []             # (rel, text) for every file this render would produce
    written = 0           # template-walk files only (the reported count; .gitkeep seeds excluded)
    for cur, dirs, files in os.walk(TEMPLATES):
        if "__pycache__" in cur:
            continue
        dirs.sort()           # deterministic walk order, independent of the filesystem
        for fn in sorted(files):
            src = os.path.join(cur, fn)
            rel = os.path.relpath(src, TEMPLATES).replace(os.sep, "/")
            if rel in NOT_RENDERED:
                continue
            if rel.startswith("docs/i18n/") and not flags["IF_I18N"]:
                continue
            if rel.startswith("docs/benchmarks/") and not flags["IF_BENCH"]:
                continue
            if rel.startswith("docs/api/") and not flags["IF_API_SPEC"]:
                continue
            if rel.startswith("docs/compliance/") and not flags["IF_ENTERPRISE"]:
                continue   # the compliance register is the enterprise posture's artifact (#248)
            if rel == "docs/workflow/announcements.md.tmpl" and not flags["IF_ANNOUNCE"]:
                continue
            if rel == "docs/workflow/operations.md.tmpl" and not flags["IF_SERVICE"]:
                continue
            if rel == "docs/workflow/packaging.md.tmpl" and not flags["IF_PACKAGING"]:
                continue
            with open(src, encoding="utf-8") as handle:
                text = handle.read()
            rendered = render(text, scalars, flags, sections, None, rel, errors)
            plan.append((out_relpath(rel, slug), rendered))
            written += 1

    # Seed the empty source-tree directories. (The project's LICENSE is templates/LICENSE.tmpl,
    # rendered in the walk above with the project's OWN {{AUTHOR}}/{{YEAR}} — never EADOS's: a repo
    # generated by anyone carries that user's copyright, not the factory owner's.)
    for key in ("SRC_MAIN", "SRC_TEST", "SRC_BENCH"):
        if scalars[key]:
            plan.append((f"{scalars[key]}/.gitkeep", ""))

    # Optional layered skeleton (#152): materialize the chosen internal packages under the main and
    # test source roots when the maintainer opted into a layered layout (capabilities.layered). A
    # library keeps the flat shape (no layers -> nothing seeded here). Only plain package segments are
    # honoured; the sandbox containment guard backstops anything unexpected.
    if flags["IF_LAYERED"]:
        for layer in sections["EACH_LAYER"]:
            name = (layer.get("name") if isinstance(layer, dict) else str(layer or "")).strip()
            if not re.match(r"^[A-Za-z0-9_]+$", name):
                continue   # skip non-identifier names rather than create an odd/unsafe path
            for root_key in ("SRC_MAIN", "SRC_TEST"):
                if scalars[root_key]:
                    plan.append((f"{scalars[root_key]}/{name}/.gitkeep", ""))

    if errors:
        print("Render: FAIL\n")
        for e in sorted(set(errors)):
            print(f"  {e}")
        print(f"\n{len(set(errors))} unresolved placeholder(s).")
        return 1

    # PRE-SCAN: resolve every destination through the shared sandbox guard (containment + `.git`)
    # and collect the ones that already exist. Refuse the whole render on any guard violation or —
    # unless --force — any clobber, before a single byte is written.
    guard_problems, collisions = [], []
    for rel, _text in plan:
        try:
            dest = sandbox.resolve(out_root, rel)
        except sandbox.SandboxError as exc:
            guard_problems.append(str(exc))
            continue
        if os.path.exists(dest):
            collisions.append(os.path.relpath(dest, out_root).replace(os.sep, "/"))
    if guard_problems:
        print("Render: FAIL — unsafe destination\n")
        for p in sorted(set(guard_problems)):
            print(f"  {p}")
        print(f"\n{len(set(guard_problems))} unsafe path(s). Nothing was written.")
        return 1
    if collisions and not args.force:
        print("Render: FAIL — refusing to overwrite existing files "
              "(pass --force to regenerate over them)\n")
        for c in sorted(set(collisions)):
            print(f"  {c}")
        print(f"\n{len(set(collisions))} existing file(s) would be overwritten "
              "(the render is additive by default). Nothing was written.")
        return 1

    # WRITE: the pre-scan has cleared containment, `.git`, and (absent --force) clobber, so this
    # is the point of no return — every planned file lands or none do.
    os.makedirs(out_dir, exist_ok=True)
    try:
        for rel, text in plan:
            write_file(out_dir, rel, text, overwrite=args.force)
    except sandbox.SandboxError as exc:      # a race created a file between pre-scan and write
        print(f"Render: FAIL — {exc}")
        return 1
    print(f"Render: OK — {written} template(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
