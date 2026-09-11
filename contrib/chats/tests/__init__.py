# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Package marker. It exists to keep two files named `conftest.py` apart.

pytest's default import mode prepends a test file's directory to `sys.path` and
imports the file under its bare basename — so with this suite added to
`testpaths`, *two* directories held a `conftest.py` and the second one to be
imported claimed the module name `conftest` for the whole session.

That is not hypothetical: `tests/test_hypothesis_profile.py` does `import
conftest` to assert the property-test profile the core suite declares (ADR-0060),
and it started reading **this** suite's conftest instead — three failures whose
message was `module 'conftest' has no attribute 'DEADLINE_MS'`.

This marker makes the directory a package, so pytest imports its conftest under a
package-qualified name and the bare `conftest` stays the core suite's. One file,
no change to the core, and the collision cannot come back for any other basename
this suite adds either.
"""
