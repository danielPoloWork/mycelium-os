#!/usr/bin/env python3
"""Behavioral smoke for setup.sh + setup.command — the guided EADOS installer (POSIX).

setup.sh is one combined script: scriptable via flags AND interactive when run bare (or
--interactive); setup.command is the macOS double-click shim. Driven through a POSIX shell (`sh`,
falling back to `bash`), this asserts: plan resolution (`--print-plan`), argument validation,
fail-closed checksum verification (incl. a local `--sums-file`, the format release.yml publishes),
additive no-clobber extraction, and the interactive flow (new = extract + git-init, existing =
extract-only) — all offline via the `--from` seam, so CI never touches the network.

    python .eados-core/tools/tests/test_setup_sh.py
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(TOOLS))
INSTALL_DIR = os.path.join(REPO_ROOT, "setup")
SETUP_SH = os.path.join(INSTALL_DIR, "setup.sh")
COMMAND = os.path.join(INSTALL_DIR, "setup.command")

SHELL = shutil.which("sh") or shutil.which("bash")
HAVE_GIT = shutil.which("git") is not None


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(script, *args, cwd=None, stdin=""):
    """Run a script via the POSIX shell with `stdin` fed to its prompts; return (rc, out, err).
    Filesystem cases pass cwd + RELATIVE paths so they work on POSIX and Git Bash alike (a drive
    path like C:/x trips GNU tar)."""
    proc = subprocess.run([SHELL, script.replace("\\", "/"), *args],
                          capture_output=True, text=True, cwd=cwd, input=stdin)
    return proc.returncode, proc.stdout, proc.stderr


def make_bundle(path):
    """Write a tiny prefix-less .tar.gz fixture (agent contract + a factory file + a Claude Code
    command adapter, mirroring the real bundle's layout since #239); return sha256 hex."""
    with tarfile.open(path, "w:gz") as tar:
        for name, body in (("AGENTS.md", b"# agent contract\n"),
                           (".eados-core/tools/render.py", b"# render\n"),
                           (".claude/commands/eados/init.md", b"# adapter fixture\n")):
            entry = tarfile.TarInfo(name)
            entry.size = len(body)
            tar.addfile(entry, io.BytesIO(body))
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def make_symlink_bundle(path):
    """A malicious bundle: a symlink whose target escapes the target root, then a file written
    through it. The entry NAMES are innocuous (no '..' / leading '/'), so only a link-type check
    catches it. Return sha256 hex. (issue #129 — tar-slip)"""
    with tarfile.open(path, "w:gz") as tar:
        link = tarfile.TarInfo("pwn")
        link.type = tarfile.SYMTYPE
        link.linkname = "../escaped"
        tar.addfile(link)
        body = b"owned\n"
        through = tarfile.TarInfo("pwn/escaped.txt")
        through.size = len(body)
        tar.addfile(through, io.BytesIO(body))
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    failures = []

    if SHELL is None:
        print("test-setup-sh: SKIP — no POSIX shell (sh / bash) on PATH")
        return 0
    for needed in (SETUP_SH, COMMAND):
        if not os.path.exists(needed):
            print(f"test-setup-sh: FAIL — not found: {needed}")
            return 1

    # --help, and the .command shim delegating to setup.sh
    rc, out, _ = run(SETUP_SH, "--help")
    check("--help exits 0", rc == 0, failures)
    check("--help shows usage + key flags",
          "USAGE" in out and "--mode" in out and "--print-plan" in out and "--interactive" in out,
          failures)
    rc, out, _ = run(COMMAND, "--help")
    check("setup.command --help delegates to setup.sh", rc == 0 and "USAGE" in out, failures)

    # plan resolution (pure: no network / disk)
    rc, out, _ = run(SETUP_SH, "--print-plan")
    check("--print-plan exits 0", rc == 0, failures)
    check("plan (default) uses the latest-download URL",
          "releases/latest/download/pgs-eados-bundle.tar.gz" in out, failures)
    check("plan (default) is mode existing", "existing" in out, failures)
    check("plan (default) repo is danielPoloWork/pgs-eados", "danielPoloWork/pgs-eados" in out,
          failures)

    rc, out, _ = run(SETUP_SH, "--print-plan", "--ref", "v2.2.0")
    check("plan --ref uses the tagged download URL",
          "releases/download/v2.2.0/pgs-eados-bundle.tar.gz" in out, failures)

    rc, out, _ = run(SETUP_SH, "--print-plan", "--mode", "new", "--path", "/tmp/x", "--repo-name", "proj")
    check("plan --mode new resolves target <path>/<name>", "/tmp/x/proj" in out, failures)
    check("plan --mode new notes a git init", "git init" in out, failures)

    rc, out, _ = run(SETUP_SH, "--print-plan", "--repo", "octo/fork")
    check("plan --repo override flows into the URL", "github.com/octo/fork/" in out, failures)

    # validation (flags given -> non-interactive)
    rc, out, err = run(SETUP_SH, "--mode", "new", "--non-interactive")
    check("--mode new without --repo-name fails", rc != 0, failures)
    check("…with a message naming repo-name", "repo-name" in (err + out), failures)
    rc, _, _ = run(SETUP_SH, "--mode", "sideways", "--print-plan")
    check("an invalid --mode fails", rc != 0, failures)

    with tempfile.TemporaryDirectory() as tmp:
        good_sha = make_bundle(os.path.join(tmp, "bundle.tar.gz"))  # relative under cwd=tmp
        seq = [0]

        def fresh_target():
            seq[0] += 1
            name = f"t{seq[0]}"
            os.mkdir(os.path.join(tmp, name))
            return name

        # --- engine (flags => non-interactive) ---
        tgt = fresh_target()
        rc, _, _ = run(SETUP_SH, "--from", "bundle.tar.gz", "--sha256", good_sha,
                       "--mode", "existing", "--path", tgt, cwd=tmp)
        check("additive install into an empty target succeeds", rc == 0, failures)
        check("…extracted the agent contract",
              os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)
        check("…extracted the factory file",
              os.path.exists(os.path.join(tmp, tgt, ".eados-core", "tools", "render.py")), failures)

        tgt = fresh_target()
        with open(os.path.join(tmp, tgt, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("ORIGINAL")
        rc, out, err = run(SETUP_SH, "--from", "bundle.tar.gz", "--no-verify",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("install refuses to overwrite an existing file", rc != 0, failures)
        check("…names the conflicting file", "AGENTS.md" in (err + out), failures)
        with open(os.path.join(tmp, tgt, "AGENTS.md"), encoding="utf-8") as fh:
            kept = fh.read() == "ORIGINAL"
        check("…leaves the existing file untouched", kept, failures)
        check("…and extracts nothing (no partial write)",
              not os.path.exists(os.path.join(tmp, tgt, ".eados-core", "tools", "render.py")), failures)

        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", "bundle.tar.gz", "--sha256", "deadbeef",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("a wrong --sha256 fails (checksum mismatch)",
              rc != 0 and "mismatch" in (out + err).lower(), failures)

        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", "bundle.tar.gz", "--mode", "existing",
                           "--path", tgt, cwd=tmp)
        check("fail-closed: refuses to extract unverified", rc != 0, failures)
        check("…extracts nothing when unverified",
              not os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)

        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", "nope.tar.gz", "--no-verify",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("a missing --from bundle fails cleanly",
              rc != 0 and "not found" in (out + err).lower(), failures)

        rc, _, _ = run(SETUP_SH, "--from", "bundle.tar.gz", "--no-verify",
                       "--mode", "existing", "--path", "absent-dir", cwd=tmp)
        check("existing mode requires the target dir to exist", rc != 0, failures)

        # --- tar-slip: reject a bundle carrying a symlink/hardlink entry (issue #129) ---
        evil_sha = make_symlink_bundle(os.path.join(tmp, "evil.tar.gz"))
        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", "evil.tar.gz", "--sha256", evil_sha,
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("rejects a symlink-bearing bundle even when its checksum matches (tar-slip)",
              rc != 0 and "symlink" in (out + err).lower(), failures)
        check("…and extracts nothing through the symlink",
              not os.path.exists(os.path.join(tmp, tgt, "pwn")), failures)
        tgt = fresh_target()
        rc, _, _ = run(SETUP_SH, "--from", "evil.tar.gz", "--no-verify",
                       "--mode", "existing", "--path", tgt, cwd=tmp)
        check("the symlink guard runs even under --no-verify", rc != 0, failures)

        # --- verify against a local SHA256SUMS (the format release.yml publishes) ---
        real = "pgs-eados-bundle.tar.gz"
        real_sha = make_bundle(os.path.join(tmp, real))
        with open(os.path.join(tmp, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{real_sha}  {real}\n")
            fh.write(f"{'0' * 64} *pgs-eados-bundle.zip\n")   # '*' (binary) form must be stripped
            fh.write(f"{'1' * 64}  setup.sh\n")
        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", real, "--sums-file", "SHA256SUMS",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("verify via --sums-file succeeds (picks the bundle line)",
              rc == 0 and os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)

        with open(os.path.join(tmp, "BAD_SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{'a' * 64}  {real}\n")
        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", real, "--sums-file", "BAD_SUMS",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("a tampered --sums-file fails (mismatch)",
              rc != 0 and "mismatch" in (out + err).lower(), failures)

        tgt = fresh_target()
        rc, out, err = run(SETUP_SH, "--from", real, "--sums-file", "missing-sums",
                           "--mode", "existing", "--path", tgt, cwd=tmp)
        check("a missing --sums-file fails cleanly",
              rc != 0 and "not found" in (out + err).lower(), failures)

        # --- host adapters (#239): scripted default is opt-in; --with-adapters places them;
        #     declined adapters neither block on nor touch a colliding user file ---
        adapter_rel = os.path.join(".claude", "commands", "eados", "init.md")
        tgt = fresh_target()
        rc, _, _ = run(SETUP_SH, "--from", "bundle.tar.gz", "--sha256", good_sha,
                       "--mode", "existing", "--path", tgt, cwd=tmp)
        check("scripted default omits the adapters (opt-in)",
              rc == 0 and not os.path.exists(os.path.join(tmp, tgt, ".claude")), failures)

        tgt = fresh_target()
        rc, _, _ = run(SETUP_SH, "--from", "bundle.tar.gz", "--sha256", good_sha,
                       "--with-adapters", "--mode", "existing", "--path", tgt, cwd=tmp)
        check("--with-adapters places the Claude Code adapters",
              rc == 0 and os.path.exists(os.path.join(tmp, tgt, adapter_rel)), failures)

        tgt = fresh_target()
        os.makedirs(os.path.join(tmp, tgt, ".claude", "commands", "eados"))
        with open(os.path.join(tmp, tgt, adapter_rel), "w", encoding="utf-8") as fh:
            fh.write("USER FILE")
        rc, _, _ = run(SETUP_SH, "--from", "bundle.tar.gz", "--sha256", good_sha,
                       "--mode", "existing", "--path", tgt, cwd=tmp)
        with open(os.path.join(tmp, tgt, adapter_rel), encoding="utf-8") as fh:
            intact = fh.read() == "USER FILE"
        check("declined adapters ignore a colliding user file (install proceeds, file intact)",
              rc == 0 and intact
              and os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)
        rc2, out2, err2 = run(SETUP_SH, "--from", "bundle.tar.gz", "--no-verify",
                              "--with-adapters", "--mode", "existing", "--path", tgt, cwd=tmp)
        check("--with-adapters still refuses to clobber a user adapter file",
              rc2 != 0 and "init.md" in (out2 + err2), failures)

        rc, out, err = run(SETUP_SH, "--with-adapters", "--no-adapters", "--print-plan")
        check("--with-adapters conflicts with --no-adapters", rc != 0, failures)
        rc, out, _ = run(SETUP_SH, "--print-plan")
        check("the plan states the adapters decision", "adapters:" in out, failures)

        # --- interactive (--interactive + offline --from) ---
        # stdin sequences: mode, path(/name), the #239 adapters question, then the confirm
        rc, out, err = run(SETUP_SH, "--interactive", "--no-gh", "--from", "bundle.tar.gz",
                           "--no-verify", cwd=tmp, stdin="1\nsub\nproj\ny\ny\n")
        target = os.path.join(tmp, "sub", "proj")
        check("interactive new install exits 0", rc == 0, failures)
        check("…extracted the bundle into <parent>/<name>",
              os.path.exists(os.path.join(target, "AGENTS.md")), failures)
        check("…and the adapters (answered yes)",
              os.path.exists(os.path.join(target, adapter_rel)), failures)
        if HAVE_GIT:
            check("…and git-inited the new repo", os.path.isdir(os.path.join(target, ".git")),
                  failures)

        os.mkdir(os.path.join(tmp, "ex"))
        rc, out, err = run(SETUP_SH, "--interactive", "--no-gh", "--from", "bundle.tar.gz",
                           "--no-verify", cwd=tmp, stdin="2\nex\nn\ny\n")
        check("interactive existing install exits 0", rc == 0, failures)
        check("…extracted into the existing dir",
              os.path.exists(os.path.join(tmp, "ex", "AGENTS.md")), failures)
        check("…without the adapters (answered no)",
              not os.path.exists(os.path.join(tmp, "ex", ".claude")), failures)
        check("…and did NOT git-init an existing repo",
              not os.path.isdir(os.path.join(tmp, "ex", ".git")), failures)

        rc, out, err = run(SETUP_SH, "--interactive", "--dry-run", cwd=tmp, stdin="2\n.\nn\nn\n")
        check("answering 'n' at the confirm aborts (exit 0)", rc == 0, failures)
        check("…with an 'aborted' message", "abort" in (out + err).lower(), failures)

        rc, out, err = run(SETUP_SH, "--interactive", "--dry-run", cwd=tmp,
                           stdin="1\n.\n\ncoolproj\ny\ny\n")
        check("an empty new-repo name re-prompts, then accepts a name",
              rc == 0 and "coolproj" in (out + err), failures)

    if failures:
        print("test-setup-sh: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-setup-sh: OK — plan resolution, arg validation, fail-closed checksum (incl. "
          "--sums-file), additive no-clobber, and interactive new/existing all hold; offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
