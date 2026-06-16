---
type: procedures
date: '2026-05-26'
updated: '2026-05-26T16:07:04.245476+00:00'
tags:
- '#flutter_sdet'
- '#goal'
- '#testing'
- '#sentri'
- '#quality'
lifecycle: archived
importance: 0.3535533905932738
---
# Distilled Summary
Goal: Achieve production-grade test coverage for Sentri Flutter codebase by 2026-05-26.

Immediate Actions: Generate coverage reports via flutter test/genhtml, identify zero-coverage modules, audit existing tests, and report findings to JARVIS.

Prioritized Coverage Areas:
- Customer profile screen (widget tests for card states and bottom sheets).
- Dashboard repository (unit tests for revenue aggregate/history).
- Card assignment flow (widget tests for assignment screen and deactivation toggle).
- Dashboard devices screen (widget tests for status rendering).

Ongoing Maintenance: Establish pre-commit gates, eliminate flaky tests, and integrate with CI.

Quality Standards: Enforce zero flakiness/sleeps, proper mocking of Firebase/Storage/Platform channels, Arrange/Act/Assert naming conventions, and documented edge cases.

## Raw Logs
# flutter_sdet Primary Goal (set 2026-05-26)

## Summary
flutter_sdet Primary Goal (set 2026-05-26)

**Mission**: Achieve production-grade test coverage across the Sentri Flutter codebase.

**Phase 1 — Coverage Baseline (immediate):**
1. Run `flutter test --coverage` and generate a coverage report via `genhtml`
2. Identify all untested features (zero-coverage modules)
3. Catalog existing tests and their quality
4. Report findings to JARVIS

**Phase 2 — Critical Path Coverage (next):**
1. Customer profile screen — widget tests for card widget states (active/inactive card, active/inactive customer, bottom sheet)
2. Dashboard repository — unit tests for revenue aggregate/history with different date ranges
3. Card assignment flow — widget tests for assignment screen, card deactivation toggle
4. Dashboard devices screen — widget tests for device status rendering

**Phase 3 — Regression Safety Net (ongoing):**
1. Pre-commit gate: ensure new tests accompany every bug fix
2. Flaky test detection and elimination
3. CI integration: tests must pass before PR merge

**Quality bar:**
- Zero flaky tests
- Zero arbitrary delays/sleeps
- Proper mocking of Firebase, Storage, Platform channels
- Descriptive test names with Arrange/Act/Assert
- Every edge case documented in test comments