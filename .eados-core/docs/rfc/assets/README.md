# RFC diagrams — source of truth

These `.mmd` files are the **diagrams as code** for [RFC-0001](../0001-eados-delivery-os.md):

| File | Diagram |
|------|---------|
| [`eados-flow.mmd`](eados-flow.mmd) | The phase state machine ("how it works"). |
| [`eados-end-to-end.mmd`](eados-end-to-end.mmd) | The end-to-end traceability / audit graph (intent → release → audit). |

## Rendering

The RFC embeds the same Mermaid in fenced ```mermaid blocks, which **GitHub renders inline** —
no build step is needed to read them in the PR or on GitHub.

To produce a standalone **SVG** (the generated artifact), run Mermaid CLI — it needs Node, which
this otherwise Python-only repo does not require, so the SVG is *generated on demand*, not
committed as a hand-maintained file (a hand-drawn SVG would rot at the first flow change):

```bash
npx -y @mermaid-js/mermaid-cli -i eados-flow.mmd        -o eados-flow.svg
npx -y @mermaid-js/mermaid-cli -i eados-end-to-end.mmd  -o eados-end-to-end.svg
```

> **Why not commit the SVG?** The decision in RFC §9 (determinism) and the owner's choice
> ("mermaid/d2 + generated SVG") is that the Mermaid source is authoritative and the SVG is a
> derived artifact. If a CI-generated, committed SVG is wanted later, a Mermaid render step can
> be added to the workflow (it introduces a Node toolchain — a deliberate, separate decision).
