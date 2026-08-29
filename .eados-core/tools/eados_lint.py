#!/usr/bin/env python3
"""Self-lint for the EADOS factory itself (the bar EADOS imposes downstream, imposed upstream).

Dependency-free (Python 3 standard library only). Run from anywhere in the repo:

    python tools/eados_lint.py

It enforces the orchestrator's own quality gates (AGENTS.md §8), which were previously only
asserted in prose:

  1. placeholder-integrity — every {{PLACEHOLDER}} used under templates/** is defined in
     orchestrator/placeholders.md (no orphans). GitHub Actions ${{ ... }} expressions and
     lower-case loop fields are ignored.
  2. profile-completeness  — every orchestrator/profiles/<lang>.yaml defines every key the
     schema (orchestrator/profiles/_schema.md) declares mandatory.
  3. generate-references   — every templates/... path the generation playbook
     (orchestrator/generate.md) names actually exists on disk (globs must match ≥1 file).

Each check runs independently; all failures are reported, then a non-zero exit on any.
"""

import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import render  # noqa: E402  — the dependency-free YAML loader, reused to parse the OS specs
import record_run  # noqa: E402  — the run-record schema authority (OUTCOMES, RUBRIC_DIMENSIONS)
import command_registry  # noqa: E402  — the ONE parser for the /eados command table (#373)

ROOT = os.path.dirname(TOOLS)
TEMPLATES = os.path.join(ROOT, "templates")
PROFILES = os.path.join(ROOT, "orchestrator", "profiles")
# The actual git repository root is one level above .eados-core/ — README.md and .github/
# live there, not under the factory folder (the i18n docs moved under .eados-core/docs/).
REPO_ROOT = os.path.dirname(ROOT)

# #167: no module-global failures list. Every check_*(fail) receives the reporting callable —
# fail(check, message) — and main() owns the accumulator, mirroring how render() threads its
# `errors` list. Checks are reentrant and standalone-runnable; a test never resets module state.


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def iter_text_files(root):
    for cur, _dirs, files in os.walk(root):
        if "__pycache__" in cur:
            continue
        for fn in files:
            if fn.endswith((".pyc", ".png", ".jpg", ".gif", ".ico")):
                continue
            yield os.path.join(cur, fn)


# Matches {{ ... }} not preceded by '$' (so GitHub Actions ${{ ... }} is excluded).
TOKEN_RE = re.compile(r"(?<!\$)\{\{\s*([^{}]*?)\s*\}\}")
UPPER_RE = re.compile(r"[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# 1. Placeholder integrity
# ---------------------------------------------------------------------------
def known_placeholders():
    """Parse the dictionary's table rows for the authoritative scalar/section names."""
    scalars, sections = set(), set()
    for line in read(os.path.join(ROOT, "orchestrator", "placeholders.md")).splitlines():
        if not line.lstrip().startswith("|"):
            continue  # only table rows are authoritative; prose examples are ignored
        for inner in TOKEN_RE.findall(line):
            inner = inner.strip()
            if not inner or inner == ".":
                continue
            if inner[0] in "#^/":
                sections.add(inner[1:].strip())
            elif UPPER_RE.match(inner):
                scalars.add(inner)
    return scalars, sections


# templates/README.md is the templates-directory meta-doc — it is never rendered into a
# generated repo, and it cites {{PLACEHOLDER}} illustratively, so it is not scanned.
NOT_RENDERED = {"templates/README.md"}


def check_placeholder_integrity(fail):
    name = "placeholder-integrity"
    scalars, sections = known_placeholders()
    if not scalars:
        fail(name, "could not parse any placeholders from orchestrator/placeholders.md")
        return
    for path in iter_text_files(TEMPLATES):
        try:
            text = read(path)
        except (UnicodeDecodeError, OSError):
            continue
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if rel in NOT_RENDERED:
            continue
        for inner in TOKEN_RE.findall(text):
            inner = inner.strip()
            if not inner or inner == ".":
                continue
            if inner[0] in "#^/":
                base = inner[1:].strip()
                if base not in sections:
                    fail(name, f"{rel}: section {{{{{inner}}}}} is not a known IF_/EACH_ "
                               "block in placeholders.md")
            elif UPPER_RE.match(inner):
                if inner not in scalars:
                    fail(name, f"{rel}: orphan placeholder {{{{{inner}}}}} is not defined "
                               "in placeholders.md")
            # lower-case / mixed tokens are loop fields ({{os}}, {{name}}) — not validated.


# ---------------------------------------------------------------------------
# 2. Profile completeness
# ---------------------------------------------------------------------------
def yaml_key_paths(text):
    """Indentation-based key-path extractor (keys only; values/list-items ignored).

    The body of a block scalar (`key: |`) is skipped — its lines are literal content
    (e.g. CI step YAML), not nested keys, so they must not become required paths.
    """
    lines = text.splitlines()
    paths, stack, i = set(), [], 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.lstrip(" ")
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        m = re.match(r"([A-Za-z0-9_]+)\s*:(.*)$", stripped)
        if not m:
            continue
        indent = len(raw) - len(stripped)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, m.group(1)))
        paths.add(".".join(k for _, k in stack))
        if m.group(2).strip() in ("|", "|-", "|+", ">", ">-", ">+"):
            while i < len(lines) and (lines[i].strip() == "" or
                                      len(lines[i]) - len(lines[i].lstrip(" ")) > indent):
                i += 1
    return paths


def schema_required_paths():
    schema = read(os.path.join(PROFILES, "_schema.md"))
    block = re.search(r"```yaml\n(.*?)```", schema, re.DOTALL)
    if not block:
        return None
    return yaml_key_paths(block.group(1))


def check_profile_completeness(fail):
    name = "profile-completeness"
    required = schema_required_paths()
    if not required:
        fail(name, "could not extract the schema YAML block from profiles/_schema.md")
        return
    # Real profiles are <lang>.yaml; underscore-prefixed files (_template.yaml) are
    # scaffolds, not languages, and are not held to completeness.
    profiles = sorted(p for p in glob.glob(os.path.join(PROFILES, "*.yaml"))
                      if not os.path.basename(p).startswith("_"))
    if not profiles:
        fail(name, "no profiles/*.yaml found")
        return
    for path in profiles:
        have = yaml_key_paths(read(path))
        missing = sorted(required - have)
        for key in missing:
            fail(name, f"profiles/{os.path.basename(path)}: missing schema key '{key}'")


# ---------------------------------------------------------------------------
# 3. Generation playbook references exist
# ---------------------------------------------------------------------------
def check_generate_references(fail):
    name = "generate-references"
    gen = read(os.path.join(ROOT, "orchestrator", "generate.md"))
    refs = set(re.findall(r"templates/[A-Za-z0-9_./*-]+", gen))
    for ref in sorted(refs):
        ref = ref.rstrip(".,)")
        if ref in ("templates", "templates/") or "**" in ref:
            continue
        abspath = os.path.join(ROOT, ref.replace("/", os.sep))
        if "*" in ref:
            if not glob.glob(abspath):
                fail(name, f"generate.md glob '{ref}' matches no file on disk")
        elif not os.path.exists(abspath):
            fail(name, f"generate.md references '{ref}' which does not exist")


# ---------------------------------------------------------------------------
# 4. Agent registry — every role file is indexed in agent/README.md, AND every persona link in
#    the index resolves to a file that exists (both directions, mirroring workflow-safety /
#    gate-coverage — a renamed or deleted persona must not leave a dead catalogue entry).
# ---------------------------------------------------------------------------
_AGENT_MD_LINK = re.compile(r"\]\(([^)]+\.md)\)")


def _persona_relative_links(index_text):
    """The persona `.md` links in agent/README.md that resolve UNDER agent/ — i.e. NOT http(s)://,
    NOT absolute, NOT `../`-escaping (the `../config/README.md` / `../learning/README.md` links stay
    out of the on-disk probe), and not the index's own README.md."""
    out = set()
    for target in (m.group(1).strip() for m in _AGENT_MD_LINK.finditer(index_text)):
        norm = target.replace("\\", "/")
        if norm.startswith(("http://", "https://", "/")) or norm.startswith("../") or "/../" in norm:
            continue
        if norm == "README.md":
            continue
        out.add(norm)
    return out


def agent_registry_problems(index_text, persona_rels):
    """Both directions of the agent-registry contract, pure/injectable (mirrors
    workflow_safety_problems / gate_coverage_problems):
      * every persona present under agent/ (relpath, README.md excluded) must be LISTED in the index;
      * every persona-relative `.md` link in the index must EXIST as a persona file.
    Returns a list of problems (empty == the index and the files agree both ways)."""
    problems = []
    listed = _persona_relative_links(index_text)
    for rel in sorted(persona_rels):
        if rel not in listed:
            problems.append(f"agent persona '{rel}' is not listed in agent/README.md")
    for rel in sorted(listed):
        if rel not in persona_rels:
            problems.append(f"agent/README.md lists '{rel}' which does not exist under agent/")
    return problems


def check_agent_registry(fail):
    name = "agent-registry"
    agent_dir = os.path.join(ROOT, "agent")
    index_path = os.path.join(agent_dir, "README.md")
    if not os.path.isdir(agent_dir) or not os.path.exists(index_path):
        return
    # Walk recursively so domain-overlay personas (agent/domains/<domain>/<role>.md) are indexed
    # too, matched by their path RELATIVE to agent/ — not basename, since an overlay shares its
    # basename with the default persona it specializes.
    persona_rels = set()
    for cur, _dirs, files in os.walk(agent_dir):
        for fn in sorted(files):
            if not fn.endswith(".md") or fn == "README.md":
                continue
            persona_rels.add(os.path.relpath(os.path.join(cur, fn), agent_dir).replace(os.sep, "/"))
    for problem in agent_registry_problems(read(index_path), persona_rels):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 5. Lessons ledger — schema of every entry (when the ledger exists)
# ---------------------------------------------------------------------------
LESSON_SCOPES_PREFIX = ("global", "lang:", "kind:")
LESSON_REQUIRED = ("id", "date", "scope", "context", "rule")


def check_lessons(fail):
    name = "lessons"
    ledger = os.path.join(ROOT, "learning", "lessons.yaml")
    if not os.path.exists(ledger):
        return
    # The ledger is a sequence-root document. It used to be split with a regex here because
    # load_yaml returned {} for that shape (#315); now that the loader reads it, this validates the
    # PARSED entries — so a field the old `[a-z_]+` regex could not even name (a kebab key, a
    # nested value) is seen, and only one parser reads this file.
    try:
        entries = render.load_yaml(read(ledger))
    except Exception as exc:                  # a broken hand-edit: data-file-validity reports the
        fail(name, f"lessons.yaml does not parse — {exc!r}")   # syntax, this states the effect
        return
    if not isinstance(entries, list):
        fail(name, f"lessons.yaml must be a YAML sequence of entries, got "
                   f"{type(entries).__name__}")
        return
    seen_ids = set()
    for pos, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            fail(name, f"lessons.yaml entry #{pos} is a {type(entry).__name__}, not a mapping")
            continue
        lid = str(entry.get("id", "") or "")
        for key in LESSON_REQUIRED:
            if not str(entry.get(key, "") or "").strip():
                fail(name, f"lessons.yaml entry missing '{key}': {lid or '?'}")
        if lid in seen_ids:
            fail(name, f"lessons.yaml duplicate id '{lid}'")
        seen_ids.add(lid)
        scope = str(entry.get("scope", "") or "").strip()
        if scope and not scope.startswith(LESSON_SCOPES_PREFIX):
            fail(name, f"lessons.yaml entry '{lid}': scope '{scope}' not global|lang:*|kind:*")


# ---------------------------------------------------------------------------
# 6. Action-pin lockstep — SHA-pinned actions shared by the factory CI and the rendered
#    workflow templates must pin the SAME commit (templates are NOT seen by the factory's
#    Dependabot, so they silently drift behind; ADR-0009). Floating tags (@v6) are exempt
#    by design — only fully SHA-pinned `uses: …@<40hex> # vX.Y.Z` lines are governed.
# ---------------------------------------------------------------------------
PIN_RE = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)@([0-9a-fA-F]{40})\s*#\s*(v[0-9][\w.-]*)")


def check_action_pins(fail):
    name = "action-pins"
    factory_ci = os.path.join(os.path.dirname(ROOT), ".github", "workflows", "ci.yml")
    tmpl_wf = os.path.join(TEMPLATES, ".github", "workflows")
    if not os.path.exists(factory_ci) or not os.path.isdir(tmpl_wf):
        return  # standalone .eados-core checkout: nothing to cross-check
    fac = {a: (sha, ver) for a, sha, ver in PIN_RE.findall(read(factory_ci))}
    for path in sorted(glob.glob(os.path.join(tmpl_wf, "*.tmpl"))):
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        for action, sha, ver in PIN_RE.findall(read(path)):
            if action in fac and (sha, ver) != fac[action]:
                fail(name, f"{rel}: {action} pinned {sha[:10]} ({ver}) but the factory CI pins "
                           f"{fac[action][0][:10]} ({fac[action][1]}) — keep them in lockstep")


# ---------------------------------------------------------------------------
# 7. i18n freshness — every `translated` row in .eados-core/docs/i18n/translation-status.md pins the
#    SHA-256 content hash of the English source it was made from; the translation is STALE
#    when the current source hashes differently. Content-based (not commit-based) so it is
#    immune to squash-merges, which rewrite history and would orphan a recorded commit
#    (ADR-0010). Git-independent. Opt-in: skipped when no manifest exists.
# ---------------------------------------------------------------------------
def _source_hash(path):
    """First 12 hex of the SHA-256 of the file's CONTENT — line endings normalized to LF first.

    It hashed raw bytes, which made the gate report a false STALE on any checkout git had given
    CRLF line endings — i.e. every Windows clone with the default `core.autocrlf=true`, including
    the windows-2022 CI runner (#318). The recorded hash was only ever valid on an LF checkout, so
    a Windows contributor could not run the lint at all.

    ADR-0010 calls this a *content* hash, and a line ending is a checkout convention rather than
    content — the same reasoning the loader applies to a UTF-8 BOM. Normalizing here keeps every
    recorded hash valid (they were all recorded from LF sources) and makes the gate portable. A
    stray CR inside a line is left alone; only the line terminator is normalized."""
    with open(path, "rb") as handle:
        raw = handle.read()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()[:12]


