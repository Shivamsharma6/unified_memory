---
type: procedures
date: '2026-05-26'
updated: '2026-05-26T10:46:27.373434+00:00'
tags:
- '#github'
- '#pr'
- '#workflow'
- '#description'
- '#update'
lifecycle: archived
importance: 0.3535533905932738
---
# Distilled Summary
# PR Description Update Rule

## Summary
PR Description Update Rule

Whenever a new commit is pushed to a branch that already has an open PR, the PR description MUST be updated to reflect the new changes. ... [Distilled] ... Use `gh pr edit <NUMBER> --body '...'` to update

Exception: Trivial commits (typo fixes, CI workflow changes, formatting-only) that don't change user-facing behaviour don't need description updates.

## Raw Logs
# PR Description Update Rule

## Summary
PR Description Update Rule

Whenever a new commit is pushed to a branch that already has an open PR, the PR description MUST be updated to reflect the new changes. 

Steps:
1. After `git push` to a PR branch, check if the PR description mentions only the original changes
2. If the new commit adds different functionality or fixes (not just CI fixes or trivial corrections), update the PR body with a new section under "Additional Changes" or merge into the existing sections
3. Use `gh pr edit <NUMBER> --body '...'` to update

Exception: Trivial commits (typo fixes, CI workflow changes, formatting-only) that don't change user-facing behaviour don't need description updates.