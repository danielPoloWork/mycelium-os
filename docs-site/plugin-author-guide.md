# Plugin author guide

Mycelium OS is open to extension through in-process Python entry points, resolved by
explicit configuration and never by "best available" (spec 05 §4.2). This guide covers
the three contracts you can build against **today** and points at what
[`docs/compatibility.md`](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/compatibility.md)
promises will not move under you while you do.

The fastest start is the plugin cookiecutter (below); this page is what it generates,
and why.

## The three contracts, and the one that is not open yet

| Contract | What it does | Registered through | Pinned in |
|---|---|---|---|
| `Connector` | Acquires a source's bytes under custody | `mycelium.plugins` entry-point group | `[ingest] connectors` |
| `Parser` | Turns acquired bytes into KIR | `mycelium.plugins` entry-point group | `[ingest] parsers` |
| `Module` | A packaged, activatable capability — the fourth is a *set* of extension points, not one operation | `mycelium.modules` entry-point group | `[modules] enabled` |

**`Synthesizer` is a real, frozen Protocol in `mycelium.sdk.protocols`, and there is no
registry path to it yet.** Spec 05 §4.1 lists it among the plugin Protocols the SDK
exports, but `mycelium.synthesis.build_synthesizer` resolves exactly one built-in
(`wiki`) and `[synthesis] plugin` refuses any other name outright — there is no
`mycelium.plugins` (or other) entry-point lookup for it. Writing a class that satisfies
`Synthesizer` today gets you a class nothing in the product will load. This is stated
here rather than left for you to discover: build against the three contracts above, and
watch the roadmap for when a second synthesizer plugin has a way in.

`Chunker`, `Extractor` and `Reranker` are named in spec 05 §4.1's sketch and exist in no
code and no registry at all — the same situation, one step earlier.

## Naming your plugin (spec 05 §4.4)

One identifier, used everywhere — the entry point, the config value, the manifest, the
CLI mount if it is a module:

1. **Lowercase kebab-case, one or two words**, and a **capability noun**: `pdf`,
   `wiki`, `chats` — what it does, not how.
2. **No technology suffix** (`-llm`, `-ai`, `-gpt`). The implementation behind a stable
   name is expected to change; put the technology in `PluginMeta.description` instead.
3. **Reserved words are off limits**: `search`, `index`, `graph`, `build`, `snapshot`,
   `evidence`, `verify` are core concepts a plugin cannot claim.
4. The distribution name, display name and CLI mount are **mechanical** from the id:
   `mycelium-<id>`, "Mycelium \<Id\>", `mycelium <id> …`. One id, zero synonyms.

The cookiecutter's `pre_gen_project` hook checks all three rules and refuses to
generate a plugin whose id fails them, with the reason.

## `PluginMeta`: what every plugin declares

```python
from mycelium.sdk.protocols import PluginMeta

meta = PluginMeta(
    id="my-plugin",
    version="3.2.0",       # the ENGINE's version this adapts, not your package's own
    description="One operator-facing line — the technology goes here, never in the id",
    deterministic=True,    # False only if identical input can produce different output
    api_min=0,
    api_max=1,             # the range of MYCELIUM_API_VERSION this plugin speaks
)
```

Every field here is recorded in the snapshot manifest and in the build key of the stage
that used it — a build must be explainable from its manifest alone, so the manifest
names the exact implementation and version that produced each artifact. `version` is
the number that explains the *output*: a parser is an adapter, so it is pandoc's
version, or docling's, never this plugin's own release number.

`deterministic` matters beyond documentation: gate G6 (byte-identical rebuild) excludes
a stage that declares `False` from its comparison, the same way the local embedder
does. Declare it honestly — a stage that claims determinism it cannot deliver corrupts
the guarantee rather than one document.

## Writing a `Parser`

```python
from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, Ulid

class MyParser:
    meta = PluginMeta(id="my-format", version="1.0", description="Reads .myfmt files")
    media_types = ("application/x-myfmt",)

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        ...
        return KirDocument(doc_id=doc_id, source_digest=blob.digest, nodes=(...))
```

`doc_id` is **supplied**, never minted here — identity belongs to the build that calls
you, and a parser that minted its own would hand back a different id on every run and
quietly break incremental rebuilds. Raise
`mycelium.ingest.errors.ParseError` for bytes you cannot represent at all; ingestion
quarantines that one document rather than failing the whole build.

**Never lose an element silently.** Something your format has that KIR's closed node
vocabulary cannot model becomes an `opaque` node — `variant="degraded"` if structure
was simplified but content survived, `variant="lost"` if it did not. `opaque` is KIR's
lawful escape hatch (spec 03 §4), and the fidelity report `mycelium ingest` prints is
computed from exactly this bookkeeping.

Register it:

```toml
[project.entry-points."mycelium.plugins"]
my-format = "my_package:MyParser"
```

