# Phase Plan — Solar Panel Performance Monitor

12 strictly ordered phases. After each phase: run the full available test suite,
fix failures, then commit and tag `phase-N-complete`.

- [x] Phase 1: Project structure and GUI foundation
- [ ] Phase 2: Core logic and measurement models
- [ ] Phase 3: SQLite database and persistence
- [ ] Phase 4: Simulation backend
- [ ] Phase 5: Measurement engine and energy tracking
- [ ] Phase 6: Complete six-page GUI
- [ ] Phase 7: Live graphs and dashboard integration
- [ ] Phase 8: Historical data and CSV reports
- [ ] Phase 9: Settings and system diagnostics
- [ ] Phase 10: Real INA219 hardware integration
- [ ] Phase 11: Full testing, regression fixes, and final audit
- [ ] Phase 12: Documentation, GitHub release, and Raspberry Pi deployment

## Pending hardware tests (executed only on Pi + INA219)

- Genuine INA219 readings over I²C
- INA219 initialization failure handling
- Sensor disconnection mid-run
- Hardware mode never silently falls back to simulation
