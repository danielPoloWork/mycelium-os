# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Connectors: acquisition with custody (spec 02 §5).

One ships in v1 — :mod:`~mycelium.ingest.connectors.file`, the local tree — and
it is where the security posture's path rules live: declared roots, resolution
before the check so no symlink escapes, and a byte ceiling on an untrusted read
(spec 02 §8, D-017). Remote schemes are a later item and a separate trust
conversation.
"""
