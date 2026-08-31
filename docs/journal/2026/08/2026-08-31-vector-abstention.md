# 2026-08-31 — the floor that measured well and shipped anyway would have been a lie (roadmap 3.11)

- **Session scope:** roadmap 3.11 — abstention for the vector leg, the finding that cost
  hybrid its default (ADR-0017). Route: frontier-reasoning / high, and the weight really was
  in the decision, not the diff.
- **PR:** #41 (`feat/vector-abstention`). Follows #40 (3.9), merged as `a8df58d`.
- **Milestone 3:** 3.1–3.11 done except 3.12–3.13.

## The measurement that looked like a reversal

ADR-0017 swept a similarity floor and refused it: the answerable and unanswerable score
bands overlapped. Re-measuring on today's corpus, they *separate* — top-1 similarity
0.641–0.836 against 0.540–0.588, a clean gap. A floor at 0.60 passes gate G4 today.

The trap is in where the judged unanswerables come from: 3.7 redrew them to be alien to the
corpus (bread baking, birds of prey, music theory, coastal geology) after the originals were
contaminated.
Alien queries are easy. So before believing the separation, I measured two things the
judged set cannot show:

**The background.** Cosine similarity of 300 *unrelated* chunk pairs from this corpus: p50
0.624, p95 0.715, max 0.780. Unrelated text scores higher than some relevant answers
(0.641). In the band where a floor would have to operate, absolute similarity carries no
relevance meaning — that is anisotropy, stated with our own numbers.

**The counterfactual.** Eight questions this corpus genuinely cannot answer, phrased in its
own vocabulary — payment gateways, Kubernetes, SSO, a web dashboard, analytics retention,
sharding, GPU support, a newsletter. Top-1: 0.671–0.741, all *inside* the answerable band.
Every floor that passes the judged set answers all eight. The score-gap signals straddle
the same boundary. The separation the judged set shows is a property of the set, not of
the signal.

That is the finding I care about keeping: **a gate can be passed by an artifact of its own
test data.** The floor would have shipped green and rotted silently, per corpus, per model,
with no judged unanswerable set at any deployment to catch it.

## What ships instead, and what it honestly claims

Lexical evidence as the vector leg's precondition: lexical empty → vector withheld → hybrid
abstains, with a note naming ADR-0025 and no embedding latency paid. G4 for hybrid goes
100 % → 0 % with every answerable metric byte-identical — on our 16 answerable cases the
precondition fired exactly never, so its cost here is exactly nothing.

The claim is deliberately narrow: **abstention parity with the gated baseline, by
construction.** Not unanswerability detection — the eight probes defeat the precondition
too (they all have lexical hits, all ten of ten). No measured signal detects near-domain
unanswerability; the difference is that the precondition guarantees something without a
constant, and a floor guarantees nothing while carrying one.

The forgone class is stated rather than hidden: an answerable query sharing not one surface
form with its answer (unicode61 does not stem — "fails" does not match "failed") now
abstains under hybrid. On this corpus the class is empty. Where it is not, G2's protected
slices are the net.

G2 itself is unchanged and hybrid stays opt-in: +5.8 % nDCG overall, but conceptual −5.7 %
and injection −22.6 %. This item removed one of hybrid's two disqualifiers. The other is
3.12/3.13 work.

## Process notes

- **G4 caught me in 3.7's own trap, live.** The first draft of this ADR and journal *named*
  the unanswerable queries' words while describing them, which put those words into the
  corpus, and the re-blessed gate run reported lexical false answers at 75 %. The documents
  now describe the queries' domains without their vocabulary. Writing about an unanswerable
  case is itself a corpus edit — second time this project has had to learn it, first time
  the gate did the catching instead of a human.

- The before/after evals ran against a staged copy with the real model, and the "before"
  numbers were taken **before** patching `src/` — `uv run` spawns a fresh interpreter per
  eval, so editing source mid-measurement would silently turn "before" into "after".
- The long-ADR heredoc died again ("unexpected EOF"); writing the file in three appends is
  now the default, not the fallback.
