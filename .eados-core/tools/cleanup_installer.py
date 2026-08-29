#!/usr/bin/env python3
"""Remove the guided-installer leftovers from a repo root (M9 follow-up).

The guided installer ships its scripts as standalone release assets; the consumer downloads one or
more (`setup.sh` / `setup.ps1` / `setup.bat` / `setup.command`) into their repo to run it. Once EADOS
is in place (`.eados-core/`), those scripts are just the downloader and can go. `/eados init` calls
this to tidy them — at the moment a user transitions from *installing* to *using*.

It removes **only** the known installer artifacts, never anything else:

  * `setup.sh` / `setup.ps1` / `setup.bat` / `setup.command` — loose files at the repo root;
  * a `setup/` directory — **only** when it contains nothing but those known installer files (so a
    user's own `setup/` with other content is never touched).

Symlinks are ignored (never followed or removed). The pure core (`installer_leftovers`) stats the
filesystem and mutates nothing — it is unit-tested; removal is a thin, guarded shell. Dry-run by
default; `--apply` removes.

    python .eados-core/tools/cleanup_installer.py [ROOT] [--apply]
"""

import os
import shutil
import sys

# The exact artifacts the guided installer can leave at a repo root — the only things ever removed.
INSTALLER_FILES = ("setup.sh", "setup.ps1", "setup.bat", "setup.command")
INSTALLER_DIR = "setup"


def installer_leftovers(root):
    """Return the root-relative names of guided-installer leftovers present under `root` (files end
    plain, the dir ends with `/`). Pure: it stats the filesystem and mutates nothing. A loose
    installer file counts; the `setup/` dir counts only when it holds nothing beyond the known
    installer files — so a user's own `setup/` is never reported."""
    found = []
    for name in INSTALLER_FILES:
        path = os.path.join(root, name)
        if os.path.isfile(path) and not os.path.islink(path):
            found.append(name)
    setup_dir = os.path.join(root, INSTALLER_DIR)
    if os.path.isdir(setup_dir) and not os.path.islink(setup_dir):
        try:
            entries = os.listdir(setup_dir)
        except OSError:
            entries = None
        # Match on TYPE, not just name: a subdir or symlink named like an installer file (e.g. a
        # `setup.bat/` directory) must NOT make the dir look like a pure-installer leftover. An
        # empty setup/ still qualifies (all() over [] is True).
        if entries is not None and all(
                e in INSTALLER_FILES
                and os.path.isfile(os.path.join(setup_dir, e))
                and not os.path.islink(os.path.join(setup_dir, e))
                for e in entries):
            found.append(INSTALLER_DIR + "/")
    return found


def remove_leftovers(root, names):
    """Remove the given leftover `names` (as returned by installer_leftovers) under `root`; return
    the list actually removed. Re-checks each path's type and skips symlinks — it never removes
    anything not on the installer list."""
    removed = []
    for name in names:
        path = os.path.join(root, name.rstrip("/"))
        if name.endswith("/"):
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
                removed.append(name)
        elif os.path.isfile(path) and not os.path.islink(path):
            os.remove(path)
            removed.append(name)
    return removed


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="Remove guided-installer leftovers from a repo root.")
    ap.add_argument("root", nargs="?", default=".", help="repo root to tidy (default: .)")
    ap.add_argument("--apply", action="store_true", help="actually remove (default: dry-run)")
    args = ap.parse_args(argv)

    leftovers = installer_leftovers(args.root)
    if not leftovers:
        print("cleanup-installer: nothing to remove (no setup.* / setup/ leftovers).")
        return 0
    if args.apply:
        removed = remove_leftovers(args.root, leftovers)
        print("cleanup-installer: removed " + ", ".join(removed) if removed
              else "cleanup-installer: nothing to remove.")
    else:
        print("cleanup-installer: would remove " + ", ".join(leftovers) + "  (re-run with --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
