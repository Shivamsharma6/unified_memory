# UAMS v1.0.0 Public Release Design

## Overview
This document specifies the strategy for preparing, tagging, and launching the `v1.0.0` public release of the Unified Agent Memory System (UAMS) repository on GitHub.

## 1. Pre-Release Documentation Polish
The repository recently gained cross-platform capability and cloud LLM configurability. Before tagging the release, the `README.md` must be updated to reflect these capabilities so new users can onboard easily.

**Required README Additions:**
- **Windows Deployment:** Explicitly document the usage of `install.bat` and `uams.bat` alongside the `Makefile` instructions.
- **Cloud LLM Integration:** Provide a snippet showcasing how to use `UAMS_LLM_PROVIDER=openai`, `UAMS_EMBED_PROVIDER=openai`, and API keys in `.env` to bypass local Ollama hardware requirements.

## 2. CI/CD Release Automation
To ensure seamless future versions (e.g., v1.1.0, v2.0.0), a GitHub Actions workflow will handle the release generation.

**File:** `.github/workflows/release.yml`

**Workflow Behavior:**
- **Trigger:** Executes strictly when a git tag matching `v*` is pushed to the remote.
- **Job:** Uses `softprops/action-gh-release@v1` (or equivalent) to draft a GitHub Release.
- **Features:** 
  - Automatically generates release notes (changelog) from commit history.
  - Attaches source code zip/tarballs automatically.
- **Permissions:** Requires `contents: write` to allow the GitHub Actions bot to publish the release.

## 3. Release Execution Sequence
1. Commit the `README.md` updates and the newly created `.github/workflows/release.yml` to the `main` branch.
2. Ensure all other outstanding changes (e.g., Windows `.bat` scripts) are staged, committed, and pushed.
3. Locally create the tag: `git tag v1.0.0`.
4. Push the tag to origin: `git push origin v1.0.0`.
5. Monitor the Actions tab to verify the workflow succeeds and the release is live on the repository's Releases page.

## Post-Release Verification
Check the GitHub Releases page to confirm:
- The `v1.0.0` release exists.
- The auto-generated changelog accurately reflects the merged history.
- The source code downloads are accessible.
