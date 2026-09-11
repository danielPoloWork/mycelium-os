# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Module discovery, activation, and what an active module may contribute (D-023/D-025).

D-027 fixes a two-level extension taxonomy and this module owns the second
level. A **plugin** is an engine extension — a typed Protocol satisfied by a
class, resolved by `[ingest] parsers` through the ``mycelium.plugins``
entry-point group (:mod:`mycelium.ingest.registry`). A **module** is a *packaged
activatable capability*: a distribution of its own that adds a whole feature,
switched on by name in ``[modules] enabled``. Two levels, two entry-point
groups, and the difference is worth the second group: a parser is asked *can you
read this media type*, and a module is asked nothing at all until an operator
names it.

**Resolution is pinned, exactly as it is for plugins (spec 05 §4.2).** A name in
``[modules] enabled`` that no installed distribution provides is a
:class:`~mycelium.config.ConfigError` that says what to install — never a
silent skip. The alternative is a `mycelium.toml` that means different things on
two machines, which is the ambiguity the whole resolution design exists to
remove.

**What "inactive = zero runtime footprint" means, precisely** (spec doc 08 §2).
An inactive module contributes nothing to a build, a query, or a published
snapshot: nothing here is consulted by the compiler or the retriever, and a
module cannot register a stage or a hook because those mechanisms do not exist
yet (see below). What an *installed* module does cost is the CLI's own startup,
because a command tree has to be built before argv is parsed — so
:func:`mount` imports every installed module, enabled or not, and every command
it mounts checks enablement against the repository it was pointed at. The
alternative — a lazily-loaded Click group — would hide a module's subcommands
from ``--help``, which is worse than a cost that does not register.

**Mounting happens in ``main()``, and the reason is a cycle it caused when it
did not.** A module's CLI reuses the core's output conventions
(:mod:`mycelium.cli.output`, ADR-0010), so importing the module imports
``mycelium.cli`` — and if ``mycelium.cli.app`` mounted modules *at import*, that
import re-entered a module which was still half-initialised, the entry point
raised an :class:`AttributeError`, and the command vanished. A test caught it
(roadmap 5.5); nothing else would have, because the failure was swallowed. Both
halves are fixed here: :func:`mount` is called explicitly once the command tree
exists, and it **returns its failures** instead of hiding them.

**One of D-023's four mechanisms is implemented here, and that is a finding
rather than an omission** (ADR-0077). Spec 05 §4.1.1 lists four: pipeline
stages, lifecycle hooks, CLI subcommands, and MCP tools. The first real module
needs exactly one of them — a CLI subcommand — declares no MCP tools by design
(spec doc 08 §2: transcripts are indexed like any document, so
``mycelium_search`` already serves them), and does its writing at authoring time
rather than inside a build, so it has nothing for a stage or a hook to do.
Building the other three now would freeze three contracts against no consumer,
which is what the 1.0 freeze must not do; :class:`Module` is shaped so each
arrives additively, as an optional method a later reader checks for.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING, Final

from mycelium.sdk.protocols import MYCELIUM_API_VERSION, Module

if TYPE_CHECKING:
    import typer

__all__ = [
    "MODULE_ENTRY_POINT_GROUP",
    "ModuleError",
    "ModuleStatus",
    "activated",
    "installed_ids",
    "load_module",
    "mount",
    "require_enabled",
    "statuses",
]

MODULE_ENTRY_POINT_GROUP: Final = "mycelium.modules"
"""Where a distribution registers itself as an activatable module (D-025).

Deliberately *not* ``mycelium.plugins``: that group answers "which parser reads
this media type", and a name in it is resolved by `[ingest] parsers`. Sharing one
group would make `[modules] enabled = ["docling"]` a sentence the loader had to
refuse at a level below the one that could explain it.
"""


class ModuleError(RuntimeError):
    """An installed module cannot be loaded, or does not satisfy the contract."""


@dataclass(frozen=True, slots=True)
class ModuleStatus:
    """One module's id, availability and one operator-facing line.

    The same shape :class:`~mycelium.ingest.registry.PluginStatus` has, for the
    same reason: `mycelium doctor` reports rather than raises, so it needs a
    record that can carry a failure without being one.
    """

    id: str
    available: bool
    enabled: bool
    detail: str

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "id": self.id,
            "available": self.available,
            "enabled": self.enabled,
            "detail": self.detail,
        }


def _points() -> Mapping[str, EntryPoint]:
    """Installed module entry points by id, ignoring nothing and loading nothing.

    Reading the metadata without importing is what lets configuration *validate*
    a module name — refusing one nothing provides, with a remedy — while leaving
    the cost of importing it to whoever actually uses it.
    """
    found: dict[str, EntryPoint] = {}
    for point in entry_points(group=MODULE_ENTRY_POINT_GROUP):
        found.setdefault(point.name, point)
    return found


