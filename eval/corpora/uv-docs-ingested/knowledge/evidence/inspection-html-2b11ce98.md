---
title: Inspecting environments
origin: ingested
source: "file:sources/pip/inspection.html"
source_digest: "sha256:2b11ce98260cba2b48527460e1be39fa57e10a1dcc66a138df5e01c5374d26cf"
---

# Inspecting environments

## Listing installed packages

To list all the packages in the environment:

```
$ uv pip list
```

To list the packages in a JSON format:

```
$ uv pip list --format json
```

To list all the packages in the environment in a requirements.txt format:

```
$ uv pip freeze
```

## Inspecting a package

To show information about an installed package, e.g., numpy:

```
$ uv pip show numpy
```

Multiple packages can be inspected at once.

## Verifying an environment

It is possible to install packages with conflicting requirements into an environment if installed in multiple steps.

To check for conflicts or missing dependencies in the environment:

```
$ uv pip check
```
