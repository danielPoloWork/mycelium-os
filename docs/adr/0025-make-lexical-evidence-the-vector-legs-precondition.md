# ADR-0025: Make lexical evidence the vector leg's precondition, and refuse every similarity floor

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §2, §7.3
- **Related:** [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (which
  measured the failure and filed this item), [ADR-0013](0013-adopt-the-evaluation-harness.md),
  [ADR-0024](0024-serve-what-the-configuration-admits.md); D-009, D-011; roadmap 3.11

## Context

ADR-0017's worst finding was structural: **hybrid destroys abstention**. Cosine similarity
produces a ranking for *every* query, so a vector leg asked for 50 candidates returns 50,
and hybrid answered all four judged `unanswerable` cases where lexical abstained. A
similarity floor was swept from 0.50 to 0.75 and refused: the two populations overlapped
(unanswerable 0.6364-0.6677, answerable from 0.6427), so any floor traded false answers for
lost recall at an arbitrary exchange rate. Roadmap 3.11 asked for a different signal -
lexical agreement as a precondition, score-gap analysis, or per-corpus calibration - each
measured before it ships.

All three were measured on the current corpus (646 chunks, bge-small-en-v1.5, the 20 judged
cases). The judged set's four unanswerable queries were redrawn at 3.7 to be *alien* to the
corpus domain (bread baking, birds of prey, music theory, coastal geology), and that matters below.

**What the distributions say.** On the judged set, three shapes now separate cleanly:

| signal | answerable (16) | unanswerable (4) | separates the judged set? |
|--------|----------------:|-----------------:|:--------------------------|
| top-1 similarity | 0.6406-0.8362 | 0.5398-0.5879 | yes |
| top-1 - top-2 | 0.0020-0.0861 | 0.0003-0.0095 | no (overlap) |
| top-1 - top-10 | 0.0371-0.1834 | 0.0139-0.0243 | yes |
| top-1 - median(top-50) | 0.0625-0.1944 | 0.0268-0.0354 | yes |

That looks like a reversal of ADR-0017 - until the *background* is measured: the cosine
similarity of 300 unrelated chunk pairs from this corpus sits at p50 **0.6241**, p95
**0.7148**, max 0.7795. Unrelated text scores 0.62-0.78 while a *relevant* answer can score
0.6406: in the band that matters, absolute similarity carries no relevance meaning at all
(embedding anisotropy). The judged unanswerables separate only because they are alien -
they score below the background median, i.e. further from the corpus than the corpus is
from itself.

**The counterfactual that decides it.** Eight probe questions this corpus genuinely cannot
answer, phrased in its *own vocabulary* (payment gateways, Kubernetes deployment, SSO for
the MCP server, a web dashboard, analytics retention, sharding, GPU acceleration, a
newsletter):

| | top-1 similarity | top-1 - top-10 | lexical hits |
|---|---:|---:|---:|
| 8 near-domain unanswerable probes | 0.6708-0.7414 | 0.0226-0.0571 | 10 of 10, all |

Every floor that passes the judged set (it must sit in the empty band 0.588-0.641) answers
**all eight** probes - their scores sit squarely inside the answerable band. The gap
signals straddle their boundary. And the lexical precondition answers all eight too. **No
measured signal detects near-domain unanswerability.** The difference between the
candidates is therefore not detection power - none has it - but what they *guarantee* and
what they cost to hold.

## Decision

**Lexical evidence is the vector leg's precondition.** In `mycelium.retrieval.search`, when
the profile is hybrid and the lexical leg returns nothing, the vector leg is *withheld*:
the outcome is empty, carries a note saying why (naming this ADR), and pays no embedding
latency, because a query that will get no answer should not spend 30 ms proving it. When
lexical finds even one hit, both legs run and fuse exactly as before.

The property this buys is **abstention parity with the gated baseline, by construction**:
hybrid abstains precisely where lexical abstains, on any corpus, for any query set, with no
constant to calibrate and no knob to forget. Lexical abstention is the behaviour gate G4
already gates; hybrid now inherits it instead of undoing it.

**No similarity floor ships, and none is configurable.** A floor is a per-corpus, per-model
constant that claims to detect unanswerability, and the probes show it cannot - it passes
the judged set only because that set's unanswerables are alien. A deployment has no judged
unanswerable set of its own to re-verify against, so the constant would silently rot. The
gap signals fail the same measurement, and per-corpus calibration cannot manufacture a
separation that does not exist (the bands overlap: answerable begins at 0.6406, the probes
begin at 0.6708 - inside it).

## Alternatives Considered

- **A calibrated similarity floor** (absolute, or relative to the corpus's background
  band). Rejected on the probe table: every floor that passes the judged set answers all
  eight near-domain probes, and the background measurement shows why - unrelated pairs
  score 0.62-0.78 on this model, so the floor separates "alien" from "everything else",
  not "unanswerable" from "answerable". Shipping it would look like a fix and be one only
  against questions nobody near the corpus would ask.
- **Score-gap abstention** (top-1 minus top-10, or minus the median). Rejected: separates
  the judged set, straddled by the probes (0.0226-0.0571 across a boundary at
  ~0.024-0.037). Same artifact, weaker margin.
- **The precondition per hit rather than per leg** - drop vector-only hits everywhere.
  Rejected: that turns the vector leg into a pure re-ranker and forfeits the recall
  contribution G2 measured (+5.8 % nDCG overall comes partly from vector-only hits); the
  failure being fixed is the *empty-lexical* case, so the guard belongs on exactly that
  edge.
- **Combine signals** - abstain when lexical is empty only if similarity is also low.
  Rejected: the precondition alone already restores G4 to 0 % on the judged set, and the
  added floor contributes nothing but the constant this ADR refuses to own.
- **A config knob to disable the precondition.** Rejected: a knob nobody has eval evidence
  for is a liability (D-011), and the only behaviour it could re-enable is answering
  questions the corpus cannot answer.

## Consequences

- **Gate G4 for hybrid: 100 % -> 0 %** on the judged set, measured with the real model.
  Every answerable metric is **byte-identical** before and after - the precondition fired
  on zero answerable cases, so its cost on this corpus is exactly nothing.
- **G2 is unchanged and hybrid stays opt-in.** The same run reports +5.8 % nDCG overall
  (bar +5 %) but `conceptual` -5.7 % and `injection` -22.6 % (bar -2 %): this item removes
  one of hybrid's two disqualifiers, not both. The slice regressions are 3.12/3.13
  territory, and the default stays `lexical`.
- **The forgone class is real and stated**: an answerable query sharing not one surface
  form with its answer (FTS5 `unicode61` does not stem, so "fails" does not match
  "failed") now abstains under hybrid where the raw vector leg might have found the
  passage. On the 16 judged answerable cases that class is empty; on a corpus where it is
  not, G2's protected slices are where the loss would surface, which is the gate built to
  catch it.
- **Near-domain unanswerables remain unsolved, on purpose and in writing**: the probes
  defeat every signal measured *including the shipped one* (they all have lexical hits).
  The precondition's claim is parity with lexical, not unanswerability detection. Anything
  stronger needs signals no ranking function provides - a claim-verification layer, which
  is later-phase material.
- **Two behavioural bonuses**: the empty query no longer returns 50 nearest neighbours
  under hybrid, and an abstained query pays no `embed_query` latency (the leg is withheld
  before the model runs, worth ~30 ms p95 on CPU).
- No config keys change, so the determinism golden is untouched; the eval baselines are
  re-blessed only because this ADR and its journal entry grow the corpus.

## References

- Spec 04 §2 (candidate generation), §7.3 (gates G2, G4); D-009, D-011
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) - the measured failure
- Measurements: judged-set distributions, background pair band, near-domain probes, and the
  before/after eval runs (roadmap 3.11, PR #41)
