"""A Parser plugin: adapts one engine's bytes into KIR (spec 05 §4.1).

Mycelium OS owns the representation (KIR) and its guarantees; a parser owns the
parsing library and the whole job of losing nothing silently (D-007). It is
resolved through the `mycelium.plugins` entry-point group and pinned by name in
`[ingest] parsers` — never "best available" (spec 05 §4.2).
"""

from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, Ulid


class Plugin:
    """Reads {{ cookiecutter.description }}."""

    meta = PluginMeta(
        id="{{ cookiecutter.plugin_id }}",
        # The *engine's* version this adapts (pandoc 3.10, docling 2.124, ...),
        # not this package's own — replace once there is a real engine behind it.
        version="{{ cookiecutter.version }}",
        description="{{ cookiecutter.description }}",
        api_min=int("{{ cookiecutter.mycelium_api_min }}"),
        api_max=int("{{ cookiecutter.mycelium_api_max }}"),
    )

    media_types = ("text/plain",)
    """Every media type this parser declares it can read (spec 05 §4.1). The
    registry tries pinned parsers in the order `[ingest] parsers` names them and
    picks the first one whose `media_types` includes the source's — so this
    tuple is what makes this plugin reachable at all."""

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        """Compile `blob`'s bytes into a KIR document (spec 03 §4).

        `doc_id` is supplied, never minted here: identity belongs to the build
        that calls this, and a parser that minted its own would break
        incremental rebuilds by handing back a different id every run.

        Replace this body with real structure — headings, paragraphs, tables —
        instead of one node holding the whole file. Never lose an element
        silently: something this format has that KIR cannot represent becomes an
        `opaque` node with a `variant` of `"degraded"` (structure lost, content
        kept) or `"lost"` (content did not survive) — see spec 03 §4 and
        `mycelium.sdk.types.OpaqueDisposition`. Raise
        `mycelium.ingest.errors.ParseError` for bytes this parser cannot
        represent at all; ingestion quarantines that document rather than
        failing the whole build.
        """
        text = blob.data.decode("utf-8", errors="replace")
        return KirDocument(
            doc_id=doc_id,
            source_digest=blob.digest,
            nodes=(KirNode(id="n1", kind=NodeKind.PARAGRAPH, ord=0, text=text),),
        )
