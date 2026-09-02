---
title: Getting help
origin: ingested
source: "file:sources/getting-started/help.html"
source_digest: "sha256:92a769a54beca9b6f68d158ea64040b58d48b2c300592e7f008c9b59498ce0e1"
---

# Getting help

## Help menus

The --help flag can be used to view the help menu for a command, e.g., for uv:

```
$ uv --help
```

To view the help menu for a specific command, e.g., for uv init:

```
$ uv init --help
```

When using the --help flag, uv displays a condensed help menu. To view a longer help menu for a command, use uv help:

```
$ uv help
```

To view the long help menu for a specific command, e.g., for uv init:

```
$ uv help init
```

When using the long help menu, uv will attempt to use less or more to "page" the output so it is not all displayed at once. To exit the pager, press q.

## Displaying verbose output

The -v flag can be used to display verbose output for a command, e.g., for uv sync:

```
$ uv sync -v
```

The -v flag can be repeated to increase verbosity, e.g.:

```
$ uv sync -vv
```

Often, the verbose output will include additional information about why uv is behaving in a certain way.

## Viewing the version

When seeking help, it's important to determine the version of uv that you're using - sometimes the problem is already solved in a newer version.

To check the installed version:

```
$ uv self version
```

The following are also valid:

```
$ uv --version      # Same output as `uv self version`
$ uv -V             # Will not include the build commit and date
```

!!! note

```
Before uv 0.7.0, `uv version` was used instead of `uv self version`.
```

## Troubleshooting issues

The reference documentation contains a troubleshooting guide for common issues.

## Open an issue on GitHub

The issue tracker on GitHub is a good place to report bugs and request features. Make sure to search for similar issues first, as it is common for someone else to encounter the same problem.

## Chat on Discord

Astral has a Discord server, which is a great place to ask questions, learn more about uv, and engage with other community members.
