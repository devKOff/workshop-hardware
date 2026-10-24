# Solar Panel Performance Monitor — Agent Rules

Project root: `solar_pi_project_v4/` (Git repo root). All work inside it. Never touch `solar_pi_project_v3/` or siblings.

Hard rules:
1. Simulation vs Hardware mode chosen explicitly by the user, shown in header.
2. Hardware failure → honest error state. NEVER substitute simulated/stale readings. Distinguish "unavailable" from real 0.
3. Every simulated record labeled (`sensor_mode`).
4. Acquisition and DB writes off GUI thread. One acquisition worker max. Page switching must not start/stop monitoring. Pausing graph must not stop recording. Clearing graph must not delete history.
5. Never overwrite/delete user files without confirmation.
6. Never claim a test/reading/deployment succeeded unless executed and seen. Never weaken/disable tests.
7. Source files ~<400 lines, type hints, no circular imports, no duplicated logic.

Decisions: PySide6 + pyqtgraph (no matplotlib); stdlib sqlite3 WAL mode, parameterized SQL, `PRAGMA user_version`; stdlib csv UTF-8+BOM, temp+atomic rename; pytest + pytest-qt with offscreen QT_QPA_PLATFORM; adafruit-circuitpython-ina219 lazy import in hardware backend only (Windows unaffected).

Protocol: implement → run phase tests → fix failures → update PROGRESS.md. Commit per phase. Part end: CHECK COMMANDS → GIT COMMANDS → report → STOP.