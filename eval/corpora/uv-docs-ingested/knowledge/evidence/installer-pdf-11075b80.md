---
title: installer.pdf
origin: ingested
source: "file:sources/reference/installer.pdf"
source_digest: "sha256:11075b809fd160a86e7d94f08c8e3dbd81fb5420eb7176b281e62519afb1c8b4"
---

The uv installer
Changing the installation path
By default, uv is installed in the user executable directory.
To change the installation path, use UV\_INSTALL\_DIR:
=== "macOS and Linux"
\`\`\`console
$ curl -LsSf https://astral.sh/uv/install.sh | env UV\_INSTALL\_DIR="/custom/path" sh
\`\`\`
=== "Windows"
\`\`\`pwsh-session
PS> powershell -ExecutionPolicy ByPass -c {$env:UV\_INSTALL\_DIR = "C:\\Custom\\Path";irm
https://astral.sh/uv/install.ps1 | iex}
\`\`\`
!!! note
Changing the installation path only affects where the uv binary is installed. uv will
still store
its data (cache, Python installations, tools, etc.) in the default locations. See the
\[storage reference\](./storage.md) for details on these locations and how to customize
them.
Disabling shell modifications
The installer may also update your shell profiles to ensure the uv binary is on your PATH. To disable
this behavior, use UV\_NO\_MODIFY\_PATH. For example:
$ curl -LsSf https://astral.sh/uv/install.sh | env UV\_NO\_MODIFY\_PATH=1 sh
If installed with UV\_NO\_MODIFY\_PATH, subsequent operations, like uv self update, will not modify
your shell profiles.
Unmanaged installations
In ephemeral environments like CI, use UV\_UNMANAGED\_INSTALL to install uv to a specific path while
preventing the installer from modifying shell profiles or environment variables:
$ curl -LsSf https://astral.sh/uv/install.sh | env UV\_UNMANAGED\_INSTALL="/custom/
path" sh
The use of UV\_UNMANAGED\_INSTALL will also disable self-updates (via uv self update).
Passing options to the installation script
Using environment variables is recommended because they are consistent across platforms.
However, options can be passed directly to the installation script. For example, to see the available
options:
$ curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --help
