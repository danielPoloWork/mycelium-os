# 2026-08-30 — the local embedder, hybrid retrieval, and the gate that said no (roadmap 3.3)

- **Session scope:** roadmap item 3.3 — local ONNX embedder, vectors keyed
  `(chunk_digest, model_id)`, hybrid RRF (D-013/D-009; spec 04 §§3, 7.3).
- **PR:** #33 (`feat/local-embedder-hybrid`). Follows #32 (3.2), merged as `587b950`.
- **The headline is a refusal:** hybrid retrieval works, is measured, and **is off by
  default**, because gate G2 said so.

## What the measurement decided

Everything in this item was buildable from the existing seams. What could not be decided in
advance was whether hybrid should be *on*, and spec 04 §7.3 is explicit that the harness
decides: ≥ +5 % nDCG@10 overall **and** no slice worse than −2 %.

Run against our own snapshot (78 docs, 564 chunks, 559 vectors) over the 20 judged cases:

| Retriever | nDCG@10 | R@10 | MRR | p50 |
|---|---|---|---|---|
| lexical | 0.4970 | 0.7292 | 0.5151 | 3 ms |
| hybrid | **0.5603** (+12.7 %) | 0.7708 | 0.5677 | 33 ms |
| grep | 0.4304 | 0.7396 | 0.4277 | 85 ms |

The overall bar is cleared comfortably. The slice bar is not: `exact` falls
0.9531 → 0.7838 (**−17.8 %**), because the vector leg dilutes queries where a literal term
*is* the answer. `relationship` meanwhile more than doubles (+117 %), which is the shape
everyone expects and exactly why an overall average must not be the whole test.

**And a worse finding the gate did not need.** On the four `unanswerable` cases, hybrid
answers *all four*: every chunk has non-zero cosine similarity to every query, so a leg
asked for 50 candidates returns 50. I swept a minimum-similarity floor from 0.50 to 0.75
before conceding, and the data closed the door: unanswerable queries scored **0.6364–0.6677**
while answerable ones scored **0.6427–0.8362** — overlapping ranges, with one answerable
case *below* three unanswerable ones. No floor separates them, so none ships. Filed as 3.11.

So: `[retrieval] profile = "lexical"`, hybrid one setting away, README says so. That is not
a disappointing outcome — it is the milestone goal's explicitly allowed one, and it is the
first time the harness has overruled a design intention.

## The three tensions, and how each resolved

- **A 133 MB model versus "zero network calls unless configured" (D-017).** The registry
  pins every file by URL, size and SHA-256; resolution is `model_path` → cache → *refuse*,
  and the refusal names `allow_download`, names `model_path`, states the megabytes, and says
  builds continue without vectors meanwhile. Downloads verify the pin before installing, so
  a substituted artifact never lands at the destination path even briefly.
- **ONNX is not portably deterministic.** Kernels are selected by instruction set. The stage
  declares `deterministic: false` — which spec 02 §4.1 explicitly allows — and G6 now builds
  its corpus with `provider = "none"` *stated in code*, so the golden cannot depend on
  whether the machine running CI happens to have a model cached.
- **Twenty-odd packages for a lexical-only user.** An optional extra, with absence degrading
  the build rather than breaking it (spec 02 §4.3): `degraded: ["vectors"]`, lexical intact.

## What the benchmarks corrected

I wrote in the ADR that an exact scan "is fast enough inside the envelope". The benchmark
said **168 ms over 10 000 chunks** against a 60 ms budget — at one tenth of the reference
profile. Two rounds of query shaping followed:

1. Score from `(key, vector)` only and hydrate full chunk rows for the top-k alone. The
   original `SELECT c.*` dragged every chunk's text and JSON columns into Python to rank
   them and threw all but 50 away. **168 → 113 ms.**
2. Skip the joins entirely when there are no filters — they exist only to filter.
   **113 → 94 ms.**

Still over budget, and linear. So the ADR now *states the limit* instead of claiming the
budget: it is affordable today precisely because G2 left hybrid opt-in, and making the
vector leg fast enough to be a default is roadmap 3.12 — a prerequisite for hybrid ever
earning one. The wrong claim survived about twenty minutes because a benchmark existed to
contradict it.

## What else the measurement turned up

Running the harness by hand exposed **[BUG-0007](../../../bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)**:
gate G4 fails for the *lexical* retriever too, at 25 %, because building this repository
indexes `tests/fixtures/determinism/knowledge/` and a fixture contains the word "broker",
answering the unanswerable case `q-0019`. Pre-existing since #24, invisible because CI has
no eval job yet (that is 3.7). Not fixed here: rewriting a judged case to fit the corpus is
the one move D-010 forbids, so it is recorded, filed as 3.10, and the number is reported
rather than suppressed.

Running the shipped binary in a Windows terminal — the check ADR-0010 made standing practice
— turned up a second one, and this one was small enough to fix here:
**[BUG-0008](../../../bugs/2026/08/BUG-0008-bom-hides-frontmatter.md)**. A UTF-8 byte-order
mark puts the `---` fence at byte three, so `split_frontmatter` decided the document had
none: metadata was ignored and the frontmatter block, `mycelium_id` and all, was indexed as
prose and came back as a *search result*. Identity was unaffected — the orchestrator's
pinning path had handled the BOM since 2.7 — so the damage was confined to content, which is
why nothing noticed. Every test fixture is written by `write_text`, which never emits a BOM;
the file that exposed it was written by PowerShell, which does so by default.

## Where the project stands

- **3.3 complete** pending merge. Milestone 3: 3.1, 3.2, 3.3 done; 3.4–3.12 open (3.9–3.12
  were filed by this item).
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (514 passed, 18 skipped — the skips are the model-dependent tests, which run
  here and skip in CI), benchmarks run, `python tools/consistency_lint.py` passes.
- The G6 golden's only change is `config_digest`, verified field by field before re-blessing:
  every document, chunk, count and artifact digest is byte-identical.

## How the next session resumes

- Wait for PR #33 to merge, then **3.4** (`mycelium_neighbors` on authored links +
  `mycelium_explain`). It adds the third candidate generator, and `mycelium.retrieval` was
  built so a new leg is one more rank list into the same fusion.
- Carry into 3.4: the `exact` regression above is the first *measured* argument for spec
  04 §2's planner (route identifier-like queries lexically). That planner arrives with the
  symbol leg, and now it has evidence behind it rather than a design intuition.
