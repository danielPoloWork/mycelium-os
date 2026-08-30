# Brand assets

The Mycelium OS wordmark and hexagonal node-lattice icon, vendored from the archived
legacy repository (`.mycelium-os-legacy/.bootstrap-os/.assets/`) at roadmap item 2.12.
They are the one part of the legacy project carried forward unchanged: the design work is
sound and the name is decided (D-024).

| File | Use |
|---|---|
| [`mycelium-os-banner.png`](mycelium-os-banner.png) | Wordmark + icon, landscape. The root `README.md` header. |
| [`mycelium-os-icon.png`](mycelium-os-icon.png) | Icon alone. Avatars, favicons, docs-site logo. |
| [`mycelium-os-logo.png`](mycelium-os-logo.png) | Portrait lockup with a tagline. **See the caveat below.** |

## Caveat: the logo carries a superseded tagline

`mycelium-os-logo.png` renders the strapline *"Semantic Cognitive Knowledge Filesystem
Operating System"* — the legacy positioning, which RFC-0001 supersedes. Mycelium OS is a
**knowledge compiler and serving layer for AI agents**: not an agent runtime, not a
cognitive OS (D-001). The file is kept because it is the only portrait lockup that exists,
but it must not be used anywhere the tagline is legible until it is re-rendered without it.
The banner and the icon carry no strapline and are safe everywhere.

## Not salvaged

The legacy `architecture.svg` and `architecture-mycelium.svg` diagrams are **deliberately
not vendored** (roadmap 2.12). They depict the superseded dual-layer design — a human wiki
layer beside a machine reasoning layer — which is not this project's architecture. Diagrams
for the v1 design belong to the docs site (roadmap 6.2), drawn from
[`.draft-specs/02-architecture.md`](../../../.draft-specs/02-architecture.md).

## Trademark

No trademark search has been run and no mark is claimed. That is roadmap item 6.5, gating
the public branding push.

## License

Apache-2.0, © 2026 Daniel Polo — the repository's license covers these files.
