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
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from mycelium.chunking import ChunkingPolicy
from mycelium.sdk.identity import digest_json
from mycelium.sdk.types import Sha256Digest, VerificationStatus

__all__ = [
    "CONFIG_FILENAME",
    "ChunkingConfig",
    "ConfigError",
    "EmbeddingConfig",
    "IngestConfig",
    "ModulesConfig",
    "MyceliumConfig",
    "ProjectConfig",
    "RetrievalConfig",
    "UNHONOURED_SECTIONS",
    "load_config",
]

CONFIG_FILENAME: Final = "mycelium.toml"

UNHONOURED_SECTIONS: Final = frozenset({"synthesis", "verification", "sources", "eval"})
"""Sections spec 05 §2 documents whose features this milestone has not built.

They are accepted so a spec-valid file is not rejected, and digested so a build
remains reproducible from its config, but nothing reads their values yet:
`synthesis` (roadmap 4.4), `verification` (4.5), `sources` (4.5 — trust per
origin is a verification input), `eval` (the harness takes its case set on the
command line). `retrieval` left this set at roadmap 3.3, when hybrid search gave
it something to control; `ingest` left it at 4.1, and is the first section
honoured *in part* — see :class:`IngestConfig`.
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
    exclude: tuple[str, ...] = ()
    """Paths that are not documentation, however Markdown they look.

    A repository's tree carries more than its knowledge: test fixtures,
    vendored samples, generated reports. Indexing those is not a cosmetic
    problem — this project's own eval corpus scored an `unanswerable` case
    against a test fixture and reported gate G4 red for it (BUG-0007).

    A pattern matches a document's repository-relative POSIX path, any of its
    ancestor directories, or its file name. `*` stays within one segment,
    `**` spans segments, `?` is one character. So `tests` drops a tree,
    `docs/journal` drops a subtree, `**/fixtures` drops it wherever it sits,
    and `*.draft.md` drops by name. `.mycelium/` and `export/` need no pattern:
    the compiler never reads what it writes (ADR-0021).
    """

    @model_validator(mode="after")
    def _exclusions_are_relative(self) -> Self:
        for pattern in self.exclude:
            if not pattern.strip():
                msg = "[project] exclude must not contain empty patterns"
                raise ValueError(msg)
            if pattern.startswith("/") or PureWindowsPath(pattern).is_absolute():
                msg = f"[project] exclude pattern {pattern!r} must be relative to the repository"
                raise ValueError(msg)
        return self

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

    target_tokens: int | None = Field(default=None, gt=0)
    """Unset means "the ceiling": prose fills toward ``max_tokens`` as it always
    did, so lowering ``max_tokens`` alone stays a one-line edit rather than a
    contradiction between two keys (ADR-0023)."""

    max_tokens: int = Field(default=800, gt=0)
    atomic: tuple[str, ...] = ("table", "code")

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.target_tokens is not None and self.target_tokens > self.max_tokens:
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

        Both keys reach the packer under their own names and mean what they say:
        prose aims at ``target_tokens`` and never breaches ``max_tokens``. Lowering
        the target shrinks chunks, which is what it did not do before ADR-0023.

        An unset target *is* the ceiling — the measured default (ADR-0023), and the
        one setting under which a build produces exactly what it produced before.
        """
        return ChunkingPolicy(
            target_tokens=self.target_tokens or self.max_tokens, max_tokens=self.max_tokens
        )


class IngestConfig(_Section):
    """`[ingest]` — which plugins compile a source, and two knobs that do not yet.

    The first section honoured *by key rather than as a whole*, which ADR-0014's
    section-level scheme did not have a shape for. The reason is that ingestion
    arrives in four roadmap items: 4.1 pins the plugins, 4.3 spends the loss
    budget, 4.6 scans for secrets. Marking the whole section unhonoured would lie
    about `parsers`; marking it honoured would lie about the other two. So the
    keys are declared here, digested like everything else, and
    :attr:`unhonoured_keys` names the ones an operator has set that still do
    nothing — the same promise ADR-0014 makes, one level finer.

    `parsers` is *ordered* and *pinned*. The order is the dispatch policy —
    `["docling", "pandoc"]` is architecture §5's "docling first, pandoc
    fallback", stated rather than inferred from what happens to be installed —
    and every name in it must resolve or the command fails saying what to install
    (spec 05 §4.2). That is why the default is the one parser with no optional
    runtime: a fresh checkout compiles its Markdown, and ingesting anything else
    is a deliberate edit.
    """

    parsers: tuple[str, ...] = ("markdown",)
    connectors: tuple[str, ...] = ("file",)

    redact_secrets: bool = True
    """Accepted, digested, not honoured yet — the secret scan lands at roadmap 4.6."""

    max_failed_elements: float = Field(default=0.05, ge=0.0, le=1.0)
    """Accepted, digested, not honoured yet — the loss budget lands at roadmap 4.3."""

    @model_validator(mode="after")
    def _lists_are_not_empty(self) -> Self:
        for field in ("parsers", "connectors"):
            names = getattr(self, field)
            if not names:
                msg = f"[ingest] {field} must name at least one plugin"
                raise ValueError(msg)
            if any(not name.strip() for name in names):
                msg = f"[ingest] {field} must not contain empty names"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _connectors_are_not_parsers(self) -> Self:
        """Catch spec 05 §2's single `connectors` list and name its replacement.

        The spec's example is `connectors = ["markdown", "html", "pdf"]` — parser
        ids under a connector key, because §2 predates §4.1's split of the two
        Protocols. This project honours the split (ADR-0032), so the old shape is
        refused *by name* rather than accepted into a resolution failure three
        commands later.
        """
        from mycelium.ingest.registry import BUILTIN_PARSERS

        confused = sorted(set(self.connectors) & set(BUILTIN_PARSERS))
        if confused:
            msg = (
                f"[ingest] connectors names parser(s) {confused}; parsers are pinned by "
                "[ingest] parsers, and connectors names how a source is acquired "
                '(v1: ["file"]) - see ADR-0032'
            )
            raise ValueError(msg)
        return self

    @property
    def unhonoured_keys(self) -> tuple[str, ...]:
        """The keys this file *sets* that nothing reads yet, in file order."""
        pending = ("redact_secrets", "max_failed_elements")
        return tuple(name for name in pending if name in self.model_fields_set)


