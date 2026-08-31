# Threat model — mycelium-os

> **Owner:** the **security-auditor** role (it drafts here; findings feed the audit risk
> register). Produced and kept current by the **audit threat-modeling sub-mode**
> (`/eados security` → `/eados audit`). Method: **STRIDE**. First filled by the
> **bootstrap audit, 2026-08-29** (register:
> [`audit-2026-08-29-bootstrap.md`](audit-2026-08-29-bootstrap.md)). Boundaries marked
> *(design)* come from the accepted design (RFC-0001 / spec docs 02 §8, 04 §6) and gain
> their mechanical controls at the named milestone — they are modeled now so the controls
> are built in, not bolted on. **Last revised 2026-09-01** (roadmap 4.1, PR #50): B4 and B7
> gained their first live controls, and **B9 — parser subprocess** is a new boundary,
> because the pandoc adapter runs an external binary on untrusted bytes.

## 1. Scope & trust boundaries

| Boundary | Untrusted inputs crossing it | Assumptions |
|---|---|---|
| **B1 — GitHub PR/CI edge** (today): external contributions execute workflows | PR diffs (workflow-adjacent files, `tools/consistency_lint.py` runs on PR code) | `pull_request` event only (never `pull_request_target`); default `GITHUB_TOKEN` is read-only in ci.yml (`permissions: contents: read`); no repository secrets exist for CI to leak; repo currently private (no external contributors yet) |
| **B2 — GitHub Actions supply chain** (today): third-party actions run with repo access | Action code resolved at run time | Template-native actions SHA-pinned with version labels; profile-injected actions (setup-python, setup-uv) tag-pinned **by decision** (factory ADR-0009 §3) and Dependabot-managed weekly; release.yml has `contents: write` but fires only on `v*.*.*` tag push — tags are owner-pushed |
| **B3 — Vendored EADOS factory** (today): `.eados-core/` tooling executes locally and (lint only) in CI | The bundle's own code; future `/eados upgrade` diffs | Vendored tracked by owner decision (PR #1); updates arrive as reviewable diffs, never silent; only `tools/consistency_lint.py` (generated, in-repo) runs in CI |
| **B4 — Ingested source content** *(partly live — the acquire/parse half landed at 4.1)*: PDFs/DOCX/HTML/wikis enter the compiler | File bytes, embedded instructions, hostile structures (zip-bombs, parser exploits) | D-017: **all** source content untrusted, including the user's own; parsers wrapped behind KIR with quarantine-not-abort (`ParseError` is per document, `ConnectorError` refuses custody); acquisition is confined to declared roots, resolves before it checks so no symlink escapes, and reads under a byte ceiling; an extension the project does not ingest is refused by name. Secret scan (4.6) and loss budgets (4.3) are still design |
| **B5 — LLM synthesis lane** *(design — lands M4)*: provider-generated Markdown enters tier 2 | Model output (potential fabrication, injected instructions from evidence it read) | D-020/D-021: synthesized docs are born `candidate`, cite evidence per statement, earn `verified` only through grounding gate G7 + human promotion; the LLM never writes indexes |
| **B6 — MCP serving edge** *(design — lands M2)*: any MCP client queries the store | Tool-call arguments (queries, URIs, filters) | D-011/D-017: read-only tools only; typed errors; every response carries the data-not-instructions notice; retrieved text returned as quoted evidence, never interpreted |
| **B7 — Plugins** *(live from 4.1 for parsers/connectors; the rest M5)*: third-party code in-process | Plugin package code | D-012 stance: a plugin is installed code, same trust as any pip dependency — stated plainly in docs; resolution is *pinned* through the `mycelium.plugins` entry-point group, a plugin may not shadow a built-in id, and an unresolvable name is an error rather than a fall-back to something else; sandboxing deferred with an explicit trigger (spec 06 §3) |
| **B9 — Parser subprocess** *(live from 4.1)*: the `pandoc` parser runs an external binary on untrusted bytes | The document's bytes, on stdin; pandoc's own stdout/stderr | Fixed argument vector, never a shell string; `--sandbox`, which is why pandoc < 3 is refused; the bytes go in over stdin so no attacker-influenced path is ever passed; a wall-clock timeout bounds the run; a non-zero exit is a per-document `ParseError`, not a build failure |
| **B8 — Network egress** *(design)*: remote embedders/sources when configured | Provider responses | D-013/D-017: zero network by default (local ONNX embedder); remote providers opt-in via config; no telemetry |

## 2. STRIDE pass

| Category | Threat considered | Boundary / component | Mitigation / control | Status |
|---|---|---|---|---|
| Spoofing — is the caller who it claims? | A PR author impersonating a maintainer to merge | B1 | Only the owner merges (contract §6); GitHub authn; branch protection pending public/Pro — interim control is collaborator roles + policy (register F2) | ✅ mitigated / F2 tracks residual |
| Spoofing | A forged `v*.*.*` tag triggering a release draft | B2 | Tag push requires write access (owner); workflow only **drafts** — a human publishes | ✅ mitigated |
| Spoofing | An MCP client is not authenticated in v1 | B6 (design) | n/a by design at v1 scale: stdio transport, local single-user (D-002); authn arrives with the Phase-5 server profile via its own RFC | ▢ n/a (reason recorded) |
| Tampering — can data/code be altered? | A malicious action version altering the repo or release artifacts | B2 | SHA pins for template actions; tag-pinned profile actions are Dependabot-managed (ADR-0009 §3 — decided trade-off); `contents: write` confined to the tag-triggered release job | ✅ mitigated / decided residual |
| Tampering | Hostile ingested file corrupting the store or projections | B4 (partly live) | Quarantine path (never abort the build), KIR opaque nodes, fidelity reports, hostile-fixture suite is an M4 exit gate; from 4.1 a parse failure is already per document, and a file outside the declared roots is refused before it is read | ▢ partly live (4.1) — hostile-fixture gate at 4.2/4.7 |
| Tampering | A path or symlink reaching outside the declared source roots | B4 | The connector resolves to the real path *before* it checks containment, so `..` and a symlink pointing out of the tree are both refused; the check is on the resolved path, not a textual prefix (spec 02 §8) | ✅ mitigated (4.1) |
| Tampering | A plugin claiming a built-in parser id, so one configuration means two things | B7 | An entry point registering a built-in id is refused by name; resolution is pinned and ordered, never "best available" (spec 05 §4.2) | ✅ mitigated (4.1) |
| Tampering | Synthesized doc silently entering `verified` truth | B5 (design) | Folder-encoded status; G7 grounding gate (cites ≥ 0.95, entailment ≥ 0.90); promotion is a human/Git action; builds never move tier-2 files | ▢ design control — M4 |
| Repudiation — actions deniable? | Phase moves / merges without a trail | B1/B3 | Checkpoint ledger in the manifest (gate_results + confirmed_by), run records under `.eados-core/learning/runs/`, Git history, PR cross-links (traceability graph verified whole this audit) | ✅ mitigated |
| Repudiation | A build unexplainable from its output | B3/B4 (design) | Snapshot manifests record inputs, config digest, toolchain, plugin identities (D-008/D-023); journal.jsonl for diagnostics | ▢ design control — M2/M3 |
| Information disclosure — can data leak? | Secrets committed to the repo | B1 | Secret-pattern grep clean this audit; `.gitignore` excludes local agent settings; **no repository secrets configured**; ingestion-time secret scanning (redact_secrets) lands M4 | ✅ today / M4 extends |
| Information disclosure | CI leaking data from a private repo | B1/B2 | ci.yml `permissions: contents: read`; no secrets available to PR workflows; telemetry: none (D-017) | ✅ mitigated |
| Information disclosure | Indexed content served across a trust boundary | B6 (design) | v1 is single-user local (D-002) — n/a until the server profile; `trust:` filters + labels exist from M2 so consumers can exclude low-trust tiers | ▢ n/a at v1 scale (reason recorded) |
| Denial of service — exhaustible surface? | A hostile document exhausting the build (zip-bomb, pathological parse) | B4 (partly live) | Quarantine + loss budgets + hostile-fixture exit gate (M4); build is a local, owner-initiated action — no public compute to exhaust. From 4.1 acquisition checks the file's size against a ceiling *before* reading it, so an oversized source costs a `stat` | ▢ partly live (4.1) — decompression bombs are 4.2's gate |
| Denial of service | A document that makes the parser subprocess hang | B9 | The pandoc run is bounded by a wall-clock timeout; expiry is a per-document `ParseError` | ✅ mitigated (4.1) |
| Denial of service | CI-minute exhaustion via PR spam | B1 | Private repo today; concurrency group cancels superseded PR runs; GitHub-side rate controls; revisit at public launch | ✅ adequate for current exposure |
| Denial of service | MCP query exhausting the local store | B6 (design) | Budgeted packing (`budget_tokens`), typed `BUDGET_EXCEEDED`, latency budgets are CI gates (G5) | ▢ design control — M2/M3 |
| Elevation of privilege — ungranted authority? | A PR gaining write via workflow modification | B1 | `pull_request` event runs with read-only token regardless of workflow edits in the PR; release workflow unreachable from PRs (tag trigger) | ✅ mitigated |
| Elevation of privilege | Agent exceeding its delivery authority (merge, publish, phase-skip) | B3 | Authority model (authority.yaml) + human-gated transitions + owner-only merge/publish; `authority_check.py` run per phase; this audit's own boundary: draft-only advisories | ✅ mitigated |
| Elevation of privilege | Retrieved content acting as instructions in a client agent | B6 (design) | D-017 doctrine: quoted-evidence contract + explicit notice string; injection corpus is a release gate (G-series, 04 §6) — the residual (what the *client* does) is documented as the client's responsibility | ▢ design control — M2+, residual documented |

## 3. Findings → the risk register

A threat that survives analysis lands in the audit **risk register** with its severity
(low/medium/high/critical), affected component, realistic impact, and a concrete mitigation — the
same record shape the audit phase emits. A confirmed, reproducible defect additionally becomes a
[bug-ledger](../bugs/README.md) record; a vulnerability needing coordinated disclosure becomes a
**draft** advisory the human publishes.

Current register: [`audit-2026-08-29-bootstrap.md`](audit-2026-08-29-bootstrap.md) —
findings F1–F5 (one confirmed defect → [BUG-0001](../bugs/2026/08/BUG-0001-release-workflow-matrix-context.md)).
