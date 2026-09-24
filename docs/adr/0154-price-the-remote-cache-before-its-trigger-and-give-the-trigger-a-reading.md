# ADR-0154: Price the remote cache before its trigger fires, and give the trigger a reading

- **Status:** Accepted
- **Date:** 2026-09-23
- **Deciders:** the maintainer (who chose, on 2026-09-23, to measure rather than to build or
  to override) with the tech-lead (EADOS delivery agent), per RFC-0001 / spec 06 §3
- **Related:**
  [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (a deferral names the
  condition that ends it, in code — the rule this applies to a product deferral),
  [ADR-0138](0138-recut-the-adoption-gates-onto-acts-we-can-observe.md) (the adoption
  instrument this extends, and the other shape an unobservable condition has taken),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the build keys, and the
  risk it accepts for a behaviour change without a stage-version bump),
  [ADR-0009](0009-adopt-build-publication-semantics.md) (a file's mtime becomes its
  document's `created_at`/`updated_at`),
  [ADR-0133](0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md)
  (the incremental floor a restored cache could reach),
  [ADR-0145](0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md)
  (what a blob write costs on the machine of record, and why),
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the reference profile this reuses); D-005 and D-008 (the derived world is a cache, and a
  shared one is the eventual team answer), D-017 (no telemetry), D-030; spec 02 §4.1, spec 06
  §3 and Phase 5; roadmap 6.12, 6.20, 6.30, 7.1;
  [BUG-0034](../bugs/2026/09/BUG-0034-the-reference-profile-harvests-one-of-the-two-corpora-it-names.md),
  [BUG-0035](../bugs/2026/09/BUG-0035-a-generated-reference-title-can-be-yaml-the-parser-refuses.md)

## Context

