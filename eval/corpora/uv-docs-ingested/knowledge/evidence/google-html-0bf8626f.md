---
title: Google Artifact Registry
origin: ingested
source: "file:sources/guides/integration/google.html"
source_digest: "sha256:0bf8626f3fc0caf746e0a52bbf861adc161fe328126ee9ed205e8998559f81dd"
---

# Google Artifact Registry

uv can install packages from Google Artifact Registry, either by using an access token, or using the keyring package.

!!! note

```
This guide assumes that [`gcloud`](https://cloud.google.com/sdk/gcloud) CLI is installed and
authenticated.
```

To use Google Artifact Registry, add the index to your project:

```
toml title="pyproject.toml" [[tool.uv.index]] name = "private-registry" url = "https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/simple/"
```

## Authenticate with a Google access token

Credentials can be provided via "Basic" HTTP authentication scheme. Include access token in the password field of the URL. Username must be oauth2accesstoken, otherwise authentication will fail.

Generate a token with gcloud:

```Bash
export ARTIFACT_REGISTRY_TOKEN = $(
gcloud auth application-default print-access-token
)
```

!!! note

```
You might need to pass extra parameters to properly generate the token (like `--project`), this
is a basic example.
```

Then set credentials for the index with:

```Bash
export UV_INDEX_PRIVATE_REGISTRY_USERNAME = oauth2accesstoken
export UV_INDEX_PRIVATE_REGISTRY_PASSWORD = " $ARTIFACT_REGISTRY_TOKEN "
```

!!! note

```
`PRIVATE_REGISTRY` should match the name of the index defined in your `pyproject.toml`.
```

## Authenticate with keyring and keyrings.google-artifactregistry-auth

You can also authenticate to Artifact Registry using keyring package with the keyrings.google-artifactregistry-auth plugin. Because these two packages are required to authenticate to Artifact Registry, they must be pre-installed from a source other than Artifact Registry.

The keyrings.google-artifactregistry-auth plugin wraps gcloud CLI to generate short-lived access tokens, securely store them in system keyring, and refresh them when they are expired.

uv only supports using the keyring package in subprocess mode. The keyring executable must be in the PATH, i.e., installed globally or in the active environment. The keyring CLI requires a username in the URL and it must be oauth2accesstoken.

```Bash
# Pre-install keyring and Artifact Registry plugin from the public PyPI
uv tool install keyring --with keyrings.google-artifactregistry-auth

# Enable keyring authentication
export UV_KEYRING_PROVIDER = subprocess

# Set the username for the index
export UV_INDEX_PRIVATE_REGISTRY_USERNAME = oauth2accesstoken
```

!!! note

```
The [`tool.uv.keyring-provider`](../../reference/settings.md#keyring-provider)
setting can be used to enable keyring in your `uv.toml` or `pyproject.toml`.

Similarly, the username for the index can be added directly to the index URL.
```

## Publishing packages

If you also want to publish your own packages to Google Artifact Registry, you can use uv publish as described in the Building and publishing guide.

First, add a publish-url to the index you want to publish packages to. For example:

```
toml title="pyproject.toml" hl_lines="4" [[tool.uv.index]] name = "private-registry" url = "https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/simple/" publish-url = "https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/"
```

Then, configure credentials (if not using keyring):

```
$ export UV_PUBLISH_USERNAME=oauth2accesstoken
$ export UV_PUBLISH_PASSWORD="$ARTIFACT_REGISTRY_TOKEN"
```

And publish the package:

```
$ uv publish --index private-registry
```

To use uv publish without adding the publish-url to the project, you can set UV_PUBLISH_URL:

```
$ export UV_PUBLISH_URL=https://<REGION>-python.pkg.dev/<PROJECT>/<REPOSITORY>/
$ uv publish
```

Note this method is not preferable because uv cannot check if the package is already published before uploading artifacts.
