# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The optional entity stage (roadmap 5.4, spec 03 §6, ADR-0076).

The claims under test, in the order they matter:

**An entity is declared, never guessed.** Tags and aliases mint entities; a
document title on its own does not, and a name nothing declared is never in the
table however often the prose says it.

**One entity, several names.** Two surface forms that slug alike are one record
with two names, and an ``aliases`` key names the thing the document is about
rather than three separate things.

**Off by default, and off means nothing published.** A default build writes no
entity rows, no `mentions` edges, no `entities` digest and no `entities.jsonl` —
and enabling the stage needs no recompile, because the declarations were cached
all along.

**A mention resolves or produces nothing** (ADR-0074's rule), and a rollback
restores exactly the entity table its snapshot published.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mycelium.build import build, rollback
from mycelium.build.snapshots import decode_snapshot_state
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.config import ConfigError, load_config
from mycelium.entities import (
    ALIAS,
    FRONTMATTER_TAG,
    INLINE_TAG,
    MIN_NAME_LENGTH,
    TAG_KIND,
    TOPIC_KIND,
    EntityDeclaration,
    declare_document,
    declare_entities,
    decode_declarations,
    encode_declarations,
    entities_digest,
    entity_mentions,
    resolve_entities,
)
from mycelium.export import RECORDS_DIRNAME, export_bundle
from mycelium.markdown import parse_markdown
from mycelium.sdk.identity import derived_ulid, entity_ref
from mycelium.sdk.types import EdgeStatus, EdgeType, Entity, ProvenanceOrigin
from mycelium.store import SqliteStore

ENABLED = "[entities]\nenabled = true\n"

CORPUS = {
    "knowledge/architecture.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC1\ntitle: Architecture\n"
        "aliases: [Arch, the design]\ntags: [architecture, event-bus]\n---\n\n"
        "# Architecture\n\nThe bus routes messages. #architecture\n\n"
        "## Delivery\n\nDelivery is at-least-once, and retries are bounded.\n"
    ),
    "knowledge/retries.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC2\ntags: [delivery]\n---\n\n"
        "# Retry Policy\n\nThe Architecture document explains the event-bus.\n\n"
        "## Code\n\n```python\nevent_bus = 1\n```\n"
    ),
    "knowledge/guide.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC3\n---\n\n"
        "# Guide\n\nRead about the event-bus here. See also #2252 and #4022.\n"
    ),
}


def repo(tmp_path: Path, files: Mapping[str, str] | None = None, *, enabled: bool = True) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    if enabled:
        with (root / "mycelium.toml").open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(ENABLED)
    return root


def stored(root: Path) -> tuple[Entity, ...]:
    with SqliteStore.open(root, read_only=True) as store:
        return store.all_entities()


def mentions(root: Path) -> list[tuple[str, str]]:
    with SqliteStore.open(root, read_only=True) as store:
        return sorted(
            (edge.from_, edge.to) for edge in store.all_edges() if edge.type is EdgeType.MENTIONS
        )


@dataclass(frozen=True)
class _State:
    path: str
    entities: tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    origin: str = ProvenanceOrigin.AUTHORED.value
    """Who declared these. An ingested document declares nothing a human meant,
    so its entities resolve `extracted` (roadmap 5.7, ADR-0079)."""


def _declared(*declarations: EntityDeclaration) -> tuple[Mapping[str, str], ...]:
    return tuple(encode_declarations(declarations))


# ---------------------------------------------------------------------------
# Declaration: what a document says it names
# ---------------------------------------------------------------------------


def test_tags_and_aliases_declare_and_a_bare_title_does_not() -> None:
    declared = declare_entities(
        tags=("architecture", "event-bus"),
        aliases=("Arch",),
        title="Architecture",
        inline_tags=(("delivery", "a.md#x/0"),),
    )
    assert [(item.slug, item.name, item.kind, item.source) for item in declared] == [
        ("architecture", "architecture", TAG_KIND, FRONTMATTER_TAG),
        ("event-bus", "event-bus", TAG_KIND, FRONTMATTER_TAG),
        ("delivery", "delivery", TAG_KIND, INLINE_TAG),
        ("architecture", "Architecture", TOPIC_KIND, ALIAS),
        ("architecture", "Arch", TOPIC_KIND, ALIAS),
    ]
    # An inline tag knows the passage it sits in; frontmatter belongs to the document.
    assert declared[2].anchor == "a.md#x/0"
    assert declared[0].anchor == ""

    # A title with no aliases is not a declaration — the stage's central refusal.
    assert declare_entities(tags=(), aliases=(), title="Architecture") == ()


