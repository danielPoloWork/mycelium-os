# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ingestion secret scan (roadmap 4.6).

Two properties carry this file, and they pull against each other on purpose:
every rule fires on a credential shaped the way its vendor shapes them, and
**nothing fires on ordinary documentation**. The second is the one that decides
whether the feature survives contact with a real corpus — a scanner that flags
prose is a scanner an operator turns off — so the negative corpus below is this
repository's own writing, not an invented sample.
"""

import pytest

from mycelium.ingest.secrets import (
    RULES,
    Finding,
    describe,
    redact_text,
    redaction_for,
    scan_kir,
    scan_text,
)
from mycelium.sdk.types import KirDocument, KirNode, NodeKind

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = "sha256:" + "0" * 64

# One credential per rule, in the shape its vendor issues. Fabricated values with
# the real structure: AWS's own documentation example, and otherwise random.
POSITIVES: list[tuple[str, str]] = [
    ("aws-access-key-id", "the key is AKIAIOSFODNN7EXAMPLE for the job"),
    (
        "aws-secret-access-key",
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
    ),
    ("github-token", "token ghp_16C7e42F292c6912E7710c838347Ae178B4a is in the vault"),
    ("slack-token", "xoxb-2314513412-2354623462-aBcDeFgHiJkLmNoPqRsT"),
    ("google-api-key", "AIzaSyD-1234567890abcdefghijklmnopqrstu"),
    ("stripe-secret-key", "sk_live_4eC39HqLyjWDarjtT1zdp7dc"),
    ("openai-api-key", "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
    ("anthropic-api-key", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"),
    ("credentials-in-url", "clone https://deploy:hunter2@git.example.com/repo.git"),
    ("private-key-assignment", 'client_secret: "s3cr3t-value-here"'),
    (
        "private-key-block",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK\n-----END RSA PRIVATE KEY-----",
    ),
]

# Prose, structure and code that a real corpus is full of. Every line here is the
# kind of thing this project's own documents contain.
NEGATIVES: list[str] = [
    "Retry policy: deliveries are retried five times with exponential backoff.",
    "The digest is sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "See https://example.com/docs/retries and https://api.example.com/v1/webhooks",
    "doc_id: 01J1ZC8Q4R6XKQ3F0V9T8B2M7N",
    "| attempt | delay |\n|---------|-------|\n| 1       | 1 s   |",
    "delay = 2 ** attempt  # seconds",
    "Set AWS_ACCESS_KEY_ID in the environment before running the job.",
    "password: see the vault",
    "Base64 payload: iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8",
    "A UUID looks like 123e4567-e89b-12d3-a456-426614174000 in the logs.",
    "authorization: Bearer <token>",
]


def kir_of(*texts: str) -> KirDocument:
    return KirDocument(
        doc_id=DOC_ID,
        source_digest=DIGEST,
        nodes=tuple(
            KirNode(id=f"n{index + 1}", kind=NodeKind.PARAGRAPH, ord=index, text=text)
            for index, text in enumerate(texts)
        ),
    )


# ---------------------------------------------------------------------------
# Recall: every rule catches the shape it names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("rule_id", "text"), POSITIVES, ids=[case[0] for case in POSITIVES])
def test_each_rule_fires_on_its_own_credential(rule_id: str, text: str) -> None:
    assert rule_id in {finding.rule_id for finding in scan_text(text)}


def test_every_rule_has_a_case_in_this_file() -> None:
    # A rule with no fixture is a rule nobody checked. The set is closed on
    # purpose (module docstring), so it can be asserted closed.
    assert {rule.id for rule in RULES} == {rule_id for rule_id, _ in POSITIVES}


def test_a_rule_id_is_kebab_case_because_it_becomes_a_document_flag() -> None:
    # `secret_flags` is part of the document record and therefore of the store;
    # D-026's naming rule applies to it like every other identifier.
    for rule in RULES:
        assert rule.id == rule.id.lower()
        assert rule.id.replace("-", "").isalnum()


# ---------------------------------------------------------------------------
# Precision: the property the feature lives or dies on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", NEGATIVES)
def test_ordinary_documentation_is_not_flagged(text: str) -> None:
    assert scan_text(text) == [], "a scanner that fires on prose is one nobody leaves on"


def test_this_repository_s_own_documents_are_clean() -> None:
    """The negative corpus that matters: the project's real writing.

    A rule that fires here would be flagging a document this project ships, which
    is the failure mode the whole design is arranged against.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted((root / "docs").rglob("*.md")):
        for finding in scan_text(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(root)}: {finding.rule_id}")
    assert offenders == []


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


