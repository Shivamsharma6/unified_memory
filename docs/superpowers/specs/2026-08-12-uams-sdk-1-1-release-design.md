---
type: architecture
status: approved
aliases:
  - UAMS SDK 1.1 Release
tags:
  - "#release"
  - "#pypi"
  - "#uams"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[Python Package Index]]"
timestamps:
  created: 2026-08-12
  updated: 2026-08-12
---

# UAMS SDK 1.1 Release Design

## TL;DR

Release `uams-sdk` 1.1.0 from the current `main` branch and replace its outdated PyPI landing page with an accurate SDK-focused guide.

## Root Cause

The publish workflow is healthy but triggers only when a `v*` Git tag is pushed. The repository advanced after `v1.0.2` without changing `uams_sdk/pyproject.toml` or creating another release tag, so PyPI correctly remained at 1.0.2.

## Release Content

- Set the package version to `1.1.0`.
- Expand the short package description to mention shared agent memory and MCP.
- Rewrite `uams_sdk/README.md` with a valid `pip install uams-sdk` path, server prerequisite, task lifecycle, SDK example, all 14 MCP tools, resource, prompt, compatibility, and project links.
- Keep the public Python API backward compatible.
- Publish by pushing annotated tag `v1.1.0` only after local verification and a successful `main` CI run.

## Safety and Verification

- Assert package version, description, and README content before editing, then invert those assertions after editing.
- Build both wheel and source distribution in a clean temporary directory.
- Run `twine check`, inspect wheel metadata and contents, install the wheel in a clean virtual environment, import `UAMSClient`, and resolve `uams-mcp`.
- Run the repository test suite and dependency checks.
- Commit and push `main`, wait for CI, create and push `v1.1.0`, then wait for both tag workflows.
- Verify PyPI JSON, rendered project page, downloadable files, and clean `pip install uams-sdk==1.1.0`.

## Failure Handling

The tag is not pushed if any pre-release check fails. If a tag workflow fails, inspect the exact job log and correct the root cause with a new version; never overwrite an immutable PyPI release.
