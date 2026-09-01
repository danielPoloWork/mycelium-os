# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Configuration loading (roadmap 2.14): the spec's file parses, defaults hold when it is
absent, every error names its key, and the digest reacts to exactly what reaches the
compiler."""

from pathlib import Path

import pytest

from mycelium.config import (
    CONFIG_FILENAME,
    UNHONOURED_SECTIONS,
    ConfigError,
    MyceliumConfig,
    load_config,
)
from mycelium.sdk.types import VerificationStatus

# spec 05 §2, verbatim except for the commented-out alternatives and one documented
# deviation: the spec's single `[ingest] connectors` list names *parsers*, because §2
# predates §4.1's split of the Connector and Parser Protocols. This project honours the
# split (ADR-0032), so the parser list lives under `parsers` and `connectors` names how a
# source is acquired. `test_the_specs_connector_list_is_refused_by_name` covers the old
# shape.
SPEC_FILE = """
[project]
name = "acme-docs"
namespace = "default"
knowledge_dir = "knowledge"
sources_dir = "sources"

[ingest]
parsers = ["markdown", "docling", "pandoc", "pdf"]
connectors = ["file"]
redact_secrets = true
max_failed_elements = 0.05

[chunking]
target_tokens = 400
max_tokens = 800
atomic = ["table", "code"]

[embedding]
provider = "local-onnx"
model_id = "bge-small-en-v1.5"

[modules]
enabled = []

[synthesis]
enabled = "auto"
plugin = "wiki"
provider = "anthropic"
model_id = "claude-opus-5"

[verification]
cites_coverage_min = 0.95
entailment_min = 0.90
auto_promote = false

[sources]
"docs.python.org" = "high"
"internal-wiki" = "medium"
"*" = "unknown"

[retrieval]
profile = "hybrid"
k = 10
budget_tokens = 4000
include_candidate = true
graph_expansion = false