def check_i18n_freshness(fail):
    name = "i18n-freshness"
    manifest_path = os.path.join(ROOT, "docs", "i18n", "translation-status.md")
    if not os.path.exists(manifest_path):
        return  # the factory ships no translations — nothing to check
    i18n_dir = os.path.join(ROOT, "docs", "i18n")
    rows = 0
    for line in read(manifest_path).splitlines():
        # Data rows begin with a link cell `| [...](...)`; skips the legend + header rows.
        if not line.lstrip().startswith("| [") or "`translated`" not in line:
            continue
        link = re.search(r"\]\(([^)]+)\)", line)
        rec = re.search(r"\|\s*`([0-9a-f]{12,64})`\s*\|", line)
        if link is None or rec is None:
            fail(name, f"could not parse translated manifest row: {line.strip()}")
            continue
        rows += 1
        src = os.path.normpath(os.path.join(i18n_dir, link.group(1)))
        rel = os.path.relpath(src, REPO_ROOT).replace(os.sep, "/")
        if not os.path.exists(src):
            fail(name, f"manifest references English source {rel} which does not exist")
            continue
        recorded, actual = rec.group(1), _source_hash(src)
        if actual != recorded:
            fail(name, f"i18n translation of {rel} is STALE: source content hash {actual} "
                       f"≠ recorded {recorded} — refresh the translation and update its "
                       "translation-status.md row")
    if rows == 0:
        fail(name, "translation-status.md exists but has no parseable `translated` rows")


# ---------------------------------------------------------------------------
# 8. OS-spec completeness — every orchestrator/os/<spec>/ ships a `_schema.md` (with a yaml
#    block) and a `<spec>.yaml` instance that defines every top-level key the schema declares.
#    The same data+schema contract as profile-completeness, applied to the machine-readable
#    delivery-OS specs (ADR-0011). Opt-in: skipped until the os/ directory exists.
# ---------------------------------------------------------------------------
def check_os_specs(fail):
    name = "os-spec-completeness"
    os_dir = os.path.join(ROOT, "orchestrator", "os")
    if not os.path.isdir(os_dir):
        return  # the OS specs are introduced with the delivery-OS pivot; absent before it
    specs = sorted(d for d in os.listdir(os_dir)
                   if os.path.isdir(os.path.join(os_dir, d)))
    checked = 0
    for spec in specs:
        d = os.path.join(os_dir, spec)
        schema_path = os.path.join(d, "_schema.md")
        inst_path = os.path.join(d, f"{spec}.yaml")
        if not os.path.exists(schema_path):
            fail(name, f"orchestrator/os/{spec}/ has no _schema.md")
            continue
        if not os.path.exists(inst_path):
            fail(name, f"orchestrator/os/{spec}/ has no {spec}.yaml instance")
            continue
        block = re.search(r"```yaml\n(.*?)```", read(schema_path), re.DOTALL)
        if not block:
            fail(name, f"orchestrator/os/{spec}/_schema.md has no yaml schema block")
            continue
        required = yaml_key_paths(block.group(1))
        have = yaml_key_paths(read(inst_path))
        for key in sorted(required - have):
            fail(name, f"orchestrator/os/{spec}/{spec}.yaml: missing schema key '{key}'")
        checked += 1
    if specs and checked == 0:
        fail(name, "orchestrator/os/ exists but holds no <spec>/_schema.md + <spec>.yaml pair")


# ---------------------------------------------------------------------------
# 9. Domain-completeness — every orchestrator/domains/<domain>.yaml defines every key the domain
#    schema (orchestrator/domains/_schema.md) declares. The second axis of genericity, held to the
#    same data+schema contract as the language profiles (RFC-0001 §3-4). Underscore-prefixed files
#    (_template.yaml) are scaffolds, not domains. Opt-in: skipped until the domains/ dir exists.
# ---------------------------------------------------------------------------
def check_domains(fail):
    name = "domain-completeness"
    ddir = os.path.join(ROOT, "orchestrator", "domains")
    if not os.path.isdir(ddir):
        return  # the domain axis is introduced in M1; absent before it
    schema_path = os.path.join(ddir, "_schema.md")
    if not os.path.exists(schema_path):
        fail(name, "orchestrator/domains/_schema.md is missing")
        return
    block = re.search(r"```yaml\n(.*?)```", read(schema_path), re.DOTALL)
    if not block:
        fail(name, "orchestrator/domains/_schema.md has no yaml schema block")
        return
    required = yaml_key_paths(block.group(1))
    domains = sorted(p for p in glob.glob(os.path.join(ddir, "*.yaml"))
                     if not os.path.basename(p).startswith("_"))
    if not domains:
        fail(name, "no orchestrator/domains/<domain>.yaml found")
        return
    for path in domains:
        have = yaml_key_paths(read(path))
        for key in sorted(required - have):
            fail(name, f"domains/{os.path.basename(path)}: missing schema key '{key}'")


# ---------------------------------------------------------------------------
# 10. Authority-personas — the persona <-> authority pairing (RFC-0001 §4 / roadmap 1.5). Every
#     role in orchestrator/os/authority/authority.yaml has an agent/<role>.md persona OR is listed
#     in `pending_personas`; every agent/<role>.md persona maps to a declared role; a pending role
#     must not already have a persona. Opt-in: skipped until the authority spec exists.
# ---------------------------------------------------------------------------
def check_authority_personas(fail):
    name = "authority-personas"
    auth = os.path.join(ROOT, "orchestrator", "os", "authority", "authority.yaml")
    agent_dir = os.path.join(ROOT, "agent")
    if not os.path.exists(auth) or not os.path.isdir(agent_dir):
        return
    text = read(auth)
    roles = set(re.findall(r"(?m)^\s*-\s*name:\s*([A-Za-z][\w-]*)", text))
    if not roles:
        fail(name, "could not parse any role names from authority.yaml")
        return
    pend_m = re.search(r"pending_personas:\s*\[([^\]]*)\]", text)
    pending = {s.strip() for s in (pend_m.group(1).split(",") if pend_m else []) if s.strip()}
    # Persona role-ids, collected recursively: a default agent/<role>.md and a domain overlay
    # agent/domains/<d>/<role>.md both map to the same role id (the filename stem).
    personas = set()
    for cur, _dirs, files in os.walk(agent_dir):
        for fn in files:
            if fn.endswith(".md") and fn != "README.md":
                personas.add(os.path.splitext(fn)[0])
    for role in sorted(roles - personas - pending):
        fail(name, f"authority role '{role}' has no agent/{role}.md persona and is not in "
                   "pending_personas")
    for persona in sorted(personas - roles):
        fail(name, f"persona agent/{persona}.md has no role record in authority.yaml")
    for role in sorted(pending & personas):
        fail(name, f"role '{role}' is in pending_personas but agent/{role}.md exists — "
                   "remove it from pending_personas")


# ---------------------------------------------------------------------------
# 11. Cross-spec consistency — referential integrity ACROSS the delivery-OS specs. os-spec-
#     completeness checks that each spec carries its own keys; this checks that the references
#     BETWEEN them resolve. A role named in workflow/plan/rfc/a domain must exist in the authority
#     model; a gate named in a workflow transition / plan / rfc must exist in the workflow gate
#     registry; a from/to/required_for state must exist; a domain's workflow_overlay must exist;
#     a risk level / domain-override must resolve. This is the gate that stops the OS from
#     silently fragmenting as the specs evolve — a `tech-led` typo, a phantom transition gate, a
#     dangling overlay would otherwise pass unnoticed (the OS thesis: knowledge as data, applied
#     by gates). The git spec's cross-cutting `traceability` gate is NOT a phase-transition gate and
#     is intentionally outside this registry check. Opt-in: skipped until orchestrator/os/ exists.
# ---------------------------------------------------------------------------
def _load_spec(spec):
    """Parse orchestrator/os/<spec>/<spec>.yaml with the dependency-free loader; None if absent."""
    path = os.path.join(ROOT, "orchestrator", "os", spec, f"{spec}.yaml")
    return render.load_yaml(read(path)) if os.path.exists(path) else None


def _load_domains():
    """Parse every orchestrator/domains/<domain>.yaml (skipping _scaffolds) -> {filename: data}."""
    out = {}
    ddir = os.path.join(ROOT, "orchestrator", "domains")
    if os.path.isdir(ddir):
        for path in sorted(glob.glob(os.path.join(ddir, "*.yaml"))):
            if not os.path.basename(path).startswith("_"):
                out[os.path.basename(path)] = render.load_yaml(read(path))
    return out


def cross_spec_problems(authority, workflow, plan=None, rfc=None, risk=None, domains=None, git=None,
                        contribution=None, interaction=None):
    """Pure referential-integrity check across the parsed delivery-OS specs. Returns a list of
    problem strings (empty == every cross-reference resolves). I/O-free so it is unit-testable
    with in-memory fixtures; check_cross_spec_consistency() supplies the on-disk specs."""
    problems = []
    if not isinstance(authority, dict) or not isinstance(workflow, dict):
        return problems   # a missing/unparseable core spec is os-spec-completeness's report, not ours
    domains = domains or {}

    def vocab(records, key):
        return {r[key] for r in (records or []) if isinstance(r, dict) and r.get(key) is not None}

    roles = vocab(authority.get("roles"), "name")
    states = vocab(workflow.get("states"), "id")
    gates = vocab(workflow.get("gates"), "id")
    overlays_map = workflow.get("domain_overlays") or {}
    if not isinstance(overlays_map, dict):
        overlays_map = {}
    overlays = set(overlays_map)
    levels = set(risk.get("levels") or []) if isinstance(risk, dict) else set()
    domain_ids = {d["domain"] for d in domains.values()
                  if isinstance(d, dict) and d.get("domain") is not None}

    HUMAN = {"human-owner", "human"}   # escalation/PR terminals that are not authority roles

    def one(label, value, allowed, kind):
        if value is not None and value not in allowed:
            problems.append(f"{label} references unknown {kind} '{value}'")

    def many(label, values, allowed, kind):
        for v in (values if isinstance(values, list) else []):
            one(label, v, allowed, kind)

    # --- authority: routing + escalation reference its own roles ---
    for om in (authority.get("ownership_map") or []):
        if isinstance(om, dict):
            one(f"authority.ownership_map[{om.get('glob')!r}].role", om.get("role"), roles, "role")
    for esc in (authority.get("escalation") or []):
        if isinstance(esc, dict):
            one(f"authority.escalation L{esc.get('level')}.decider",
                esc.get("decider"), roles | HUMAN, "role")

    # --- workflow: state owners, transition states + gates, gate target states, overlay domains ---
    for st in (workflow.get("states") or []):
        if isinstance(st, dict):
            one(f"workflow.states[{st.get('id')!r}].role", st.get("role"), roles, "role")
    for tr in (workflow.get("transitions") or []):
        if isinstance(tr, dict):
            edge = f"workflow.transition {tr.get('from')}->{tr.get('to')}"
            one(f"{edge}.from", tr.get("from"), states, "state")
            one(f"{edge}.to", tr.get("to"), states, "state")
            many(f"{edge}.entry_gates", tr.get("entry_gates"), gates, "gate")
    for g in (workflow.get("gates") or []):
        if isinstance(g, dict):
            many(f"workflow.gate {g.get('id')!r}.required_for", g.get("required_for"), states, "state")
    # #165: an overlay's add_gates must resolve to the gate REGISTRY — a bare id is a reference,
    # never a definition (the old lenience left overlay gates with no kind/runs/blocking, and the
    # hole was codified in tests; apply_overlay needs the entry's required_for to place the gate).
    for ov_key in sorted(overlays):
        ov = overlays_map[ov_key]
        if isinstance(ov, dict):
            many(f"workflow.domain_overlays[{ov_key!r}].add_gates", ov.get("add_gates"),
                 gates, "gate")
    if domain_ids:
        for ov_key in sorted(overlays):
            one("workflow.domain_overlays key", ov_key, domain_ids, "domain")

    # --- plan: negotiation roles + the plan->scaffold transition gate ---
    if isinstance(plan, dict):
        plan_roles = plan.get("roles")
        if isinstance(plan_roles, dict):
            for role_key, role_val in plan_roles.items():
                one(f"plan.roles.{role_key}", role_val, roles, "role")
        one("plan.gate", plan.get("gate"), gates, "gate")

    # --- rfc: author/reviewer/approver roles + the design->plan transition gate ---
    if isinstance(rfc, dict):
        many("rfc.author_roles", rfc.get("author_roles"), roles, "role")
        many("rfc.reviewer_roles", rfc.get("reviewer_roles"), roles, "role")
        one("rfc.approver_role", rfc.get("approver_role"), roles, "role")
        one("rfc.gate", rfc.get("gate"), gates, "gate")

    # --- risk: the mandatory gate level + per-domain overrides resolve ---
    if isinstance(risk, dict) and levels:
        one("risk.mandatory_gate_level", risk.get("mandatory_gate_level"), levels, "level")
        dov = risk.get("domain_overrides") if isinstance(risk.get("domain_overrides"), dict) else {}
        for dname, override in dov.items():
            if domain_ids:
                one(f"risk.domain_overrides[{dname!r}]", dname, domain_ids, "domain")
            if isinstance(override, dict):
                one(f"risk.domain_overrides[{dname!r}].mandatory_gate_level",
                    override.get("mandatory_gate_level"), levels, "level")

    # --- git: the cross-cutting (non-phase) gate references resolve to the gate registry — the
    #     scope deferred from #62 (6.8), now also the inbound-review gate (M8 8.5). A typo'd
    #     cross-cutting gate id is caught here. ---
    if isinstance(git, dict):
        if isinstance(git.get("traceability"), dict):
            one("git.traceability.gate", git["traceability"].get("gate"), gates, "gate")
        if isinstance(git.get("pr"), dict):
            one("git.pr.review_gate", git["pr"].get("review_gate"), gates, "gate")

    # --- domains: declared roles, role-label keys, and the workflow overlay all resolve ---
    for fname, data in sorted(domains.items()):
        if not isinstance(data, dict):
            continue
        many(f"domains/{fname}.roles", data.get("roles"), roles, "role")
        if isinstance(data.get("role_labels"), dict):
            for rkey in data["role_labels"]:
                one(f"domains/{fname}.role_labels key", rkey, roles, "role")
        one(f"domains/{fname}.workflow_overlay", data.get("workflow_overlay"), overlays,
            "workflow_overlay")

    # --- contribution: the escalation decider resolves to a role / the human terminal, and the
    #     escalation disposition is one the policy itself declares (M8 8.1 — the inbound-review
    #     policy is data, so a typo'd decider/disposition is caught here, not at review time) ---
    if isinstance(contribution, dict):
        esc = contribution.get("escalation")
        if isinstance(esc, dict):
            one("contribution.escalation.decider", esc.get("decider"), roles | HUMAN, "role")
            disp_ids = {d.get("id") for d in (contribution.get("dispositions") or [])
                        if isinstance(d, dict)}
            if esc.get("disposition") is not None and disp_ids and esc["disposition"] not in disp_ids:
                problems.append("contribution.escalation.disposition references unknown disposition "
                                f"'{esc['disposition']}'")

    # --- interaction: conversation-external escalation points at another spec's ladder AS DATA
    #     (M17 17.3, #279). The OS carries exactly one escalation ladder — the authority spec's —
    #     so the pointer resolves to `authority` with a non-empty `escalation:` list. A renamed or
    #     typo'd target is caught here, like the git cross-cutting gate-ref above (#86). ---
    if isinstance(interaction, dict):
        dissent = interaction.get("dissent")
        ladder = dissent.get("escalation_ladder") if isinstance(dissent, dict) else None
        if ladder is not None:
            if ladder != "authority":
                problems.append(f"interaction.dissent.escalation_ladder references unknown spec "
                                f"'{ladder}' — the conversation-external escalation ladder is the "
                                "authority spec (../authority/authority.yaml)")
            elif not (isinstance(authority.get("escalation"), list) and authority.get("escalation")):
                problems.append("interaction.dissent.escalation_ladder names 'authority' but that "
                                "spec declares no escalation ladder to resolve to")

    return problems


