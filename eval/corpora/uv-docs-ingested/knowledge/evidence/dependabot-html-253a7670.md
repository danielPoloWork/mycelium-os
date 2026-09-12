---
title: Dependabot
origin: ingested
source: "file:sources/guides/integration/dependabot.html"
source_digest: "sha256:253a76703736d9df0e115e2001968e5136874c65c7982cb1acc492636c5c1abf"
---

# Dependabot

It is considered best practice to regularly update dependencies, to avoid being exposed to vulnerabilities, limit incompatibilities between dependencies, and avoid complex upgrades when upgrading from a too old version.

Dependabot has announced support for uv, but there are some use cases that are not yet working. See [astral-sh/uv#2512](https://github.com/astral-sh/uv/issues/2512) for updates.

Dependabot supports updating `uv.lock` files. To enable it, add the uv `package-ecosystem` to your `updates` list in the `dependabot.yml`:

```YAML
version : 2

updates :
- package-ecosystem : "uv"
directory : "/"
schedule :
interval : "weekly"
```

## Dependency cooldown

If you use [exclude-newer](../../reference/settings.md#exclude-newer) option, it is recommended to also set the equivalent [cooldown](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#cooldown-) option in Dependabot, to avoid ending up with pull requests where uv would not be able to lock the dependencies.

For instance, if you've set `exclude-newer` to `1 week`, you can set:

```YAML
version : 2

updates :
- package-ecosystem : "uv"
directory : "/"
schedule :
interval : "weekly"
cooldown :
default-days : 7
```
