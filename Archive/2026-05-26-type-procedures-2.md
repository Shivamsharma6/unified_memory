---
type: procedures
date: '2026-05-26'
updated: '2026-05-26T10:39:32.919684+00:00'
tags:
- '#sentri'
- '#flutter'
- '#commit'
- '#analyze'
- '#quality-gate'
lifecycle: archived
importance: 0.3535533905932738
---
# Distilled Summary
# Pre-Commit Gate for Sentri Flutter

## Summary
Pre-Commit Gate for Sentri Flutter

ABSOLUTE RULE — no exceptions:
Before EVERY git commit on any Sentri branch, run `flutter analyze`. ... [Distilled] ... This is a hard gate — no workaround, no bypass, no "I'll fix it later".

## Raw Logs
# Pre-Commit Gate for Sentri Flutter

## Summary
Pre-Commit Gate for Sentri Flutter

ABSOLUTE RULE — no exceptions:
Before EVERY git commit on any Sentri branch, run `flutter analyze`.
The analysis MUST produce "No issues found!" — zero errors, zero warnings, zero info-level lints.
If any issue exists, fix it before committing. Do not commit with pending issues.

This covers: lib/, test/, scratch/, and every other directory in the project.
This is a hard gate — no workaround, no bypass, no "I'll fix it later".