def check_cross_spec_consistency(fail):
    name = "cross-spec-consistency"
    if not os.path.isdir(os.path.join(ROOT, "orchestrator", "os")):
        return  # the OS specs arrive with the delivery-OS pivot; absent before it
    authority, workflow = _load_spec("authority"), _load_spec("workflow")
    if not isinstance(authority, dict) or not isinstance(workflow, dict):
        return  # os-spec-completeness reports a missing/unparseable core spec
    problems = cross_spec_problems(authority, workflow, _load_spec("plan"),
                                   _load_spec("rfc"), _load_spec("risk"), _load_domains(),
                                   _load_spec("git"), _load_spec("contribution"),
                                   _load_spec("interaction"))
    for problem in problems:
        fail(name, problem)


# ---------------------------------------------------------------------------
# 12. Version lockstep — EADOS dogfoods the `version-lockstep` gate it ships to generated repos
#     (roadmap 6.7 / F4): every README release badge (EN + i18n) and the CHANGELOG's "latest is"
#     prose must match the CHANGELOG's latest released `## [X.Y.Z]`. The factory is held to the bar
#     it imposes downstream — a release bump now moves every badge + the prose in lockstep or fails.
# ---------------------------------------------------------------------------
RELEASE_BADGE_RE = re.compile(r"release-v(\d+\.\d+\.\d+)")


def version_lockstep_problems(changelog_text, readmes):
    """Pure check: every (label, text) README's `release-vX.Y.Z` badge — and the CHANGELOG's
    'the latest is **vX.Y.Z**' prose — must equal the CHANGELOG's latest released `## [X.Y.Z]`
    heading. Returns a list of problem strings (empty == in lockstep)."""
    releases = re.findall(r"(?m)^##\s*\[(\d+\.\d+\.\d+)\]", changelog_text)
    if not releases:
        return ["CHANGELOG.md has no released `## [X.Y.Z]` heading to lock the badges to"]
    latest = releases[0]   # CHANGELOG is newest-first; `[Unreleased]` is not an X.Y.Z, so skipped
    problems = []
    prose = re.search(r"the latest is \*\*v(\d+\.\d+\.\d+)\*\*", changelog_text)
    if prose and prose.group(1) != latest:
        problems.append(f"CHANGELOG 'the latest is v{prose.group(1)}' != latest release v{latest}")
    for label, text in readmes:
        badge = RELEASE_BADGE_RE.search(text)
        if badge is None:
            problems.append(f"{label}: no `release-vX.Y.Z` badge found")
        elif badge.group(1) != latest:
            problems.append(f"{label}: release badge v{badge.group(1)} != latest release v{latest}")
    return problems