def test_redaction_replaces_only_the_match_and_names_the_rule() -> None:
    text = "the key is AKIAIOSFODNN7EXAMPLE for the job"
    redacted = redact_text(text, scan_text(text))
    assert redacted == "the key is [redacted: aws-access-key-id] for the job"
    assert "AKIA" not in redacted


def test_a_url_keeps_its_host_and_loses_its_credentials() -> None:
    text = "clone https://deploy:hunter2@git.example.com/repo.git"
    redacted = redact_text(text, scan_text(text))
    assert redacted == ("clone https://[redacted: credentials-in-url]@git.example.com/repo.git")
    # The host is not the secret, and a reader needs it to know what the
    # credential was for.
    assert "git.example.com" in redacted
    assert "hunter2" not in redacted


def test_two_credentials_in_one_paragraph_are_both_replaced() -> None:
    text = "id AKIAIOSFODNN7EXAMPLE and token ghp_16C7e42F292c6912E7710c838347Ae178B4a"
    redacted = redact_text(text, scan_text(text))
    assert redacted.count("[redacted:") == 2
    assert "AKIA" not in redacted and "ghp_" not in redacted


def test_overlapping_matches_collapse_rather_than_nest() -> None:
    # `private-key-assignment` and `openai-api-key` both cover this line.
    text = 'api_key: "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCD"'
    findings = scan_text(text)
    assert len({finding.rule_id for finding in findings}) > 1
    redacted = redact_text(text, findings)
    assert redacted.count("[redacted:") == 1
    assert "sk-proj" not in redacted


def test_redacting_nothing_returns_the_text_unchanged() -> None:
    assert redact_text("plain prose", []) == "plain prose"


def test_a_placeholder_names_its_rule() -> None:
    assert redaction_for("github-token") == "[redacted: github-token]"


# ---------------------------------------------------------------------------
# Over a KIR document
# ---------------------------------------------------------------------------


def test_a_clean_document_comes_back_identical_not_merely_equal() -> None:
    # Identity, not equality: a scan that rebuilt every document would make every
    # ingestion of an ordinary file pay for a check that found nothing.
    kir = kir_of("Retry policy", "Deliveries are retried five times.")
    scanned, flags, findings = scan_kir(kir)
    assert scanned is kir
    assert flags == ()
    assert findings == ()


def test_flags_are_sorted_and_deduplicated() -> None:
    kir = kir_of(
        "token ghp_16C7e42F292c6912E7710c838347Ae178B4a",
        "id AKIAIOSFODNN7EXAMPLE",
        "another ghp_26C7e42F292c6912E7710c838347Ae178B4a",
    )
    _, flags, _ = scan_kir(kir)
    assert flags == ("aws-access-key-id", "github-token")


def test_only_the_matching_nodes_are_rewritten() -> None:
    kir = kir_of("Retry policy", "id AKIAIOSFODNN7EXAMPLE", "Backoff doubles.")
    scanned, _, findings = scan_kir(kir)
    assert scanned.nodes[0] is kir.nodes[0]
    assert scanned.nodes[2] is kir.nodes[2]
    assert scanned.nodes[1].text == "id [redacted: aws-access-key-id]"
    assert [finding.node_id for finding in findings] == ["n2"]


def test_the_scan_is_idempotent() -> None:
    kir = kir_of("id AKIAIOSFODNN7EXAMPLE")
    once, _, _ = scan_kir(kir)
    twice, flags, _ = scan_kir(once)
    assert twice is once, "a placeholder must not itself look like a secret"
    assert flags == ()


def test_a_node_with_no_text_is_left_alone() -> None:
    kir = KirDocument(
        doc_id=DOC_ID,
        source_digest=DIGEST,
        nodes=(KirNode(id="n1", kind=NodeKind.TABLE, ord=0),),
    )
    scanned, flags, _ = scan_kir(kir)
    assert scanned is kir
    assert flags == ()


def test_findings_come_back_in_document_order() -> None:
    text = "first AKIAIOSFODNN7EXAMPLE then ghp_16C7e42F292c6912E7710c838347Ae178B4a"
    positions = [finding.start for finding in scan_text(text)]
    assert positions == sorted(positions)


def test_describe_names_the_rule_and_what_it_matches() -> None:
    described = describe(["github-token", "unknown-rule"])
    assert "github-token (a GitHub token)" in described
    assert "unknown-rule" in described


def test_a_finding_carries_the_span_it_covers() -> None:
    text = "id AKIAIOSFODNN7EXAMPLE."
    (finding,) = scan_text(text, node_id="n7")
    assert isinstance(finding, Finding)
    assert finding.node_id == "n7"
    assert text[finding.start : finding.end] == "AKIAIOSFODNN7EXAMPLE"