```toml
# a repository's mycelium.toml
[ingest]
parsers = ["my-format", "docling"]
```

The **order is the policy**: the first pinned parser whose `media_types` matches wins,
and which one ran is recorded per document. A plugin may not take a built-in id
(`markdown`, `docling`, `pandoc`, `pdf`) — the registry refuses that outright, because
two installations of the same `mycelium.toml` must mean the same thing regardless of
what else happens to be installed.

## Writing a `Connector`

Acquisition is where untrusted input enters the system (D-017): a connector's whole job
is custody, never parsing.

```python
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob, PluginMeta

class MyConnector:
    meta = PluginMeta(id="s3", version="1.0", description="Fetches from S3")
    schemes = ("s3",)

    def acquire(self, source: str) -> Blob:
        data = ...  # fetch the bytes for `source`
        return Blob.of(data, media_type="application/pdf", source_uri=source)
```

`Blob.of` digests the bytes verbatim — never normalize what a citation must later quote
exactly (spec 03 §1, the CAS rule). Raise
`mycelium.ingest.errors.ConnectorError` when the source cannot be taken into custody at
all: outside declared roots, absent, oversized, unreadable. That is a harder failure
than a parse error and is never quarantined, because there are no bytes to keep and
look at afterwards.

## Writing a `Module`

A module is not an engine extension — it is a *packaged activatable capability*
(D-025), the only one of the four typed contracts the core never calls inside a
pipeline. It contributes surfaces; the core discovers it, refuses it clearly when a
name resolves to nothing, and mounts what it offers.

```python
import typer
from mycelium.sdk.protocols import PluginMeta

app = typer.Typer(help="What this module does")

@app.command()
def status() -> None:
    typer.echo("installed")

class MyModule:
    meta = PluginMeta(id="my-module", version="0.1.0", description="...")

    def commands(self) -> typer.Typer:
        return app
```

**One contribution is required — a CLI sub-app** — because a module built on no
consumer's needs is a guess, the same refusal every unbuilt extension mechanism gets
until something needs it. Three more are optional and arrive additively as your module
grows: `stages()`, `hooks()`, `tools()`, checked with `hasattr` by whoever eventually
reads them.

```toml
[project.entry-points."mycelium.modules"]
my-module = "my_package:MyModule"
```

A module does nothing in a repository — not even show up in `mycelium doctor` as more
than "installed" — until an operator writes it into `[modules] enabled`. Installing a
module changing what a repository compiles without that line would be exactly the
ambiguity resolution exists to remove.

**A module needs more than the plugin API.** Beyond `mycelium.sdk`, six components are
declared module-facing and importable: `mycelium.config`, `mycelium.modules`,
`mycelium.ingest`, `mycelium.chunking`, `mycelium.cli.output`, `mycelium.synthesis` —
each because a second implementation of it would make the *product* inconsistent, not
merely your module. See `mycelium.modules.MODULE_SURFACE` for the current list and the
reason beside each entry, and never import anything else from the core: a name a
declared component does not export in its own `__all__` is private whatever its
spelling, and the in-repo `chats` module's acceptance test enforces exactly that
allowlist.

## The naming and compatibility discipline this all rests on

- **Resolution is pinned, never "best available."** Every id above must be named in
  the repository's own configuration to run at all; nothing is chosen because it is
  merely installed.
- **A build must be explainable from its manifest alone** — which is why `PluginMeta`
  exists and why a build key folds every plugin's id, version, and configuration
  digest into itself.
- **What may not change under you** is `docs/compatibility.md`: the plugin protocols
  are one of the five stable contracts, pinned to a golden of their shape and checked
  on every change to the core. `MYCELIUM_API_VERSION` is the number that tells you
  whether a Protocol you satisfy today still describes what a build expects — declare
  the range your plugin supports (`api_min`/`api_max`) and the registry will refuse an
  incompatible build with a precise error rather than a confusing crash.

## Generate one: the plugin cookiecutter

```bash
pip install cookiecutter
cookiecutter https://github.com/danielPoloWork/mycelium-os \
  --directory tools/cookiecutter-mycelium-plugin
```

(or, from a checkout: `cookiecutter tools/cookiecutter-mycelium-plugin`.) It asks for
your plugin's id, kind (`parser`, `connector`, or `module` — `synthesizer` is
deliberately not offered, for the reason above), description, and the API generation
range, validates the id against spec 05 §4.4 before writing anything, and produces a
complete, installable package: a `pyproject.toml` with the entry point already wired to
the kind you chose, a minimal-but-correct implementation satisfying the right Protocol,
a test that checks that Protocol conformance and `PluginMeta`, and an Apache-2.0
`LICENSE`. Every kind it can generate is tested the same way this repository tests its
own code: rendered, then linted and type-checked with `ruff` and `mypy --strict`.
