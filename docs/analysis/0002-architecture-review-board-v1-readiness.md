# Analysis 0002 — Architecture Review Board: is the repository ready to be the stable v1 foundation of the Mycelium ecosystem?

- **Status:** Draft for maintainer review. An assessment, not a decision: it files no ADR, changes no code and flips no roadmap checkbox except 7.12's own. Every proposal below enters the roadmap only through the maintainer (AGENTS.md §6–§7), and every GitHub issue it drafts is opened one at a time on the maintainer's confirmation.
- **Date:** 2026-10-06 (board convened 2026-10-05)
- **Author:** the board clerk (agent), convening a panel of independent reviewer agents at the maintainer's request (roadmap 7.12, re-cut on 2026-10-05 from "a panel on the order of two hundred, ranked by how many reviewers reached a finding" to "24–40 independent disciplines, severity by impact, adversarial challenge before any blocker")
- **Subject:** `danielPoloWork/mycelium-os` at commit `ea0d167` (v0.6.0 + roadmap 7.3–7.11, 7.13), branch `feat/architects-panel-review`, identical to `origin/main` throughout the review
- **Question asked:** is the repository ready to serve as the stable v1 foundation of the Mycelium ecosystem, with future capabilities developed primarily as standalone modules over the plugin API (D-025, D-029)?
- **Related:** RFC-0001; spec 06 §§1, 4; AGENTS.md §13; D-025, D-029; `docs/compatibility.md`; the registers `docs/security/`, `docs/benchmarks/`, `docs/bugs/`

> **Calibration** (AGENTS.md §12.1). `certain` — verified on the commit by a reviewer or the clerk, by reading the line or running the command named; `likely` — an inference from named evidence; `guessing` — flagged where it occurs. The repository was **read and run**: 452 commands, 145 of them probes or targeted tests on copies of fixture corpora; the full suite and the benchmarks were not run by the board (CI at `ea0d167`, green on 2026-09-25, is the authority for them).

---

## 0. Verdict

**CONDITIONAL GO.** The architecture is viable as the v1 foundation: the compiler, the store, the serving shells and the plugin seams are decomposed, tested and documented to a standard the board rarely meets, and no owner decision is contradicted by the code. It is not yet the *stable* foundation the question asks about, for three kinds of reason, each with a condition the owner can check: a short list of code defects that survived an adversarial challenge as release-blocking (one P0 and three consolidated P1s, each reproduced on this commit; eight further P1 groups were confirmed but judged not to block the tag); a ledger of owner actions the repository has recorded for weeks and whose absence its own tools report; and three decisions nobody has taken, beginning with what the v1.0.0 tag exits on. All 55 independent assessments, from two panel configurations, reached the same call, and the challengers who tried to overturn the blockers confirmed every one of the five that remain.

### Strongest evidence supporting the decision

- **The five contracts are tested artefacts, not prose** (`certain`): `tests/test_contracts.py` holds each to a golden of its shape with its own anti-vacuity checks; no golden has moved since the freeze commit; the v0.5.0 history records load with today's readers. **Deterministic builds are a gate that can fail** (`certain`): G6 is mutation-tested and runs on three operating systems; incremental equalled clean under every realistic source mutation the determinism seats produced (rename, case-only rename, delete, same-size edit, copied tree with and without mtimes, a build after a kill).
- **The boundaries that matter are mechanical** (`certain`): the package graph is acyclic and SQL is confined to the store package; the CLI import guard is a property over `sys.modules`; the build's only tier-2 write is isolated and byte-tested with a control; the first module's imports are checked against the core's declared surface by the module's own acceptance gate.
- **Failure is refused rather than reinterpreted where the design chose to** (`certain`): publication is one transaction plus one atomic pointer swap and survives a real process kill at both crash points; the CAS re-hashes on every read; a foreign store version is refused with the remedy on CLI, doctor and MCP; read-only MCP is the SQLite open mode, not a convention; offline-by-default is a property of the import graph.
- **The project measures itself honestly** (`certain`): the three performance budgets it misses are published with manifests; the adoption gate was re-cut onto observable acts and the instrument excludes the owner's own activity by test; deferrals carry an executable expiry and the tool reported, on the day of review, exactly the expired state the register predicted.
- **No accepted owner decision (D-001…D-032) is contradicted by the implementation** (`certain`, Q14): seven seats walked the log; what they found are ADR-level contradictions (ADR-0055's tag claim, ADR-0009's "exactly one wins" and "microseconds-wide", ADR-0014/0024 on the MCP path, ADR-0016 on vectors), recorded below as findings, not as reversals of a decision.

### Unresolved release blockers

Three conditions, in the order the board would take them. Full records: §3, §4, §8 and `docs/analysis/0002` appendices.

