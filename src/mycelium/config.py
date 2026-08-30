# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""`mycelium.toml` — the repository's configuration (spec 05 §2).

The file is read once per command, validated with precise errors, and digested into
the snapshot manifest so that a build is explainable from its manifest alone: the
config digest participates in build keys, and a config change invalidates exactly
the stages it affects (spec 05 §2, D-008).

Configuration is deliberately **partial** at this milestone. The spec's file has
sections for features that do not exist yet — ingestion connectors, synthesis,
verification thresholds, retrieval profiles. Those sections are *accepted and
digested* but not interpreted, and :func:`MyceliumConfig.unhonoured_sections` names
them so `mycelium doctor` can tell an operator that editing them changes nothing
today. Silently ignoring them would be worse: an operator would tune a knob and
believe it worked.

Everything else is strict. An unknown section, an unknown key inside an honoured
section, or a value that cannot be satisfied is an error naming the file, the key,
and what was expected — a typo in a config file must not degrade quietly into a
default (ADR-0014).
"""

import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from mycelium.chunking import ChunkingPolicy
from mycelium.sdk.identity import digest_json
from mycelium.sdk.types import Sha256Digest

__all__ = [
    "CONFIG_FILENAME",
    "ChunkingConfig",
    "ConfigError",
    "EmbeddingConfig",
    "ModulesConfig",
    "MyceliumConfig",
    "ProjectConfig",
    "UNHONOURED_SECTIONS",
    "load_config",
]

CONFIG_FILENAME: Final = "mycelium.toml"

UNHONOURED_SECTIONS: Final = frozenset(
    {"ingest", "synthesis", "verification", "sources", "retrieval", "eval"}
)
"""Sections spec 05 §2 documents whose features this milestone has not built.

They are accepted so a spec-valid file is not rejected, and digested so a build
remains reproducible from its config, but nothing reads their values yet:
`ingest` (roadmap 4.1), `synthesis` (4.4), `verification` (4.5), `sources` (4.1),
`retrieval` (3.3), `eval` (the harness takes its case set on the command line).
"""

_SUPPORTED_ATOMIC: Final = ("code", "table")


class ConfigError(ValueError):
    """`mycelium.toml` is unreadable, invalid, or asks for something unsupported."""


class _Section(BaseModel):
    """Base for honoured sections: frozen, and typos are errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ProjectConfig(_Section):
    """`[project]` — identity and the trees the compiler reads."""

    name: str = "mycelium"
    namespace: str = Field(
        default="default", description="Reserved for the team phase; one value in v1 (D-002)."
    )
    knowledge_dir: str = "knowledge"
    sources_dir: str = "sources"

    @model_validator(mode="after")
    def _directories_are_relative(self) -> Self:
        for field in ("knowledge_dir", "sources_dir"):
            value = getattr(self, field)
            if not value:
                msg = f"[project] {field} must not be empty"
                raise ValueError(msg)
            # Both flavours, deliberately: `Path("/etc").is_absolute()` is False on
            # Windows and True on Linux, so the native class alone would accept a
            # config on one platform and reject it on another.
            posix, windows = PurePosixPath(value), PureWindowsPath(value)
            if posix.is_absolute() or windows.is_absolute():
                # The compiler reads what the repository contains; a path that can
                # leave the repository is a supply-chain question, not a setting.
                msg = f"[project] {field} must be a relative path inside the repository"
                raise ValueError(msg)
            if ".." in posix.parts or ".." in windows.parts:
                msg = f"[project] {field} must be a relative path inside the repository"
                raise ValueError(msg)
        return self


class ChunkingConfig(_Section):
    """`[chunking]` — the knobs spec 03 §5 exposes."""

    target_tokens: int = Field(default=400, gt=0)
    max_tokens: int = Field(default=800, gt=0)
    atomic: tuple[str, ...] = ("table", "code")

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.target_tokens > self.max_tokens:
            msg = (
                f"[chunking] target_tokens ({self.target_tokens}) exceeds "
                f"max_tokens ({self.max_tokens})"
            )
            raise ValueError(msg)
        unsupported = sorted(set(self.atomic) - set(_SUPPORTED_ATOMIC))
        if unsupported:
            supported = ", ".join(_SUPPORTED_ATOMIC)
            msg = (
                f"[chunking] atomic entries {unsupported} are not supported; "
                f"v1 knows only: {supported}"
            )
            raise ValueError(msg)
        if set(self.atomic) != set(_SUPPORTED_ATOMIC):
            # Making tables or code blocks non-atomic is not a knob the chunker has
            # (ADR-0007): atomicity is what keeps a table from being split mid-row.
            missing = sorted(set(_SUPPORTED_ATOMIC) - set(self.atomic))
            msg = (
                f"[chunking] atomic must list every supported kind; {missing} cannot be "
                "made splittable in v1"
            )
            raise ValueError(msg)
        return self

    def to_policy(self) -> ChunkingPolicy:
        """Build the chunker's policy from these settings.

        ``max_tokens`` is the real ceiling. ``target_tokens`` maps to the policy's
        *advisory* lower target: the packer fills toward the ceiling and splits at
        the paragraph before breaching it, and it deliberately does not enforce a
        minimum, because reaching one would mean merging across a heading boundary
        (ADR-0007). Lowering ``target_tokens`` therefore does not shrink chunks
        today — see ADR-0014 and roadmap 3.8.
        """
        return ChunkingPolicy(
            target_min_tokens=self.target_tokens, target_max_tokens=self.max_tokens
        )


