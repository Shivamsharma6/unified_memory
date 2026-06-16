---
type: episodic
date: '2026-05-24'
updated: '2026-05-24T07:21:08.447598+00:00'
tags: []
lifecycle: archived
importance: 0.3375874865420475
---
# Distilled Summary
# Sentri Flutter-Firmware Integration Points

## Summary
# Sentri Flutter-Firmware Integration Points

## Architecture Overview
Sentri is a smart access control system with two main layers:
- **Flutter Mobile App** (iOS/Android) — staff-facing portal for device management, access logs, analytics, and configuration. ... [Distilled] ... **Firmware:** platformio.ini (board=esp32dev, framework=arduino, monitor_speed=115200), Dependencies: ArduinoJson version 7.4.3, FirebaseClient version 2.2.9, MFRC522 version 1.4.12, Build envs: esp32dev (target), native (unit tests with ArduinoFake + Unity), Storage: min_spiffs.csv partitions, LittleFS.

## Raw Logs
# Sentri Flutter-Firmware Integration Points

## Summary
# Sentri Flutter-Firmware Integration Points

## Architecture Overview
Sentri is a smart access control system with two main layers:
- **Flutter Mobile App** (iOS/Android) — staff-facing portal for device management, access logs, analytics, and configuration.
- **ESP32 Firmware** (Arduino/PlatformIO) — edge hardware running on esp32dev board with MFRC522 RFID reader, LCD display, buzzer, relay/gate controller, and WiFi/BLE connectivity.

## Integration Point 1: Device Registration & Discovery
**Flow:** Staff registers device MAC address + name in Flutter app → device appears on local network.
**Mechanism:** LanScanManager in Flutter broadcasts UDP probes every N seconds on the local subnet. Each ESP32 responds with its MAC, uptime, and the customer UID currently being scanned.
**Flutter code:** LanScanManager (broadcasts UDP), DeviceStatusUtil (evaluates heartbeat delta).
**Firmware code:** Responds to UDP heartbeat probes, includes MAC + uptime + customer UID in response payload.
**Status thresholds:** <30s heartbeat = online, <180s = recent, >180s = offline.

## Integration Point 2: Access Decision Engine (Card Scoring)
**Flow:** Customer scans RFID card on ESP32 → firmware sends scan event to Flutter → Flutter evaluates composite access score → result sent back to ESP32.
**Scoring logic (composite access score):**
- No blacklist match = pass (base)
- Active shift for customer = +50%
- Business seats available = +30%
- No overdue payments = +20%
**Decision:** If total score >= 60% threshold → gate opens for 3 seconds. If < threshold → buzzer activates + LCD shows rejection message.
**Data flow:** Flutter computes score using Firestore/RTDB data (customer profile, shift schedule, business seats, payment status) and pushes decision to ESP32 via local network.

## Integration Point 3: Heartbeat & Status Sync
**Flow:** ESP32 sends periodic heartbeat to Flutter app over local network.
**Payload:** MAC address, uptime, customer UID being scanned, signal strength.
**Flutter processes:** DeviceStatusUtil calculates status from heartbeat delta. Flutter displays device status on dashboard (online/recent/offline).
**Firmware config:** platformio.ini — CORE_DEBUG_LEVEL=3, VERBOSE_LOGS=1, ENABLE_DATABASE, ENABLE_FIRESTORE, ENABLE_USER_AUTH.

## Integration Point 4: Firebase Cloud Sync (Bidirectional)
**Flutter side:** Primary DB is Cloud Firestore 5.x (NoSQL). Secondary: Realtime Database. Flutter reads customer data, writes access logs, push notifications via Firebase Cloud Messaging.
**Firmware side:** ESP32 connects directly to Firebase via FirebaseClient version 2.2.9 library. Sends scan events, receives config updates, writes to Firestore/RTDB.
**Shared data models:** Customer UID, access logs, device config, blacklist entries.
**Auth:** ENABLE_USER_AUTH flag on firmware; Flutter handles OAuth/Firebase Auth; firmware validates tokens.

## Integration Point 5: RFID Scanning Pipeline
**Hardware:** MFRC522 RFID reader on ESP32 (dependency: MFRC522 version 1.4.12).
**Flow:** Customer taps card → ESP32 reads UID → firmware looks up customer in local cache or queries Firebase → sends result to Flutter for scoring.
**Flutter integration:** Access logs feature (1 of 15 feature modules) displays scan history, timestamps, outcomes (granted/denied), and associated customer info.

## Integration Point 6: Captive Portal Fallback (Portal Mode)
**Trigger:** WiFi connection to main network fails.
**Behavior:** ESP32 spins up its own AP (SSID: ESP32-XXXX) hosting a captive portal for WiFi configuration.
**Flutter integration:** Staff can discover the ESP32-XXXX AP via BLE or LAN scan, connect to configure WiFi credentials through the captive portal, then re-register the device in the Flutter app.

## Integration Point 7: OTA Firmware Updates
**Flutter side:** update_service.dart, update_trigger_*.dart — manages firmware update lifecycle.
**Flow:** Flutter initiates OTA update → firmware receives binary via Firebase/HTTP → validates checksum → flashes new firmware → reboots.
**Storage:** ESP32 uses min_spiffs.csv partitions with LittleFS filesystem for storing update binaries.

## Integration Point 8: Display & HMI Feedback
**Components:** LCD display + buzzer on ESP32.
**Flutter control:** Flutter sends status messages to ESP32 → firmware displays on LCD (welcome, access granted/denied, error codes) and triggers buzzer for rejections.
**Messages:** Welcome [Name], Access Granted, Access Denied with Reason, Please try again.

## Integration Point 9: BLE Connectivity (Secondary Channel)
**Use case:** Initial device pairing, proximity-based features, fallback when WiFi unavailable.
**Flutter:** Uses Flutter BLE plugins to discover and communicate with ESP32 directly.
**Firmware:** ESP32 advertises BLE service, accepts pairing commands from Flutter app.

## Data Flow Summary
Customer taps RFID card → ESP32 reads UID via MFRC522 → ESP32 queries Firebase (or local cache) for customer data → ESP32 sends scan event to Flutter via local network (UDP/TCP) → Flutter computes composite access score (blacklist, shift, seats, payments) → Flutter sends decision back to ESP32 → ESP32 acts: gate relay opens 3s OR buzzer + LCD rejection → Access log written to Firestore via both Flutter and firmware → Flutter dashboard updates in real-time.

## Key Files Reference
**Flutter:** lib/core/services/aggregate_maintenance_service.dart, lib/core/services/update_service.dart, lib/core/utils/device_heartbeat.dart, lib/core/utils/device_status.dart, lib/features/access_logs/ (15 feature modules total), lib/app/app_router.dart, route_paths.dart.

**Firmware:** platformio.ini (board=esp32dev, framework=arduino, monitor_speed=115200), Dependencies: ArduinoJson version 7.4.3, FirebaseClient version 2.2.9, MFRC522 version 1.4.12, Build envs: esp32dev (target), native (unit tests with ArduinoFake + Unity), Storage: min_spiffs.csv partitions, LittleFS.