1. **The owner's ledger** (`certain`; `tools/check_repo_settings.py` exit 1 and `tools/adoption_report.py` exit 1 on 2026-10-05/06): branch protection with a code-owner review and private vulnerability reporting (register F2/F3, both **expired**, SECURITY.md routes reporters to the disabled form); `pull_request_creation_policy=all` (the one external contribution, issue #149, still cannot become a pull request); publish to TestPyPI then PyPI with the `pypi` environment and a tag ruleset (`pip install mycelium-os` answers 404 on both indexes); GitHub Pages and the About box. Nothing in this list is an agent's to do.
2. **Three decisions owed** (§4): **D-01** what v1.0.0 exits on — the v1.0.0 label on Milestone 7 is the owner's recorded correction (ADR-0113), so spec 06 §1, `project.yaml` and the GitHub milestone title are the stale records; what no record states is the exit gate the tag binds to: the D-030 Phase-4 contribution gate stands at 0/3 and 0/1, unreachable while intake is closed and the package is on no index, and nothing says whether the tag carries it by name as v0.6.0 did; the support window SECURITY.md delegates to a page that defines none; where public RFCs live. **D-03** the module-facing surface (ADR-0086's trigger *is* the tag and nothing owns it; confirmed P1 by its challenger). **D-05** the performance envelope the tag advertises (NFR-2 missed by 9–16× at 10⁵ chunks, NFR-3 past ~1 200 documents, both published, neither owned; confirmed P1).
3. **Code defects that survived the adversarial pass as blocking** (§3, Appendix C): **I-01 (P0, confirmed by both challengers)** — the authored lane follows symlinks and junctions out of the repository, indexes the outside file as `authored`, serves it over MCP and, under the default pinning build, writes a `mycelium_id` block into it; the threat model marks this threat mitigated for a boundary it says includes authored Markdown. **I-03** — Dependabot widened BUG-0022's tree-sitter pin to `<0.27`, so a consumer of `[symbols]` resolves the release that faults inside the compiler while CI runs the lock's 0.25.2. **I-05** — `rollback` and `gc` open a foreign-version store as a writer and wipe it, leaving `CURRENT` naming a manifest the store no longer holds and `search` answering empty with exit 0 (the corrupt-store crash in the same group was confirmed P1 and judged fixable or acceptable in writing). **I-12** — MCP stdin is decoded in the Windows code page, so a non-ASCII query silently returns nothing on a supported platform. Eight more groups were confirmed at P1 and judged not to block the tag by the reviewer who tried to disprove them — tier-2 writes that are not atomic (I-07), the Windows `CURRENT` swap under a reader (I-09), the corrupt-store crash (I-05's other half), `Connector` frozen with no registry path (I-02), the MCP configuration fallback (I-11), the tag cut before CI (I-10), the authored-lane read-cost bounds (I-14), the KIR/identity/ingested-identity freeze items (I-16, I-18, I-22) and the query path (I-23) — each with a fix-or-accept decision the owner takes before the tag. Two blocking votes fell: the `api_max` default (I-04) to P2 as a one-line, golden-neutral fix, and the missing publish environments (I-10's second half) to P3 because ADR-0116's design is safe while nothing is configured.

### Accepted residual risks (proposed; the owner accepts or declines each in writing)

