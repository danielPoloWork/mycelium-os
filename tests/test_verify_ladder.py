# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The verification ladder means the same thing locally and in CI (roadmap 4.35).

`ci.yml` says of the mode: *"one implementation, two callers"*, and that is true —
both ask `tools/verify.py` which mode a diff is. It was never true of the **plan**.
What a mode *runs* was written twice: once as `verify.py`'s `plan()`, once as job
conditions and shell steps in the workflow. They drifted, and the drift was
invisible because nothing compared them: at `retrieval`, CI gated three corpora
and the local tool gated one (ADR-0059).

So this file is the comparison. It reads the workflow, extracts the verification
commands each job would run and the mode each job runs at, and asserts that
everything CI would do at a mode is something the local plan does too. A
contributor who passes `tools/verify.py` cannot then be told something new by CI —
which is the whole promise the local loop makes.

Until roadmap 4.40 the comparison read only `mycelium` invocations, so a gate CI
ran as a **script** was invisible to it — and two were: the ingested corpus's
reproduction check and the carried cases'. That is ADR-0059's defect surviving in
the jobs it did not look at, which is the argument for widening the reading rather
than exempting them.

Record-keeping steps are deliberately excluded: a step ending `|| true` cannot
fail, so it is not a gate and the local loop owes nothing to it.
"""

import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import verify  # noqa: E402

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"

_MODE_EQUALS = re.compile(r"outputs\.mode\s*==\s*'([a-z]+)'")
_MODE_NOT_EQUALS = re.compile(r"outputs\.mode\s*!=\s*'([a-z]+)'")

EXCLUDED_TOOLS = frozenset({"tools/verify.py"})
"""`verify.py` is the thing being compared, not a gate it runs.

CI's `bootstrap` job invokes it to *derive the mode* — the one call that cannot
appear in its own plan without recursion. Every other tool in the workflow is a
gate and must appear."""


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def modes_of(condition: str) -> set[str]:
    """The modes a job's `if:` admits, read from the condition itself."""
    if not condition:
        return set(verify.MODES)
    equals = set(_MODE_EQUALS.findall(condition))
    if equals:
        return equals
    excluded = set(_MODE_NOT_EQUALS.findall(condition))
    return set(verify.MODES) - excluded


def commands_of(job: dict[str, Any]) -> list[str]:
    """Every shell command a job runs that can actually fail the build."""
    found = []
    for step in job.get("steps", []):
        script = step.get("run")
        if not script:
            continue
        for line in script.splitlines():
            command = line.strip()
            if not command or command.endswith("|| true"):
                continue
            found.append(" ".join(command.split()))
    return found


def gate_targets(command: str) -> tuple[str, ...]:
    """The verification a command performs, in a runner-free form.

    CI says `uv run mycelium eval X --gate`; the local plan says
    `<python> -c "…" eval X --gate`. Comparing the two means dropping however the
    interpreter was reached and keeping what was asked of the product.

    Two shapes count. A `mycelium` invocation that builds or gates — and a
    **repository tool**, because a tool CI runs is a gate whatever it is written
    in, and reading only `mycelium` commands is how two of them stayed CI-only
    (roadmap 4.40).

    For a tool, the path and its **flags** are compared and its positional
    arguments are not: `measure_hybrid_gate.py --check` asks a different question
    from the bare form and must not match it, while
    `check_frozen_release_sets.py` legitimately takes the PR's base SHA in CI and
    `origin/main` locally. A flag changes what a tool does; a ref changes what it
    does it to.
    """
    words = command.split()
    for index, word in enumerate(words):
        if word.startswith("tools/") and word.endswith(".py"):
            if word in EXCLUDED_TOOLS:
                return ()
            return (word, *sorted(a for a in words[index + 1 :] if a.startswith("--")))
        if word.endswith("mycelium") or word == "main()":
            rest = words[index + 1 :]
            if rest and rest[0] in {"build", "eval"} and "--gate" in rest or rest[:1] == ["build"]:
                return tuple(rest)
            if rest[:2] == ["eval", "."] and "--tasks" in rest:
                return tuple(rest)
    return ()


def local_targets(mode: str) -> set[tuple[str, ...]]:
    return {
        targets for _, command in verify.plan(mode) if (targets := gate_targets(" ".join(command)))
    }


# ---------------------------------------------------------------------------


def test_the_modes_the_workflow_names_are_the_modes_the_tool_has(workflow: dict[str, Any]) -> None:
    """A job keyed on a mode that does not exist would never run, silently."""
    named = {
        mode
        for job in workflow["jobs"].values()
        for mode in _MODE_EQUALS.findall(str(job.get("if", "")))
        + _MODE_NOT_EQUALS.findall(str(job.get("if", "")))
    }
    assert named
    assert named <= set(verify.MODES), f"ci.yml names a mode verify.py does not have: {named}"


@pytest.mark.parametrize("mode", verify.MODES)
def test_everything_ci_gates_at_a_mode_is_in_the_local_plan(
    workflow: dict[str, Any], mode: str
) -> None:
    """The claim `ci.yml` makes, made checkable.

    Superset rather than equality: CI legitimately runs more *jobs* than the local
    loop — a build matrix on three operating systems, the determinism gate by name
    — and those are the same `pytest` the local plan already runs. What must not
    happen is CI gating something the local loop never touches.
    """
    mine = local_targets(mode)
    for name, job in workflow["jobs"].items():
        if mode not in modes_of(str(job.get("if", ""))):
            continue
        for command in commands_of(job):
            targets = gate_targets(command)
            if not targets:
                continue
            assert targets in mine, (
                f"at mode {mode!r} the CI job {name!r} runs `mycelium "
                f"{' '.join(targets)}` and tools/verify.py does not. The mode is one "
                "implementation with two callers; the plan must not be two with one name."
            )
