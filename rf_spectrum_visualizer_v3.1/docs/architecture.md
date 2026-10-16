# Architecture — rf_spectrum_visualizer v3.1 (GUI skeleton)

## Overview

Single-window PyQt6 desktop application. A dark navy sidebar navigates between
three pages hosted in a `QStackedWidget`. The module layering is:

```
main.py                              # process entry point (QApplication)
└── src/rf_spectrum_visualizer/
    ├── __init__.py                  # package metadata
    ├── config.py                    # AppConfig dataclass (defaults, feature flags)
    ├── constants.py                 # fixed limits, page ids, layout sizes
    ├── gui/
    │   ├── main_window.py           # shell: sidebar + stacked pages + status bar
    │   ├── sidebar.py               # exactly three nav items with icons
    │   ├── theme.py                 # palette, fonts, programmatic icons, stylesheets
    │   ├── canvas.py                # reusable matplotlib Qt canvas
    │   ├── live_spectrum_page.py    # empty chart, channel table, scan buttons
    │   ├── start_analysis_page.py   # summary cards, chart placeholder, results table
    │   └── blocker_page.py          # channel input, add/remove, temporary list
    └── utils/
        └── channel.py               # validate_channel, channel_to_frequency
```

## Design decisions

- **No backend yet:** scan/analysis buttons toggle UI state only and emit honest
  status messages ("backend not yet implemented"). No fake measurements are
  plotted or displayed.
- **Programmatic icons:** drawn with `QPainter` in `theme.py.IconFactory` so the
  GUI has no external image dependencies.
- **Reusable components:** `MplCanvas` (matplotlib), `SummaryCard`, `SidebarItem`.
- **Temporary state only:** the blocker exclusion list is held in memory and
  cleared on window close; nothing is written to disk.
- **Signals for integration:** pages expose signals (`scan_toggled`,
  `status_message`, `blocker_list_changed`) so a future backend can be wired
  into `MainWindow` without touching page internals.

## Domain rules

- Valid channels: 0–125 inclusive.
- Frequency (MHz) = 2400 + channel_number.

## Test areas

- `tests/test_channel_validation.py` — validation + frequency math
- `tests/test_blocker_add_remove.py` — add / remove / clear / duplicates
- `tests/test_gui_navigation.py` — launch, page switching, shutdown
