# Progress - rf_spectrum_visualizer v3.1

Phase status: **in progress** (Phase 5 - Blocker page + JSON persistence).

## Phase 1 - Scaffold + hardware check scripts (APPROVED)

Tag `v3.1-phase1` pushed.

## Phase 2 - Scan backend (APPROVED)

Tag `v3.1-phase2` pushed.

## Phase 3 - GUI shell + Live Spectrum page (APPROVED)

Tag `v3.1-phase3` pushed.

## Phase 4 - Start Analysis page (APPROVED)

Tag `v3.1-phase4` pushed.

## Phase 5 - Blocker page + JSON persistence (in progress)

New files:
- `src/rf_spectrum_visualizer/blocker.py` (BlockerManager: add/remove/clear/list, JSON load/save, persists across instances, rejects out-of-range, handles corrupt file)
- `tests/test_blocker.py` (8 tests)

Changed files:
- `src/rf_spectrum_visualizer/gui/main_window.py` (creates shared BlockerManager, passes to Start Analysis + Blocker pages)
- `src/rf_spectrum_visualizer/gui/pages/start_analysis.py` (accepts blocker_manager, passes excluded_channels to AnalysisEngine, saves exclusions on change)
- `src/rf_spectrum_visualizer/gui/pages/blocker.py` (replaced stub: explanatory text, channel spinbox + derived frequency, Add/Remove/Clear All buttons, feedback line, excluded-channels list "N - FREQ MHz", Analysis vs Live Spectrum footnote)
- `docs/PROGRESS.md` (updated)

Dev-machine pytest: 56 passed total (48 from Phases 1-4 + 8 new Phase 5).
Could NOT verify without hardware: BlockerManager JSON persistence on real Pi filesystem (mock-tested with tempdir). Tkinter on Pi OS not yet verified.

Open issues:
- Tkinter on Raspberry Pi OS not yet verified.
- Matplotlib on Pi OS: user reported installing it; not yet verified with GUI.