- The performance budgets NFR-2 and NFR-3 are missed at the top of the advertised envelope and the misses are published; the bounded first fix (rank inside FTS5, hydrate by rowid, I-23) is an issue, the envelope is decision D-05.
- An incremental store built under one dependency version and read under another can serve stale artifacts until `mycelium build --clean` (I-13, P2 after challenge): the gap is recorded in ADR-0015/ADR-0154, no released store was affected (store versions v5→v6→v8→v9 forced a recreate at every release), and the net the ADRs cite cannot see it.
- Two-writer windows in the lock and a ten-minute stall after a killed build (I-26, P2), with a manual remedy.
- The disagreements D-02 (the document record's unchanged token), D-04 (tag-pinned actions in identity-holding jobs), D-06 (duplicate-identity rule) and D-07 (the export bundle outside the promise), if the owner keeps the recorded decisions.

### Architectural strengths worth preserving

The build key as the unit of truth and the stage-version discipline it needs; goldens of shape rather than prose; the measured-refusal habit (ADR-0144, ADR-0153, ADR-0028) and the ADR-per-decision record that makes a stranger's audit possible at all; the single serving core under two thin shells; quarantine-not-abort per document; the deferral-with-expiry pattern (ADR-0118); the adoption instrument that counts nobody twice; the threat model that names its tests; the one-maintainer release process that holds no credential.

### Where the evidence remains insufficient

Actual line coverage (never measured, NFR-9 is unenforced); power-loss durability of the `CURRENT` swap and the CAS on Windows (no fault-injection harness); behaviour on network or cloud-synced filesystems; whether any markdown-it-py release in the declared range changes KIR (0 of 326 digests differed between 3.0.0 and 4.2.0); the Python 3.13 half of the slug-divergence finding (no 3.13 interpreter on the review machine); whether BUG-0022's fault is a read fault or a write primitive; NFR-4 on a stranger's machine (measured on a shared machine only: venv 115 s, install 354 s, first build 29 s, MCP initialise 27.9 s cold); absolute latency at 10⁵ chunks on an idle machine at this commit; peak memory and concurrent MCP clients; release reproducibility by a second maintainer (steps 9–11 of `release.md` have never been executed by anyone); and the owner's intent on the Phase-4 gate.

### Conditions required to reverse this decision

**To GO:** D-01 exists as a decision record; `tools/check_repo_settings.py` exits 0 and `tools/adoption_report.py`'s index precondition reads met; every blocking issue that survives the adversarial pass is closed or explicitly carried as a residual in an ADR; D-03 is taken or explicitly re-deferred with an owner. **To NO-GO:** a P0 that cannot be closed before the tag (none of that kind was found), a frozen contract shown unkeepable (none was), or a tag cut without D-01 (a release with no exit criteria).

---

## 1. The fifteen questions, answered

Every seat answered the questions in its remit; every answer below is the board's consolidation. The seat tally is metadata (Appendix D), not a vote.

| # | Question | Answer | Basis (`certain` unless marked) |
|---|---|---|---|
| 1 | Implementation matches the normative specs and ADRs? | **Partially** | Where a golden or constant pins it, exactly (16 commands, 6 error codes, manifest fields, the `.mycelium` layout). Spec 01 (the "frozen contract"), spec 05 §§1–3 and RFC-0001 still advertise six Protocols and four mechanisms, `build --profile`, `ingest <url>`, a `tag` filter and a config example the loader refuses, without amendment notes (I-24). The authored-lane link control spec 02 §8 states exists only on the ingest side (I-01). |
| 2 | Boundaries real or documentary? | **Partially** | Real: acyclic package graph, SQL confined to `store/`, CLI import guard, tier-2 write isolation, module-surface gate, verify-ladder parity (all tests). Documentary: the `Store` protocol (no consumer typed to it; nine methods used that it lacks); CLI and MCP re-implement the read path and already diverge on a dead anchor (R-ARCH). |
| 3 | Plugin API stable enough for independent modules? | **Partially** | For `Parser` and `Module` it held: four additive commits, the first module with zero core patches, gate 6 mechanical. `Connector` and `Synthesizer` are frozen with no registry path; the generation check cannot refuse; the six module-facing components are unfrozen with no owner for the decision the tag triggers (I-02, I-04, D-03); three D-023 mechanisms are unbuilt by decision. |
| 4 | Contracts have ownership, compatibility rules, versioning? | **Partially** | Ownership and change control for the five are clear and tested (compatibility.md, CODEOWNERS, `test_contracts`). The plugin range is elastic (I-04); the additive-keeps-token rationale is false for closed records (I-25); the document record changed incompatibly under one token (D-02); `mycelium.toml` and `--json` are SemVer surface with no check (I-11, I-25). |
| 5 | Determinism and incrementality valid under realistic change? | **Partially** | Within one environment, yes, including case-only renames and a kill. The parse key omits the parser libraries and the Unicode database; a missed stage bump has no mechanical net; custody is outside the assemble key; `.MD` membership differs by OS (I-13, P2 after challenge). |
| 6 | Failures leave things recoverable? | **Partially** | Pre-COMMIT failure rolls back whole; CAS blobs re-hash; doctor detects the commit-to-swap window. A corrupt store crashes every command including the documented remedy; `rollback`/`gc` wipe a foreign-version store; the compile catch-all publishes an empty index on ENOSPC; a killed build blocks writers for ten minutes (I-05, I-06, I-26). Tier 2 was never damaged in any probe except by the non-atomic pin write (I-07). |
| 7 | Security boundaries understood and controlled? | **Partially** | MCP edge bounded in code, schema and test; read-only by open mode; the 6.3 controls hold under re-probe. The authored lane's path containment is claimed and absent (I-01); the configuration file is an unmodelled input (I-11); two expired deferrals and a disabled disclosure channel (O-01); dependency and secret signals absent (I-34). |
| 8 | Tests protect invariants or exercise implementations? | **Partially** | Invariants held as properties: contract goldens with anti-vacuity, G6 mutation test, import guard, no-pin control arm, ladder parity. Not exercised: two writers, a kill mid-pin, torn reads, platform-variant inputs; the threat-model suite is a marker census (I-36); the BUG-0009 regression test cannot fail; NFR-9 coverage is measured by nothing (I-20). |
| 9 | Performance claims supported at relevant scales? | **Partially** | Every stated budget has a manifest at its named condition and the misses are published. The release headline figure has no committed manifest; nothing is measured past ~5 000 documents; memory, concurrent clients and large-file ingest have no measurement; the CI benchmark job cannot fail on a regression (I-20, I-23, D-05). |
| 10 | Diagnosable outside the developer's machine? | **Partially** | Typed MCP errors with declared fields, `timings_ms`, `build --json`, quarantine records with digests. Journal records carry no time or version; doctor ignores the published manifest and crashes on a corrupt store; the bug template asks for none of the diagnostics (I-28). |
| 11 | Install, configure, upgrade, downgrade, recovery defined? | **Partially** | Install is honest (tag install; "not on PyPI yet"); config is strict with named errors; upgrade and downgrade are D-016 rebuild in both directions and tested. The consequences (rollback cannot cross a store bump; snapshots become unrestorable) are undocumented and the release notes say "nothing is required of you"; the tutorial installs v0.5.0; recovery of a corrupt store has no working command (I-05, I-30, R-OPS). |
| 12 | Governance, rules, ADRs, RFCs and implementation agree? | **Partially** | The structural chain agrees and is linted (ADR index, amendments, bug ledger, version lockstep, ladder parity). Contributor-facing text does not: PRs "from anyone" against `collaborators_only`; a DCO rule nobody follows; a coverage gate nothing runs; spec 06, `project.yaml` and the GitHub title stale against the recorded v1.0.0 label; a public RFC track that does not exist (O-01, D-01, I-20, I-24). |
| 13 | Known debt threatens the v1.x line? | **Partially** | One item does: the widened tree-sitter pin (I-03). The rest is bounded: a 366-line `_build_locked`, four copies of the embedder mapping, 24 tool scripts restating the corpus list, the open NFR-2 miss with no owner (T-01, D-05). |
| 14 | Any accepted owner decision contradicted by the code? | **No** | Twenty-seven of D-001…D-032 honoured, the rest not yet reached; the contradictions found are at ADR level (ADR-0055, ADR-0009, ADR-0014/0024, ADR-0016) and are findings here. |
| 15 | Ready to shift the centre of gravity to ecosystem development? | **Not yet** | The engineering side is in place (five goldens, G1–G7 green, one module with zero core patches). Every precondition the ecosystem needs is an owner act not taken or a plugin-API gap: nothing installable by name, docs unpublished, intake closed, `Connector`/`Synthesizer` unloadable, the module surface undecided, `mycelium-chats` unpublishable as D-029 plans. The shift is ready to be *prepared* in the release milestone and *executed* in the one after (§7). |

## 2. Method and panel composition

- **Independent review.** 30 seats across the 24 disciplines the brief names (architecture ×2, plugin API ×2, determinism ×2, security ×2, test architecture ×2, release readiness ×2, one each for the rest), each with its own persona, remit, reading list and allowed probes; 15 ran on the frontier model at high effort, 15 on the standard model at high effort (owner decision, 2026-10-06). Each seat read a shared evidence pack (the mandate, the fifteen questions, the finding record, live probes the clerk had taken) and the repository, and wrote one record per finding with the 19 fields the brief requires. No seat saw another's work. **Supplementary:** 25 area-lens seats from the earlier 210-seat configuration (identity, Markdown, chunking, build; same commit) were recovered from their transcripts and converted to the same record; they entered triage under the same rules. Together: **55 assessments, 410 findings; 301 distinct repository paths opened by the board seats (83 of the 103 source files between both configurations); 452 commands run, 145 of them probes or targeted tests on fixture copies.**
- **Evidence rule, applied twice.** Mechanically: a finding with no tracked path, number, test or command was to be dropped before counting — none was (410 of 410 carried verifiable evidence). By reading: seven partition clerks merged semantically equivalent findings (410 → 180 clusters; 46 merged across partitions), recorded 49 contradictions between reviewers, and rejected none as unsupported.
- **Severity is impact.** A cluster's severity is the highest a member assigned, never its member count; the reviewer count is recorded as metadata.
- **Adversarial pass.** Every P0/P1 cluster was challenged by a reviewer who did not originate it, instructed to disprove it by the seven routes the brief names (incomplete evidence, intentional, ADR-accepted, unrealistic, existing test, overstated severity, roadmap work): the P0 by two frontier challengers, the 15 P1 clusters carrying release-blocking votes by one frontier challenger each, the 33 other P1 clusters by one standard-model challenger each. Of the 33 standard-model verdicts: 7 confirmed at P1, 23 downgraded (mostly to P2, three to P3), 3 reclassified as disagreements with a recorded decision, 0 refuted outright. Of the 17 frontier verdicts: 10 confirmed (the P0 by both challengers; eight P1 clusters), 6 downgraded in severity or stripped of their release-blocking vote, 1 reclassified as an owner action, 0 refuted outright. After the pass: 1 P0, 19 P1, 98 P2, 62 P3 clusters; five clusters remain release-blocking. P2 and P3 clusters were adjudicated by the clerk from the record.
- **Classification.** Each of the 180 clusters is exactly one of: GitHub issue (141 clusters, consolidated by remedy into 30 drafts, §8); roadmap candidate (22, §7); documented disagreement with an owner decision (4, §4); accepted technical debt (9, §5); owner action already tracked (4, a condition, never a new issue); rejected (0 after triage; three severities were cut to P3 and two findings re-read as disagreements by the challenge).

## 3. Validated findings ranked by impact

Thirty consolidated findings; each row is a GitHub-ready draft under the board's working directory, opened only on the owner's confirmation. "Seats" counts distinct independent seats (metadata). Challenge: outcome of the adversarial pass on the P0/P1 members.

| # | Finding (draft title, abridged) | Sev | Blocking | Category | Clusters | Seats | Challenge |
|---|---|---|---|---|---|---|---|
| I-01 | Discovery follows symlinks and junctions out of the repository | P0 | **yes** | defect | compiler-c11 | 3 | confirmed P0 by both challengers; the escape and the write-through reproduced again |
| I-03 | Restore the tree-sitter defect pin; test the ranges a wheel resolves | P1 | **yes** | defect | security-c4, security-c45 | 4 | c4 confirmed, blocking |
| I-05 | Corrupt or foreign-version store: refuse by name, repair, report | P1 | **yes** | defect | operations-c2, compiler-c7/c8/c9 | 9 | c8 confirmed, blocking (the gc half found worse than claimed); c2 confirmed P1; c7, c9 → P2 |
| I-12 | Windows console code page: MCP stdin, tools `--help` | P1 | **yes** | defect | security-c14, operations-c20 | 2 | c14 confirmed, blocking |
| I-02 | Every frozen plugin Protocol must be reachable, or leave the freeze | P1 | no | defect | plugins-c2/c3/c11/c21, security-c38 | 7 | c2 confirmed P1, blocking vote removed (two recorded remedies, both cheap); c3, c11, c38 → P2 |
| I-07 | Every tier-2 write atomic and byte-preserving | P1 | no | defect | compiler-c10, security-c35, representation-c34 | 4 | c10 confirmed P1 (the probe strengthened it); fix or accept before the tag |
| I-09 | Publication under concurrent readers (Windows swap; MCP reads outside one snapshot) | P1 | no | defect | compiler-c5, compiler-c6 | 7 | c5 confirmed P1 (a flawed first probe was redone with a readiness sentinel) |
| I-10 | A release tag must be a verified commit; publish gates must exist and be read back | P1 | no | gap | security-c6, security-c3 | 3 | c6 confirmed P1, blocking vote and "security" framing removed; c3 → P3 (ADR-0116's design is safe while nothing is configured) |
| I-11 | `mycelium.toml` honoured, fail-closed on MCP, governed | P1 | no | defect | security-c13/c24/c39, plugins-c15, operations-c8 | 6 | c13 reproduced independently, blocking vote removed; c24 confirmed P1 |
| I-04 | `PluginMeta.api_max` must be a literal the registry can refuse | P2 | no | defect | plugins-c1 | 9 | reproduced; downgraded to P2 as a one-line, golden-neutral fix recommended before the tag |
| I-14 | Bound the authored lane's read cost; type every parser refusal | P1 | no | risk | representation-c25/c26, security-c26, governance-c43 | 12 | c25 confirmed P1; c26 → P2 |
| I-16 | Authored-lane correctness sweep before KIR semantics freeze | P1 | no | defect | representation-c4/c22/c23/c24/c27/c28/c29/c30/c32/c33 | 19 | c22 confirmed P1; c4, c23 → P2 |
| I-18 | Identity contract: golden coverage and edge cases before it binds | P1 | no | gap | representation-c17/c18/c19/c2/c21/c3, plugins-c13 | 14 | c21 confirmed P1; c18, c2 → P2 |
| I-22 | Ingested identity tied to its source; survive re-ingest | P1 | no | defect | security-c27, representation-c36 | 5 | c27 confirmed P1 |
| I-23 | Query path: rank in FTS5, hydrate by rowid; warm MCP handle | P1 | no | risk | compiler-c31, security-c12 | 5 | c31 confirmed P1 |
| I-06 | Compile catch-all publishes an empty index on ENOSPC | P2 | no | defect | compiler-c32 | 1 | downgraded: the "core bug" half does not hold, the ENOSPC half does |
| I-13 | Build keys and the manifest cover the whole environment | P2 | no | gap | compiler-c1/c2/c15/c18/c20/c23, governance-c17, representation-c1 | 23 | c1 → P2 debt (ADR-0015/0154 accept the gap on a net that cannot see it); c2 → P2 (no released store affected) |
| I-15 | MCP serving bounds: fetch, ancestor walk, heading length, budget rule, neighbors URI | P2 | no | gap | security-c19/c21/c23, representation-c11, plugins-c20 | 7 | c21 → P2 |
| I-17 | Chunking and anchor semantics before anchors freeze | P2 | no | defect | governance-c26, representation-c7/c8/c9/c10/c12/c13/c40/c41, security-c18 | 14 | c26 → P2 |
| I-19 | Token estimate: scripts, calibration, 512-token window | P2 | no | gap | representation-c5/c6, security-c25 | 10 | c5, c6 → P3 (the estimate matches the shipped tokenizer for the scripts named) |
| I-20 | Declared-but-unenforced gates: coverage, DCO, benchmark, lock, docs mode, BLE | P2 | no | drift | security-c43/c5/c34, governance-c3/c9, quality-c1 | 11 | c43 → P2 |
| I-24 | Amendment pass over the normative documents | P2 | no | drift | 22 clusters (governance, representation, operations) | 20 | c4 → P2 |
| I-25 | Record compatibility beyond the five | P2 | no | gap | plugins-c7/c12/c25, representation-c16, compiler-c22, operations-c16 | 15 | c12 → P2 |
| I-26 | Writer path under contention: lock liveness/ownership, watch re-queue | P2 | no | defect | compiler-c3/c4, security-c11 | 10 | record |
| I-28 | Journal and doctor as a support path | P2 | no | drift | compiler-c29/c30, operations-c3/c4/c21 | 7 | record |
| I-29 | Snapshot lifecycle edge cases | P2 | no | defect | compiler-c14/c16/c19/c21, operations-c19 | 5 | record |
| I-30 | Front door: released version, PDF how-to, serve root, client config, cookiecutter install | P2 | no | drift | operations-c6/c7/c9/c12/c13, plugins-c16, security-c7 | 7 | record |
| I-33 | Plugin loading and seam robustness | P2 | no | gap | plugins-c22/c26, security-c29/c33 | 4 | record |
| I-34 | Standing dependency-vulnerability and secret signal | P2 | no | gap | security-c10 | 1 | record |
| I-36 | Threat-model suite asserts controls, not markers | P2 | no | gap | security-c40/c41 | 2 | record |

## 4. Decisions owed and documented disagreements with owner decisions

- **D-01 — What v1.0.0 exits on, and what it promises** (decision owed; clusters governance-c1, operations-c23, security-c2, governance-c5, governance-c8; challenge: P1, not blocking). The v1.0.0 label on Milestone 7 is the owner's recorded correction (ADR-0113's dated note, restated by ADR-0114, relied on by roadmap 7.3), so the stale records are spec 06 §1, `project.yaml` and the GitHub milestone title. What no record states: the exit gates the tag binds to (ADR-0138 says "Phase 4 is the 1.0 exit"), whether the D-030 Phase-4 gate (0/3, 0/1) binds the tag or is carried by name with an owner as v0.6.0 did, the supported-versions window SECURITY.md cites, where public RFCs live, and the red-main rule. One decision record beside D-030, restated on the M7 heading, closes all five and brings the three stale records to the label.
- **D-02 — Disagreement with D-032/ADR-0157** (representation-c15; 14 seats, challenge: P2, disagreement). Keeping `mycelium/document/v0` on a record whose old and new shapes refuse each other (`extra="forbid"`) contradicts compatibility.md's own token rule. The board does not contest the removal of the timestamps; it asks the owner to bump the token and record the manifest-golden move as the contract event it is, or to make the pinned non-frozen tags names rather than shapes and amend the rule.
- **D-03 — The module-facing surface at the tag** (plugins-c4; 6 seats; challenge: confirmed P1). ADR-0086's trigger has fired; nothing owns the decision; `contrib/chats` has no upper bound. Freeze, version or shrink, with a mechanism.
- **D-04 — Disagreement with the inherited tag-pin decision** (security-c9; challenge: P2, disagreement). Tag-pinned `setup-uv`/`setup-python` run in the jobs holding the Sigstore and PyPI identities; the test exempts them by name. Clerk check: 8 of 10 `ci.yml` uses and both identity-holding workflows are tag-pinned.
- **D-05 — The performance envelope v1.0.0 advertises** (compiler-c31, quality-c6, governance-c35; challenge on c31: confirmed P1). Own the sublinear candidate-generation work, or restate the envelope and budgets, or accept the misses explicitly at the tag.
- **D-06 — Disagreement with ADR-0015's first-claim rule** (compiler-c27; reclassified by the challenger). A candidate copy that sorts first captures a verified document's id and its citations, by recorded and tested design; name it as an accepted residual in the threat model or fail closed before identity freezes.
- **D-07 — Disagreement with ADR-0114's scope on the export bundle** (plugins-c14; reclassified). The interchange surface D-029 names for `app`/`codex` has no compatibility rule; amend the scope or reconcile D-029's sentence.

## 5. Accepted technical debt (recorded, no v1.0 action)

Nine clusters with a stated consequence: no per-stage parse timing; edge identity derived twice per edge and the edge set rewritten on a no-op build; restoring `.mycelium/` costs ~50 s of a 58 s cold build at 1 000 documents (roadmap 7.1 owns it); the vector pack name is a lossy projection of `model_id` with no model in the header (latent while one model exists); the manifest records duration but not the rebuilt count; the config-to-embedder mapping copied four times; builds from `main` report the previous release's version; 24 tool scripts restate the corpus list and 33 patch `sys.path`; anchors carry no namespace (7.2's checklist asks).