def check_version_lockstep(fail):
    name = "version-lockstep"
    changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
    if not os.path.exists(changelog_path):
        return  # a partial checkout without the changelog — nothing to lock to
    readmes = []
    en = os.path.join(REPO_ROOT, "README.md")
    if os.path.exists(en):
        readmes.append(("README.md", read(en)))
    i18n_dir = os.path.join(ROOT, "docs", "i18n")
    if os.path.isdir(i18n_dir):
        for sub in sorted(os.listdir(i18n_dir)):
            readme = os.path.join(i18n_dir, sub, "README.md")
            if os.path.isfile(readme):
                readmes.append((f"docs/i18n/{sub}/README.md", read(readme)))
    for problem in version_lockstep_problems(read(changelog_path), readmes):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 12.5. Roadmap freshness (#237) — ROADMAP.md declares itself the single source of truth for
#     EADOS's own delivery plan, but nothing enforced that a milestone the CHANGELOG documents as
#     RELEASED actually got a "done" row in the roadmap's status table — the gap that let M10–M14
#     ship undocumented for four consecutive milestones before this check existed. Every milestone
#     number tagged in a RELEASED CHANGELOG section (`(#NNN, M<n>` — the citation style every entry
#     has used since M11) must appear as a done row (`**M<n>` + a ✅ on the same line) in
#     ROADMAP.md's status table. Unreleased milestones (still under `## [Unreleased]`, e.g. M15+)
#     are exempt — they are tracked by their own `.issues/M<n>-*-milestone.md` plan doc until
#     released, per the roadmap-vs-issues-plan-doc split that emerged starting M15.
# ---------------------------------------------------------------------------
_CHANGELOG_MILESTONE_TAG_RE = re.compile(r"\(#\d+,\s*M(\d+)\b")
_ROADMAP_DONE_ROW_RE = re.compile(r"\*\*M(\d+)\b[^\n]*✅")


def roadmap_freshness_problems(changelog_text, roadmap_text):
    """Pure check: every milestone number tagged in a RELEASED CHANGELOG section (text from the
    first `## [X.Y.Z]` heading onward — `[Unreleased]` is excluded) must have a done row in
    ROADMAP.md's status table. Returns problem strings (empty == fresh)."""
    released_start = re.search(r"(?m)^##\s*\[\d+\.\d+\.\d+\]", changelog_text)
    if released_start is None:
        return []  # nothing released yet — nothing to backfill
    released_text = changelog_text[released_start.start():]
    tagged = {int(m) for m in _CHANGELOG_MILESTONE_TAG_RE.findall(released_text)}
    done = {int(m) for m in _ROADMAP_DONE_ROW_RE.findall(roadmap_text)}
    missing = sorted(tagged - done)
    if not missing:
        return []
    names = ", ".join(f"M{n}" for n in missing)
    return [f"ROADMAP.md's status table has no done row for {names} — the CHANGELOG documents "
            f"{'it' if len(missing) == 1 else 'them'} as released; backfill the milestone "
            "section(s) + status row(s) in the same PR (the cross-cutting lockstep invariant)"]


def check_roadmap_freshness(fail):
    name = "roadmap-freshness"
    changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
    roadmap_path = os.path.join(ROOT, "docs", "rfc", "ROADMAP.md")
    if not os.path.exists(changelog_path) or not os.path.exists(roadmap_path):
        return  # a partial checkout without one of the two documents — nothing to check
    for problem in roadmap_freshness_problems(read(changelog_path), read(roadmap_path)):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 13. Manifest-template integrity — orchestrator/project.yaml.template is the one factory file a
#     consumer copies and hand-fills, yet nothing validated it: it is not under templates/** (so
#     placeholder-integrity skips it) and render-smoke renders reference.yaml instead. A broken
#     hand-edit here (invalid YAML, a dropped section, a typo'd `-> {{MARKER}}`) would ship
#     silently. This gate keeps it valid, complete, and well-annotated — the safety net the
#     issue-#90 episode showed was missing for a file external contributors can touch.
# ---------------------------------------------------------------------------
MANIFEST_TEMPLATE = os.path.join(ROOT, "orchestrator", "project.yaml.template")
MANIFEST_SECTIONS = ["schema_version", "domain", "identity", "ownership", "language",
                     "toolchain", "ci", "governance", "i18n", "announce", "spec"]
# A `-> {{MARKER}}` annotation points a field at the placeholder it resolves; capture the optional
# section sigil (#/^//) so both scalars ({{X}}) and sections ({{#EACH_X}}) are validated.
ANNOTATION_RE = re.compile(r"->\s*\{\{\s*([#^/]?)\s*([^{}]*?)\s*\}\}")


def manifest_template_problems(text, scalars, sections):
    """Pure check of the manifest template: (a) parses as a YAML mapping, (b) keeps every expected
    top-level section, (c) every `-> {{MARKER}}` annotation names a placeholder defined in
    placeholders.md. Returns a list of problem strings (empty == clean)."""
    try:
        data = render.load_yaml(text)
    except Exception as exc:                       # a hand-edit that breaks YAML must be caught
        return [f"does not parse as YAML: {exc!r}"]
    if not isinstance(data, dict):
        return ["does not parse to a top-level mapping"]
    problems = [f"missing required top-level section '{s}'" for s in MANIFEST_SECTIONS
                if s not in data]
    known = scalars | sections
    for sigil, name in ANNOTATION_RE.findall(text):
        name = name.strip()
        if not name or name.endswith("_*"):
            continue                               # an illustrative wildcard, not a real placeholder
        if name not in known:
            marker = "{{" + sigil + name + "}}"
            problems.append(f"annotation '-> {marker}' names an undefined placeholder")
    return problems


def check_manifest_template(fail):
    name = "manifest-template"
    if not os.path.exists(MANIFEST_TEMPLATE):
        return  # a partial checkout without the template — nothing to validate
    scalars, sections = known_placeholders()
    for problem in manifest_template_problems(read(MANIFEST_TEMPLATE), scalars, sections):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 14. Data-file validity — the universal floor for the factory's machine-read data: every
#     .eados-core/**/*.yaml must parse with the hand-rolled loader. Most are already loaded by a
#     semantic check (profiles, os-specs, domains, lessons); this also covers the ones nothing else
#     parsed inside the self-lint — questionnaire.yaml, config/defaults.yaml, the reference manifest
#     — so a syntax slip in any data file fails here rather than at a consumer's render.
# ---------------------------------------------------------------------------
def _has_yaml_content(text):
    """True when the file carries at least one line of actual data — blank lines, comments and
    the document markers do not count."""
    for raw in (text or "").split("\n"):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and stripped not in ("---", "..."):
            return True
    return False


def data_file_problems(items):
    """items: (relpath, text) pairs for every tracked .eados-core YAML. Returns a problem per file
    that does not parse, or that parses to NOTHING despite having content — empty == all data files
    are syntactically valid AND were actually read.

    The second half closes a fail-open (#315): this gate treated "did not raise" as "valid", so
    `learning/lessons.yaml` passed for months while the loader discarded all eight of its entries
    and returned `{}`. A gate that cannot fail is not coverage, and reporting a file as valid when
    its content vanished is the worst version of that — it is a gate asserting the opposite of the
    truth."""
    problems = []
    for rel, text in items:
        try:
            data = render.load_yaml(text)
        except Exception as exc:                       # a hand-edit that breaks YAML must be caught
            problems.append(f"{rel}: not valid YAML — {exc!r}")
            continue
        if _has_yaml_content(text) and not data:
            problems.append(f"{rel}: parsed to an empty {type(data).__name__} although the file has "
                            "content — the loader read nothing and did not say so (#315 class); "
                            "'did not raise' is not 'was read'")
    return problems


def check_data_files(fail):
    name = "data-file-validity"
    items = []
    for cur, _dirs, fns in os.walk(ROOT):
        for fn in fns:
            if fn.endswith((".yaml", ".yml")):
                path = os.path.join(cur, fn)
                items.append((os.path.relpath(path, REPO_ROOT).replace("\\", "/"), read(path)))
    for problem in data_file_problems(items):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 14b. Run-record schema — learning/runs/*.yaml is an externally-modifiable data class (per the
#      gate-coverage mandate). record_run.py (#172) gives it a real schema; a malformed record
#      silently poisons the auto-tuner and the lesson audit, so it must be inside the perimeter,
#      not prose. Syntax is data-file-validity's job (parse errors are its report); this validates
#      the STRUCTURE of the records that parse. The empty-dir state (only runs/README.md) is
#      trivially green — there is nothing to validate until the first record lands.
# ---------------------------------------------------------------------------
RUN_RECORD_REQUIRED = ("slug", "date", "lang", "kind", "outcome")


def run_record_problems(records):
    """records: (relpath, parsed_record) pairs. Validate each against the recorder schema
    (record_run.py: the five required keys; outcome vocabulary; date shape; overrides triples;
    failures {gate, message} with the outcome-consistency rule; rubric dims 0-2 drawn from the
    ten). Pure so the contract is unit-testable — empty == every record is well-formed."""
    problems = []

    def bad(rel, msg):
        problems.append(f"{rel}: {msg}")

    for rel, rec in records:
        if not isinstance(rec, dict):
            bad(rel, "a run record must be a YAML mapping")
            continue
        for key in RUN_RECORD_REQUIRED:
            if key not in rec or str(rec.get(key)).strip() == "":
                bad(rel, f"missing or empty required key '{key}'")
        date = str(rec.get("date", "")).strip()
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            bad(rel, f"date '{date}' is not YYYY-MM-DD")
        outcome = rec.get("outcome")
        if outcome is not None and outcome not in record_run.OUTCOMES:
            bad(rel, f"outcome {outcome!r} not one of {'|'.join(record_run.OUTCOMES)}")
        # #215: `phase` is an optional phase tag (records default to scaffold); when present it must
        # name a real delivery phase, so a mistyped phase can't slip into the ledger.
        phase = rec.get("phase")
        if phase is not None and phase not in record_run.PHASES:
            bad(rel, f"phase {phase!r} not one of {'|'.join(record_run.PHASES)}")

        overrides = rec.get("overrides", [])
        if not isinstance(overrides, list):
            bad(rel, "overrides must be a list")
        else:
            for i, ov in enumerate(overrides):
                if not isinstance(ov, dict) or not all(k in ov for k in ("key", "default", "chosen")):
                    bad(rel, f"overrides[{i}] must be a {{key, default, chosen}} mapping")
                elif str(ov.get("key")).strip() == "":
                    bad(rel, f"overrides[{i}] has an empty key")

        failures = rec.get("failures", [])
        if not isinstance(failures, list):
            bad(rel, "failures must be a list")
        else:
            for i, f in enumerate(failures):
                if not isinstance(f, dict) or "gate" not in f or "message" not in f:
                    bad(rel, f"failures[{i}] must be a {{gate, message}} mapping")
                elif str(f.get("gate")).strip() == "":
                    bad(rel, f"failures[{i}] has an empty gate")
            if failures and outcome != "failed":
                bad(rel, "a recorded failure means the run failed — outcome must be 'failed'")

        applied = rec.get("lessons_applied", [])
        if not isinstance(applied, list):
            bad(rel, "lessons_applied must be a list")
        else:
            for lid in applied:
                if not re.fullmatch(r"L-\d{4}", str(lid).strip()):
                    bad(rel, f"lessons_applied entry {lid!r} is not an L-NNNN id")

        rubric = rec.get("rubric", {})
        if not isinstance(rubric, dict):
            bad(rel, "rubric must be a mapping")
        else:
            for dim, score in rubric.items():
                if dim not in record_run.RUBRIC_DIMENSIONS:
                    bad(rel, f"rubric dimension {dim!r} is not one of the ten eval/rubric.md "
                             "dimensions")
                elif str(score).strip() not in ("0", "1", "2"):
                    bad(rel, f"rubric {dim} score {score!r} is not 0, 1, or 2")
    return problems


def check_run_records(fail):
    name = "run-records"
    runs_dir = os.path.join(ROOT, "learning", "runs")
    records = []
    for path in sorted(glob.glob(os.path.join(runs_dir, "*.yaml"))):
        rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
        try:
            rec = render.load_yaml(read(path))
        except Exception:
            continue                        # a syntax error is data-file-validity's report
        records.append((rel, rec))
    for problem in run_record_problems(records):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 15. Gate coverage (meta-gate) — every tracked file is either covered by a named gate or
#     consciously allow-listed as human-reviewed prose (with a reason). A NEW file class that
#     nobody gated fails CI until it is gated or allow-listed — so coverage can never silently
#     regress. This is the enforcement behind "gate every externally-modifiable file": the
#     issue-#90 episode (project.yaml.template was gated by nothing) becomes structurally
#     impossible to repeat. `*` matches within a path segment; `**` spans directories.
# ---------------------------------------------------------------------------
GATE_COVERAGE = [
    (".eados-core/templates/**",                          "render-smoke + placeholder-integrity + action-pins/pin-label-truth (.github/workflows/*.tmpl)"),
    (".eados-core/orchestrator/profiles/*.yaml",          "profile-completeness"),
    (".eados-core/orchestrator/profiles/_schema.md",      "profile-completeness (schema)"),
    (".eados-core/orchestrator/os/**",                    "os-spec-completeness + cross-spec-consistency + gate-executability (workflow runs:) + routing-delegation (os/routing/delegation.md) + interaction-lockstep (os/interaction/ <-> AGENTS.md + templates/AGENTS.md.tmpl)"),
    (".eados-core/orchestrator/domains/*.yaml",           "domains + data-file-validity"),
    (".eados-core/orchestrator/placeholders.md",          "placeholder-integrity (the dictionary)"),
    (".eados-core/orchestrator/generate.md",              "generate-references"),
    (".eados-core/orchestrator/project.yaml.template",    "manifest-template"),
    (".eados-core/orchestrator/examples/*.yaml",          "render-smoke (the reference manifest)"),
    (".eados-core/orchestrator/questionnaire.yaml",       "data-file-validity"),
    (".eados-core/orchestrator/triage.yaml",              "examples + data-file-validity"),
    (".eados-core/config/defaults.yaml",                  "data-file-validity"),
    (".eados-core/agent/*.md",                            "agent-registry"),
    (".eados-core/learning/lessons.yaml",                 "lessons + data-file-validity"),
    (".eados-core/learning/scope-examples.yaml",          "examples + data-file-validity"),
    (".eados-core/learning/runs/**",                      "run-records (schema) + data-file-validity"),
    (".eados-core/tools/*.py",                            "byte-compile + unit tests (CI)"),
    (".eados-core/tools/tests/*.py",                      "byte-compile + unit tests (CI)"),
    (".eados-core/docs/i18n/**",                          "i18n-freshness"),
    ("README.md",                                         "version-lockstep + i18n-freshness"),
    ("CHANGELOG.md",                                      "version-lockstep"),
    (".github/workflows/*.yml",                           "action-pins + pin-label-truth + workflow-safety"),
    ("setup/*.sh",                                        "installer-smoke (test_setup_sh.py) + shellcheck (CI)"),
    ("setup/*.command",                                   "installer-smoke (test_setup_sh.py) + shellcheck (CI)"),
    ("setup/*.ps1",                                       "installer-smoke (test_setup_ps1.py) + PowerShell parse-check (CI)"),
    (".claude/commands/**",                               "command-adapters (every available command row ships its pointer adapter)"),
]
# Intentionally NOT machine-validated — prose/config under human review. Each needs a reason; this
# is the conscious record of "we looked and chose not to gate this", not a blind skip.
GATE_ALLOWLIST = [
    ("AGENTS.md",                                  "human-reviewed prose, PARTLY gated — interaction-lockstep (§10) + git-scope-lockstep (§6 vocabulary)"),
    ("CLAUDE.md",                                  "agent contract — human-reviewed prose"),
    ("GEMINI.md",                                  "agent contract — human-reviewed prose"),
    ("CONTRIBUTING.md",                            "governance prose — human-reviewed"),
    ("SECURITY.md",                                "governance prose — human-reviewed"),
    ("LICENSE",                                    "license text — render.py's source, exercised by render-smoke"),
    (".gitattributes",                             "VCS / bundle export-ignore config"),
    (".gitignore",                                 "VCS config"),
    (".eados-dev",                                 "repo marker file"),
    (".portfolio.json",                            "portfolio-card metadata"),
    (".issues/**",                                 "issue drafts / milestone backlog — human-reviewed prose"),
    (".github/CODEOWNERS",                         "GitHub config"),
    (".github/dependabot.yml",                     "GitHub config"),
    (".github/PULL_REQUEST_TEMPLATE.md",           "GitHub PR template"),
    (".github/ISSUE_TEMPLATE/**",                  "GitHub issue forms"),
    (".eados-core/README.md",                      "bundle entry-point prose"),
    (".eados-core/orchestrator/*.md",              "orchestrator playbook prose (interview, recovery, …)"),
    (".eados-core/orchestrator/commands/*.md",     "phase command playbook prose"),
    (".eados-core/orchestrator/domains/*.md",      "domain schema/readme prose"),
    (".eados-core/agent/domains/**",               "domain persona prose"),
    (".eados-core/config/*.md",                    "config prose (README, house-rules)"),
    (".eados-core/config/agents/**",               "user role-override dir"),
    (".eados-core/learning/*.md",                  "learning-ledger prose"),
    (".eados-core/docs/*.md",                      "docs prose (USAGE, walkthrough)"),
    (".eados-core/docs/adr/**",                    "ADR prose"),
    (".eados-core/docs/rfc/**",                    "RFC / roadmap / diagram prose"),
    (".eados-core/eval/**",                        "eval rubric prose"),
    (".eados-core/maintenance/**",                 "maintenance prose"),
    (".eados-core/tools/requirements-ci.txt",      "CI pinned + hashed deps (render-smoke)"),
    ("setup/*.bat",                                "Windows cmd double-click shim - trivial pass-through to setup.ps1 (the logic + its gate live there); no Linux analyzer"),
]


def _glob_re(pattern):
    """gitignore-ish glob: `*` matches within a path segment, `**` spans directories."""
    out, i = [], 0
    while i < len(pattern):
        if pattern[i:i + 2] == "**":
            out.append(".*"); i += 2
        elif pattern[i] == "*":
            out.append("[^/]*"); i += 1
        elif pattern[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(pattern[i])); i += 1
    return re.compile("^" + "".join(out) + "$")


def gate_coverage_problems(tracked, covered=GATE_COVERAGE, allowlist=GATE_ALLOWLIST):
    """tracked: repo-relative paths. A problem for any file matched by neither a covered nor an
    allow-listed pattern. Pure (the registry is injectable) so the contract is unit-testable."""
    cov = [_glob_re(p) for p, _ in covered]
    allow = [_glob_re(p) for p, _ in allowlist]
    problems = []
    for path in tracked:
        if any(rx.match(path) for rx in cov):
            continue
        if any(rx.match(path) for rx in allow):
            continue
        problems.append(f"{path}: no gate covers it and it is not allow-listed — add a validating "
                        f"gate (GATE_COVERAGE) or, if it is reviewed prose, a GATE_ALLOWLIST entry")
    return problems


def check_gate_coverage(fail):
    name = "gate-coverage"
    tracked = _tracked_files()
    if tracked is None:
        return  # not a git checkout (e.g. an extracted bundle) — cannot enumerate the tree
    for problem in gate_coverage_problems(tracked):
        fail(name, problem)
    # registry hygiene: a pattern that matches nothing is dead weight / a moved path — surface it.
    for pattern, _ in GATE_COVERAGE + GATE_ALLOWLIST:
        rx = _glob_re(pattern)
        if not any(rx.match(t) for t in tracked):
            fail(name, f"stale registry entry — pattern matches no tracked file: '{pattern}'")


def _tracked_files():
    """The repo's tracked files (git ls-files), repo-relative with forward slashes. None when not
    in a git checkout — the meta-gate then skips, like the other checks do on a partial tree."""
    try:
        out = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 16. Workflow safety — the external-contributor *security* surface. A workflow triggered by
#     `pull_request_target` or `workflow_run` runs with the base repo's secrets + write token on a
#     partially-untrusted event; combined with checking out PR-authored code it is the classic
#     secret-exfiltration / self-merge vector. Such triggers are forbidden — in this repo's own
#     workflows AND in the workflow templates shipped to every generated repo (a bad trigger there
#     has the widest blast radius) — unless a workflow is allow-listed with a justification.
#     Complements `action-pins` (which pins action SHAs); this guards the trigger surface.
# ---------------------------------------------------------------------------
SENSITIVE_TRIGGERS = ("pull_request_target", "workflow_run")
WORKFLOW_SAFETY_ALLOWLIST = {
    "dependabot-pin-sync.yml":
        "ADR-0013 — workflow_run runs the trusted default-branch workflow definition (never PR "
        "code), gated to actor==dependabot[bot] + same-repo (no forks), and executes only the "
        "repo's deterministic sync_action_pins.py.",
}
_TRIGGER_KEY_RE = re.compile(r"(?m)^\s{0,6}(pull_request_target|workflow_run)\s*:")
_ON_INLINE_RE = re.compile(r"(?m)^on\s*:\s*[\[{](.+)[\]}]\s*$")


def workflow_safety_problems(items, allowlist=WORKFLOW_SAFETY_ALLOWLIST):
    """items: (name, text) for each workflow (this repo's *.yml + the rendered *.tmpl). Flags any
    that uses a sensitive trigger unless allow-listed. `name` is the basename so a workflow and its
    template share one allow-list key. Pure (allow-list injectable) so the contract is testable."""
    problems = []
    for name, text in items:
        triggers = set(_TRIGGER_KEY_RE.findall(text))
        inline = _ON_INLINE_RE.search(text)
        if inline:
            triggers.update(t for t in SENSITIVE_TRIGGERS
                            if re.search(r"\b" + t + r"\b", inline.group(1)))
        if triggers and name not in allowlist:
            problems.append(f"{name}: uses sensitive trigger(s) {sorted(triggers)} that run with "
                            f"repository secrets on a partially-untrusted event — review and add to "
                            f"WORKFLOW_SAFETY_ALLOWLIST with a justification, or use pull_request/push")
    return problems


def _workflow_items():
    """(basename, text) for this repo's workflows + the rendered workflow templates. A template's
    trailing '.tmpl' is dropped so it shares an allow-list key with its rendered form."""
    items = []
    for root in (os.path.join(REPO_ROOT, ".github", "workflows"),
                 os.path.join(ROOT, "templates", ".github", "workflows")):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.endswith((".yml", ".yaml", ".tmpl")):
                base = fn[:-5] if fn.endswith(".tmpl") else fn
                items.append((base, read(os.path.join(root, fn))))
    return items


def check_workflow_safety(fail):
    name = "workflow-safety"
    items = _workflow_items()
    if not items:
        return  # a partial checkout without workflows
    for problem in workflow_safety_problems(items):
        fail(name, problem)
    # hygiene: an allow-list entry for a workflow that is gone, or no longer uses a sensitive
    # trigger, is stale — surface it so the allow-list stays honest.
    by_name = {}
    for n, text in items:
        by_name.setdefault(n, text)
    for fname in WORKFLOW_SAFETY_ALLOWLIST:
        if fname not in by_name:
            fail(name, f"workflow-safety allow-list names a missing workflow: '{fname}'")
        elif not workflow_safety_problems([(fname, by_name[fname])], allowlist={}):
            fail(name, f"workflow-safety allow-list entry no longer needed (no sensitive trigger): "
                       f"'{fname}'")


# ---------------------------------------------------------------------------
# 17. Gate executability — the data→code seam of the workflow spec (#164). workflow.yaml's gate
#     registry documents `runs:` commands and `wired:` execution claims, but nothing executed the
#     declarative side, so it had already drifted (the documented `render.py --check` did not
#     exist). This check keeps the data honest: every `python <script> …` gate must name a script
#     that exists — in the factory checkout, or shipped under templates/ into every generated
#     repo — whose source mentions each `--flag` it is invoked with (a cheap static proxy for
#     "the flag is real"), and the set of gates marked `wired: in-process` must equal the
#     GATE_EVALUATORS registry in eados.py, so a gate wired (or unwired) in code without
#     updating the data fails here instead of rotting silently.
# ---------------------------------------------------------------------------
GATE_WIRED_VALUES = {"in-process", "external"}


def wired_in_process_ids(eados_source):
    """Gate ids the checker evaluates in-process, read statically from eados.py's
    GATE_EVALUATORS dict source (no import: the lint stays side-effect-free)."""
    m = re.search(r"GATE_EVALUATORS\s*=\s*\{(.*?)\}", eados_source, re.DOTALL)
    return set(re.findall(r"\"([\w-]+)\"\s*:", m.group(1))) if m else set()


def gate_executability_problems(gates, find_script, wired_in_code):
    """Pure check of the gate registry's executable claims. `gates`: workflow.yaml gates[];
    `find_script(rel)` -> the script's source text or None if it exists nowhere;
    `wired_in_code`: gate ids evaluated in-process. Returns problem strings (empty == honest)."""
    problems = []
    wired_in_data = set()
    for g in (gates if isinstance(gates, list) else []):
        if not isinstance(g, dict):
            continue
        gid = g.get("id", "?")
        wired = g.get("wired")
        if wired not in GATE_WIRED_VALUES:
            problems.append(f"gate '{gid}': wired must be one of "
                            f"{sorted(GATE_WIRED_VALUES)}, got {wired!r}")
        elif wired == "in-process":
            wired_in_data.add(gid)
        runs = str(g.get("runs") or "")
        if not runs.startswith("python "):
            continue                       # manual:/human: gates make no executable claim
        tokens = runs.split()
        script = tokens[1] if len(tokens) > 1 else ""
        source = find_script(script)
        if source is None:
            problems.append(f"gate '{gid}': runs references missing script '{script}'")
            continue
        for flag in (t for t in tokens[2:] if t.startswith("--")):
            if flag not in source:
                problems.append(f"gate '{gid}': script '{script}' does not know flag '{flag}'")
    for gid in sorted(wired_in_data - wired_in_code):
        problems.append(f"gate '{gid}' claims wired: in-process but eados.py's "
                        "GATE_EVALUATORS has no entry for it")
    for gid in sorted(wired_in_code - wired_in_data):
        problems.append(f"eados.py evaluates gate '{gid}' in-process but workflow.yaml "
                        "does not mark it wired: in-process")
    return problems


def find_gate_script(rel):
    """Resolve a gate's script path to its source text: a factory path (repo-root-relative,
    e.g. .eados-core/tools/render.py) or a generated-repo path the factory ships via
    templates/ (e.g. tools/consistency_lint.py, with or without a .tmpl suffix)."""
    for cand in (os.path.join(REPO_ROOT, rel.replace("/", os.sep)),
                 os.path.join(TEMPLATES, rel.replace("/", os.sep)),
                 os.path.join(TEMPLATES, rel.replace("/", os.sep) + ".tmpl")):
        if os.path.isfile(cand):
            return read(cand)
    return None


def check_gate_executability(fail):
    name = "gate-executability"
    workflow = _load_spec("workflow")
    if not isinstance(workflow, dict):
        return  # a missing/unparseable workflow spec is os-spec-completeness's report
    wired = wired_in_process_ids(read(os.path.join(TOOLS, "eados.py")))
    for problem in gate_executability_problems(workflow.get("gates"), find_gate_script, wired):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 19. Worked-example decision surfaces (#224) — the judgment-laden "which way?" calls that used to
#     live only as prose (ask-vs-default in the interview, adopt/decline/escalate on a contribution,
#     apply-vs-skip a lesson's scope) are now few-shot policy AS DATA: an `examples:` block with a
#     verdict vocabulary and labelled cases. This validates their SHAPE only (never that the agent
#     obeyed them — that stays the reviewer's job, exactly like the lessons ledger): every case has
#     input+verdict+why, verdicts are drawn from the block's declared set, and the block covers >= 2
#     verdicts with >= 2 cases each (a genuine decision surface — >= 2 "positive" + >= 2 "negative").
# ---------------------------------------------------------------------------
EXAMPLE_FILES = (
    "orchestrator/os/contribution/contribution.yaml",   # adopt / decline / escalate
    "orchestrator/questionnaire.yaml",                  # ask / default
    "learning/scope-examples.yaml",                     # apply / skip (companion to the lessons ledger)
    "orchestrator/triage.yaml",                         # answer / focused-change / five-step-loop (Step-0)
    "orchestrator/os/routing/routing.yaml",             # fast / standard / frontier-reasoning (tier calls)
)
EXAMPLE_CASE_REQUIRED = ("input", "verdict", "why")


def examples_problems(name, data):
    """Pure shape check of one `examples:` block (a mapping with `verdicts` + `cases`). Returns a
    list of problem strings (empty == a well-formed decision surface). No I/O — unit-testable."""
    problems = []
    ex = data.get("examples") if isinstance(data, dict) else None
    if ex is None:
        return [f"{name}: no `examples:` block — issue #224 requires a worked-example decision surface"]
    if not isinstance(ex, dict):
        return [f"{name}: `examples:` must be a mapping with `verdicts` and `cases`"]
    verdicts = ex.get("verdicts")
    if not isinstance(verdicts, list) or len(verdicts) < 2:
        problems.append(f"{name}: `examples.verdicts` must list >= 2 allowed verdicts")
        verdicts = verdicts if isinstance(verdicts, list) else []
    vset = {str(v).strip() for v in verdicts}
    cases = ex.get("cases")
    if not isinstance(cases, list) or not cases:
        problems.append(f"{name}: `examples.cases` must be a non-empty list")
        cases = []
    counts = {}
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            problems.append(f"{name}: `examples.cases[{i}]` must be a mapping")
            continue
        for key in EXAMPLE_CASE_REQUIRED:
            if not str(case.get(key, "")).strip():
                problems.append(f"{name}: `examples.cases[{i}]` missing/empty '{key}'")
        verdict = str(case.get("verdict", "")).strip()
        if verdict and vset and verdict not in vset:
            problems.append(f"{name}: `examples.cases[{i}]` verdict '{verdict}' not in "
                            f"verdicts {sorted(vset)}")
        elif verdict:
            counts[verdict] = counts.get(verdict, 0) + 1
    covered = [v for v, n in counts.items() if n >= 2]
    if len(covered) < 2:
        problems.append(f"{name}: `examples` must cover >= 2 verdicts with >= 2 cases each "
                        f"(>= 2 positive + >= 2 negative); have {counts or '{}'}")
    return problems


def check_examples(fail):
    name = "examples"
    for rel in EXAMPLE_FILES:
        path = os.path.join(ROOT, *rel.split("/"))
        if not os.path.exists(path):
            fail(name, f"{rel}: expected an `examples:` decision surface (#224) but the file is missing")
            continue
        try:
            data = render.load_yaml(read(path))
        except (ValueError, OSError) as exc:
            fail(name, f"{rel}: cannot parse for the examples check ({exc!r})")
            continue
        for problem in examples_problems(rel, data):
            fail(name, problem)


# ---------------------------------------------------------------------------
# 19. safe-write containment (#235, guards #195/#196) — every file write in the factory's tools
#     must route through `sandbox` (safe_write/resolve), the single guarded sink that closed the
#     `render --in-place` clobber (#195) and the `.git`-segment escape (#196). render.write_file
#     is now a pure delegator to sandbox.safe_write; a tool that opens its own truncating write
#     path bypasses the containment + no-clobber + `.git` refusal and silently re-opens that defect
#     class. The factory-internal writers that legitimately write OUTSIDE a rendered repo — the
#     learning ledger, a maintainer `--out`, the factory's own workflow templates — are allow-listed
#     WITH a justification (mirroring WORKFLOW_SAFETY_ALLOWLIST), and the sandbox primitive itself is
#     the sink they all funnel into. Symmetric hygiene: an allow-list entry that no longer writes
#     directly is flagged stale, exactly like workflow-safety and agent-registry.
# ---------------------------------------------------------------------------
SAFE_WRITE_ALLOWLIST = {
    "sandbox.py": "the guarded write primitive itself — safe_write's open() is the single sink "
                  "every other writer funnels through (containment + .git refusal + no-clobber)",
    "record_run.py": "writes the factory's own learning ledger under learning/runs/ with its own "
                     "#197 same-day no-clobber suffix; never a rendered-repo path",
    "derive_links.py": "writes the traceability links file to an explicit maintainer --out (or "
                       "stdout) — a CI/factory artifact, not a rendered repo file",
    "sync_action_pins.py": "rewrites the factory's OWN templates/**/.github workflows in --fix "
                           "mode; never a rendered-repo path",
}

