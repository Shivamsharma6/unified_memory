# Sentri Firmware – System-Level Understanding

## Runtime shape
Mixed Arduino loop + FreeRTOS multi-task ESP32 application.
- Hermes/Arduino task runs `sentriLoop()` and services portal HTTP, local event timers, WiFi/time fixes.
- `rfidTask` polls both MFRC522 readers on Core 0 / Priority 3.
- `relayTask` handles door unlock timing on Core 0 / Priority 6.
- `accessTask` validates cards against in-memory active set on Core 0 / Priority 5.
- `networkTask` owns all Firebase I/O on Core 1 / Priority 2.
- `healthMonitorTask` watches liveness and heap on Core 1 / Priority 7.

## Boot / setup sequence
`sentriSetup()` in `src/App.cpp`:
1. Release BT memory and init serial.
2. Create mutexes: `g_activeCardsMutex`, `g_fileMutex`, `g_logMutex`.
3. Create queues/event groups: `g_relayQueue`, `g_accessLogQueue`, `g_networkCommandQueue`, `g_networkQueueSet`, `g_diagPersistQueue`.
4. Create and start FreeRTOS timers: `resetPoll` (50 ms), `mainSvc` (1 s), `netSvc` (1 s).
5. Mount LittleFS.
6. Load config, advanced config, access list, activity cache, journal cursor, last-good time.
7. Configure RFID SPI CS/RST pins, bring up SPI, attempt readers.
8. Start tasks; if any fail, `selfHealRestart()`.

## Active card memory model
`src/ActiveCards.cpp` and `src/StateManagers.cpp`.
- `g_activeCards` is the authoritative vector of `ActiveCardEntry` items with shift windows.
- `g_activeSet` is an `unordered_set<string>` of normalized UIDs.
- `loadAccessListFromFile()` deserializes GLED-style list then delegates to `AccessController::replaceActiveCards()`.
- `replaceActiveCards()` pre-normalizes/moves data OUTSIDE the lock, then swaps under `g_activeCardsMutex` for microseconds.
- Lookups use `g_activeSet.find()` first to short-circuit the vector loop.
- `increaseActivityEnabled` / `decreaseActivityEnabled` toggle global `g_activityEnabled` and write activity cache (RTC-backed).

## RFID / access validation path
`src/ActiveCards.cpp` provides:
- `findActiveCardTimes(uid, checkTargetHHMM, outStart, outEnd)`: returns true if UID matches an active shift, optionally restricted to a current time window via `timeInRange()`.
- `getAccessStateForRfid(...)`: high-level helper returning `AccessState` (none/card/activity state) for reader UI and access task.
- Scan debounce trackers live in `RfidReaderState` from `Common.h`.

## Network / cloud pipeline
`src/NetworkTask.cpp`, `src/FirebaseInit.cpp`, `src/Firebase.cpp`.
- `networkTaskLoop` waits on `g_networkQueueSet` covering access log + network command queues.
- Commands defined in `NetworkCommandType` in `Common.h`:
  - firebase init, stream watchdog, circuit tick, emergency flush, night watchman,
    pre-reboot flush, log upload and clear, heartbeat, log upload, device presence/circuit heartbeat,
    register retry, flush check, OTA check, datasync loop.
- `processNetworkCommand()` routes each command; long operations use `feedWatchdog()`.
- IoT style `datasync` loop: writes device data including presence, logs, status to RTDB.
- RTDB database expected: `device_{mac}` tree with `logs`, `access_logs`, metadata fields.
- Night Watchman: IST-hour maintenance window; retries at 5 min cadence if today's run not completed.
- Access log drain: `drainAccessLogQueue(maxItems, forceDrain)` drains queue, writes to LittleFS journal, then uploads via Firebase. It now updates `g_lastAccessLogDrainAt` for health monitor.

## Portal HTTP endpoints
`src/Portal.cpp`.
- `/` — dashboard UI.
- `/api/v1/config` POST — Wi-Fi/user/business config save then `NETCMD_PRE_REBOOT_FLUSH`.
- `/api/v1/config/advanced` POST — business/advanced config; immediate effect.
- `/reboot` / `/api/v1/device/action?action=reboot` — async reboot.
- `/status` JSON — WiFi status, Firebase ready, card stream healthy, heap, storage, queue counts, activity state.
- `/logs` — text dump, `?clear=1` clears local storage, `?action=upload-clear` queues async upload/clear.
- `/fs` JSON list, `/api/v1/fs/delete` POST.
- `/api/v1/ota/check` — fire-and-forget OTA check; returns current metadata plus `check_pending`.
- `/api/v1/ota` POST — trigger OTA apply.
- `/api/v1/ota/upload` POST — multipart `.bin` upload and flash.
- Auth: provisioning + portal auth via `preflightAuth()`.

## Over-the-air
`src/Ota.cpp`.
- OTA state in globals: `g_otaInProgress`, `g_otaUpdateAvailable`, `g_availableFirmwareVersion`, request/completed IDs.
- Check command posts async; UI needs to poll or handle `check_pending=true`.

## Self-heal and stability
`src/Utils.cpp`, `src/App.cpp`, `src/HealthMonitor.cpp`.
- `selfHealRestart()` with exponential backoff on boot failure or fatal path; stored in RTC `s_bootRecoveryCount`.
- Task WDT configured for 30 s; `esp_task_wdt_add` per task; trigger panic/resets on stall.
- `healthMonitorTask` adds software liveness on top:
  - main loop / rfidTask / log drain stall >120s → `selfHealRestart()`
  - RFID poll stall <120s with readers present warns at 30s threshold.
  - heap <20KB sustained 30 seconds triggers restart.

## File / log persistence
`src/LogBuffer.cpp`, `src/AccessLog.cpp`, `src/Utils.cpp`.
- LittleFS used for logs and journal; access log uses `FILE_ACCESS_LOG` and `FILE_ACCESS_LOG_JOURNAL`.
- Mutex protection via recursive `g_fileMutex` with short/long helpers.
- `uploadPersistentDeviceLogsAndClear()` pushes device logs to Firebase then clears local log.
- Byte-level config/activity caches persist across reboots.

## Hardware map highlights
- Relay: `RELAY` pin; defaults to `RELAY_LOCKED_STATE`.
- Factory reset: `FACTORY_RESET_PIN` input pulldown; optional full reset pin.
- RFID: MFRC522 entry on `MFRC522_ENTRY_SS`, `MFRC522_ENTRY_RST`; exit on `MFRC522_EXIT_SS`, `MFRC522_EXIT_RST`.
- SPI CS managed carefully to avoid boot strapping glitches.

## Behavioral contracts
- Card scan never blocked by full active list reload: double-buffer under mutex keeps lookup O(1) set hit and short vector scan.
- Network queue set allows `xQueueSelectFromSet` pattern.
- Night Watchman uses IST-adjusted `time(nullptr)`.
- Presence enabled/disabled via activity cache; affects relay pulse behavior.
