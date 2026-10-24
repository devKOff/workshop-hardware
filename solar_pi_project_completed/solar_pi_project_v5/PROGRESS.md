# v5 Progress

Status: Phase 2 complete — recorder.py + CSV export committed. Next: Phase 3 (main.py window + README).

Resume steps:
1. cd E:\GIT\workshop\v5
2. python -m compileall -q . && python -m pytest -q
3. Create main.py (Tkinter window) + README.md
4. Double-check passes, launch check `python main.py --duration 20 --interval 0.5`
5. Commit "feat: window and README", git status clean.

Done:
- Commit 37babd2 feat: sensor layer
- Commit (this phase) feat: recorder and CSV export — recorder.py, tests/test_recorder.py
- sensor.py: SensorReading, validate_reading (V=bias+shunt, P=V×I), INA219HardwareSensor (lazy import), SimulatedSensor (5-6V, tens of mA, simulation-labeled), make_sensor
- recorder.py: Recorder with ONE worker thread, queue.Queue, threading.Event stop, time.monotonic deadline scheduling, auto-complete/early-stop, in-memory samples, atomic CSV export (utf-8-sig BOM, temp+rename), has_unexported_data, summary, drain_queue, close
- tests/test_sensor.py (13), tests/test_recorder.py (25 total across both files)
- requirements.txt, requirements-dev.txt, .gitignore, PROGRESS.md

Hardware mode not verified on a real Pi (no Pi available).