# The lint reads its own source when it walks the tools dir; its regex literals below name the very
# write verbs it hunts for, which would self-trip. A lint that performs no file writes need not
# police itself — exclude it rather than allow-list it (an entry that never fires reads as noise).
SAFE_WRITE_UNSCANNED = {"eados_lint.py"}

# Direct file-creation/write sites: open(...) with a w/a/x/+ mode, pathlib write_*, os.replace/
# rename, shutil copy/move. A static proxy (like gate-executability's flag check) — good enough to
# catch a new private write path; the allow-list carries the reviewed exceptions.
_DIRECT_WRITE_RE = re.compile(
    r"""open\([^)]*["'][rbt+]*[wax][rwaxbt+]*["']"""             # open(..., "w"/"a"/"x"/"w+"/"wb"…)
    r"""|\.write_text\(|\.write_bytes\("""                       # pathlib.Path.write_*
    r"""|\bos\.(?:replace|rename)\("""                           # atomic replace / rename
    r"""|\bshutil\.(?:copy|copyfile|copy2|copytree|move)\("""    # shutil file copy/move
)


def _strip_line_comments(text):
    """Drop whole-line `#` comments so a commented-out example write isn't flagged. Inline comments
    and docstrings are left in — a proxy check tolerates the rare docstring hit, and the
    guard-required scope plus the allow-list keep false positives out of practice."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def safe_write_problems(items, allowlist=SAFE_WRITE_ALLOWLIST):
    """items: (basename, source_text) per tool module. Flags a direct file-write outside the
    allow-list. Pure (allow-list injectable) so the synthetic-direct-write contract is testable."""
    problems = []
    for name, text in items:
        if name in allowlist:
            continue
        if _DIRECT_WRITE_RE.search(_strip_line_comments(text)):
            problems.append(
                f"{name}: opens a file for writing directly instead of routing through "
                f"sandbox.safe_write — the containment / .git / no-clobber guard that closed "
                f"#195/#196 is bypassed. Delegate to sandbox.safe_write/resolve, or add '{name}' "
                f"to SAFE_WRITE_ALLOWLIST with a justification if it writes outside a rendered repo")
    return problems


def _tool_sources():
    """(basename, source) for each production tool module (tests/, __pycache__, and the lint's own
    self-tripping source excluded)."""
    items = []
    for fn in sorted(os.listdir(TOOLS)):
        if fn.endswith(".py") and fn not in SAFE_WRITE_UNSCANNED:
            items.append((fn, read(os.path.join(TOOLS, fn))))
    return items


def check_safe_write(fail):
    name = "safe-write"
    items = _tool_sources()
    if not items:
        return  # a partial checkout without the tools
    for problem in safe_write_problems(items):
        fail(name, problem)
    by_name = {n: t for n, t in items}
    for fname in SAFE_WRITE_ALLOWLIST:
        if fname not in by_name:
            fail(name, f"safe-write allow-list names a missing tool: '{fname}'")
        elif not safe_write_problems([(fname, by_name[fname])], allowlist={}):
            fail(name, f"safe-write allow-list entry no longer needed (no direct write): '{fname}'")


# ---------------------------------------------------------------------------
# 20. Command adapters (#239, ADR-0019 class 4) — every AVAILABLE row of the canonical command
#     table (orchestrator/commands/README.md) must ship its Claude Code adapter at
#     .claude/commands/eados/<name>.md, and every adapter must be a genuine POINTER at the row's
#     own procedure file (it carries the canonical path; the procedure stays the single source of
#     truth). ALIAS adapters (#241): a live (non-planned) alias-table row — e.g. `security` ->
#     `/eados audit` — MAY ship an adapter too; it is optional, and when present it must point at
#     its TARGET command's procedure (an alias routes, never adds behavior). Symmetric, like
#     agent-registry: an orphan adapter matching neither an available row nor a live alias is
#     stale (a planned command/alias must not ship an adapter before it flips live). Runs only
#     in the factory checkout (the `.eados-dev` sentinel): a consumer who installed the bundle
#     and declined the adapters must not fail their own self-lint.
# ---------------------------------------------------------------------------
# The command table is parsed by `command_registry` (#373) — the CLI reads the same rows, and a
# second matcher for the same table is a second list to drift, which is the defect #365/#366 each
# spent a gate closing. The alias table below is this check's alone, so it stays here.
# Alias-table rows: `| <verb(s)> | ... `/eados <target>` ... | <class> | <ref> |`. The verbs cell
# may carry several backticked verbs (the design sub-modes row); the ref cell's `planned` marker
# excludes a row (the alias is not live yet). Command-table rows cannot match: their SECOND cell
# is a bare phase name, never a backticked `/eados <cmd>`.
# The lazy `[^|]*?` matters: a routes-to cell may carry several `/eados X` tokens (`interview` ->
# init, with a brownfield `adopt` aside) and the FIRST one is the alias's target — a greedy
# quantifier would capture the last.
_ALIAS_ROW_RE = re.compile(
    r"^\|([^|]+)\|[^|]*?`/eados (\w+)`[^|]*\|[^|]*\|([^|]*)\|", re.MULTILINE)
_ALIAS_VERB_RE = re.compile(r"`(\w+)`")


def command_adapter_problems(readme_text, adapters, where=".claude/commands/eados", ext=".md",
                             host="Claude Code", prefix=""):
    """Pure check. `readme_text`: orchestrator/commands/README.md; `adapters`: {name: file text}
    for .claude/commands/eados/*.md. Every available `/eados <name>` row needs an adapter whose
    text carries the row's own canonical procedure path (the pointer contract). A LIVE alias-table
    verb (#241) may optionally ship an adapter pointing at its TARGET's procedure. Every adapter
    needs one of the two (no orphans). Returns problem strings (empty == covered)."""
    rows = [(c["name"], c["procedure"]) for c in command_registry.parse(readme_text)]
    if not rows:
        return ["could not parse any available `/eados <name>` rows from commands/README.md — "
                "the adapter-coverage contract has nothing to check against"]
    problems = []
    available = {}
    for cmd, procedure in rows:
        available[cmd] = procedure
    # Live aliases: verb -> the TARGET command's canonical procedure. A `planned` ref cell or a
    # target that is not itself available keeps the alias out (not live yet).
    aliases = {}
    for verbs_cell, target, ref_cell in _ALIAS_ROW_RE.findall(readme_text):
        if "planned" in ref_cell or target not in available:
            continue
        for verb in _ALIAS_VERB_RE.findall(verbs_cell):
            if verb not in available:
                aliases[verb] = available[target]
    for cmd, proc in sorted(available.items()):
        if cmd not in adapters:
            problems.append(f"{where}/{prefix}{cmd}{ext} is missing — every available "
                            f"`/eados {cmd}` row must ship its {host} adapter (#239)")
        elif proc not in adapters[cmd]:
            problems.append(f"{where}/{prefix}{cmd}{ext} does not point at its canonical "
                            f"procedure `{proc}` — an adapter is a pointer, never a copy "
                            "(ADR-0019 class 4)")
    for cmd in sorted(adapters):
        if cmd in available:
            continue
        if cmd in aliases:
            if aliases[cmd] not in adapters[cmd]:
                problems.append(f"{where}/{prefix}{cmd}{ext} is an alias adapter but does "
                                f"not point at its target's canonical procedure `{aliases[cmd]}` "
                                "— an alias routes, never adds behavior (ADR-0019 class 4, #241)")
            continue
        problems.append(f"{where}/{prefix}{cmd}{ext} matches no available `/eados {cmd}` row "
                        "and no live alias-table verb — a planned command/alias must not ship an "
                        "adapter before it flips live (orphan adapter)")
    return problems


def _adapter_hosts():
    """`[(host_id, commands_block)]` for every host declaring a PROJECT-scoped command tree — read
    from `os/routing/routing.yaml`, so admitting a host is a data change (#375, ADR-0019 addendum).
    A `home`/`none` host has no tree in the repository to hold to anything."""
    try:
        import route_advice
        spec = route_advice.load_routing()
    except Exception:      # noqa: BLE001 — an unreadable routing spec is os-spec-completeness's report
        return []
    out = []
    for h in (spec.get("catalog") or {}).get("hosts") or []:
        block = h.get("commands") if isinstance(h, dict) else None
        if isinstance(block, dict) and block.get("scope") == "project" and block.get("dir"):
            out.append((h.get("id"), block))
    return out


def check_command_adapters(fail):
    name = "command-adapters"
    if not os.path.exists(os.path.join(REPO_ROOT, ".eados-dev")):
        return  # a consumer install (bundle), where the adapters are opt-in — factory-only check
    readme_path = os.path.join(ROOT, "orchestrator", "commands", "README.md")
    if not os.path.exists(readme_path):
        return  # a partial checkout without the command surface
    readme = read(readme_path)
    # EVERY project-scoped host, not just Claude Code (#375). The trees are generated on demand
    # (`adapter_render.py`), and whether a consumer COMMITS one is #372's open question — so a
    # declared-but-absent tree is fine, and only a tree that EXISTS is held to the contract. A
    # present tree that has fallen behind the registry is exactly the drift this gate is for.
    for host, block in _adapter_hosts():
        adapter_dir = os.path.join(REPO_ROOT, *block["dir"].split("/"))
        if not os.path.isdir(adapter_dir):
            continue
        ext = block.get("ext") or ".md"
        prefix = "" if block.get("nest") else "eados-"
        adapters = {}
        for fn in sorted(os.listdir(adapter_dir)):
            if fn.endswith(ext) and fn.startswith(prefix):
                adapters[fn[:-len(ext)][len(prefix):]] = read(os.path.join(adapter_dir, fn))
        if not adapters:
            continue
        for problem in command_adapter_problems(readme, adapters, where=block["dir"], ext=ext,
                                                host=host, prefix=prefix):
            fail(name, problem)


# A host matrix ROW: a table line whose first cell bolds the host id. Anchored to `|` + `**…**` so
# a host named in ordinary prose is not mistaken for a declaration — the distinction the substring
# test could not make.
_MATRIX_ROW = re.compile(r"(?m)^\|\s*\*\*([a-z0-9][a-z0-9-]*)\*\*(.*)$")


def matrix_hosts(text):
    """`{host id -> posture}` from delegation.md's application matrix, where posture is
    'applied' / 'advisory-only' / None (the row declares neither)."""
    out = {}
    for host, rest in _MATRIX_ROW.findall(text or ""):
        low = rest.lower()
        # `advisory-only` contains no 'applied', and the applied row says '**applied**' — check the
        # more specific one first so a row mentioning both words still resolves deterministically.
        posture = "advisory-only" if "advisory-only" in low else (
            "applied" if "applied" in low else None)
        out[host] = posture
    return out


def routing_delegation_problems(delegation_text, readme_text, schema_text, routing_spec):
    """Pure check of the 16.4 delegation-hook contract (#255). The advice policy is *applied* only
    in `os/routing/delegation.md`; this keeps that doc honest and wired. Fails when the doc is
    unreferenced by its two pointers (commands/README.md, os/routing/_schema.md), does not name the
    evaluator it delegates resolution to, omits the advisory-only fallback, or leaves any catalog
    host without a stated delegation posture (the anti-rot property — a host added to the catalog
    must declare applied-vs-advisory in the matrix). Returns problem strings (empty == covered)."""
    problems = []
    if "delegation.md" not in (readme_text or ""):
        problems.append("orchestrator/commands/README.md does not point at "
                        "os/routing/delegation.md — the Host-adapters section must carry the "
                        "routing hook (#255)")
    if "delegation.md" not in (schema_text or ""):
        problems.append("orchestrator/os/routing/_schema.md does not reference delegation.md — "
                        "the applied-path doc must be linked from the routing schema (#255)")
    if "route_advice" not in (delegation_text or ""):
        problems.append("os/routing/delegation.md does not name route_advice.py — the hook must "
                        "resolve routes through the evaluator, not restate the policy")
    if "advisory" not in (delegation_text or "").lower():
        problems.append("os/routing/delegation.md documents no advisory-only fallback — hosts "
                        "without per-delegation model control must have a stated posture (#255)")
    # --- the host matrix, checked BOTH ways (#327) -------------------------------------------
    # This ran one way only — catalog -> matrix — which is the #202 defect class: a registry check
    # walked in a single direction validates half a relationship and reports it as whole. The
    # reverse is where the rot actually was: the matrix documented `codex` and `gemini` for a
    # milestone while the catalog had neither, so `route_advice.py --host codex` failed on a host
    # the documentation said was supported.
    #
    # Rows are read STRUCTURALLY, not by substring. delegation.md legitimately names hosts in
    # prose ("Run the same relay on codex or gemini…"), and a substring test reads those as
    # declarations — so deleting a real matrix row would keep passing.
    declared = matrix_hosts(delegation_text or "")
    if routing_spec is not None:
        # Both directions need both sides. With the spec absent or unparseable there is nothing to
        # compare against — and the reverse loop would then flag EVERY row as undeclared, turning a
        # parse failure into a wall of misleading errors. That failure is data-file-validity's to
        # report; here it means "cannot check", not "everything is wrong".
        hosts = [str(h.get("id"))
                 for h in ((routing_spec.get("catalog") or {}).get("hosts") or [])
                 if isinstance(h, dict) and h.get("id")]
        for host in hosts:
            if host not in declared:
                problems.append(f"os/routing/delegation.md has no matrix ROW for catalog host "
                                f"'{host}' — add one declaring applied or advisory-only, so a new "
                                "host cannot ship without a stated delegation posture")
        for host in declared:
            if host not in hosts:
                problems.append(f"os/routing/delegation.md declares a delegation posture for "
                                f"'{host}', which is not a catalog host — add it to "
                                "`routing.yaml` `catalog.hosts` or drop the row; documenting a host "
                                "the evaluator cannot resolve is worse than not documenting it")
    for host, posture in declared.items():
        if posture is None:
            problems.append(f"os/routing/delegation.md's row for '{host}' states neither "
                            "'applied' nor 'advisory-only' — the posture is the point of the row")
    return problems


def check_routing_delegation(fail):
    name = "routing-delegation"
    routing_dir = os.path.join(ROOT, "orchestrator", "os", "routing")
    routing_yaml = os.path.join(routing_dir, "routing.yaml")
    if not os.path.exists(routing_yaml):
        return  # routing is introduced with M16; absent before it
    delegation_path = os.path.join(routing_dir, "delegation.md")
    if not os.path.exists(delegation_path):
        fail(name, "orchestrator/os/routing/delegation.md is missing — the 16.4 delegation-hook "
                   "contract (#255) is unspecified")
        return
    readme_path = os.path.join(ROOT, "orchestrator", "commands", "README.md")
    schema_path = os.path.join(routing_dir, "_schema.md")
    try:
        routing_spec = render.load_yaml(read(routing_yaml))
    except Exception:  # noqa: BLE001 — a parse failure is data-file-validity's to report
        routing_spec = None
    for problem in routing_delegation_problems(
            read(delegation_path),
            read(readme_path) if os.path.exists(readme_path) else "",
            read(schema_path) if os.path.exists(schema_path) else "",
            routing_spec):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 21. Interaction lockstep (#279, M17 17.3) — the interaction policy is data (os/interaction/
#     interaction.yaml, ADR-0022); 17.2 rendered it into the two agent contracts (factory
#     AGENTS.md §10 + templates/AGENTS.md.tmpl §12). Nothing stopped the prose and the data from
#     drifting — the exact failure class version-lockstep / i18n-freshness exist for. This gate
#     keeps them congruent: every `sycophancy.banned_openers` phrase and every `confidence.levels`
#     tag in the spec must appear in EACH rendered surface. Data is the source of truth; prose may
#     elaborate, but it may never omit an entry (a dropped banned phrase or confidence tag = the
#     contract silently diverging from the policy). Presence, not paraphrase — the enforceable
#     proxy for "never contradict or omit", mirroring version-lockstep's badge-equality check.
# ---------------------------------------------------------------------------
def interaction_lockstep_problems(interaction, surfaces):
    """Pure check. `interaction`: the parsed interaction.yaml; `surfaces`: (label, text) pairs for
    each rendered contract surface. Every banned opener and every confidence tag the spec declares
    must be present verbatim in each surface. Returns problem strings (empty == congruent). I/O-free
    so the contract is unit-testable with in-memory fixtures."""
    if not isinstance(interaction, dict):
        return []   # a missing/unparseable spec is os-spec-completeness / data-file-validity's report
    syc = interaction.get("sycophancy") if isinstance(interaction.get("sycophancy"), dict) else {}
    openers = [str(o).strip() for o in (syc.get("banned_openers") or []) if str(o).strip()]
    conf = interaction.get("confidence") if isinstance(interaction.get("confidence"), dict) else {}
    levels = [str(v).strip() for v in (conf.get("levels") or []) if str(v).strip()]
    if not openers and not levels:
        return ["interaction.yaml declares no banned_openers or confidence.levels to lock the "
                "contract surfaces to"]
    problems = []
    for label, text in surfaces:
        for phrase in openers:
            if phrase not in text:
                problems.append(f"{label}: banned opener {phrase!r} from interaction.yaml is not "
                                "rendered — the contract must carry every denylist entry (data is "
                                "the source of truth; prose may elaborate, never omit)")
        for tag in levels:
            if tag not in text:
                problems.append(f"{label}: confidence tag {tag!r} from interaction.yaml is not "
                                "rendered — the contract must carry every confidence level (data is "
                                "the source of truth; prose may elaborate, never omit)")
    return problems


def check_interaction_lockstep(fail):
    name = "interaction-lockstep"
    interaction = _load_spec("interaction")
    if not isinstance(interaction, dict):
        return  # interaction spec absent (pre-M17) or unparseable — the other gates report it
    surfaces = []
    factory = os.path.join(REPO_ROOT, "AGENTS.md")
    if os.path.exists(factory):
        surfaces.append(("AGENTS.md §10", read(factory)))
    tmpl = os.path.join(TEMPLATES, "AGENTS.md.tmpl")
    if os.path.exists(tmpl):
        surfaces.append(("templates/AGENTS.md.tmpl §12", read(tmpl)))
    if not surfaces:
        return  # a partial checkout without the rendered contract surfaces — nothing to lock
    for problem in interaction_lockstep_problems(interaction, surfaces):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 22. Routing catalog freshness + model-name lockstep (#326, M19 19.5, ADR-0024 D6).
#
#     `catalog.as_of` was documented as "the review cue" with nothing enforcing it, and model names
#     lived in TWO homes — the dated catalog and the READMEs' ranking prose — with no gate between
#     them. They drifted into direct disagreement: for weeks the catalog routed every ADR, security
#     and foundational-decision unit of work to a model all three READMEs described as *not
#     benchmarked*, while the one they ranked first sat a tier below. Nothing was red.
#
#     Two checks, both offline and dependency-free:
#       * `catalog-freshness`      — the dated catalog is within its own staleness budget.
#       * `routing-model-lockstep` — the prose and the catalog cannot contradict each other.
#
#     Deliberately NOT rendering the ranking from the catalog: the prose carries editorial nuance
#     ("not yet benchmarked", the rotation caveat) that a generated table would flatten, and the
#     ADR-0015/0016 honesty posture wants that nuance kept. So it is checked, not generated.
# ---------------------------------------------------------------------------
README_SURFACES = [
    ("README.md", "not yet benchmarked"),
    (os.path.join("docs", "i18n", "zh-Hans", "README.md"), "尚未针对 EADOS"),
    (os.path.join("docs", "i18n", "ja", "README.md"), "まだベンチマーク"),
]


def catalog_freshness_problems(spec, today):
    """Pure: is the dated catalog still within its own `max_age_days`? `today` is a date object.
    Also flags a per-model `verified:` date OLDER than the catalog's own — a model nobody
    re-checked while the catalog around it was refreshed."""
    catalog = (spec or {}).get("catalog") if isinstance(spec, dict) else None
    if not isinstance(catalog, dict):
        return ["routing.yaml has no `catalog` block"]
    as_of, budget = str(catalog.get("as_of") or "").strip(), catalog.get("max_age_days")
    try:
        stamped = datetime.date.fromisoformat(as_of)
    except ValueError:
        return [f"catalog.as_of {as_of!r} is not an ISO date (YYYY-MM-DD)"]
    if not isinstance(budget, int) or budget <= 0:
        return ["catalog.max_age_days must be a positive integer — the staleness budget is what "
                "turns the review cue into a gate (ADR-0024 D6)"]
    problems = []
    age = (today - stamped).days
    if age > budget:
        problems.append(f"catalog.as_of {as_of} is {age} days old, past its {budget}-day budget — "
                        "re-verify the ladder against the market and re-date it (a stale catalog "
                        "routes today's work by last quarter's assessment)")
    for p in catalog.get("providers") or []:
        for m in (p.get("models") or []) if isinstance(p, dict) else []:
            v = str(m.get("verified") or "").strip() if isinstance(m, dict) else ""
            if not v:
                continue
            try:
                when = datetime.date.fromisoformat(v)
            except ValueError:
                problems.append(f"model '{m.get('id')}': verified {v!r} is not an ISO date")
                continue
            if (today - when).days > budget:
                problems.append(f"model '{m.get('id')}': verified {v} is {(today - when).days} "
                                f"days old, past the {budget}-day budget")
    return problems


def model_lockstep_problems(spec, surfaces):
    """Pure: the catalog and the prose that names models must agree.

    `surfaces` are (label, text, unassessed_clause) triples. Two rules, both catalog-driven so they
    hold in any language:

      1. Every **assessed** model is a live routing target, so its name must appear in the prose.
         A model the catalog routes to but the docs never mention is drift by omission.
      2. No assessed model may be named in the paragraph that introduces the *not benchmarked*
         list. That disagreement IS #326, and it is the one this gate exists to make impossible.
    """
    catalog = (spec or {}).get("catalog") if isinstance(spec, dict) else {}
    assessed = [str(m.get("name") or m.get("id"))
                for p in (catalog or {}).get("providers") or []
                for m in (p.get("models") or []) if isinstance(p, dict)
                if isinstance(m, dict) and m.get("assessed")]
    problems = []
    for label, text, clause in surfaces:
        for name in assessed:
            if name not in text:
                problems.append(f"{label}: the catalog routes work to '{name}' but the prose never "
                                "names it — one fact, one home (#326)")
        if clause not in text:
            continue          # this surface carries no not-benchmarked list; rule 2 does not apply
        # The list of unbenchmarked things PRECEDES the phrase ("X and Y are not yet benchmarked"),
        # so look backwards from it — but only to the nearest clause boundary, never the whole
        # paragraph: in the shipped README the ladder and this phrase share one paragraph, and
        # taking all of it would flag every model the ranking legitimately names.
        start = text.index(clause)
        cut = max((text.rfind(b, 0, start) for b in (". ", "; ", "。", "；", "\n")), default=-1)
        segment = text[cut + 1:start]
        for name in assessed:
            if name in segment:
                problems.append(f"{label}: '{name}' is named as NOT benchmarked, but the catalog "
                                "marks it assessed and routes work to it — the catalog and the "
                                "prose contradict each other (#326)")
    return problems


def check_catalog_freshness(fail):
    name = "catalog-freshness"
    spec = _load_spec("routing")
    if not isinstance(spec, dict):
        return  # routing spec absent or unparseable — other gates report that
    for problem in catalog_freshness_problems(spec, datetime.date.today()):
        fail(name, problem)


def check_routing_model_lockstep(fail):
    name = "routing-model-lockstep"
    spec = _load_spec("routing")
    if not isinstance(spec, dict):
        return
    surfaces = []
    for rel, clause in README_SURFACES:
        path = os.path.join(REPO_ROOT, rel) if rel == "README.md" else os.path.join(ROOT, rel)
        if os.path.exists(path):
            surfaces.append((rel.replace(os.sep, "/"), read(path), clause))
    if not surfaces:
        return  # a partial checkout without the READMEs
    for problem in model_lockstep_problems(spec, surfaces):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 23. Phase state-writer authority (#346, ADR-0025). Every workflow state names the role that
#     RECORDS its outcome — the manifest's delivery_state and the run record under learning/runs/.
#     Declaring a writer is worthless if the writer cannot actually write those paths, which is the
#     exact failure this issue was: three procedures instructed the PHASE role to write paths
#     `authority.yaml` denies it, so following the procedure literally tripped the project's own
#     gate. This keeps the declaration honest — a state_writer that is undeclared, or that authority
#     would deny on the state paths, fails here rather than at a consumer's keyboard.
# ---------------------------------------------------------------------------
STATE_PATHS = ("orchestrator/project.yaml", ".eados-core/learning/runs/2026-01-01-x.yaml")


def state_writer_problems(workflow, authority):
    """Pure: every state declares a `state_writer` that is a declared role AND is authorized to
    write the paths recording a phase outcome requires. Returns problem strings (empty == sound)."""
    import authority_check
    problems = []
    for state in (workflow or {}).get("states") or []:
        if not isinstance(state, dict):
            continue
        sid = state.get("id")
        writer = str(state.get("state_writer") or "").strip()
        if not writer:
            problems.append(f"workflow state '{sid}' declares no `state_writer` — who records its "
                            "delivery_state and run record is then folklore (#346)")
            continue
        globs = authority_check.role_globs(authority, writer)
        if globs is None:
            problems.append(f"workflow state '{sid}': state_writer '{writer}' is not a role in "
                            "authority.yaml")
            continue
        denied = authority_check.denied_paths(authority, writer, list(STATE_PATHS))
        if denied:
            problems.append(f"workflow state '{sid}': state_writer '{writer}' may not write "
                            f"{', '.join(denied)} — a declared writer that authority denies is the "
                            "#346 defect with an extra step")
    return problems


def check_state_writer(fail):
    name = "state-writer-authority"
    workflow = _load_spec("workflow")
    authority = _load_spec("authority")
    if not isinstance(workflow, dict) or not isinstance(authority, dict):
        return  # a partial checkout — other gates report the missing spec
    for problem in state_writer_problems(workflow, authority):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 24. Subprocess timeouts (#321). `subprocess.run` without one waits FOREVER, and the tools most
#     exposed are the ones written to degrade gracefully offline: they handle "gh is missing" and
#     "gh returned an error" carefully, but not "gh never returns" — the failure a flaky network
#     actually produces. It then blocks until the CI job's own timeout and reports as a generic job
#     timeout rather than as a hung network call.
#
#     Fixing the eight sites was the easy half; this is the half that keeps the ninth from being
#     added silently. Scoped to the SHIPPED CLIs: tools/tests/* drive local `sys.executable` runs
#     with no network or credential path, so a bounded budget there would be ceremony, and CI's own
#     job timeout already covers a genuinely stuck test.
# ---------------------------------------------------------------------------
def subprocess_timeout_problems(items):
    """items: (relpath, source) pairs. Returns a problem per `subprocess.run(...)` with no
    `timeout=`. Parsed with `ast`, not a regex — a call spanning lines is exactly the shape a
    textual check would miss, and this gate exists because of a silent omission."""
    import ast
    problems = []
    for rel, src in items:
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:                 # byte-compile is the gate that reports this
            problems.append(f"{rel}: does not parse — {exc}")
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "run"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and not any(kw.arg == "timeout" for kw in node.keywords)):
                problems.append(f"{rel}:{node.lineno}: subprocess.run without a `timeout=` — a "
                                "hung child blocks until the job dies, and reports as a job "
                                "timeout rather than as the stalled call it is (#321)")
    return problems


def check_subprocess_timeouts(fail):
    name = "subprocess-timeouts"
    tools = os.path.join(ROOT, "tools")
    if not os.path.isdir(tools):
        return
    items = [(os.path.relpath(os.path.join(tools, fn), REPO_ROOT).replace(os.sep, "/"),
              read(os.path.join(tools, fn)))
             for fn in sorted(os.listdir(tools)) if fn.endswith(".py")]
    for problem in subprocess_timeout_problems(items):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 25. pin-label-truth (#312) — a SHA pin's `# vX.Y.Z` comment must be TRUE of its SHA.
#
#     `action-pins` (#6) compares a pin's SHA ACROSS files. Nothing checked that the trailing
#     version comment is true of it. On 2026-07-26 a merge resolved two `ci.yml` lines to `main`'s
#     SHA while keeping the branch's comment, landing the v7.0.0 commit under a `# v7.0.1` label
#     (#309/#310). `main` went red only because the mangling was NON-uniform and #6 saw the
#     cross-file disagreement; had it hit every file alike, the gate would have been green over a
#     pin that lied about its own version.
#
#     ADR-0009 gives that comment two load-bearing jobs — the gate reads it, and Dependabot reads it
#     to propose bumps — but mandates only its PRESENCE, never its TRUTH. This closes that half.
#     Scope follows PIN_RE: only fully SHA-pinned `uses:` lines. A profile's floating `@v6` has no
#     SHA to contradict and stays out by design (ADR-0009 §3 + its 2026-06-28 addendum).
# ---------------------------------------------------------------------------
GH_TIMEOUT = 30                     # network-bound (#321)
PIN_CACHE = os.path.join(tempfile.gettempdir(), "eados-pin-labels.json")
PIN_CACHE_TTL_DAYS = 30


def _gh_api(path, run=subprocess.run):
    """One `gh api` GET as parsed JSON. Raises RuntimeError naming the cause — never returns a
    plausible empty result, because "could not check" and "checked, fine" must not look alike."""
    try:
        proc = run(["gh", "api", path], capture_output=True, text=True,
                   encoding="utf-8", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh api {path}` timed out after {GH_TIMEOUT}s")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` ({exc})")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh api {path}` failed: {(proc.stderr or proc.stdout or '').strip()}")
    try:
        return json.loads(proc.stdout or "null")
    except ValueError as exc:
        raise RuntimeError(f"could not parse `gh` JSON for {path}: {exc}")


def resolve_tag_commit(action, tag, run=subprocess.run):
    """`owner/repo@tag` -> the COMMIT sha the tag names.

    Two hops when the tag is **annotated**: `git/ref/tags/<tag>` then yields an object of type
    `tag`, whose own `object.sha` is the commit. Stopping at the first hop would compare a pin
    against the tag OBJECT's sha and fail every annotated tag — a gate that cries wolf on correct
    pins gets switched off, so the dereference is not optional."""
    ref = _gh_api(f"repos/{action}/git/ref/tags/{tag}", run) or {}
    obj = ref.get("object") or {}
    if obj.get("type") == "tag":
        obj = (_gh_api(f"repos/{action}/git/tags/{obj.get('sha')}", run) or {}).get("object") or {}
    sha = str(obj.get("sha") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise RuntimeError(f"{action}@{tag} did not resolve to a commit sha (got {sha!r})")
    return sha.lower()


def _cache_load(path=PIN_CACHE):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}                    # a corrupt cache is a cold cache, never a wrong answer


def _cache_store(cache, path=PIN_CACHE):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=1, sort_keys=True)
    except OSError:
        pass                         # the cache is an optimisation; failing to write one is not


def cached_resolver(resolve=resolve_tag_commit, cache=None, today=None,
                    ttl_days=PIN_CACHE_TTL_DAYS):
    """`resolve(action, tag)` memoised on disk, keyed `owner/repo@tag` with the date it was read.

    The cache is a **memo, not an authority** — the distinction matters here more than usual,
    because "a recorded claim nobody re-checks" is the exact defect this gate exists to catch, and
    a cache trusted forever would reintroduce it one level up. Hence the TTL: past it, the network
    is asked again, and the cached value survives only as a fallback the caller must report as
    such (`from_cache`)."""
    store = _cache_load() if cache is None else cache
    today = today or datetime.date.today()

    def get(action, tag):
        key = f"{action}@{tag}"
        entry = store.get(key) if isinstance(store.get(key), dict) else None
        if entry:
            try:
                age = (today - datetime.date.fromisoformat(str(entry.get("resolved_at")))).days
            except ValueError:
                age = ttl_days + 1
            if 0 <= age <= ttl_days:
                return str(entry.get("sha") or ""), False
        try:
            sha = resolve(action, tag)
        except RuntimeError:
            if entry and entry.get("sha"):
                return str(entry["sha"]), True     # stale, and the caller says so
            raise
        store[key] = {"sha": sha, "resolved_at": today.isoformat()}
        return sha, False

    get.store = store
    return get


def pin_label_problems(pins, resolve):
    """Pure. `pins`: {(action, tag): {sha: [files]}}. `resolve(action, tag)` -> `(sha, from_cache)`
    or raises RuntimeError. Returns `(problems, unverified)` — the second is what the run could NOT
    establish, which the caller must surface rather than let an OK imply it was checked (L-0006)."""
    problems, unverified = [], []
    for (action, tag), by_sha in sorted(pins.items()):
        try:
            actual, stale = resolve(action, tag)
        except RuntimeError as exc:
            unverified.append(f"{action}@{tag}: {exc}")
            continue
        for sha, files in sorted(by_sha.items()):
            if sha.lower() == actual:
                continue
            where = ", ".join(sorted(files))
            problems.append(
                f"{where}: {action} is pinned {sha[:10]} but its `# {tag}` comment is not true of "
                f"it — {tag} is {actual[:10]} upstream. The SHA is the security boundary and the "
                f"comment is how a human (and Dependabot) audits WHICH release it is; a label that "
                f"lies survives exactly as long as nobody resolves it (#312, ADR-0009). Fix toward "
                f"the UPSTREAM TAG — `sync_action_pins.py --fix` copies the factory CI's SHA into "
                f"the templates, so it would propagate a wrong pin under a right-looking label.")
        if stale:
            unverified.append(f"{action}@{tag}: upstream unreachable — compared against a cached "
                              f"resolution, not re-verified")
    return problems, unverified


def check_pin_label_truth(fail, resolve=None):
    name = "pin-label-truth"
    roots = [os.path.join(os.path.dirname(ROOT), ".github", "workflows"),
             os.path.join(TEMPLATES, ".github", "workflows")]
    pins = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for path in sorted(glob.glob(os.path.join(root, "*.yml"))
                           + glob.glob(os.path.join(root, "*.tmpl"))):
            rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
            for action, sha, tag in PIN_RE.findall(read(path)):
                pins.setdefault((action, tag), {}).setdefault(sha.lower(), [])
                if rel not in pins[(action, tag)][sha.lower()]:
                    pins[(action, tag)][sha.lower()].append(rel)
    if not pins:
        return                                   # a checkout with no SHA-pinned workflows
    resolver = resolve or cached_resolver()
    problems, unverified = pin_label_problems(pins, resolver)
    for problem in problems:
        fail(name, problem)
    if resolve is None and getattr(resolver, "store", None) is not None:
        _cache_store(resolver.store)
    if unverified:
        # NOT a failure: a network-dependent gate that turns red on a missing network trains people
        # to ignore it. But silence would let "OK — congruent" imply a verification that never
        # happened, so the run says exactly which pins it could not vouch for (L-0006).
        fail.note(name, f"{len(unverified)} of {len(pins)} pin label(s) NOT verified — "
                        + "; ".join(sorted(unverified)))


# ---------------------------------------------------------------------------
# 26. git-scope-lockstep (#365) — the commit-scope vocabulary lives in `os/git/git.yaml`, and
#     `AGENTS.md` §6 restates it for the agent that has to use it. Nothing held the two together,
#     and they drifted to **8 vs 21** — the surface an agent reads FIRST being the most wrong,
#     which is the worst possible direction for a contract to be stale in.
#
#     Modelled on `interaction-lockstep` (#279): data is the source of truth, the prose may
#     elaborate but may never omit. The difference is that this gate is **two-way** — an extra
#     scope in the prose is just as much a divergence as a missing one, and #202/#327 taught that a
#     one-way check validates half a relationship and reports it as whole (L-0009).
#
#     The generated contract needs no rule here: `templates/AGENTS.md.tmpl` renders its scopes
#     from the manifest via `{{#EACH_SCOPE}}`, so a generated repo is congruent by construction.
#     Only the factory hand-maintains two copies — which is how it ended up the one that drifted.
# ---------------------------------------------------------------------------
# The list, and ONLY the list: the contiguous comma-separated run of backticked tokens after the
# marker. Matching the STRUCTURE rather than a span between delimiters is deliberate — the first
# version bounded the capture by the closing period and swept up every other backticked token
# nearby, including this gate's own name in the note beneath the list. It failed on the very tree
# that introduced it, and would have gone on over-reporting whenever the terminator moved.
# Separator is `\s*,?\s*`, not a required comma: the factory contract writes the list
# comma-separated and the rendered one space-separated (`{{#EACH_SCOPE}}`), and a gate that only
# understood one of them would silently capture a single scope from the other and then report every
# remaining one as "omitted" — a confident wrong answer, which is worse than not checking.
_SCOPE_PROSE = re.compile(r"Scopes for this repo:\s*((?:`[a-z0-9][a-z0-9-]*`\s*,?\s*)+)")


def git_scope_lockstep_problems(scopes, contract_text):
    """Pure check. `scopes`: `commit.scopes` from git.yaml; `contract_text`: AGENTS.md. The prose
    list must equal the declared vocabulary, **both ways**. Returns problem strings."""
    declared = [str(s).strip() for s in (scopes or []) if str(s).strip()]
    if not declared:
        return ["os/git/git.yaml declares no commit.scopes to lock AGENTS.md against"]
    m = _SCOPE_PROSE.search(contract_text or "")
    if not m:
        return ["AGENTS.md does not state the commit-scope vocabulary ('Scopes for this repo…') — "
                "the contract an agent re-grounds against must carry it (#365)"]
    prose = re.findall(r"`([a-z0-9][a-z0-9-]*)`", m.group(1))
    problems = []
    missing = [s for s in declared if s not in prose]
    extra = [s for s in prose if s not in declared]
    if missing:
        problems.append(f"AGENTS.md §6 omits {len(missing)} declared scope(s) "
                        f"({', '.join(missing)}) — data is the source of truth and the prose may "
                        "elaborate, never omit (#365)")
    if extra:
        # The other direction, and the one a one-way gate misses: prose that outlives its data
        # sends an agent to a scope git_check will reject (L-0009).
        problems.append(f"AGENTS.md §6 lists {len(extra)} scope(s) git.yaml does not declare "
                        f"({', '.join(extra)}) — `git_check` would reject them (#365)")
    return problems


def check_git_scope_lockstep(fail):
    name = "git-scope-lockstep"
    spec_path = os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")
    contract = os.path.join(REPO_ROOT, "AGENTS.md")
    if not os.path.exists(spec_path) or not os.path.exists(contract):
        return  # a partial checkout / a consumer install without the factory contract
    try:
        spec = render.load_yaml(read(spec_path)) or {}
    except ValueError as exc:
        fail(name, f"os/git/git.yaml did not parse: {exc}")
        return
    for problem in git_scope_lockstep_problems((spec.get("commit") or {}).get("scopes"),
                                               read(contract)):
        fail(name, problem)


# ---------------------------------------------------------------------------
# 27. command-table-lockstep (#374) — the generated `AGENTS.md` carries the `/eados` command table,
#     and it must stay GENERATED. `AGENTS.md` is the one file every host auto-loads; in a generated
#     repo it listed no commands at all, while the registry that has them lives inside the
#     gitignored `.eados-core/` — the contract guaranteed to be read pointing at a file guaranteed
#     not to be committed.
#
#     There is nothing to compare two lists against, because there is only one: the template holds
#     `{{EADOS_COMMANDS}}` and `render.commands_table()` fills it from the registry. So what this
#     gate protects is exactly that — that nobody "simplifies" the placeholder into a literal table.
#     A hand-written copy would be the second list, and a STALE command table is worse than none: it
#     sends an agent at a command that no longer exists.
# ---------------------------------------------------------------------------
_LITERAL_CMD_ROW = re.compile(r"(?m)^\|\s*`/eados \w+`\s*\|")


def command_table_lockstep_problems(template_text, rendered=None, registry=None):
    """Pure check. `template_text`: templates/AGENTS.md.tmpl. `rendered`: an optional rendered
    contract to verify the table actually landed in. `registry`: the canonical command list."""
    problems = []
    if "{{EADOS_COMMANDS}}" not in template_text:
        problems.append("templates/AGENTS.md.tmpl no longer carries {{EADOS_COMMANDS}} — the "
                        "command table must be RENDERED from orchestrator/commands/README.md, "
                        "never typed into the template (#374)")
    if _LITERAL_CMD_ROW.search(template_text):
        problems.append("templates/AGENTS.md.tmpl contains a literal `| `/eados …` |` table row — "
                        "that is a second copy of the registry, and a stale command table sends an "
                        "agent at a command that no longer exists (#374)")
    if rendered is not None and registry:
        missing = [c["name"] for c in registry if f"`/eados {c['name']}`" not in rendered]
        if missing:
            problems.append(f"the rendered AGENTS.md omits {len(missing)} declared command(s) "
                            f"({', '.join(missing)}) — the contract every host reads must list "
                            "them all (#374)")
    return problems


def check_command_table_lockstep(fail):
    name = "command-table-lockstep"
    tmpl = os.path.join(TEMPLATES, "AGENTS.md.tmpl")
    if not os.path.exists(tmpl):
        return  # a partial checkout without the contract template
    registry = command_registry.load()
    rendered = None
    if registry:
        try:
            rendered = render.commands_table(registry)
        except Exception as exc:  # noqa: BLE001 — a broken renderer is the render-smoke's report
            fail(name, f"could not render the command table: {exc!r}")
            return
    for problem in command_table_lockstep_problems(read(tmpl), rendered, registry):
        fail(name, problem)


CHECKS = [
    check_placeholder_integrity,
    check_profile_completeness,
    check_generate_references,
    check_agent_registry,
    check_lessons,
    check_action_pins,
    check_i18n_freshness,
    check_os_specs,
    check_domains,
    check_authority_personas,
    check_cross_spec_consistency,
    check_version_lockstep,
    check_roadmap_freshness,
    check_manifest_template,
    check_data_files,
    check_run_records,
    check_gate_coverage,
    check_workflow_safety,
    check_gate_executability,
    check_examples,
    check_safe_write,
    check_command_adapters,
    check_routing_delegation,
    check_interaction_lockstep,
    check_catalog_freshness,
    check_routing_model_lockstep,
    check_state_writer,
    check_subprocess_timeouts,
    check_pin_label_truth,
    check_git_scope_lockstep,
    check_command_table_lockstep,
]


class _Reporter:
    """The one reporter, with two channels.

    It is **callable**, so every existing check's `fail(name, message)` is unchanged, and it also
    carries `.note(name, message)` for a finding that must be SEEN without failing the run — a
    network-dependent gate that could not reach the network (#312). Two channels because collapsing
    them either turns a missing network into a red build (which trains people to ignore the gate)
    or hides it entirely (which lets "OK" imply a verification that never happened, L-0006).
    The accumulators live per-run, never in the module (#167)."""

    def __init__(self):
        self.failures = []
        self.notes = []

    def __call__(self, check, message):
        self.failures.append((check, message))

    def note(self, check, message):
        self.notes.append((check, message))


def run_checks(checks=CHECKS, reporter=None):
    """Run `checks`, each receiving its own view of the one reporter. Returns the (check, message)
    findings; pass a `_Reporter` to also collect the non-failing notes."""
    rep = reporter if reporter is not None else _Reporter()
    for fn in checks:
        try:
            fn(rep)
        except Exception as exc:  # a crashing check is itself a failure
            rep(fn.__name__, f"check crashed: {exc!r}")
    return rep.failures


def main():
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    reporter = _Reporter()
    failures = run_checks(reporter=reporter)
    for check, message in reporter.notes:
        # Printed on BOTH paths: what a run could not verify is exactly as true when the rest
        # passed, and an "OK" that quietly covered an unchecked gate is the lie this guards.
        print(f"  [{check}] NOTE: {message}")
    if failures:
        print("EADOS self-lint: FAIL\n")
        for check, message in failures:
            print(f"  [{check}] {message}")
        print(f"\n{len(failures)} factory-integrity problem(s) found.")
        return 1
    print("EADOS self-lint: OK — placeholders, profiles, and playbook references are congruent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
