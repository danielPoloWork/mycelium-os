# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Anthropic provider — the v1 synthesis backend (spec 05 §2).

One non-streaming Messages call per document, through the official `anthropic`
SDK. The SDK rather than a hand-rolled POST: it owns the auth resolution order,
the retry policy for 429 and 5xx, and a typed error hierarchy this module maps
onto Mycelium's own — three things that would otherwise be reimplemented here and
get subtly wrong. It costs four packages, behind the optional `synthesis` extra.

Three settings are deliberate rather than default:

- **Adaptive thinking.** Writing a grounded document — reading several evidence
  documents, deciding what is claim-bearing, attaching a citation to each claim —
  is the kind of work thinking is for, and the citation contract is what makes
  the extra tokens measurable rather than a matter of taste.
- **A generous `max_tokens`.** A document truncated mid-sentence fails the
  citation contract in a way that looks like a model error and is not.
- **No streaming.** There is no user watching a synthesis run; the request is
  bounded and the SDK's timeout covers it.

Everything about this module is opt-in. It is imported only when `[synthesis]
provider = "anthropic"` names it, which is the only way a network call can happen
in this project without the operator asking for one (D-013/D-017).
"""

import os
from typing import Any, Final

from pydantic import JsonValue

from mycelium.synthesis.errors import ProviderError, ProviderUnavailableError
from mycelium.synthesis.provider import Completion

__all__ = ["API_KEY_ENV", "DEFAULT_MODEL", "PROVIDER_ID", "AnthropicProvider", "build"]

PROVIDER_ID: Final = "anthropic"

DEFAULT_MODEL: Final = "claude-opus-5"
"""The model asked for when `[synthesis] model_id` says nothing.

Spec 05 §2's sample file shows a Sonnet id; it is an illustration written in
2026-07, not a contract, and the default here is the most capable model in the
family because the failure this lane must avoid — an unsupported claim in
`knowledge/candidate/` — is a reasoning failure. An operator who would rather
trade capability for cost says so in one line."""

DEFAULT_MAX_TOKENS: Final = 16000
DEFAULT_TIMEOUT_S: Final = 300.0

API_KEY_ENV: Final = "ANTHROPIC_API_KEY"


class AnthropicProvider:
    """Sends one Messages request per synthesis run."""

    def __init__(self, *, client: Any, model: str, max_tokens: int, effort: str) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    @property
    def name(self) -> str:
        return PROVIDER_ID

    @property
    def model(self) -> str:
        return self._model

    def complete(self, *, system: str, prompt: str) -> Completion:
        import anthropic

        parameters: dict[str, JsonValue] = {
            "max_tokens": self._max_tokens,
            "thinking": "adaptive",
            "effort": self._effort,
        }
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                thinking={"type": "adaptive"},
                output_config={"effort": self._effort},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIStatusError as error:
            msg = f"{PROVIDER_ID}: the API answered {error.status_code} - {error}"
            raise ProviderError(msg) from error
        except anthropic.APIConnectionError as error:
            msg = f"{PROVIDER_ID}: the API could not be reached - {error}"
            raise ProviderError(msg) from error

        # A safety decline is an HTTP 200 with no usable text; reading `content`
        # without checking would hand the citation validator an empty document
        # and report a grounding failure for something that never was one.
        if getattr(response, "stop_reason", None) == "refusal":
            detail = getattr(getattr(response, "stop_details", None), "category", None)
            msg = f"{PROVIDER_ID}: the model declined this request ({detail or 'no category'})"
            raise ProviderError(msg)

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        if not text.strip():
            reason = getattr(response, "stop_reason", "unknown")
            msg = f"{PROVIDER_ID}: the model returned no text (stop_reason={reason})"
            raise ProviderError(msg)
        if getattr(response, "stop_reason", None) == "max_tokens":
            # Truncated prose fails the citation contract for a reason that has
            # nothing to do with grounding; say which it was.
            msg = (
                f"{PROVIDER_ID}: the answer hit the {self._max_tokens}-token ceiling and is "
                "truncated; raise [synthesis] max_output_tokens or narrow the evidence set"
            )
            raise ProviderError(msg)

        return Completion(
            text=text,
            model=str(getattr(response, "model", self._model)),
            parameters=parameters,
        )


def build(*, model: str, max_tokens: int, effort: str, timeout_s: float) -> AnthropicProvider:
    """Construct the provider, or say precisely what is missing.

    Credentials are the SDK's business, not this module's: it resolves an API
    key, an auth token, or a logged-in profile in that order, and reimplementing
    that resolution here would only get it wrong. What this checks is that *some*
    credential exists, so an operator who configured the lane and forgot the key
    is told so before a document is read rather than after.
    """
    try:
        import anthropic
    except ImportError as error:
        msg = (
            f"the {PROVIDER_ID!r} provider needs the anthropic SDK; install it with "
            f"`pip install 'mycelium-os[synthesis]'`, or set [synthesis] enabled = false "
            f"({error})"
        )
        raise ProviderUnavailableError(msg) from error

    try:
        client = anthropic.Anthropic(timeout=timeout_s)
    except Exception as error:  # noqa: BLE001 - the SDK raises on a missing credential
        msg = (
            f"the {PROVIDER_ID!r} provider has no credential: set ${API_KEY_ENV}, or run "
            f"`ant auth login`, or set [synthesis] enabled = false ({error})"
        )
        raise ProviderUnavailableError(msg) from error
    return AnthropicProvider(client=client, model=model, max_tokens=max_tokens, effort=effort)


def has_credential() -> bool:
    """Whether an API key is in the environment — the cheap half of the check.

    Used by `mycelium doctor` to say "configured but no key" without constructing
    a client. It answers `False` for a machine authenticated through a CLI
    profile, so it is a *hint*, never the gate: construction is the gate.
    """
    return bool(os.environ.get(API_KEY_ENV))