[eval]
sets = ["eval/dev.jsonl", "eval/release.jsonl"]
"""


def write(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / CONFIG_FILENAME).write_text(body, encoding="utf-8", newline="\n")
    return root


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_the_specs_own_file_loads(tmp_path: Path) -> None:
    """Every section spec 05 §2 documents is accepted, honoured or not."""
    config = load_config(write(tmp_path, SPEC_FILE))
    assert config.project.name == "acme-docs"
    assert config.project.knowledge_dir == "knowledge"
    assert config.chunking.max_tokens == 800
    assert config.embedding.provider == "local-onnx"
    assert set(config.unhonoured_sections) == UNHONOURED_SECTIONS
    assert config.ingest.parsers == ("markdown", "docling", "pandoc", "pdf")
    # `[ingest]` is honoured by key rather than as a whole: the parser list steers
    # ingestion (4.1), the loss budget bounds a projection (4.3), and only the
    # secret scan is still waiting (4.6).
    assert config.unhonoured_keys == ("ingest.redact_secrets",)
    assert config.ingest.max_failed_elements == 0.05
    assert config.source == tmp_path / CONFIG_FILENAME


def test_the_specs_connector_list_is_refused_by_name(tmp_path: Path) -> None:
    """Copying spec 05 §2's `connectors = ["markdown", ...]` says what replaced it.

    Accepting it would be worse than refusing: the names would resolve as
    connectors, fail three commands later, and the operator would have no way to
    know the key had split (ADR-0032).
    """
    body = '[ingest]\nconnectors = ["markdown", "html", "pdf"]\n'
    with pytest.raises(ConfigError, match="names parser"):
        load_config(write(tmp_path, body))


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """`mycelium build` works in a bare directory; init writes the file for convenience."""
    config = load_config(tmp_path)
    assert config == MyceliumConfig()
    assert config.source is None
    assert config.project.knowledge_dir == "knowledge"


def test_partial_files_take_defaults_for_the_rest(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, '[project]\nname = "only-a-name"\n'))
    assert config.project.name == "only-a-name"
    assert config.project.namespace == "default"
    assert config.chunking.max_tokens == 800


def test_the_generated_template_is_valid(tmp_path: Path) -> None:
    """`mycelium init` must not write a file that `mycelium build` then rejects."""
    from mycelium.cli.app import _CONFIG_TEMPLATE

    config = load_config(write(tmp_path, _CONFIG_TEMPLATE.format(name="demo")))
    assert config.unhonoured_sections == ()
    # The template comments out the keys that do nothing yet, so a scaffolded
    # repository has nothing for `doctor` to warn about.
    assert config.unhonoured_keys == ()
    # The scaffold states the defaults explicitly, so it must equal them.
    assert config.chunking.to_policy() == MyceliumConfig().chunking.to_policy()


# ---------------------------------------------------------------------------
# `[synthesis]` — the lane that must stay off until it is asked for (roadmap 4.4)
# ---------------------------------------------------------------------------


def test_the_synthesis_lane_is_off_by_default() -> None:
    """The offline default (D-013): a fresh install makes no network call."""
    synthesis = MyceliumConfig().synthesis
    assert synthesis.enabled == "auto"
    assert synthesis.provider is None
    assert synthesis.active is False


def test_auto_means_on_when_a_provider_is_named(tmp_path: Path) -> None:
    body = '[synthesis]\nprovider = "anthropic"\n'
    assert load_config(write(tmp_path, body)).synthesis.active is True


def test_the_lane_can_be_switched_off_with_a_provider_configured(tmp_path: Path) -> None:
    body = '[synthesis]\nenabled = false\nprovider = "anthropic"\n'
    assert load_config(write(tmp_path, body)).synthesis.active is False


def test_forcing_the_lane_on_without_a_provider_is_refused(tmp_path: Path) -> None:
    # `enabled = true` says "this must run"; without a provider it cannot, and a
    # silent no-op would be the worst reading of an explicit instruction.
    with pytest.raises(ConfigError, match="no provider is configured"):
        load_config(write(tmp_path, "[synthesis]\nenabled = true\n"))


def test_an_unknown_synthesizer_plugin_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="wiki"):
        load_config(write(tmp_path, '[synthesis]\nplugin = "freestyle"\n'))


def test_the_citation_floor_defaults_to_every_claim(tmp_path: Path) -> None:
    # "Mandatory wikilink citations" as a number: 1.0, stricter than gate G7's
    # 0.95, because relaxing a floor is easier than un-publishing a claim.
    assert MyceliumConfig().synthesis.min_citation_coverage == 1.0


def test_the_citation_floor_is_a_fraction(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="less than or equal to 1"):
        load_config(write(tmp_path, "[synthesis]\nmin_citation_coverage = 1.5\n"))


def test_synthesis_settings_reach_the_config_digest(tmp_path: Path) -> None:
    plain = load_config(write(tmp_path / "a", "[project]\n"))
    tuned = load_config(write(tmp_path / "b", "[synthesis]\nmin_citation_coverage = 0.9\n"))
    assert plain.digest() != tuned.digest()


# ---------------------------------------------------------------------------
# Errors name the file and the key
# ---------------------------------------------------------------------------


def test_broken_toml_is_reported_with_the_path(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(write(tmp_path, "[project\nname = "))


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('[project]\nunknown_key = "x"\n', "unknown_key"),
        ("[chunking]\ntarget_tokens = 900\n", "exceeds"),
        ("[chunking]\nmax_tokens = 0\n", "greater than 0"),
        ('[chunking]\natomic = ["table", "code", "quote"]\n', "not supported"),
        ('[chunking]\natomic = ["code"]\n', "cannot be made splittable"),
        ('[modules]\nenabled = ["chats"]\n', "no modules exist yet"),
        ('[project]\nknowledge_dir = "/etc"\n', "relative path"),
        ('[project]\nknowledge_dir = "../outside"\n', "relative path"),
        ('[project]\nknowledge_dir = ""\n', "must not be empty"),
    ],
)
def test_invalid_values_are_refused_with_a_named_key(
    tmp_path: Path, body: str, expected: str
) -> None:
    with pytest.raises(ConfigError, match=expected):
        load_config(write(tmp_path, body))


def test_an_unknown_section_lists_the_known_ones(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, "[retreival]\nk = 10\n"))  # typo, deliberately
    message = str(caught.value)
    assert "retreival" in message
    assert "retrieval" in message  # the correct spelling is offered by the list


def test_errors_name_the_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=CONFIG_FILENAME):
        load_config(write(tmp_path, "[chunking]\nmax_tokens = -1\n"))


# ---------------------------------------------------------------------------
# The chunking mapping (ADR-0014)
# ---------------------------------------------------------------------------


def test_max_tokens_is_the_real_ceiling(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, "[chunking]\nmax_tokens = 250\ntarget_tokens = 100\n"))
    policy = config.chunking.to_policy()
    assert policy.max_tokens == 250
    assert policy.target_tokens == 100


def test_default_config_yields_the_default_policy() -> None:
    """The scaffolded defaults must not change what the compiler already produces."""
    from mycelium.chunking import ChunkingPolicy

    policy = MyceliumConfig().chunking.to_policy()
    assert policy.max_tokens == ChunkingPolicy().max_tokens
    assert policy.target_tokens == ChunkingPolicy().target_tokens
    assert policy.count_tokens is ChunkingPolicy().count_tokens


# ---------------------------------------------------------------------------
# The digest binds config to a build (spec 05 §2)
# ---------------------------------------------------------------------------


def test_digest_ignores_formatting_but_not_settings(tmp_path: Path) -> None:
    plain = load_config(write(tmp_path / "a", "[chunking]\nmax_tokens = 800\n"))
    reordered = load_config(
        write(
            tmp_path / "b",
            "# a comment\n\n[chunking]\n\nmax_tokens   =   800   # spacing\n",
        )
    )
    changed = load_config(write(tmp_path / "c", "[chunking]\nmax_tokens = 700\n"))
    assert plain.digest() == reordered.digest()
    assert plain.digest() != changed.digest()


def test_digest_covers_sections_that_are_not_honoured_yet(tmp_path: Path) -> None:
    """They will be honoured; two builds under different values must not collide."""
    one = load_config(write(tmp_path / "a", '[retrieval]\nprofile = "hybrid"\n'))
    two = load_config(write(tmp_path / "b", '[retrieval]\nprofile = "lexical"\n'))
    assert one.digest() != two.digest()


def test_digest_is_stable_across_loads(tmp_path: Path) -> None:
    root = write(tmp_path, SPEC_FILE)
    assert load_config(root).digest() == load_config(root).digest()


# ---------------------------------------------------------------------------
# The settings actually reach the build (the point of roadmap 2.14)
# ---------------------------------------------------------------------------

DOC = """---
title: Retries
---

