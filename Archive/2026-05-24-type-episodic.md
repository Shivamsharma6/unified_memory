---
type: episodic
date: '2026-05-24'
updated: '2026-05-24T06:20:21.129141+00:00'
tags: []
lifecycle: archived
importance: 0.3375874865420475
---
# Distilled Summary
Sentri Firmware v3.6 implements an ESP32 RFID access control system using Arduino/PlatformIO with dual MFRC522 readers. Key design decisions include Firebase integration (Firestore + RTDB), a single-owner networkTask for cloud I/O, and an event-driven architecture utilizing FreeRTOS timers, queues, and event bits. To resolve potential connectivity and power instability, the firmware utilizes a cached active-card list for indefinite offline operation, LittleFS journaling for durable logging, and a self-healing startup routine with RTC-backed restart backoff. Diagnostics are persisted to survive system reboots.

## Raw Logs
# Sentri Firmware v3.6: ESP32-based RFID access control firmware running Arduino f

## Summary
Sentri Firmware v3.6: ESP32-based RFID access control firmware running Arduino framework via PlatformIO. Dual MFRC522 RFID readers (entry/exit), Firebase cloud integration (Firestore + RTDB), durable offline logging via LittleFS journal, OTA updates, and a local 24x7 provisioning portal. Key design: indefinite offline operation with cached active-card list, single-owner cloud I/O via networkTask, event-driven control flow using FreeRTOS timers/queues/event bits, self-healing startup with RTC-backed restart backoff, and persisted diagnostics (WARN/ERROR survive reboot).