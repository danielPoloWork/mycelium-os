"""A Connector plugin: acquires a source's bytes under custody (spec 05 §4.1).

Acquisition is where untrusted input enters the system (D-017, spec 02 §5): a
connector's job is custody — a digest, a media type, and the URI the bytes came
from — never parsing. It is resolved through the `mycelium.plugins` entry-point
group and pinned by name in `[ingest] connectors`.
"""

from mycelium.sdk.protocols import Blob, PluginMeta


class Plugin:
    """Acquires {{ cookiecutter.description }}."""

    meta = PluginMeta(
        id="{{ cookiecutter.plugin_id }}",
        version="{{ cookiecutter.version }}",
        description="{{ cookiecutter.description }}",
        api_min=int("{{ cookiecutter.mycelium_api_min }}"),
        api_max=int("{{ cookiecutter.mycelium_api_max }}"),
    )

    schemes = ("{{ cookiecutter.plugin_id }}",)
    """URI schemes this connector answers for — `("file",)` for the local tree.
    Resolution tries pinned connectors in order and picks the first whose
    `schemes` contains the source URI's scheme."""

    def acquire(self, source: str) -> Blob:
        """Fetch `source` and return its bytes, digest and detected media type.

        Build the result with `Blob.of(data, media_type=..., source_uri=source)`
        — it computes the digest for you, over the bytes verbatim, which is the
        CAS rule for acquired originals (spec 03 §1): never normalize what a
        citation must later quote exactly.

        Raise `mycelium.ingest.errors.ConnectorError` when the source cannot be
        taken into custody at all — outside declared roots, absent, oversized,
        unreadable. That is a harder failure than a parse error: acquisition
        refuses outright rather than quarantining, because there are no bytes to
        keep and look at afterwards (spec 02 §5).
        """
        raise NotImplementedError("replace with a real fetch for this scheme")
