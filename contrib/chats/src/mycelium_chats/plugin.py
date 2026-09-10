# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What the core loads: this module's :class:`mycelium.sdk.protocols.Module`.

One object, registered in the ``mycelium.modules`` entry-point group, satisfying
one protocol. Everything else in this distribution hangs off the sub-app it
returns.

The declared plugin-API range is what makes a module *refusable* rather than
mysteriously broken: this build of the module speaks generation 0 and says so,
so a future core that has moved on refuses it by name instead of failing inside
a command (spec 05 §5).
"""

import typer

from mycelium.sdk.protocols import MYCELIUM_API_VERSION, PluginMeta
from mycelium_chats.cli import MODULE_ID, app

__all__ = ["ChatsModule", "plugin"]


class ChatsModule:
    """The `chats` module (D-025, spec doc 08)."""

    meta = PluginMeta(
        id=MODULE_ID,
        version="0.1.0",
        # ASCII on purpose: this string reaches consoles, and a non-ASCII
        # character in operator-facing text is how BUG-0009 corrupted an MCP
        # frame on a Windows code page.
        description="Mycelium Chats - local archive of chatbot conversations",
        # Not a stage, so determinism is not a claim this makes about a build.
        # The two things it *writes* are deterministic functions of their input
        # (a record of an import, a projection of a record) and doc 08 §10's
        # gate 2 is where that is enforced.
        deterministic=True,
        api_min=0,
        api_max=MYCELIUM_API_VERSION + 1,
    )

    def commands(self) -> typer.Typer:
        """The sub-app the core mounts at ``mycelium chats`` (D-023 mechanism 3)."""
        return app


def plugin() -> ChatsModule:
    """The entry point. A factory, so importing this module builds nothing."""
    return ChatsModule()
