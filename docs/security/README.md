# Security docs — mycelium-os

The **analysis** side of the project's security story, owned by the **security-auditor** role.
Three artifacts, three jobs — keep them distinct:

| Artifact | Job | Lives |
|---|---|---|
| `SECURITY.md` (repo root) | the **policy** — supported versions, private reporting channel | root |
| [`threat-model.md`](threat-model.md) | the **analysis** — trust boundaries + the STRIDE pass | here |
| the audit **risk register** | the **outcome** — scored findings of a concrete audit run | audit records |

The threat model is scaffolded empty and **filled by the audit phase's threat-modeling sub-mode**
(`/eados security`, an alias into `/eados audit` — ADR-0019 §2: a sub-mode adds no new phase or
state). Update it when a trust boundary changes — a new untrusted input, a new dependency on an
external service, a privilege change — in the same PR as the change, exactly like the spec.

A confirmed, reproducible defect found here becomes a [bug-ledger](../bugs/README.md) record; a
vulnerability that warrants coordinated disclosure becomes a **draft** advisory (a human
publishes — never the agent).

Two registers exist: the [bootstrap audit](audit-2026-08-29-bootstrap.md) (2026-08-29, F1–F5)
and the [6.3 security review pass](audit-2026-09-17-review-pass.md) (2026-09-17, F6–F14).
Since 6.3 the model's §4 names the tests that hold each boundary, mechanically: a test file
that holds a boundary carries `pytest.mark.boundary("Bn")`, `uv run pytest -m boundary` runs the
threat-model-derived suite, and `tests/test_threat_model.py` fails when a declared boundary has
no test behind it (ADR-0119).
