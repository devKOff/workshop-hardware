# v5 Progress

Status: Phase 1 complete — sensor layer committed. Next: Phase 2 (recorder.py + CSV export + tests).

Resume steps:
1. cd E:\GIT\workshop\v5
2. python -m compileall -q . && python -m pytest -q
3. Create recorder.py + tests/test_recorder.py
4. Double-check passes, commit "feat: recorder and CSV export", then Phase 3.

Done:
- v5/ created, git init -b main (branch main).
- sensor.py: SensorReading, ValidationError/OverflowError/OutOfRangeError, validate_reading (power = V x A), INA219HardwareSensor (lazy import), SimulatedSensor (5-6 V, tens of mA, labeled simulation), make_sensor factory.
- tests/test_sensor.py: 13 tests, all pass.
- requirements.txt (adafruit-circuitpython-ina219), requirements-dev.txt (pytest), .gitignore.
- Commit 37babd2 "feat: sensor layer", working tree clean.

Hardware mode not verified on a real Pi (no Pi available).
