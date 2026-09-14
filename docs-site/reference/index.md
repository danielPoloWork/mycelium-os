# Reference

Generated from the source's own docstrings, so it cannot drift from the code it
describes. It covers `mycelium.sdk` — the public, contributor-facing contract surface
(three of the five stable contracts: identity rules, the record schemas, the plugin
protocols) — not the whole package.

- [SDK](sdk.md) — record contracts, identity library, plugin protocols.

For the CLI's commands and flags, run `mycelium <command> --help`, or read
[`src/mycelium/cli/app.py`](https://github.com/danielPoloWork/mycelium-os/blob/main/src/mycelium/cli/app.py)
directly — the CLI is public surface under SemVer, but it is not one of the five
contracts this site generates a page for. For the JSON Schema of every record and the
compatibility goldens that pin these shapes, see
[Project](../project.md).