class EmbeddingConfig(_Section):
    """`[embedding]` — which vectors a build produces, and where the model comes from.

    `provider = "none"` switches the vector stage off entirely; it is the setting
    a lexical-only deployment states rather than achieves by accident. The two
    keys beyond spec 05 §2's file exist because a local model has to come from
    somewhere: `model_path` points at a directory you populated (vendored or
    air-gapped), and `allow_download` is the explicit consent D-017 requires
    before Mycelium makes any network call (ADR-0017).
    """

    provider: str = "local-onnx"
    model_id: str = "bge-small-en-v1.5"
    model_path: str | None = None
    allow_download: bool = False

    @model_validator(mode="after")
    def _known_provider(self) -> Self:
        if self.provider not in {"local-onnx", "none"}:
            msg = (
                f'[embedding] provider "{self.provider}" is not supported; v1 ships '
                '"local-onnx" (the default) and "none" (no vector stage)'
            )
            raise ValueError(msg)
        return self


class RetrievalConfig(_Section):
    """`[retrieval]` — the query path's defaults (spec 05 §2, spec 04 §§2-3).

    `profile` is gate G2's dial, and the one setting here decided by measurement
    rather than judgment. **It defaults to `lexical` because hybrid did not earn
    the default** (ADR-0017): on this repository's 20 judged cases hybrid gains
    +12.7 % nDCG@10 overall — comfortably past the +5 % bar — but regresses the
    `exact` slice by 17.8 % (the bar is −2 %), and answers *every* unanswerable
    query where lexical abstains. Spec 04 §7.3 prescribes exactly this outcome:
    "otherwise the shipped default config is lexical-only and the README says so".

    Set `profile = "hybrid"` to opt in; nothing else changes, and the snapshot
    already carries the vectors.

    Fusion constants are deliberately *not* here. Spec 04 §3 fixes RRF at k=60
    over 50 vector candidates, and per-profile weights are a Phase-3 concern; a
    knob nobody has eval evidence for is a liability, not a feature (D-011).
    """

    profile: Literal["hybrid", "lexical"] = "lexical"
    k: int = Field(default=10, gt=0, description="Default result count for a query.")
    budget_tokens: int = Field(default=4000, gt=0, description="Default packing budget.")
    include_candidate: bool = True
    """Whether `candidate` documents are served at all; see `served_statuses`."""

    graph_expansion: bool = False

    @property
    def hybrid(self) -> bool:
        """Whether the vector leg participates in candidate generation."""
        return self.profile == "hybrid"

    @property
    def served_statuses(self) -> frozenset[VerificationStatus] | None:
        """The verification statuses this configuration is willing to serve.

        ``None`` when every status is served, which is the default: a candidate
        is *labelled*, not hidden, and a reader who can see the label can judge
        it. ``include_candidate = false`` is the deployment that would rather not
        make that judgement available at all — a compliance posture more than a
        retrieval one — and it removes candidates from every query the process
        answers, rather than trusting each caller to remember (ADR-0024).
        """
        if self.include_candidate:
            return None
        return frozenset({VerificationStatus.VERIFIED, VerificationStatus.EVIDENCE})

    @model_validator(mode="after")
    def _only_what_exists(self) -> Self:
        if self.graph_expansion:
            msg = (
                "[retrieval] graph_expansion = true is not supported yet: there are no "
                "edges to expand over until roadmap 5.2, and the default flips only if "
                "the ablation gate passes (spec 04 §5)"
            )
            raise ValueError(msg)
        return self


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
    ingest: IngestConfig = IngestConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
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

    @property
    def unhonoured_keys(self) -> tuple[str, ...]:
        """Individual keys the file sets that nothing reads yet, `section.key` form.

        Separate from :attr:`unhonoured_sections` because they need different
        sentences: an unhonoured *section* is a feature that does not exist, an
        unhonoured *key* sits beside keys that do, which is the more surprising
        of the two and therefore the one worth naming exactly.
        """
        return tuple(f"ingest.{name}" for name in self.ingest.unhonoured_keys)

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
                "ingest": self.ingest.model_dump(mode="json"),
                "chunking": self.chunking.model_dump(mode="json"),
                "embedding": self.embedding.model_dump(mode="json"),
                "retrieval": self.retrieval.model_dump(mode="json"),
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

    honoured = {"project", "ingest", "chunking", "embedding", "retrieval", "modules"}
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
