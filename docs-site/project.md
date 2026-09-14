# Project

This site is new documentation — a tutorial, task-oriented how-tos, and the
plugin-author guide (roadmap 6.2). The canonical record of *why* Mycelium OS is built
the way it is stays in the repository itself, as reviewed, versioned files rather than
a second copy this site would have to keep in sync:

- **[README](https://github.com/danielPoloWork/mycelium-os#readme)** — the project's
  front door: what it does, what makes it different, and the measurements behind each
  claim.
- **[Specification](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/specs/01_spec_mycelium.md)**
  — the frozen functional and technical contract.
- **[RFC-0001](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/rfc/0001-mycelium-os-v1.md)**
  — the design of record for the whole v1 system.
- **[Architecture Decision Records](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/adr/README.md)**
  — one numbered file per non-trivial decision, including every retrieval leg's
  measurement and every plugin-surface call this guide summarizes.
- **[Design patterns catalogue](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/patterns/README.md)**
  — which classical patterns are exercised, where, and why; and which were considered
  and rejected.
- **[Compatibility promise](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/compatibility.md)**
  — what stays stable, from which version, and how a change to it is made. This is the
  page a plugin author should read before depending on anything in this site's
  [reference](reference/index.md).
- **[Threat model](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/security/threat-model.md)**
  — the STRIDE pass per trust boundary, beside the root
  [`SECURITY.md`](https://github.com/danielPoloWork/mycelium-os/blob/main/SECURITY.md)
  policy.
- **[Roadmap](https://github.com/danielPoloWork/mycelium-os/blob/main/ROADMAP.md)** —
  the numbered, checkbox-driven plan, and what shipped in which pull request.
- **[Session journal](https://github.com/danielPoloWork/mycelium-os/tree/main/docs/journal)**
  — dated checkpoints of how the work actually went.
- **[Contributing](https://github.com/danielPoloWork/mycelium-os/blob/main/CONTRIBUTING.md)**
  and **[`AGENTS.md`](https://github.com/danielPoloWork/mycelium-os/blob/main/AGENTS.md)**
  — the contract every human and AI contributor works under.

These links point at `main`; a document under active development. Pin a commit or tag
in the URL when you need the state a specific release described.
