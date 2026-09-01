# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""LLM providers: the one place in this project that can make a network call.

One ships in v1 — :mod:`~mycelium.synthesis.providers.anthropic` — and it is
imported only when `[synthesis] provider` names it. That is the whole of the
"zero network calls unless configured" guarantee (D-013/D-017) as code: not a
runtime check that could be bypassed, but a module nothing imports until an
operator has written a provider id into a file.
"""