## 6. Rejected findings and why

The evidence filter dropped nothing: every one of the 410 findings named a tracked path, a number, a test or a command. The clerks rejected nothing as unsupported. The adversarial pass refuted no cluster outright; it cut four severities to P3 (the token estimate's per-glyph count for Cyrillic and Greek agrees with the shipped WordPiece tokenizer, so the "over-count" was measured against the wrong unit; the estimate/ADR-0007 "contradiction" is ADR-0011's recorded override; the unbuilt D-023 readers are ADR-0077's recorded decision; the missing publish environments are the unconfigured state ADR-0116 designed to be safe in), re-read two defects as disagreements (D-06, D-07), one as an owner action already prescribed (governance-c10), and refuted one leg of D-01 (the M7 = v1.0.0 label is the owner's recorded correction, not drift). Two member claims were corrected by the clerk's own checks: the b1647df stale-chunk window never reached a released store (store versions forced a recreate at every release), and only BUG-0022 is open (BUG-0024's record says fixed; its ledger row is the drift, I-24).

## 7. Roadmap proposal — what should follow v1.0.0 (for negotiation)

A proposal in the roadmap's vocabulary, as the EADOS plan phase produced on 2026-08-29: the maintainer issues numbers and accepts or re-cuts each. The first entry is not a new milestone but a re-cut of the open one, because D-01 is the decision every other row waits on.