# Retries

The payments webhook retries with exponential backoff when the endpoint fails.

## Policy

Five attempts, doubling the delay each time, then the dead-letter queue.

A second paragraph in the same section, so a token ceiling has somewhere to cut.

A third paragraph, for the same reason, with enough words to carry weight.
"""


def seed(root: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DOC, encoding="utf-8", newline="\n")
    return root


def test_knowledge_dir_moves_what_the_build_discovers(tmp_path: Path) -> None:
    from mycelium.build import build

    seed(tmp_path, "documentation/retries.md")
    write(tmp_path, '[project]\nknowledge_dir = "documentation"\n')
    result = build(tmp_path)
    assert result.manifest.counts.documents == 1


def test_namespace_comes_from_the_config(tmp_path: Path) -> None:
    from mycelium.build import build
    from mycelium.store import SqliteStore

    seed(tmp_path, "knowledge/retries.md")
    write(tmp_path, '[project]\nnamespace = "team-a"\n')
    build(tmp_path)
    store = SqliteStore.open(tmp_path, read_only=True)
    try:
        results = store.search_chunks("retries", limit=1)
    finally:
        store.close()
    assert results
    assert results[0].chunk.namespace == "team-a"


def test_an_explicit_namespace_overrides_the_config(tmp_path: Path) -> None:
    from mycelium.build import build
    from mycelium.store import SqliteStore

    seed(tmp_path, "knowledge/retries.md")
    write(tmp_path, '[project]\nnamespace = "team-a"\n')
    build(tmp_path, namespace="override")
    store = SqliteStore.open(tmp_path, read_only=True)
    try:
        results = store.search_chunks("retries", limit=1)
    finally:
        store.close()
    assert results[0].chunk.namespace == "override"


def test_chunking_settings_change_the_chunks(tmp_path: Path) -> None:
    from mycelium.build import build

    seed(tmp_path, "knowledge/retries.md")
    loose = build(tmp_path).manifest.counts.chunks

    write(tmp_path, "[chunking]\nmax_tokens = 5\ntarget_tokens = 1\n")
    tight = build(tmp_path).manifest.counts.chunks
    assert tight > loose


def test_the_config_digest_reaches_the_manifest(tmp_path: Path) -> None:
    from mycelium.build import build

    seed(tmp_path, "knowledge/retries.md")
    first = build(tmp_path).manifest.config_digest

    write(tmp_path, "[chunking]\nmax_tokens = 400\n")
    second = build(tmp_path).manifest.config_digest
    assert first != second, "a config change must change the manifest's config digest"


def test_an_invalid_config_stops_the_build_before_it_starts(tmp_path: Path) -> None:
    from mycelium.build import build

    seed(tmp_path, "knowledge/retries.md")
    write(tmp_path, "[chunking]\nmax_tokens = 0\n")
    with pytest.raises(ConfigError):
        build(tmp_path)
    # Nothing was published: the store was never touched.
    assert not (tmp_path / ".mycelium" / "CURRENT").exists()


def test_include_candidate_false_narrows_what_is_served(tmp_path: Path) -> None:
    """Roadmap 3.9: the setting was refused by name until the store could express
    "not candidate" as a filter (ADR-0024)."""
    config = load_config(write(tmp_path, "[retrieval]\ninclude_candidate = false\n"))
    assert config.retrieval.served_statuses == frozenset(
        {VerificationStatus.VERIFIED, VerificationStatus.EVIDENCE}
    )


def test_the_default_serves_every_status() -> None:
    """A candidate is labelled, not hidden (D-021)."""
    assert MyceliumConfig().retrieval.served_statuses is None
