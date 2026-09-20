---
title: python.pdf
origin: ingested
source: "file:sources/reference/policies/python.pdf"
source_digest: "sha256:f638b3a7a5d025d11c3077e93d33c9dcd22aa529a22caa17eb0e8e9a268810ae"
---

Python support
Python versions
uv has Tier 1 support for the following Python versions:
• 3.10
• 3.11
• 3.12
• 3.13
• 3.14
As with platforms, Tier 1 support can be thought of "guaranteed to work". uv is continuously tested
against these versions.
uv has Tier 2 support for:
• 3.6
• 3.7
• 3.8
• 3.9
uv is "expected to work" with these versions. uv is tested against these versions, but they have
reached their end-of-life and no longer receive security fixes. We do not recommend using these
versions.
uv also has Tier 2 support for pre-releases of Python 3.15.
uv does not work with Python versions prior to 3.6.
Python implementations
uv has Tier 1 support for the following Python implementations:
• CPython
As with platforms, Tier 1 support can be thought of "guaranteed to work". uv supports managed
installations of these implementations, and the builds are maintained by Astral.
uv has Tier 2 support for:
• PyPy
• GraalPy
• Pyodide
uv is "expected to work" with these implementations. uv also supports managed installations of
these Python implementations, but the builds are not maintained by Astral.
uv has Tier 3 support for:
• Pyston
uv "should work" with these implementations, but stability may vary.
