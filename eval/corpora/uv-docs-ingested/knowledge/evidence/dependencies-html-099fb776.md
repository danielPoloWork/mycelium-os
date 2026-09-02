---
title: Declaring dependencies
origin: ingested
source: "file:sources/pip/dependencies.html"
source_digest: "sha256:099fb77622554b67e5532ac5e23f111d8b29d14bedad46fb67c8f518de741ad6"
---

# Declaring dependencies

It is best practice to declare dependencies in a static file instead of modifying environments with ad-hoc installations. Once dependencies are defined, they can be locked to create a consistent, reproducible environment.

## Using pyproject.toml

The pyproject.toml file is the Python standard for defining configuration for a project.

To define project dependencies in a pyproject.toml file:

```
toml title="pyproject.toml" [project] dependencies = [ "httpx", "ruff>=0.3.0" ]
```

To define optional dependencies in a pyproject.toml file:

```
toml title="pyproject.toml" [project.optional-dependencies] cli = [ "rich", "click", ]
```

Each of the keys defines an "extra", which can be installed using the --extra and --all-extras flags or package[<extra>] syntax. See the documentation on installing packages for more details.

See the official pyproject.toml guide for more details on getting started with a pyproject.toml.

## Using requirements.in

It is also common to use a lightweight requirements file format to declare the dependencies for the project. Each requirement is defined on its own line. Commonly, this file is called requirements.in to distinguish it from requirements.txt which is used for the locked dependencies.

To define dependencies in a requirements.in file:

```
requirements title="requirements.in" httpx ruff>=0.3.0
```

Optional dependencies groups are not supported in this format.
