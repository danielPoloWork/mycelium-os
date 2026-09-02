---
title: Third-party services
origin: ingested
source: "file:sources/concepts/authentication/third-party.html"
source_digest: "sha256:ae4ff1a344b6cef9892ccad43920a2cdcdfbe354fbec6de424470d77782f6186"
---

# Third-party services

## Authentication with alternative package indexes

See the dedicated guides for authentication with popular alternative Python package indexes:

- Azure Artifacts
- Google Artifact Registry
- AWS CodeArtifact
- JFrog Artifactory

## Hugging Face support

uv supports automatic authentication for the Hugging Face Hub. Specifically, if the HF_TOKEN environment variable is set, uv will propagate it to requests to huggingface.co.

This is particularly useful for accessing private scripts in Hugging Face Datasets. For example, you can run the following command to execute the script main.py script from a private dataset:

```
$ HF_TOKEN=hf_... uv run https://huggingface.co/datasets/<user>/<name>/resolve/<branch>/main.py
```

You can disable automatic Hugging Face authentication by setting the UV_NO_HF_TOKEN=1 environment variable.
