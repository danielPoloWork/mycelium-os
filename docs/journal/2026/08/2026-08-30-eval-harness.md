# 2026-08-30 — evaluation harness (roadmap 2.11)

- **Session scope:** roadmap item 2.11 — eval harness v0 + the first 20 judged cases over
  Mycelium OS's own docs (spec 04 §7).
- **PR:** #24 (`feat/eval-harness`), one item, one PR. Follows #23 (2.10), merged.

## What got done

- `src/mycelium/eval/` — `metrics.py` (Recall@k, nDCG@10 with exponential gain, MRR,
  citation coverage), `retrievers.py` (the product and the grep incumbent),
  `harness.py` (per-slice reporting, gates, run manifests), `cases.py` (JSONL sets).
- `eval/cases.jsonl` — 20 judged cases across seven slices, with `eval/README.md` stating
  what the set proves and what it does not.
- `tools/build_eval_cases.py` — judgments as data, validated against a real build so a
  case citing a non-existent anchor cannot be committed.
- `mycelium eval [--set] [--retriever] [--gate] [--json]`; runs written to
  `.mycelium/eval/`.
- Evaluation records added to `sdk.types` (`mycelium/eval-case/v0`,
  `mycelium/eval-run/v0`) and to the JSON Schema export.
- ADR-0013; 406 tests passing (+24).

## The harness found a real defect on its first realistic run

Every natural-language question scored zero. Not a metric bug — the product genuinely
returned nothing:

```
'license'                            -> 5 hits
'license apache nonexistentword'     -> 0 hits
'what license does the project use'  -> 0 hits
```

FTS5 combines adjacent quoted terms with an implicit **AND**, so a single word the corpus
lacked emptied the whole query — through the CLI and both MCP tools alike. Filed as
**BUG-0005** (high severity) and fixed by joining terms with `OR`, which is what BM25 is
for: a partial match is a result to be *ranked*, not a reason to answer "nothing found".

Twenty short test queries across milestones 2.6, 2.8 and 2.9 had all passed over it,
because short queries happen to have all their terms present. This is precisely what
D-010 says evaluation is for, and the argument for shipping the grep baseline now rather
than at 3.7: without a second retriever to compare against, a uniformly zero score looks
like a hard corpus rather than a broken product.

## First measured result

| | Mycelium | grep | |
|---|---|---|---|
| nDCG@10 | 0.70 | 0.55 | +26 % |
| MRR | 0.83 | 0.62 | +35 % |
| p95 latency | 3 ms | 52 ms | 17× |

G1 (citation coverage 1.00) and G4 (no invented matches) pass. More useful than the win is
where it is weak: `relationship` 0.32 — the typed edge graph does not exist until milestone
5 — and `conceptual` 0.66, barely ahead of grep, which is exactly the gap hybrid retrieval
has to close to earn G2 at 3.3.

## Honesty carried in the artifacts, not just the prose

- The judgments were assigned by the agent that wrote most of the documents being judged.
  Stated in `eval/README.md`, in the generator's docstring, and in the ADR: this is a seed
  set for regression detection and the grep comparison, not an independent benchmark.
- Abstention is only measured in the extreme. A query abstains when it returns nothing,
  which happens only when *every* term is absent; a natural-language question about an
  uncovered topic still returns low-ranked noise. Score-calibrated abstention needs the
  planner (3.7), so G4 currently proves that the system does not invent matches and no
  more.
- Gates that cannot be evaluated yet (G2, G3, G5) are listed with the reason, because a
  gate list with silent gaps reads as a gate list that passed.

## A contract corrected in passing

Adding the eval records exposed a shortcut: the snapshot manifest's `schema_versions` was
reporting every exported contract rather than the artifact classes the snapshot published
(the spec's example lists four). Narrowed, and the determinism golden re-blessed — the
workflow 2.10 built for exactly this case.

## Where the project stands

- Milestone 2: 2.1–2.11 ✅ · 2.12–2.14 open. Every *functional* item of the walking
  skeleton is done: the corpus compiles, publishes, serves over CLI and MCP, rebuilds
  byte-identically, and is now measured against the incumbent.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (406 passed), `pytest -m determinism`, `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #24 to merge. The remaining M2 items are documentation and configuration
  rather than compiler work: **2.12** (brand + README redesign) and **2.13** (i18n
  structure) are both deferred by the owner — do not start them unhinted — and **2.14**
  (configuration loading) was filed at 2.8 and is the natural next code item.
- When 2.14 lands, `ChunkingPolicy` and the namespace become configurable, which will
  change compiled output for anyone who edits `mycelium.toml` — the determinism golden
  pins the *defaults*, so it should not move.