### 7.0 The v1.0.0 cut (re-cut of Milestone 7 as the release milestone) — *v1.0 release blockers*

- **Objective:** tag v1.0.0 on a commit whose contracts, controls and documents say the same thing, with the owner's ledger installed and the exit criteria written down.
- **Justification:** the compatibility promise binds at the tag (ADR-0114); every item here is cheap before it and a contract event or a MAJOR after it.
- **Dependencies:** D-01 first (it decides the version and the gates); O-01 owner actions; the adversarial pass's confirmation of I-01…I-12.
- **Entry criteria:** D-01 recorded; the board's blockers triaged by the owner (fix, accept, or carry by name).
- **Exit criteria:** `tools/check_repo_settings.py` exits 0; `tools/adoption_report.py`'s index precondition met (TestPyPI rehearsal and PyPI upload done, `pypi` environment with a reviewer, tag ruleset); every surviving blocking issue closed or carried in an ADR; D-03 and D-05 taken; `release.yml` refuses to draft without a green full run of the tagged commit.
- **Principal risks:** the D-030 contribution gate cannot be met by engineering (0/3, 0/1), so the release either carries it by name again or waits on strangers; the identity and KIR items in I-16/I-17/I-18/I-19/I-22 are P1 "for the freeze" — recommended before the tag, each a MINOR-with-note today and a contract event after.
- **Included:** O-01; D-01, D-03, D-05; I-01, I-02, I-03, I-04, I-05, I-07, I-09, I-10, I-11, I-12; recommended pre-tag freeze hygiene I-16, I-17, I-18, I-19, I-22, I-24's two decision rows.
- **Why here:** the tag is the event; afterwards each row costs a MAJOR or a deprecation cycle.