def installed_ids() -> tuple[str, ...]:
    """Every installed module id, sorted. Imports nothing."""
    return tuple(sorted(_points()))


def load_module(name: str) -> Module:
    """Import and validate the module registered as `name`.

    Raises :class:`ModuleError` when nothing registers the id, when the import
    fails, when the object does not satisfy :class:`Module`, or when it declares
    a plugin API generation this build does not speak — the same four refusals
    :func:`mycelium.ingest.registry._load_parser` makes, because a module is
    installed code held to the same contract discipline (D-012).
    """
    point = _points().get(name)
    if point is None:
        known = ", ".join(installed_ids()) or "(none installed)"
        msg = (
            f"unknown module {name!r}; installed modules are: {known}. A module registers "
            f"itself in the {MODULE_ENTRY_POINT_GROUP!r} entry-point group."
        )
        raise ModuleError(msg)
    try:
        loaded = point.load()
    except Exception as error:  # noqa: BLE001 - third-party import, reported not propagated
        msg = f"module {name!r} could not be loaded from {point.value} - {error}"
        raise ModuleError(msg) from error
    module = loaded() if callable(loaded) else loaded
    if not isinstance(module, Module):
        msg = (
            f"the distribution registered as {name!r} does not satisfy the Module protocol "
            "(it needs a `meta` and a `commands()`)"
        )
        raise ModuleError(msg)
    if module.meta.id != name:
        # The one identifier rule (D-026): a module's entry-point name and its
        # own declared id must agree, or config, manifests and logs disagree.
        msg = f"module {name!r} declares the id {module.meta.id!r}; a module has exactly one id"
        raise ModuleError(msg)
    if not module.meta.supports(MYCELIUM_API_VERSION):
        msg = (
            f"module {name!r} declares Mycelium plugin API "
            f"[{module.meta.api_min}, {module.meta.api_max}) and this build speaks "
            f"{MYCELIUM_API_VERSION}"
        )
        raise ModuleError(msg)
    return module


def activated(enabled: Sequence[str]) -> tuple[Module, ...]:
    """The modules `enabled` names, loaded in the order it names them.

    Order is preserved rather than sorted because it is the operator's, and a
    module may one day contribute something order-sensitive; nothing today is.
    """
    return tuple(load_module(name) for name in enabled)


def statuses(enabled: Sequence[str] = ()) -> tuple[ModuleStatus, ...]:
    """Every installed module, whether it loads, and whether `enabled` names it."""
    reported: list[ModuleStatus] = []
    for name in installed_ids():
        try:
            module = load_module(name)
        except ModuleError as error:
            reported.append(
                ModuleStatus(id=name, available=False, enabled=name in enabled, detail=str(error))
            )
            continue
        reported.append(
            ModuleStatus(
                id=name,
                available=True,
                enabled=name in enabled,
                detail=f"{module.meta.description} (version {module.meta.version})",
            )
        )
    return tuple(reported)


def mount(app: "typer.Typer") -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Mount every installed module's sub-app on `app`. Returns ``(mounted, problems)``.

    Installed rather than enabled, because a command tree is built before argv
    is parsed and therefore before any repository root is known. Enablement is
    checked by the commands themselves, where the root is an argument — see
    :func:`require_enabled`.

    **Called from ``main()``, never at import.** Mounting while
    ``mycelium.cli.app`` was still being imported re-entered a module that was
    itself half-imported, because a module's CLI imports the core's output
    helpers; the entry point then raised and the command silently disappeared
    (roadmap 5.5).

    **A module that fails to load is reported, not hidden.** A broken
    third-party wheel must not make `mycelium build` unusable — so it does not
    raise — but the caller is handed the message to print, and `mycelium doctor`
    reports it as a failing check. Swallowing it is what turned a cycle into a
    mystery.

    Idempotent: mounting twice adds nothing, so a caller that is unsure may call
    it again.
    """
    mounted: list[str] = []
    problems: list[str] = []
    already = {group.name for group in app.registered_groups if group.name}
    for name in installed_ids():
        if name in already:
            continue
        try:
            module = load_module(name)
            app.add_typer(module.commands(), name=name)
        except Exception as error:  # noqa: BLE001 - a broken module is reported, never fatal
            problems.append(f"module {name!r} is installed but unusable: {error}")
            continue
        mounted.append(name)
    return tuple(mounted), tuple(problems)


def require_enabled(module_id: str, enabled: Sequence[str]) -> None:
    """Refuse to run a module's command where the repository has not enabled it.

    The counterpart of mounting by installation: the command exists because the
    distribution is installed, and it acts only where an operator wrote the id
    into `[modules] enabled`. Installing something must not change what a
    repository compiles or contains until its configuration says so (D-025).
    """
    if module_id in enabled:
        return
    msg = (
        f"module {module_id!r} is installed but not enabled here; add it to [modules] "
        f'enabled in mycelium.toml:\n\n[modules]\nenabled = ["{module_id}"]'
    )
    raise ModuleError(msg)
