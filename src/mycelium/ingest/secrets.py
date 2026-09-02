# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ingestion secret scan (spec 02 §8, D-017).

An ingested document is somebody else's file. It arrives with whatever its author
left in it, and the evidence lane's job is to put its content into a Git working
tree and then into an index — so a credential in a support ticket, an exported
Confluence page, or a PDF of a runbook becomes a credential in the repository,
and from there in every clone of it. That is the exposure this module closes.

**Precision, deliberately, over recall.** Every rule below is anchored on a
structure that does not occur in prose: a vendor's fixed key prefix, a PEM
armour line, credentials inside a URL's authority. There is no entropy
heuristic, because the classic high-entropy scanner fires on base64 images,
digests, UUIDs and minified code — and a scanner that cries wolf on healthy
documents is one an operator disables, which is strictly worse than not shipping
one. What that costs is real and stated: a bare password, a home-grown token, or
an API key with no distinctive prefix goes through unflagged. **This is not a
substitute for a repository secret scanner**; it is the one check ingestion can
make on content it is about to write into the tree.

**The scan always runs; the redaction is what `[ingest] redact_secrets` decides.**
Flagging is an observation and redaction is an action, and conflating them would
mean an operator who wants the verbatim text also loses the record that a
secret is in it. `secret_flags` on the document record is therefore populated
either way (spec 03 §3), and `mycelium doctor` reports it either way.

**Where the secret ends up when redaction is on.** The KIR is redacted *before*
it is stored, so the compiled document, its projection into `knowledge/`, its
chunks, and the index all carry the placeholder. The verbatim bytes survive in
exactly one artifact — the tier-1 original under `.mycelium/cas/originals/`,
which is gitignored and is the thing a citation is checked against (ADR-0033).
One copy, in the one place custody requires, and nowhere else (ADR-0037).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from mycelium.sdk.types import KirDocument, KirNode

__all__ = [
    "RULES",
    "Finding",
    "Rule",
    "describe",
    "redact_text",
    "redaction_for",
    "scan_kir",
    "scan_text",
]


@dataclass(frozen=True, slots=True)
class Rule:
    """One secret pattern, its id, and what a reader should be told it hid."""

    id: str
    """Kebab-case, and the string that lands in `Document.secret_flags` (D-026)."""

    description: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class Finding:
    """One match: which rule, where, and the span it covers."""

    rule_id: str
    node_id: str | None
    start: int
    end: int


def _rule(rule_id: str, description: str, pattern: str, flags: int = 0) -> Rule:
    return Rule(id=rule_id, description=description, pattern=re.compile(pattern, flags))


RULES: Final[tuple[Rule, ...]] = (
    _rule(
        "private-key-block",
        "a PEM private key",
        r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
        r"[\s\S]*?-----END (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----",
    ),
    _rule("aws-access-key-id", "an AWS access key id", r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
    _rule(
        "aws-secret-access-key",
        "an AWS secret access key",
        # The value alone is indistinguishable from any 40-character base64 run,
        # so the rule anchors on the assignment that names it. Precision is the
        # whole design (module docstring).
        r"(?i)\baws_?secret_?access_?key\b\s*[=:]\s*[\"']?([A-Za-z0-9/+=]{40})[\"']?",
    ),
    _rule("github-token", "a GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    _rule("slack-token", "a Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    _rule("google-api-key", "a Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    _rule("stripe-secret-key", "a Stripe secret key", r"\b[sr]k_(?:live|test)_[0-9A-Za-z]{16,}\b"),
    _rule("openai-api-key", "an OpenAI API key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    _rule("anthropic-api-key", "an Anthropic API key", r"\bsk-ant-[A-Za-z0-9_-]{32,}\b"),
    _rule(
        "credentials-in-url",
        "credentials embedded in a URL",
        # The userinfo only, not the whole URL: the host is not the secret, and a
        # redaction that swallowed it would destroy the one part of the line a
        # reader needs in order to know what the credential was *for*.
        r"(?<=://)[^\s/:@]+:[^\s/@]+(?=@)",
    ),
    _rule(
        "private-key-assignment",
        "a private key assigned to a named field",
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd)\b"
        r"\s*[=:]\s*[\"'][^\"'\n]{12,}[\"']",
    ),
)
"""The scan, in the order it is applied.

Adding a rule is a deliberate, reviewable event and each one carries its own
fixture, because the cost of a wrong rule is not a missed secret — it is an
operator turning the scan off."""

_BY_ID: Final = {rule.id: rule for rule in RULES}


def redaction_for(rule_id: str) -> str:
    """The placeholder that replaces a match, naming what it hid.

    Self-describing on purpose: a reader of the evidence document has to be able
    to tell a redaction from the document's own prose, and an operator has to be
    able to tell *which* rule fired without opening the custody record.
    """
    return f"[redacted: {rule_id}]"


def scan_text(text: str, *, node_id: str | None = None) -> list[Finding]:
    """Every rule match in `text`, in document order then rule order."""
    findings = [
        Finding(rule_id=rule.id, node_id=node_id, start=match.start(), end=match.end())
        for rule in RULES
        for match in rule.pattern.finditer(text)
    ]
    findings.sort(key=lambda finding: (finding.start, finding.end, finding.rule_id))
    return findings


def redact_text(text: str, findings: Sequence[Finding]) -> str:
    """Replace each finding's span with its placeholder.

    Applied right to left so earlier spans keep the offsets they were found at,
    and overlapping matches — two rules on one credential — collapse to the first
    of them rather than producing nested placeholders.
    """
    ordered = sorted(findings, key=lambda finding: (finding.start, -finding.end))
    kept: list[Finding] = []
    reach = -1
    for finding in ordered:
        if finding.start >= reach:
            kept.append(finding)
            reach = finding.end
    out = text
    for finding in reversed(kept):
        out = out[: finding.start] + redaction_for(finding.rule_id) + out[finding.end :]
    return out


def scan_kir(kir: KirDocument) -> tuple[KirDocument, tuple[str, ...], tuple[Finding, ...]]:
    """Scan every node's text, and return the document with the matches redacted.

    Returns `(redacted, flags, findings)`. `flags` is the sorted, de-duplicated
    rule ids — what `Document.secret_flags` records — and is non-empty exactly
    when `findings` is, whether or not the caller goes on to use the redacted
    document.

    A document with no findings comes back *identical*, not merely equal: the
    scan must not perturb the KIR of the overwhelming majority of documents, or
    every ingestion would pay a rebuild for a check that found nothing.
    """
    findings: list[Finding] = []
    nodes: list[KirNode] = []
    changed = False
    for node in kir.nodes:
        if not node.text:
            nodes.append(node)
            continue
        matches = scan_text(node.text, node_id=node.id)
        if not matches:
            nodes.append(node)
            continue
        findings.extend(matches)
        nodes.append(node.model_copy(update={"text": redact_text(node.text, matches)}))
        changed = True

    flags = _flags(findings)
    if not changed:
        return kir, flags, tuple(findings)
    return kir.model_copy(update={"nodes": tuple(nodes)}), flags, tuple(findings)


def _flags(findings: Iterable[Finding]) -> tuple[str, ...]:
    return tuple(sorted({finding.rule_id for finding in findings}))


def describe(flags: Sequence[str]) -> str:
    """An operator-facing sentence for a set of flags."""
    return ", ".join(
        f"{flag} ({_BY_ID[flag].description})" if flag in _BY_ID else flag for flag in flags
    )
