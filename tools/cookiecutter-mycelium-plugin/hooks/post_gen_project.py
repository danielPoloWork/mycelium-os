#!/usr/bin/env python3
"""Keep the one plugin-kind implementation the operator chose; drop the other two.

Three complete, independently valid implementations ship in the template — one
per `plugin_kind` — so every one of them is a real, syntactically checked Python
file in this repository's own tree rather than a bare Jinja conditional block
that would stop being valid Python between renders. This hook is cookiecutter's
documented way to choose among variants: rename the chosen file into place,
remove the other two, so a freshly generated plugin has exactly one
`plugin.py` and one `test_plugin.py`, and neither reader is shown a choice that
was already made for them.
"""

import os

PLUGIN_KIND = "{{ cookiecutter.plugin_kind }}"
PACKAGE_NAME = "{{ cookiecutter.package_name }}"

KINDS = ("parser", "connector", "module")


def main() -> None:
    src_dir = os.path.join("src", PACKAGE_NAME)
    for kind in KINDS:
        if kind == PLUGIN_KIND:
            os.rename(os.path.join(src_dir, f"_{kind}.py"), os.path.join(src_dir, "plugin.py"))
            os.rename(
                os.path.join("tests", f"_test_{kind}.py"),
                os.path.join("tests", "test_plugin.py"),
            )
        else:
            os.remove(os.path.join(src_dir, f"_{kind}.py"))
            os.remove(os.path.join("tests", f"_test_{kind}.py"))


if __name__ == "__main__":
    main()
