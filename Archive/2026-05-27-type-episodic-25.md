---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:40:44.456840+00:00'
tags:
- '#cloud-functions'
- '#utilities'
- '#python'
- '#scripts'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — Utility Scripts

## Summary
# Cloud Functions — Utility Scripts

## `send_report.py` (44 lines)
**Purpose:** Direct RTDB report sender — bypasses `send_message` CLI not found issue. ... [Distilled] ... **Key functions:**
- `parse_log(raw)` — parses log entries by regex pattern `[LEVEL] [time] message`
- `nightwatchman(entries)` — extracts nightWatchman activity (ran, last_run, completed, low_heap)
- `ts(iso_str)` / `short_ts(iso_str)` — timestamp formatting helpers
- `wrap(text, width, indent)` — text wrapping for formatted output

## Raw Logs
# Cloud Functions — Utility Scripts

## Summary
# Cloud Functions — Utility Scripts

## `send_report.py` (44 lines)
**Purpose:** Direct RTDB report sender — bypasses `send_message` CLI not found issue.
**Usage:** `python3 send_report.py <report_file> [telegram_chat_id]`
**Mechanism:** Imports Hermes gateway internals (`_send_to_platform`, `load_gateway_config`) and calls Telegram directly.
**Key detail:** Uses Hermes internal APIs — tightly coupled to Hermes Agent architecture.

## `rtdb_device_report.py` (241 lines)
**Purpose:** Sentri RTDB per-business device status report generator.
**Target businesses:** `["2026_001", "Client_2026_1"]`
**RTDB URL:** `https://sentri-ban2r1-default-rtdb.asia-southeast1.firebasedatabase.app`
**Firebase SA:** `/Users/shivamsharma/projects/sentri-ban2r1-firebase-adminsdk.json`

**What it reads from RTDB (`sentri/`):**
- `device_presence/{businessId}/{macAddress}` — device info (name, permanent_switch, last_seen, local_ip, pulse_trigger)
- `device_logs/{businessId}/{macAddress}` — log text and logs_persist
- `active_cards_version/{businessId}` — version timestamp

**What it outputs:** Formatted ASCII report with per-device cards showing gate status (🔓 OPEN/🔒 CLOSED), last seen, local IP, pulse trigger, log stats (WARN/ERROR/INFO), nightWatchman status, and recent warnings/errors.

**Key functions:**
- `parse_log(raw)` — parses log entries by regex pattern `[LEVEL] [time] message`
- `nightwatchman(entries)` — extracts nightWatchman activity (ran, last_run, completed, low_heap)
- `ts(iso_str)` / `short_ts(iso_str)` — timestamp formatting helpers
- `wrap(text, width, indent)` — text wrapping for formatted output