### 7.1 v1.1 — Hardening — *v1.x hardening*

- **Objective:** close every P1 that was not blocking and the P2 defects with a reproduction, without a contract event.
- **Justification:** 23 P1/P2 defect clusters were reproduced on this commit; all heal with a command or a manual step today, none breaks a frozen contract.
- **Dependencies:** v1.0.0 tagged; I-05's typed store error precedes I-28/I-29.
- **Entry / exit:** entry on the tag; exit when the open P1s are closed and each P2 is closed or accepted in its issue.
- **Principal risks:** a fix that moves a golden (G6) must bump its stage version — I-13's mechanical net should land first.
- **Included:** I-06, I-13, I-14, I-15, I-20, I-25, I-26, I-28, I-29, I-30, I-33; D-02, D-06, D-07 as the owner rules.
- **Why here:** behavioural fixes under SemVer PATCH/MINOR, no new surface.

### 7.2 v1.2 — Ecosystem — *plugin ecosystem work* and *architectural enablers*

- **Objective:** make the second module the instrument that finds the module-facing API: build the D-023 mechanisms against a named external module, spin `mycelium-chats` out as D-029 plans, publish the agent-facing artefact D-027 reserved, and make modules discoverable.
- **Justification:** D-025/D-029 are the ecosystem thesis; today one module exists, by the maintainer, unpublishable (no index, tests importing core internals), and the API admits one module class (CLI-only). ADR-0086's own argument says only a second consumer can decide the surface.
- **Dependencies:** v1.0.0 on PyPI; intake open; D-03 taken; I-02/I-04 closed.
- **Entry criteria:** one named external module author (a D-030 engaged actor) or a deliberately different in-repo prototype (a wiki importer or ticket connector, as the plugin seats sketched).
- **Exit criteria:** one module published and loading against the released core with zero core patches; `mycelium-chats` released from its own repository; the stage/hook/tool readers built or re-deferred against the named consumer; a plugin listing and a client configuration for at least Claude Code and Codex.
- **Principal risks:** designing the surface from a sample of two is still a sample; the Store seam (R-ARCH) must be made real before any adapter.
- **Included:** R-ECO (plugins-c5/c17/c23/c24, security-c8, operations-c11, representation-c39), R-ARCH (compiler-c12, security-c36), I-33.
- **Why here:** everything in it presupposes an installable, tagged core and an open door.