def test_an_alias_takes_the_titles_slug_rather_than_one_of_its_own() -> None:
    """`aliases: [Arch]` says the thing has another name, not that another thing exists."""
    declared = declare_entities(tags=(), aliases=("Arch", "the design"), title="Architecture")
    assert {item.slug for item in declared} == {"architecture"}
    assert [item.name for item in declared] == ["Architecture", "Arch", "the design"]


@pytest.mark.parametrize(
    ("tag", "kept"),
    [
        ("architecture", True),
        ("設計", True),
        ("Größenordnung", True),
        ("a", True),
        ("2252", False),
        ("313", False),
        ("1.2.3", False),
        ("---", False),
        ("", False),
        ("   ", False),
    ],
)
def test_a_tag_declares_only_when_it_has_a_letter_in_any_script(tag: str, kept: bool) -> None:
    """84 of the three corpora's 85 inline tags are issue numbers — and the first
    version of this filter was ASCII-only and threw away `設計` (ADR-0076)."""
    declared = declare_entities(tags=(tag,), aliases=(), title="T")
    assert bool(declared) is kept


def test_declaration_reads_a_documents_frontmatter_and_its_inline_tags() -> None:
    text = (
        "---\ntitle: Architecture\naliases: [Arch]\ntags: [architecture]\n---\n\n"
        "# Architecture\n\nThe bus routes messages. #event-bus\n"
    )
    parsed = parse_markdown(text)
    chunks = chunk_document(parsed.kir, doc_path="a.md", policy=ChunkingPolicy())
    declared = declare_document(
        parsed.kir, chunks, frontmatter=parsed.frontmatter, title="Architecture"
    )
    assert {(item.slug, item.source) for item in declared} == {
        ("architecture", FRONTMATTER_TAG),
        ("event-bus", INLINE_TAG),
        ("architecture", ALIAS),
    }
    assert next(item for item in declared if item.source == INLINE_TAG).anchor.startswith("a.md#")


def test_declarations_round_trip_through_their_encoding() -> None:
    declared = declare_entities(tags=("a-tag",), aliases=("Alias",), title="Title")
    assert decode_declarations(encode_declarations(declared)) == declared


# ---------------------------------------------------------------------------
# Resolution: one row per name, across the corpus
# ---------------------------------------------------------------------------


def test_resolution_merges_declarations_and_prefers_a_topics_own_title() -> None:
    states = [
        _State(
            "knowledge/z.md",
            _declared(*declare_entities(tags=("architecture",), aliases=(), title="Z")),
        ),
        _State(
            "knowledge/a.md",
            _declared(*declare_entities(tags=(), aliases=("Arch",), title="Architecture")),
        ),
    ]
    (entity,) = resolve_entities(states)
    assert entity.slug == "architecture"
    assert entity.name == "Architecture"  # the topic's title, not the tag's spelling
    assert entity.aliases == ("Arch", "architecture")
    assert entity.kind == TOPIC_KIND
    assert entity.status is EdgeStatus.AUTHORED
    assert entity.doc_refs == ("doc:knowledge/a.md", "doc:knowledge/z.md")
    # Order of the input never reaches the output.
    assert resolve_entities(list(reversed(states))) == resolve_entities(states)


def test_an_entity_id_is_derived_from_its_slug_not_minted() -> None:
    """A build may not write to tier 2, so there is nowhere to persist a minted
    id and two builds of one corpus must agree (ADR-0046, ADR-0076)."""
    (entity,) = resolve_entities(
        [_State("a.md", _declared(*declare_entities(tags=("thing",), aliases=(), title="T")))]
    )
    assert entity.entity_id == derived_ulid(entity_ref("thing"))
    assert (
        entity.entity_id
        == resolve_entities(
            [_State("b.md", _declared(*declare_entities(tags=("thing",), aliases=(), title="T")))]
        )[0].entity_id
    )


def test_a_corpus_that_declares_nothing_resolves_to_nothing() -> None:
    assert resolve_entities([_State("a.md"), _State("b.md")]) == ()
    assert entities_digest(()) == entities_digest(())


def test_state_written_before_the_stage_decodes_with_no_declarations() -> None:
    blob = json.dumps(
        [
            {
                "doc_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "path": "knowledge/a.md",
                "source_digest": "sha256:aa",
                "source_mtime": "2026-01-01T00:00:00+00:00",
                "env_digest": "sha256:bb",
                "document": "sha256:cc",
                "chunks": "sha256:dd",
                "warnings": [],
            }
        ]
    )
    (state,) = decode_snapshot_state(blob)
    assert state.entities == ()


