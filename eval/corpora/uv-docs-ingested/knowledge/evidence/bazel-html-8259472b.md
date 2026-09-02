---
title: Using uv with Bazel
origin: ingested
source: "file:sources/guides/integration/bazel.html"
source_digest: "sha256:8259472bdfe2839e69b3d784a7f3cc193d31f7462e2520359b1a3a5f2a62f8df"
---

# Using uv with Bazel

For broader Bazel workflows with uv, see the rules_py uv guide or the rules_python uv guide.

## Authentication

Bazel 7 and newer supports credential helpers via the --credential_helper option. To use credentials stored by uv for Bazel fetches, first authenticate uv with the service that hosts the files Bazel needs to fetch:

```
$ uv auth login https://packages.example.com
```

Then, configure Bazel to invoke uv auth helper for matching hosts:

```
text title=".bazelrc" common --credential_helper=packages.example.com=%workspace%/bazel/uv-auth-helper common --credential_helper=files.example.com=%workspace%/bazel/uv-auth-helper
```

Replace the host patterns with the hosts that serve the index and files Bazel will fetch.

Finally, add the wrapper script referenced by.bazelrc:

```
bash title="bazel/uv-auth-helper" #!/usr/bin/env bash exec uv --preview-features auth-helper auth helper --protocol=bazel "$@"
```

The script must be executable:

```
$ chmod +x bazel/uv-auth-helper
```
