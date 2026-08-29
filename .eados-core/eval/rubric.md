# Self-Evaluation Rubric

The architect scores a generation run against this rubric **before** drafting the bootstrap PR.
It is the qualitative half of the quality bar; the mechanical halves are
[`tools/consistency_lint.py`](../templates/tools/consistency_lint.py) (congruence, shipped into
the repo) and [`tools/self_review.py`](../tools/self_review.py) (structural completeness). A low
score on any dimension is a finding to fix or to record as a `ROADMAP.md` item — not a thing to
hand-wave past.

Score each dimension 0–2 (0 absent · 1 partial · 2 solid) and note the evidence.

| # | Dimension | What "solid" (2) looks like |
|---|-----------|------------------------------|
| 1 | **Spec measurability** | Every functional/non-functional requirement is phrased so CI can prove a violation (numbers, not adjectives). |
| 2 | **Spec → CI traceability** | Each spec section maps to a roadmap item and a concrete check; manual gates are flagged explicitly. |
| 3 | **Architecture rationale** | The logical architecture is captured as prose + diagram and the load-bearing choices are (or will be) ADRs. |
| 4 | **Profile fidelity** | The toolchain commands actually run on the skeleton; sanitizers map to the language's real equivalents. |
| 5 | **Pattern fit** | Any adopted pattern is justified (ADR) and matches the canonical taxonomy; nothing force-fit. |
| 6 | **Test strategy** | The verification plan covers correctness *and* the non-functional envelope (perf/memory/security as applicable). |
| 7 | **Docs coherence** | README/ROADMAP/spec/ADR index/changelog agree with each other and with the manifest. |
| 8 | **Governance fit** | Scopes, milestone, labels, branch protection, and (if set) house rules match the project's reality. |
| 9 | **Capability hygiene** | Only the capabilities the project needs are on; each enabled flag ships its artifacts (i18n/announce/bench). |
| 10 | **Security posture** | SECURITY policy present and accurate; deps locked; no secrets committed; advisory channel correct. |

## Using it

1. Score all ten; total out of 20.
2. **Any 0 is a blocker** — fix before the PR. A **1** is a finding: fix it or file a roadmap
   item in the same PR.
3. Put the score table in the hand-off report so the maintainer sees where the design is thin.
4. Turn a recurring low score into a durable [lesson](../learning/README.md) so the next run
   starts higher.
