# `rfc.yaml` — schema

The **RFC review protocol** as data: which sections an RFC must carry, who may author it, who
reviews, who approves, and how the **`rfc-approved`** gate recognizes an approval. The `design`
phase produces RFCs under this protocol; the gate is mechanical (it verifies an approval *record*,
which encodes a human decision — `AGENTS.md` §6). Human-readable protocol:
[`review-protocol.md`](review-protocol.md); the RFC skeleton: [`template.md`](template.md). The
checker is [`../../../tools/rfc_check.py`](../../../tools/rfc_check.py).

`eados_lint` (`os-spec-completeness`) requires the instance to define every top-level key below.

## Required structure

```yaml
version:            # integer schema version
required_sections:  # section names every RFC must contain (matched as a heading)
author_roles:       # roles allowed to author an RFC (authority.yaml role ids)
reviewer_roles:     # roles that review (structured findings; no final authority)
approver_role:      # the single role whose approval the rfc-approved gate requires
approval:           # how an approval is recorded — { heading, marker }
gate:               # the workflow.yaml gate id this protocol satisfies
```

## Item shapes

- **`required_sections`** — a list of names; each must appear as a markdown heading in the RFC
  (e.g. `Context`, `Decision`, `Alternatives`, `Consequences`, `Approval`). Matched loosely so a
  numbered heading (`## 3. Decision`) still counts.
- **`approval`** — `{ heading, marker }`. The RFC carries the `heading` section with a line
  `<marker> <approver_role> (<date>)` — e.g. `approved-by: tech-lead (2026-06-21)`.
- **`author_roles` / `reviewer_roles` / `approver_role`** — role ids declared in
  [`../authority/authority.yaml`](../authority/authority.yaml).

## Invariants

- `approver_role`, every `author_roles[]`, and every `reviewer_roles[]` is a declared authority role.
- `gate` is a gate id present in [`../workflow/workflow.yaml`](../workflow/workflow.yaml).
- The approver acts *after* review; an RFC without a valid approval record fails `rfc-approved`.