class EmbeddingConfig(_Section):
    """`[embedding]` — recorded now, honoured when the embedder lands (roadmap 3.3)."""

    provider: str = "local-onnx"
    model_id: str = "bge-small-en-v1.5"


class ModulesConfig(_Section):
    """`[modules]` — activatable optional modules (D-023/D-025)."""

    enabled: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _no_modules_exist_yet(self) -> Self:
        if self.enabled:
            # The first module arrives at roadmap 5.5. Accepting a name now would
            # promise a load that cannot happen.
            msg = (
                f"[modules] enabled lists {list(self.enabled)}, but no modules exist yet "
                "(the first ships at roadmap 5.5); leave it empty"
            )
            raise ValueError(msg)
        return self


class MyceliumConfig(BaseModel):
    """A validated `mycelium.toml`, plus the digest that binds it to a build."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: ProjectConfig = ProjectConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    modules: ModulesConfig = ModulesConfig()
    future: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Documented sections this milestone does not interpret.",
    )
    source: Path | None = Field(
        default=None, description="The file this came from; None when defaulted."
    )

    @property
    def unhonoured_sections(self) -> tuple[str, ...]:
        """Sections present in the file that nothing reads yet."""
        return tuple(sorted(self.future))

    def digest(self) -> Sha256Digest:
        """Digest the effective configuration for the snapshot manifest.

        Computed over the *resolved* settings rather than the file's bytes, so
        formatting, key order, and comments do not invalidate a build, while any
        change that reaches the compiler does (spec 05 §2). Sections that are not
        yet honoured are included: they will be honoured, and a build recorded
        under a config that already carried them should not silently match one
        that did not.
        """
        return digest_json(
            {
                "project": self.project.model_dump(mode="json"),
                "chunking": self.chunking.model_dump(mode="json"),
                "embedding": self.embedding.model_dump(mode="json"),
                "modules": self.modules.model_dump(mode="json"),
                "future": self.future,
            }
        )


def _describe(error: ValidationError, path: Path) -> str:
    """Render pydantic's report as operator-facing lines naming file and key."""
    lines = [f"{path}: invalid configuration"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(root)"
        lines.append(f"  {location}: {item['msg']}")
    return "\n".join(lines)


def load_config(root: Path) -> MyceliumConfig:
    """Load `mycelium.toml` from `root`, or return defaults when it is absent.

    A missing file is not an error — `mycelium build` works in a bare directory,
    and `mycelium init` writes the file for the operator's convenience, not as a
    precondition. A file that exists and is broken *is* an error: the operator
    stated an intent that cannot be satisfied.
    """
    path = root / CONFIG_FILENAME
    if not path.exists():
        return MyceliumConfig()

    try:
        raw: Mapping[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"{path}: not valid TOML - {exc}"
        raise ConfigError(msg) from exc
    except OSError as exc:
        msg = f"{path}: cannot be read - {exc}"
        raise ConfigError(msg) from exc

    honoured = {"project", "chunking", "embedding", "modules"}
    unknown = sorted(set(raw) - honoured - UNHONOURED_SECTIONS)
    if unknown:
        known = ", ".join(sorted(honoured | UNHONOURED_SECTIONS))
        msg = f"{path}: unknown section(s) {unknown}; spec 05 §2 defines: {known}"
        raise ConfigError(msg)

    future = {name: value for name, value in raw.items() if name in UNHONOURED_SECTIONS}
    try:
        return MyceliumConfig(
            **{name: value for name, value in raw.items() if name in honoured},
            future=future,
            source=path,
        )
    except ValidationError as exc:
        raise ConfigError(_describe(exc, path)) from exc
