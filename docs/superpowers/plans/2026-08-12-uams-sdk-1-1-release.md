---
type: procedural
status: approved
aliases:
  - UAMS SDK 1.1 Release Plan
tags:
  - "#release"
  - "#pypi"
entities:
  - "[[Unified Agent Memory System]]"
  - "[[Python Package Index]]"
timestamps:
  created: 2026-08-12
  updated: 2026-08-12
---

# UAMS SDK 1.1 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `uams-sdk` 1.1.0 with accurate package metadata and a complete PyPI description.

**Architecture:** Package metadata remains in `uams_sdk/pyproject.toml`; PyPI long-form content remains in `uams_sdk/README.md`; existing tag workflows build, upload, and create the GitHub release. The release tag is an irreversible final gate after artifact and CI verification.

**Tech Stack:** Python 3.11, setuptools, build, twine, GitHub Actions, PyPI

---

### Task 1: Prove the Stale-Release Condition

**Files:**

- Verify: `uams_sdk/pyproject.toml`
- Verify: `.github/workflows/pypi-publish.yml`

- [ ] Assert the local version is `1.0.2`, PyPI reports `1.0.2`, and the workflow triggers only on `v*` tags.
- [ ] Record that the latest tag is `v1.0.2` while `main` contains later commits.

### Task 2: Update Package Metadata and Description

**Files:**

- Modify: `uams_sdk/pyproject.toml`
- Modify: `uams_sdk/README.md`

- [ ] Run assertions that fail because version `1.1.0`, the public install command, server prerequisite, 14-tool capability set, profile distinction, and current architecture language are absent.
- [ ] Change the package version to `1.1.0` and use a concise shared-memory/MCP summary.
- [ ] Rewrite the package README as the PyPI landing page without claiming that the SDK wheel bundles the UAMS server.
- [ ] Re-run the assertions and require success.

### Task 3: Build and Inspect Release Artifacts

**Files:**

- Verify: `uams_sdk/pyproject.toml`
- Verify: `uams_sdk/README.md`

- [ ] Build wheel and sdist outside the repository using `python -m build`.
- [ ] Run `twine check --strict` on both files.
- [ ] Inspect wheel `METADATA` for version, summary, dependencies, project URLs, and rendered Markdown content.
- [ ] Install the wheel into a clean virtual environment and verify `UAMSClient` imports and the `uams-mcp` console entry point exists.

### Task 4: Verify and Commit

**Files:**

- Modify: `uams_sdk/pyproject.toml`
- Modify: `uams_sdk/README.md`
- Create: `docs/superpowers/specs/2026-08-12-uams-sdk-1-1-release-design.md`
- Create: `docs/superpowers/plans/2026-08-12-uams-sdk-1-1-release.md`

- [ ] Run SDK tests, full repository tests, compile checks, `pip check`, and `git diff --check`.
- [ ] Commit only the four release-owned files and push `main`.
- [ ] Wait for the resulting `main` CI workflow and require success.

### Task 5: Tag, Publish, and Verify Externally

**Files:**

- Create Git tag: `v1.1.0`

- [ ] Create annotated tag `v1.1.0` at the verified `main` commit and push it.
- [ ] Wait for `Publish SDK to PyPI` and `Create Release` workflows and require both to succeed.
- [ ] Verify `https://pypi.org/pypi/uams-sdk/json` reports `1.1.0` and contains wheel/sdist files.
- [ ] Verify the public project page renders the new title, install command, lifecycle, and capability description.
- [ ] Install `uams-sdk==1.1.0` from PyPI into a clean environment and import the client.