Roadmap 7.1 is the remote build cache — *team-scale value without a server*, the Bazel move
D-005 named as the eventual answer to a derived store every clone rebuilds. It was asked for
on 2026-09-23, and three documents state its entry rule in the same words: RFC-0001 (*"Phase
5 items enter only through their deferred-decision triggers (doc 06 §3) and their own future
RFCs"*), spec 06 §Phase 5, and the roadmap's own Milestone 7 heading. Spec 06 §3's row for it
reads:

| Decision | Deferred until | Trigger |
|---|---|---|
| Remote build cache | Phase 5 entry | ≥ 1 team dogfooding with measured duplicate-build pain |

Reading it found two things, and the second is the one that matters.

**The trigger has not fired.** `tools/adoption_report.py` stood at one engaged actor of
three on 2026-09-20, with no recurring contributor and the package on no index, and the
v0.6.0 release notes say external adoption stands at zero. Nobody outside this repository
builds its compiler, let alone a team.

**The trigger could not fire, because nothing could measure it.** *Measured duplicate-build
pain* had no unit and no instrument, so a team that had the pain could only assert it, and
the owner could only believe the assertion or not. That is the defect ADR-0138 found in the
adoption gates two rows up the same table, and it is the case ADR-0118's rule refuses: *a
deferral whose condition cannot be written as code has no expiry, and is not granted.*

The maintainer was offered four courses — measure the ceiling and make the trigger
evaluable; write the RFC now and hold it at the trigger; enter 7.1 by an owner decision
overriding the trigger; take 7.3 instead — and chose the first.

**What there is to measure.** A remote cache can change exactly one thing: a **cold build**.
After the first build every rebuild is incremental — a thousand-document no-op in 1.6 s and a
one-document edit in 1.7 s since roadmap 6.20 — and has nothing left for a cache to skip. And
within a cold build it can skip only what the build caches, which is two stages: **parse**
and **chunk** (spec 02 §4.1, ADR-0015). Assembling each document, writing the index, resolving
the graph and publishing the snapshot run for every dirty document whatever a cache holds —
and on a fresh checkout every document is dirty.

## Decision

**7.1 stays out, and is held at its trigger by name.** Its checkbox stays open, its line says
why and points here, and nothing of a remote cache is built.

**The pain gets an instrument.** `tools/measure_cache_ceiling.py` builds *fresh checkouts* —
the corpus copied to a new path with every file written anew, which is what `git clone` and
`actions/checkout` produce — and varies only what is in `.mycelium/`:

| Arm | What `.mycelium/` holds | What it stands for |
|---|---|---|
| **cold** | nothing | every clone and CI runner, today |
| **seeded** | every parse and chunk artifact with the index row naming it, nothing else | a remote cache that answers instantly — **the ceiling** |
| **restored** | another checkout's whole directory | caching `.mycelium/` in CI, today, with no feature built |
| **restored-mtimes** | the same, with each document's mtime set to the cached checkout's | a directory cache over a checkout whose mtimes are deterministic |

The seeding and the restore are timed apart from the builds they precede — the seeding is the
local half of every fetch (re-hash, write, insert) — and the computation a miss runs is timed
in memory against the one a hit runs instead, so the part of any saving that is compiler can
be told from the part that is this machine's filesystem. Every build records its cache hits
and its output digests, because an arm that missed, or a cache that changed the output, would
be timing something other than its name.

Measured on the reference profile, three rounds, arms rotated
([report](../benchmarks/2026-09-23-the-ceiling-a-remote-cache-could-buy.md); p50, seconds):

| | 250 documents | 1 000 documents (998 compiled) |
|---|---:|---:|
| cold | 15.53 | 55.03 |
| seeded — **the ceiling** is the difference | 7.37 (−52.6 %) | 35.80 (−34.9 %) |
| computation a hit saves, in memory | 2.26 | 9.19 |
| seeding the artifacts first | 7.96 | 39.07 |
| restored | 7.68 | 40.10 |
| restored-mtimes — **nothing rebuilt** | 0.59 | 1.56 |
| restoring the directory first | 12.65 | 54.00 |

Three readings, in order of how far they travel. **The computation a cache can save is about
9 ms a document** on this CPU — 2.3 s and 9.2 s — and that is the only part of the ceiling
that is the compiler's rather than the machine's. **A cache that keeps its hits pays the
ceiling back here**: writing the fetched blobs costs as much as the build no longer spends, so
at 1 000 documents the ordinary design at infinite bandwidth is **20 s slower** than building
cold, because on a machine where a small file costs milliseconds every design that
materialises files pays per file. And **the largest number is not a stage cache's at all**: a
restored directory is held to the ceiling only because every document of a fresh checkout has
a new mtime, and with the cached checkout's mtimes the same directory rebuilds nothing, 26×
and 35× faster in the build than cold, against the ideal remote cache's 2.1× and 1.5×.

**The trigger gets a reading, and a watcher.** Its number is left where the spec put it; its
two words are given meanings a command can check:

- **measured** — a report from the instrument, run on the team's own corpus with
  `--corpus` and pasted into an issue or an issue comment, whose saving lies outside the
  measurement's own noise: every seeded build faster than every cold one;
- **team** — two or more people building that corpus (`TEAM_PEOPLE_BAR`), by the reporter's
  own count, which no instrument could take for them.

`tools/adoption_report.py` reads the reports, from external logins only, and fires the
trigger on one that qualifies (`TEAM_REPORTS_BAR`, the spec's *≥ 1*). **A fired trigger is a
finding with ADR-0118's polarity**: a gate fails until it is met, a deferral fails once its
condition *has* fired, because the decision it deferred is then owed. The report exits
non-zero until the owner takes that decision, and the trigger leaves the tool in the change
that records it, as a closed deferral leaves `DEFERRALS`. **How much pain is enough** to build
an L-sized feature with a new trust boundary is precisely the decision the trigger defers, so
no magnitude is written into the code; the evidence the report prints — cold-build cost,
ceiling, the team's own cold-build rate — is what the owner decides with. Closing a report's
issue as *not planned* withdraws it.

**What the eventual RFC owes is recorded here, so that it is not rediscovered.** Four facts
the measurement established or exposed, none of which a design written without it would have
started from:

1. **Build keys are portable, measured.** Two checkouts of one tree at different paths, with
   different mtimes and different line endings — a CRLF checkout seeded from an LF build, the
   Windows clone under `core.autocrlf` — mint the same parse and chunk keys, and every artifact
   under a shared key is byte-identical (`tests/test_measure_cache_ceiling.py` pins it). The
   precondition of any shared cache holds today.
2. **The parse key does not name its parser's version.** The extract stage's key carries the
   tree-sitter binding and every grammar's version (roadmap 5.1); the parse key carries
   `PARSE_STAGE_VERSION` and nothing of `markdown-it-py`, which `pyproject.toml` admits at
   `>=3.0`. On one machine ADR-0015 accepts the gap, because gate G6 and the
   incremental-equals-clean suite compare cached against fresh output on every CI run. A
   *shared* cache mixes machines whose resolved parsers may differ, and no net compares
   across them — so the RFC must either key on the environment that produced an artifact or
   admit writers from one pinned environment only.
3. **An index row is an assertion the CAS cannot check.** `cas_get` re-hashes a blob against
   its *name*; nothing can re-hash it against its *key* without recomputing the stage. A remote
   cache's key → digest rows are therefore trusted input, cache poisoning is the threat, and
   the threat model needs a boundary row before the feature exists, not after.
4. **The document record carries the checkout's mtime, and that is what a cache cannot
   reach.** ADR-0009 made `created_at`/`updated_at` the file's mtime, *"stable across
   rebuilds in place"*, so the dirty check compares mtimes. Across checkouts nothing is
   stable: a clone's mtimes are the moment it was written, every document is dirty, and any
   cache — remote, restored, or ideal — can skip at most parse and chunk. With the mtimes the
   cache was built with, a restored `.mycelium/` rebuilds **no document** (0.59 s and 1.56 s,
   the incremental floor of roadmap 6.20). So the remote cache 7.1 describes is not where a
   team's cold build is spent, and an RFC for it would have to start from that. Anything that
   makes a checkout's mtimes a function of its commit — `git restore-mtime` is one — would give
   a directory cache this today, *likely*, from how that tool works; it was not run here. The
   decision about the record itself is filed as 7.7.

## Alternatives Considered

- **Enter 7.1 now by an owner decision overriding the trigger.** Offered and not chosen. It
  builds a feature for no consumer, which is the case the trigger exists to prevent, and it
  would have designed a transport before knowing that the stage artifacts it moves are worth
  about 9 ms a document, that keeping them costs more than that on a machine like this one,
  and that the checkout's mtime — which no transport touches — is the larger cost.
- **Write the RFC now and hold it at the trigger.** Offered and not chosen. An RFC written
  before a team exists guesses at the things a team would decide — which backend it has, who
  may write, how large its corpus is — and would have had to guess at its own motivation too:
  every number above is one its motivation section would otherwise have asserted.
- **Measure, and leave the trigger in prose.** Rejected by ADR-0118's rule: a measurement
  nobody is obliged to take, feeding a condition nothing evaluates, fires with nothing
  watching — the failure that rule was written after.
- **Write a magnitude into the trigger** — *N* hours of cacheable build a week. Rejected: that
  number is the decision the trigger defers, and fixing it in code would take it from the owner
  while looking like an implementation detail. The report prints the weekly figure beside the
  verdict instead.
- **Count this repository's CI as the team.** Rejected on roadmap 6.12's rule — closing a gate
  by counting ourselves. The CI is the maintainer's, and its cold builds are a performance
  question with its own items.
- **Read discussions as well as issues.** Deferred: one documented channel is enough to
  evaluate the trigger, and the discussion query the report runs today fetches authors, not
  bodies. A report posted in a discussion is still visible to a reader; the tool says where to
  post one so it is counted.
- **Ship the instrument as a `mycelium` subcommand.** Rejected: the CLI is a public interface
  (spec 01 §5, spec 05) and this measures a deferred decision's precondition; a tool in
  `tools/`, run from a clone, is what every other instrument here is.

## Consequences

- **`tools/adoption_report.py` exits 1 when a deferral's trigger has fired**, as well as when
  a gate is not met, and prints a *Deferred decisions* section. Today it holds: no report has
  been posted. Parsing a stranger's issue body is new input to a maintainer-run tool, and
  `docs/security/threat-model.md` §3 records how it is held: numbers only, nothing echoed,
  malformed or hostile JSON skipped rather than fatal.
- **The spec's row changes by a parenthesis, not a number.** Spec 06 §3 notes the reading
  and the instrument; `docs/workflow/adoption.md` says how a team posts a report.
- **Three follow-ups are filed rather than folded in.** 7.5 — 7.2's three triggers are the
  same kind of sentence and get the same question. 7.6 — the reference profile's generator
  builds a corpus other than the one it names: it harvests one of its two sources (BUG-0034,
  found while exporting the measurement's inputs) and can write a title YAML refuses, which is
  why the thousand-document corpus compiled 998 (BUG-0035). 7.7 — what a document record's
  timestamps should be a function of, now that the mtime is measured to be what keeps every
  fresh clone cold.
- **What the numbers are, and are not.** One machine — Windows 11 with a real-time scanner in
  the file path, whose small-file costs the benchmarks README calibrates — three rounds, and a
  generated corpus (BUG-0034's). The compute split is the part that travels; the rest is this
  filesystem. The seeded arm is a cache at infinite bandwidth and zero latency; the restored
  arms copy a directory locally rather than download and unpack an archive. CRLF is the only
  cross-platform variable exercised. `people` and the cold-build rate are self-reported. Each
  limit is a reason the trigger decides nothing on its own.

## References

- `tools/measure_cache_ceiling.py`, `tools/adoption_report.py`;
  `tests/test_measure_cache_ceiling.py`, `tests/test_adoption_report.py`.
- [`docs/benchmarks/2026-09-23-the-ceiling-a-remote-cache-could-buy.md`](../benchmarks/2026-09-23-the-ceiling-a-remote-cache-could-buy.md) and its manifest.
- `docs/workflow/adoption.md` § *The deferred decision it also watches*;
  `docs/security/threat-model.md` §3.
- Re-runnable: `python tools/measure_cache_ceiling.py --out <scratch> --harvest-root <clean
  export>`; `python tools/measure_cache_ceiling.py --corpus <repo> --out <scratch>`.
