---
type: episodic
date: '2026-05-27'
updated: '2026-05-27T08:41:00.369524+00:00'
tags:
- '#cloud-functions'
- '#utilities'
- '#applescript'
- '#whatsapp'
- '#sentri'
lifecycle: archived
importance: 0.36181730936009454
---
# Distilled Summary
# Cloud Functions — AppleScript Utility

## Summary
# Cloud Functions — AppleScript Utility

## `send_whatsapp.applescript` (54 lines)
**Purpose:** Sends a report (already on clipboard) to "Rishabh Anand" via WhatsApp desktop app. ... [Distilled] ... **Screenshots produced:**
- `/tmp/whatsapp_before.png` — WhatsApp window before automation
- `/tmp/whatsapp_before_paste.png` — Chat search results
- `/tmp/whatsapp_after_paste.png` — Message in input field
- `/tmp/whatsapp_final.png` — Sent message confirmation

## Raw Logs
# Cloud Functions — AppleScript Utility

## Summary
# Cloud Functions — AppleScript Utility

## `send_whatsapp.applescript` (54 lines)
**Purpose:** Sends a report (already on clipboard) to "Rishabh Anand" via WhatsApp desktop app.
**Usage:** `osascript send_whatsapp.applescript`

**Workflow:**
1. Takes screenshot of WhatsApp window (before)
2. Activates WhatsApp
3. Uses Cmd+Shift+F to open search
4. Types "Rishabh Anand" (4s wait for search)
5. Presses down arrow + Return to open chat (3s wait)
6. Takes screenshot before paste
7. Pastes clipboard (Cmd+V)
8. Takes screenshot after paste
9. Presses Return twice to send (sends + extra enter)
10. Takes final screenshot

**Key detail:** Hardcoded recipient "Rishabh Anand". Uses macOS accessibility features (System Events) to automate WhatsApp. Takes screenshots at multiple points for debugging.

**Screenshots produced:**
- `/tmp/whatsapp_before.png` — WhatsApp window before automation
- `/tmp/whatsapp_before_paste.png` — Chat search results
- `/tmp/whatsapp_after_paste.png` — Message in input field
- `/tmp/whatsapp_final.png` — Sent message confirmation