### 7.3 v1.3 — Scale — *performance / scalability work*

- **Objective:** make the advertised envelope true or restate it: sublinear lexical candidate generation, the incremental floor at 10⁴ documents, memory and concurrent-client budgets.
- **Justification:** NFR-2 missed 9–16× and NFR-3 past ~1 200 documents at this commit, published and unowned; the first fix is measured and ranking-preserving (I-23).
- **Dependencies:** D-05; an idle machine of record; the 10⁵ query-profile manifest at the release commit.
- **Entry / exit:** entry on D-05; exit when the budgets are met at the stated envelope or restated with manifests, and the CI benchmark job can fail.
- **Principal risks:** an index change moves goldens and the G2 verdict; measure on a corpus the project did not write (ADR-0053's rule).
- **Included:** I-23, D-05, R-PERF (quality-c7), quality-c6, governance-c35, I-20's benchmark rows.
- **Why here:** it needs the tag's envelope decision and competes with ecosystem work for the one maintainer.

### 7.4 Security hardening — *security hardening* (a track across v1.1–v1.3, not a milestone of its own)

- **Objective:** the controls the model claims become tests; the supply chain gains a signal.
- **Included:** I-34 (audit the lock, read alert/scanning settings back), I-36 (assert B1/B8 controls), D-04 (pin the identity-holding jobs), R-TEST (security-c16 platform-variant gates, security-c42 the model path on a CI cell, compiler-c13 a crash-consistency harness).
- **Entry / exit:** entry at v1.1; exit when `pytest -m boundary` asserts every named control and a kill-matrix test runs on three operating systems.
- **Why a track:** each item is small; none should wait for a milestone of its own.

### 7.5 Developer experience — *developer-experience improvements* (a track)

- **Objective:** a stranger reaches a cited answer in ten minutes and a contributor reaches a green local run from the documents alone.
- **Included:** I-30 (front door), I-24 (the amendment pass), I-20 (declared gates made true or struck), R-OPS (operator documentation: install variants, configuration reference, upgrade/downgrade, recovery), I-28's support bundle, devex findings on the ladder's cost (721 s serial suite on Windows).
- **Exit:** issue #151's walk succeeds on a clean machine against the released tag; `CONTRIBUTING.md`, `AGENTS.md` §10 and the PR template list only rules a job enforces.

### 7.6 Deferred research — *deferred research* (held at spec 06 §3 triggers)

Relocation of a dead anchor by the digest the URI already carries (representation-c39); the learned-reranker trigger, deliberately not declared met (ADR-0152's headroom is reachable by re-ordering); the graph database; roadmap 7.1 (remote cache) and 7.2 (server profile) as held; Rust hot paths. None enters without its trigger and its own RFC.

## 8. GitHub issues drafted

Thirty drafts, one per row of §3, each with problem statement, supporting evidence (every member cluster's canonical claim and evidence entries), affected components, reproduction, architectural significance, acceptance criteria, suggested priority, references and dependencies. They are held under the board's working directory and opened **one at a time on the owner's confirmation** (owner instruction of 2026-10-05), in the order of §3, with label = the lead change type and milestone = the open roadmap milestone. No existing issue duplicates any of them: #149–#151 are the reserved first-contribution issues and are named as related where they touch (I-10, I-30, I-34).

---

## Appendix A — What was read and run

The board seats opened 301 distinct repository paths (76 under `src/`, 56 under `tests/`, 44 ADRs, 9 specification documents, 116 other); with the 25 legacy seats the union is 364 paths and 83 of the 103 tracked source files. 452 commands were run, 145 of them probes on scratch copies of `tests/fixtures/determinism` or targeted single-test runs; no seat ran the full suite, a benchmark, `tools/verify.py`, or a build of the repository root. The clerk's own probes, on 2026-10-05: `tools/check_repo_settings.py` (exit 1, eight settings absent, F2/F3 expired), `tools/adoption_report.py` (exit 1; 404 on PyPI and TestPyPI; 1 of 3 engaged actors; 0 of 3 recurring; triggers holding/unreadable), `pytest --co` (2 845 tests). The per-seat `read` and `ran` lists are in each review record.

## Appendix B — Finding records

The 410 finding records (19 fields each), the 180 cluster records, the clerks' contradiction notes and the challenge verdicts are kept in the board's working directory (`panel-7-12/board/`: `reviews/`, `legacy/`, `filtered/`, `clusters.json`, `challenges/`, `triage/adjudication.json`); the cluster ids cited throughout (`compiler-c11`, `plugins-c2`, …) are stable keys into it. They are not committed: the evidence a reader needs is quoted in the issue drafts and in §3.

## Appendix C — Challenge verdicts on the release-blocking candidates

Standard-model tier (33 P1 clusters without blocking votes, one challenger each): confirmed at P1 — compiler-c31, plugins-c4, representation-c21, representation-c22, representation-c25, security-c24, security-c27; downgraded to P2 — compiler-c1 (debt: ADR-0015/0154 accept the single-machine gap on a net that cannot see it), compiler-c2, compiler-c7, compiler-c9, compiler-c32, governance-c4, governance-c12, governance-c26, plugins-c3, plugins-c11, plugins-c12, representation-c15 (disagreement), representation-c18, representation-c2, representation-c23, representation-c26, representation-c4, security-c21, security-c38, security-c43, security-c9 (disagreement); downgraded to P3 — plugins-c5, representation-c5, representation-c6; reclassified as disagreements — compiler-c27, plugins-c14.

Frontier tier (the P0 with two challengers, the 15 P1 clusters with release-blocking votes with one each; 17 verdicts): **confirmed and release-blocking** — compiler-c11 (P0, both challengers; the authored-lane escape, the write-through and the self-junction loop were re-reproduced, the loop judged a DoS component rather than the P0's driver; one correction to the reviewers: the pre-6.20 `rglob` walk followed the junction too, so it is not a regression), compiler-c8 (rollback/gc wipe; the gc half worse than claimed), security-c1 (the expired F2/F3 remedies, re-verified live), security-c14 (MCP stdin), security-c4 (tree-sitter pin); **confirmed at P1, blocking vote removed** — compiler-c10 (tier-2 writes; the uncited `except Exception` around the write makes it worse), compiler-c5 (Windows swap; a flawed first probe redone), operations-c2 (corrupt store; no sqlite3 error is translated anywhere), plugins-c2 (Connector; two recorded remedies); **downgraded** — governance-c1 (the M7 label leg refuted as the owner's recorded correction; the missing exit gate stands at P1), operations-c23 (P1: record that the tag carries the gate), security-c13 (P1, reproduced independently), security-c6 (P1; `workflow_call` is called by nothing), plugins-c1 (P2, a one-line fix), security-c3 (P3, ADR-0116's safe-when-unconfigured design); **reclassified** — governance-c10 (an owner action ADR-0158 already prescribes: the PATCH and the message to the contributor). No frontier verdict refuted a cluster outright.

## Appendix D — Reviewer verdict tally (metadata, not a vote)

55 of 55 assessments: CONDITIONAL GO (30 board seats, 25 legacy seats). Question answers across the seats that owned each: Q1–Q13 "partially" without exception; Q14 "no" (no owner decision contradicted) from the two seats that walked the full log, "partially" from five that found ADR-level contradictions; Q15 "no" from six of eight. 260 strengths named; 88 insufficient-evidence notes; 180 milestone proposals (35 of them for the v1.0 cut), folded into §7.