# ---------------------------------------------------------------------------
# Mentions: where the corpus names what it declared
# ---------------------------------------------------------------------------


def _chunks(text: str, path: str = "b.md") -> list[tuple[str, object]]:
    parsed = parse_markdown(text)
    return [
        (path, chunk)
        for chunk in chunk_document(parsed.kir, doc_path=path, policy=ChunkingPolicy())
    ]


def test_a_mention_needs_a_declaration_and_a_whole_word() -> None:
    entities = resolve_entities(
        [_State("a.md", _declared(*declare_entities(tags=("delivery",), aliases=(), title="A")))]
    )
    found = entity_mentions(entities, _chunks("# B\n\nDelivery is at-least-once.\n"))
    assert [(edge.from_, edge.to, str(edge.type)) for edge in found] == [
        ("doc:b.md", "ent:delivery", "mentions")
    ]
    assert found[0].status is EdgeStatus.EXTRACTED
    assert found[0].provenance.kind == "prose"

    # A name nothing declared is never an edge, however often prose says it.
    assert entity_mentions((), _chunks("# B\n\nDelivery, delivery, delivery.\n")) == ()
    # Substrings are not mentions.
    assert entity_mentions(entities, _chunks("# B\n\nUndeliverable deliveries.\n")) == ()


def test_a_declarer_is_not_a_mentioner_and_one_edge_covers_a_document() -> None:
    entities = resolve_entities(
        [_State("a.md", _declared(*declare_entities(tags=("delivery",), aliases=(), title="A")))]
    )
    own = entity_mentions(entities, _chunks("# A\n\nDelivery here.\n", path="a.md"))
    assert own == (), "the declaration already says so, through doc_refs"

    repeated = entity_mentions(entities, _chunks("# B\n\nDelivery, delivery, and delivery.\n"))
    assert len(repeated) == 1


def test_code_passages_are_not_prose() -> None:
    entities = resolve_entities(
        [_State("a.md", _declared(*declare_entities(tags=("delivery",), aliases=(), title="A")))]
    )
    fenced = "# B\n\n## Only code\n\n```python\ndelivery = 1\n```\n"
    assert entity_mentions(entities, _chunks(fenced)) == ()


def test_a_name_shorter_than_the_floor_is_not_searched_for() -> None:
    short = resolve_entities(
        [_State("a.md", _declared(*declare_entities(tags=("api",), aliases=(), title="A")))]
    )
    assert short and len(short[0].name) < MIN_NAME_LENGTH
    assert entity_mentions(short, _chunks("# B\n\nThe api is documented.\n")) == ()
    assert short[0].slug == "api", "the record is still minted; only the scan has a floor"


def test_the_longest_declared_name_wins_at_a_position() -> None:
    states = [
        _State(
            "a.md",
            _declared(*declare_entities(tags=("event", "event-bus"), aliases=(), title="A")),
        )
    ]
    entities = resolve_entities(states)
    found = entity_mentions(entities, _chunks("# B\n\nThe event-bus routes messages.\n"))
    assert [edge.to for edge in found] == ["ent:event-bus"]


@given(st.text(alphabet=st.characters(exclude_categories=("Cs",)), max_size=400))
def test_any_prose_is_scanned_without_error_and_deterministically(text: str) -> None:
    entities = resolve_entities(
        [
            _State(
                "a.md",
                _declared(*declare_entities(tags=("delivery", "event-bus"), aliases=(), title="A")),
            )
        ]
    )
    passages = _chunks(f"# B\n\n{text}\n") if text.strip() else _chunks("# B\n\nempty.\n")
    first = entity_mentions(entities, passages)
    assert first == entity_mentions(entities, passages)


# ---------------------------------------------------------------------------
# The build: off by default, and what happens when it is not
# ---------------------------------------------------------------------------


def test_the_stage_is_off_by_default_and_publishes_nothing(tmp_path: Path) -> None:
    root = repo(tmp_path, enabled=False)
    manifest = build(root).manifest

    assert load_config(root).entities.enabled is False
    assert manifest.counts.entities == 0
    assert "entities" not in manifest.artifact_digests
    assert stored(root) == ()
    assert mentions(root) == []
    bundle = export_bundle(root)
    assert "entities" not in bundle.counts
    assert not (bundle.bundle / RECORDS_DIRNAME / "entities.jsonl").exists()


