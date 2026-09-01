# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Anthropic provider (roadmap 4.4): the request it sends, and the four ways
it can come back wrong.

The seam is thin on purpose — one call, text in, text out — and this file tests
the whole of it against a stub client, because what the adapter owns is *not* the
HTTP: it is the request shape and the translation of the SDK's failures into
answers the lane can act on. A model that declines, a truncated answer and an
empty answer all arrive as HTTP 200, and each is a different diagnosis.

The one thing a stub cannot prove is that the request is valid — that
`thinking`, `output_config` and the model id are accepted by the real API. That
is :func:`test_a_real_request_returns_a_grounded_document`, which needs a
credential and skips without one. It is marked `llm`, it costs money, and it is
the honest boundary of what CI can assert.
"""

import os
from typing import Any

import anthropic
import httpx2
import pytest

from mycelium.synthesis.errors import ProviderError, ProviderUnavailableError
from mycelium.synthesis.provider import LlmProvider
from mycelium.synthesis.providers import anthropic as adapter


class StubResponse:
    def __init__(
        self,
        *,
        text: str = "a document",
        stop_reason: str = "end_turn",
        model: str = "claude-opus-5",
        category: str | None = None,
    ) -> None:
        self.content = [_TextBlock(text)] if text else []
        self.stop_reason = stop_reason
        self.model = model
        self.stop_details = _StopDetails(category) if category else None


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _StopDetails:
    def __init__(self, category: str) -> None:
        self.category = category


class StubClient:
    """Records the request and returns whatever the test scripted."""

    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def provider(response: object, **kwargs: Any) -> adapter.AnthropicProvider:
    return adapter.AnthropicProvider(
        client=StubClient(response),
        model=str(kwargs.get("model", "claude-opus-5")),
        max_tokens=int(kwargs.get("max_tokens", 16000)),
        effort=str(kwargs.get("effort", "high")),
    )


def status_error(code: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIStatusError(
        "boom", response=httpx2.Response(code, request=request), body=None
    )


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


def test_the_adapter_satisfies_the_provider_protocol() -> None:
    assert isinstance(provider(StubResponse()), LlmProvider)
    assert provider(StubResponse()).name == "anthropic"


def test_the_default_model_is_the_most_capable_of_the_family() -> None:
    # The failure this lane exists to avoid — an unsupported claim in
    # `knowledge/candidate/` — is a reasoning failure, so the default is not the
    # cheap model. An operator trades capability for cost in one config line.
    assert adapter.DEFAULT_MODEL == "claude-opus-5"


# ---------------------------------------------------------------------------
# The request
# ---------------------------------------------------------------------------


def test_the_request_carries_the_model_the_thinking_mode_and_the_effort() -> None:
    engine = provider(StubResponse(), model="claude-opus-5", effort="xhigh")
    engine.complete(system="rules", prompt="write it")
    (call,) = engine._client.calls  # type: ignore[attr-defined]
    assert call["model"] == "claude-opus-5"
    assert call["system"] == "rules"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "xhigh"}
    assert call["messages"] == [{"role": "user", "content": "write it"}]


def test_the_completion_reports_the_model_that_answered_not_the_one_asked_for() -> None:
    # A provider that routed elsewhere must not be recorded as the model that was
    # requested: the manifest states what produced the document (spec 05 §4.2).
    engine = provider(StubResponse(model="claude-opus-4-8"), model="claude-opus-5")
    assert engine.complete(system="s", prompt="p").model == "claude-opus-4-8"


def test_the_parameters_recorded_are_the_ones_that_shaped_the_output() -> None:
    engine = provider(StubResponse(), effort="low", max_tokens=4096)
    parameters = engine.complete(system="s", prompt="p").parameters
    assert parameters == {"max_tokens": 4096, "thinking": "adaptive", "effort": "low"}


# ---------------------------------------------------------------------------
# The four ways it comes back wrong
# ---------------------------------------------------------------------------


def test_a_safety_decline_is_a_provider_error_naming_its_category() -> None:
    # HTTP 200 with no usable text. Reading `content` without checking would hand
    # the citation validator an empty document and report a grounding failure for
    # something that never was one.
    engine = provider(StubResponse(text="", stop_reason="refusal", category="cyber"))
    with pytest.raises(ProviderError, match="declined"):
        engine.complete(system="s", prompt="p")


def test_a_truncated_answer_says_it_was_truncated_and_not_ungrounded() -> None:
    engine = provider(StubResponse(text="half a document", stop_reason="max_tokens"))
    with pytest.raises(ProviderError, match="ceiling"):
        engine.complete(system="s", prompt="p")


def test_an_empty_answer_is_reported_with_its_stop_reason() -> None:
    engine = provider(StubResponse(text="", stop_reason="end_turn"))
    with pytest.raises(ProviderError, match="no text"):
        engine.complete(system="s", prompt="p")


@pytest.mark.parametrize("code", [400, 401, 429, 500])
def test_an_api_status_error_carries_its_code(code: int) -> None:
    engine = provider(status_error(code))
    with pytest.raises(ProviderError, match=str(code)):
        engine.complete(system="s", prompt="p")


def test_a_connection_failure_says_the_api_could_not_be_reached() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    engine = provider(anthropic.APIConnectionError(request=request))
    with pytest.raises(ProviderError, match="could not be reached"):
        engine.complete(system="s", prompt="p")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_a_missing_sdk_names_the_extra_that_installs_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(ProviderUnavailableError, match=r"mycelium-os\[synthesis\]"):
        adapter.build(model="claude-opus-5", max_tokens=16000, effort="high", timeout_s=60.0)


def test_the_credential_hint_reads_the_environment_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(adapter.API_KEY_ENV, raising=False)
    assert adapter.has_credential() is False
    monkeypatch.setenv(adapter.API_KEY_ENV, "sk-ant-not-a-real-key")
    assert adapter.has_credential() is True


# ---------------------------------------------------------------------------
# The one thing a stub cannot prove
# ---------------------------------------------------------------------------


@pytest.mark.llm
@pytest.mark.skipif(
    not os.environ.get(adapter.API_KEY_ENV),
    reason=f"no {adapter.API_KEY_ENV}; the live provider test costs money and is opt-in",
)
def test_a_real_request_returns_a_grounded_document() -> None:
    """The request shape is valid against the real API, and the contract holds.

    Everything else in this suite proves the lane behaves correctly given a
    provider; this proves the provider is real. It is not asserted on content —
    a model's prose is not a fixture — only that the citation contract, run
    against a live answer, passes.
    """
    from pathlib import PurePosixPath

    from mycelium.markdown.adapter import parse_markdown
    from mycelium.sdk.protocols import EvidenceDocument, SynthesisContext
    from mycelium.synthesis.wiki import WikiSynthesizer

    text = "# Retry Policy\n\nWebhook deliveries are retried five times.\n"
    parsed = parse_markdown(text)
    evidence = EvidenceDocument(
        path=PurePosixPath("knowledge/evidence/retry-policy.md"),
        title="Retry Policy",
        kir=parsed.kir,
        headings=("Retry Policy",),
        source_uri="file:///retry.pdf",
    )
    engine = adapter.build(
        model=adapter.DEFAULT_MODEL, max_tokens=4096, effort="low", timeout_s=180.0
    )
    draft = WikiSynthesizer(engine).draft(
        SynthesisContext(topic="Retry Policy", evidence=(evidence,))
    )
    assert draft.report.coverage == 1.0
    assert draft.report.citations
