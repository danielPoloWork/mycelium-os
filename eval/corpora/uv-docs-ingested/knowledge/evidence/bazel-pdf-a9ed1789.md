---
title: bazel.pdf
origin: ingested
source: "file:sources/guides/integration/bazel.pdf"
source_digest: "sha256:a9ed17892055f0094a67d0214ed66ae0f70e616b0cc69e6d55ac4b1d470ee569"
---

Using uv with Bazel
For broader Bazel workflows with uv, see the rules_py uv guide or the rules_python uv guide.
Authentication
Bazel 7 and newer supports credential helpers via the --credential_helper option. To use
credentials stored by uv for Bazel fetches, first authenticate uv with the service that hosts the files
Bazel needs to fetch:
$ uv auth login https://packages.example.com
Then, configure Bazel to invoke uv auth helper for matching hosts:
common --credential_helper=packages.example.com=%workspace%/bazel/uv-auth-helper
common --credential_helper=files.example.com=%workspace%/bazel/uv-auth-helper
Replace the host patterns with the hosts that serve the index and files Bazel will fetch.
Finally, add the wrapper script referenced by .bazelrc:
#!/usr/bin/env bash
exec uv --preview-features auth-helper auth helper --protocol=bazel "$@"
The script must be executable:
$ chmod +x bazel/uv-auth-helper