def test_enabling_the_stage_publishes_the_table_and_its_mentions(tmp_path: Path) -> None:
    root = repo(tmp_path)
    manifest = build(root).manifest
    entities = stored(root)

    assert manifest.counts.entities == len(entities) == 3
    assert manifest.artifact_digests["entities"] == entities_digest(entities)
    by_slug = {entity.slug: entity for entity in entities}
    # `Retry Policy` is a title with no aliases, so it declares nothing — the
    # refusal that keeps every document's heading out of the table.
    assert set(by_slug) == {"architecture", "delivery", "event-bus"}
    assert by_slug["architecture"].name == "Architecture"
    assert by_slug["architecture"].aliases == ("architecture", "Arch", "the design")
    assert by_slug["architecture"].kind == TOPIC_KIND
    assert by_slug["delivery"].kind == TAG_KIND
    # `#2252` and `#4022` are issue references, not declarations.
    assert not any(slug.isdigit() for slug in by_slug)

    assert ("doc:knowledge/guide.md", "ent:event-bus") in mentions(root)
    assert ("doc:knowledge/retries.md", "ent:architecture") in mentions(root)
    # retries.md declares `delivery`, so it does not also mention it.
    assert ("doc:knowledge/retries.md", "ent:delivery") not in mentions(root)


def test_turning_the_stage_on_costs_no_recompile(tmp_path: Path) -> None:
    """The declarations are cached whatever the flag says, so the flag gates
    publication and nothing else (ADR-0076)."""
    root = repo(tmp_path, enabled=False)
    build(root)
    with (root / "mycelium.toml").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(ENABLED)

    result = build(root)

    assert result.stats.rebuilt == 0 and result.stats.reused == 3
    assert len(stored(root)) == 3


def test_turning_the_stage_off_again_removes_what_it_published(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    assert stored(root)
    (root / "mycelium.toml").unlink()

    manifest = build(root).manifest

    assert stored(root) == ()
    assert mentions(root) == []
    assert "entities" not in manifest.artifact_digests


def test_an_export_carries_the_entities_the_snapshot_holds(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    result = export_bundle(root)

    lines = (result.bundle / RECORDS_DIRNAME / "entities.jsonl").read_text("utf-8").splitlines()
    exported = [Entity.model_validate_json(line) for line in lines]
    assert result.counts["entities"] == len(exported) == 3
    assert exported == list(stored(root))


def test_a_declaration_added_elsewhere_reaches_an_untouched_document(tmp_path: Path) -> None:
    """Resolution is global: a tag declared in a *new* document gives an old one
    a mention, without the old one being recompiled (ADR-0018's property, for
    the entity table)."""
    root = repo(tmp_path)
    build(root)
    assert ("doc:knowledge/architecture.md", "ent:messages") not in mentions(root)

    # architecture.md already says "The bus routes messages" and is not touched.
    with (root / "knowledge" / "glossary.md").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC5\ntags: [messages]\n---\n\n# Glossary\n"
        )
    result = build(root)

    assert result.stats.rebuilt == 1 and result.stats.reused == 3
    assert ("doc:knowledge/architecture.md", "ent:messages") in mentions(root)


def test_rollback_restores_the_entity_table_its_snapshot_published(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root).manifest
    before = stored(root)

    with (root / "knowledge" / "guide.md").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n---\n\nMore prose.\n")
    with (root / "knowledge" / "extra.md").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC4\ntags: [novel]\n---\n\n# Extra\n"
        )
    build(root)
    assert "novel" in {entity.slug for entity in stored(root)}

    rollback(root, first.snapshot_id)

    assert stored(root) == before
    assert first.artifact_digests["entities"] == entities_digest(before)


def test_a_snapshot_built_with_the_stage_off_rolls_back_without_it(tmp_path: Path) -> None:
    """Whether the stage ran is read from the manifest, not from today's config,
    so flipping the flag never makes an older snapshot unrestorable."""
    root = repo(tmp_path, enabled=False)
    first = build(root).manifest
    with (root / "mycelium.toml").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(ENABLED)
    build(root)
    assert stored(root)

    rollback(root, first.snapshot_id)

    assert stored(root) == ()


def test_the_section_is_validated_like_every_other(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "mycelium.toml").write_text("[entities]\nenabled = true\n", encoding="utf-8")
    assert load_config(root).entities.enabled is True

    (root / "mycelium.toml").write_text("[entities]\nenabld = true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="enabld"):
        load_config(root)
