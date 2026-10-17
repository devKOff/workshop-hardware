# Progress - rf_spectrum_visualizer v3.1

Phase status: **in progress** (Phase 6 - final).

## Phase 1 - Scaffold + hardware check scripts (APPROVED)

Tag `v3.1-phase1` pushed.

## Phase 2 - Scan backend (APPROVED)

Tag `v3.1-phase2` pushed.

## Phase 3 - GUI shell + Live Spectrum page (APPROVED)

Tag `v3.1-phase3` pushed.

## Phase 4 - Start Analysis page (APPROVED)

Tag `v3.1-phase4` pushed.

## Phase 5 - Blocker page + JSON persistence (APPROVED)

Tag `v3.1-phase5` pushed.

## Phase 6 - Waterfall, scan-rate readout, Clear button, docs, launch script/desktop shortcut (in progress)

New files:
- `scripts/run_gui.py` — launch script with optional file logging
- `scripts/rf_spectrum_visualizer.desktop` — desktop shortcut / autostart entry
- `docs/phase6.md` — launch, autostart, logging, GUI feature docs

Changed files:
- `src/rf_spectrum_visualizer/scan_worker.py` — added scan-rate tracking (`scan_rate` property)
- `src/rf_spectrum_visualizer/gui/pages/live_spectrum.py` — added Clear Display button,
  scan-rate readout, waterfall heatmap (matplotlib imshow, newest cycle at top)
- `README.md` — updated Run section, roadmap marked complete, launch script/desktop shortcut
- `docs/PROGRESS.md` — updated

Dev-machine pytest: 56 passed (unchanged from Phase 5; no new test file needed
for Phase 6 GUI features since they require a display).
Could NOT verify without hardware: HardwareBackend end-to-end in GUI, Tkinter
on Pi OS, matplotlib on Pi OS, waterfall rendering on Pi, desktop shortcut,
autostart.

Open issues:
- Tkinter on Raspberry Pi OS not yet verified (no display on dev machine).
- Matplotlib on Pi OS: user reported installing it; not yet verified with GUI.
- Waterfall requires matplotlib `imshow` — verified to import on dev machine.
