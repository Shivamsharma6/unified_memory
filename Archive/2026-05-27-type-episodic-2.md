---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:35:22.645397+00:00'
tags:
- '#cloud-functions'
- '#utilities'
- '#helpers'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — Utility Functions (Lines 32-189)

## Summary
# Cloud Functions — Utility Functions (Lines 32-189)

## `chunkArray(array, size)`
Splits array into chunks of given size. ... [Distilled] ... ## `buildAccessLogDocId(businessPrefix, sequenceNumber)`
Creates document ID: `{prefix}_ACCESS_LOGS_{NNNN}` (4-digit zero-padded).

## Raw Logs
# Cloud Functions — Utility Functions (Lines 32-189)

## Summary
# Cloud Functions — Utility Functions (Lines 32-189)

## `chunkArray(array, size)`
Splits array into chunks of given size. Used for Firestore "in" queries (max 30 items) and batch operations.

## `parseDateField(val)`
Robust date parser handling Firestore `Timestamp`, native `Date`, and string values. Returns `null` on failure.

## `hhmmFromDate(date, tz)`
Formats a Date to `HH:MM` string in given timezone (default IST). Uses `Intl.DateTimeFormat` with fallback.

## `dateOnlyInTz(d, tz)`
Extracts `YYYY-MM-DD` date string in given timezone using `Intl.DateTimeFormat("en-CA")`.

## `isDateWithinRangeInclusive(now, startDate, endDate, tz)`
Checks if `now` falls within `[startDate, endDate]` (inclusive) in given timezone. Handles partial ranges (start-only or end-only).

## `isWholeDayWindow(startDate, endDate, tz)`
Returns `true` if start is `00:00` and end is `23:59` in given timezone.

## `isActiveStatus(value)`
Normalizes status: `true` (boolean) or `"true"` (string, case-insensitive).

## `hhmmToMinutes(hhmm)` / `minutesToHhmm(totalMinutes)`
Bidirectional conversion between `HH:MM` strings and integer minutes.

## `getExtendedWindow(startDate, endDate, extensionMinutes, tz)`
Applies `business_time_extension` (minutes) to a shift's time window. Returns extended start/end times. If extension would go out of bounds (< 00:00 or > 23:59), returns original window unchanged.

## `buildActiveCardsCsv(cards)`
Groups cards by `card_data` value, concatenates time ranges with `|` separator, joins cards with `,`. Format: `cardData:HH:MM-HH:MM|HH:MM-HH:MM,cardData2:00:00-23:59,...`

## `parseAccessLogEntry(rawEntry)`
Pipes-delimited string → `{log_card_id, log_status, log_type, log_device_id, log_timestamp}`. Requires 5+ pipe-separated parts.

## `buildAccessLogDocId(businessPrefix, sequenceNumber)`
Creates document ID: `{prefix}_ACCESS_LOGS_{NNNN}` (4-digit zero-padded).