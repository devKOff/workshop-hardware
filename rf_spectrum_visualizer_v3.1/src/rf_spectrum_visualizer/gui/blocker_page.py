"""Blocker page: software-level channel exclusion with persistent storage.

Manages a set of excluded channel numbers (0-125). Excluded channels are
omitted from Analysis recommendations but remain fully visible in Live
Spectrum measurements. This is software-level channel exclusion only — it
does NOT physically block RF signals or prevent transmissions.

The exclusion list is persisted to a local JSON file and restored when the
application restarts. Missing, corrupted, or invalid storage files are
handled safely.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

from ..utils.channel import channel_to_frequency, validate_channel
from ..utils.persistence import (
    save_excluded_channels,
    load_excluded_channels,
    clear_storage_file,
)
from ..constants import (
    COLOR_WORKSPACE_BG,
    COLOR_TEXT_DARK,
    COLOR_CRIMON_ACCENT,
    RF_CHANNEL_MIN,
    RF_CHANNEL_MAX,
    RF_BASE_FREQUENCY_MHZ,
)


def _confirm_action(title: str, message: str, parent=None) -> bool:
    """Show a confirmation dialog.

    In test mode (RF_SPECTRUM_TEST_MODE env var set), auto-confirms so that
    headless tests do not block on a modal dialog.
    """
    if os.environ.get("RF_SPECTRUM_TEST_MODE"):
        return True
    return messagebox.askyesno(title, message, parent=parent)


class BlockerPage(tk.Frame):
    """Software-level channel blocker UI with persistent storage."""

    def __init__(self, parent, main_window, spectrum_data):
        super().__init__(parent, bg=COLOR_WORKSPACE_BG)
        self.main_window = main_window
        self.spectrum_data = spectrum_data
        # Load persisted exclusions on startup; in-memory working set.
        self._excluded: list[int] = sorted(load_excluded_channels())
        self._build_ui()
        # Reflect loaded exclusions in the UI.
        self._refresh_list()
        self._update_remove_state()
        if self._excluded:
            self._set_feedback(
                f"Restored {len(self._excluded)} excluded channel(s) from storage."
            )

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = tk.Frame(self, bg=COLOR_WORKSPACE_BG)
        root.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tk.Label(
            root, text="Channel Blocker",
            font=("Segoe UI", 16, "bold"), bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK,
        ).pack(anchor=tk.W, pady=(0, 8))

        hint = tk.Label(
            root,
            text=(
                "Software-level channel exclusion: enter a channel (0-125) to "
                "exclude it from Analysis recommendations. Excluded channels "
                "remain visible in Live Spectrum measurements — this does NOT "
                "physically block RF signals or prevent transmissions. "
                "The exclusion list is saved to disk and restored on restart."
            ),
            bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
            wraplength=700, justify=tk.LEFT,
        )
        hint.pack(anchor=tk.W, pady=(0, 12))

        # --- Input row ---
        input_row = tk.Frame(root, bg=COLOR_WORKSPACE_BG)
        input_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(input_row, text="Channel:", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT)
        self.spin_channel = tk.Spinbox(
            input_row, from_=RF_CHANNEL_MIN, to=RF_CHANNEL_MAX,
            width=6,
        )
        self.spin_channel.pack(side=tk.LEFT, padx=(4, 10))
        self.spin_channel.delete(0, tk.END)
        self.spin_channel.insert(0, "0")

        self.lbl_frequency = tk.Label(
            input_row, text=f"Frequency: {RF_BASE_FREQUENCY_MHZ} MHz",
            bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
        )
        self.lbl_frequency.pack(side=tk.LEFT, padx=(0, 20))

        self.btn_add = tk.Button(
            input_row, text="Add Exclusion", command=self._on_add,
            bg=COLOR_CRIMON_ACCENT, fg="white", activebackground="#b71c1c",
            relief=tk.FLAT, padx=12, pady=4,
        )
        self.btn_add.pack(side=tk.LEFT, padx=2)

        self.btn_remove = tk.Button(
            input_row, text="Remove Selected", command=self._on_remove_selected,
            bg="#9e9e9e", fg="white", activebackground="#616161",
            relief=tk.FLAT, padx=12, pady=4,
        )
        self.btn_remove.pack(side=tk.LEFT, padx=2)

        self.btn_clear = tk.Button(
            input_row, text="Clear All", command=self._on_clear,
            bg="#9e9e9e", fg="white", activebackground="#616161",
            relief=tk.FLAT, padx=12, pady=4,
        )
        self.btn_clear.pack(side=tk.LEFT, padx=2)

        self.spin_channel.bind("<KeyRelease>", lambda e: self._on_channel_changed())

        # --- Validation feedback ---
        self.lbl_feedback = tk.Label(
            root, text="", fg="#b00020", bg=COLOR_WORKSPACE_BG,
            font=("Segoe UI", 9),
        )
        self.lbl_feedback.pack(anchor=tk.W, pady=(0, 8))

        # --- Exclusion list ---
        tk.Label(
            root, text="Excluded Channels (software-level exclusion)",
            font=("Segoe UI", 14, "bold"), bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK,
        ).pack(anchor=tk.W, pady=(0, 4))

        self.list_widget = tk.Listbox(
            root, height=10, activestyle=tk.NONE,
            selectmode=tk.EXTENDED,
        )
        self.list_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.list_widget.bind("<<ListboxSelect>>", lambda e: self._update_remove_state())

        # Status note under the list.
        self.lbl_note = tk.Label(
            root,
            text=(
                "Excluded channels are omitted from Analysis recommendations "
                "but remain visible in Live Spectrum."
            ),
            fg="#666666", bg=COLOR_WORKSPACE_BG,
            font=("Segoe UI", 9, "italic"),
        )
        self.lbl_note.pack(anchor=tk.W, pady=(0, 8))

        self._on_channel_changed()
        self._update_remove_state()

    # ------------------------------------------------------------------ logic
    def _on_channel_changed(self) -> None:
        try:
            channel = int(self.spin_channel.get())
        except ValueError:
            channel = 0
        self.lbl_frequency.config(text=f"Frequency: {RF_BASE_FREQUENCY_MHZ + channel} MHz")
        self.lbl_feedback.config(text="")

    def _on_add(self) -> None:
        try:
            channel = int(self.spin_channel.get())
        except ValueError:
            self._set_feedback("Enter a valid channel number (0-125).")
            return
        if not validate_channel(channel):
            self._set_feedback(f"Channel {channel} is out of range (0-125).")
            return
        if channel in self._excluded:
            self._set_feedback(f"Channel {channel} is already excluded.")
            return
        self._excluded.append(channel)
        self._excluded.sort()
        self._refresh_list()
        save_excluded_channels(self._excluded)
        self._set_feedback(
            f"Channel {channel} ({RF_BASE_FREQUENCY_MHZ + channel} MHz) "
            f"added to exclusion list."
        )

    def _on_remove_selected(self) -> None:
        selection = self.list_widget.curselection()
        if not selection:
            return
        channels_to_remove = []
        for idx in selection:
            item_text = self.list_widget.get(idx)
            channel = int(item_text.split(" ")[0])
            channels_to_remove.append(channel)
        # Confirmation before removing.
        if len(channels_to_remove) == 1:
            msg = (
                f"Remove channel {channels_to_remove[0]} "
                f"({RF_BASE_FREQUENCY_MHZ + channels_to_remove[0]} MHz) "
                f"from the exclusion list?"
            )
        else:
            ch_list = ", ".join(str(c) for c in channels_to_remove)
            msg = (
                f"Remove {len(channels_to_remove)} channels ({ch_list}) "
                f"from the exclusion list?"
            )
        if not _confirm_action("Confirm removal", msg, parent=self):
            return
        for channel in channels_to_remove:
            if channel in self._excluded:
                self._excluded.remove(channel)
        self._refresh_list()
        save_excluded_channels(self._excluded)
        self._set_feedback(
            f"Removed {len(channels_to_remove)} channel(s) from exclusion list."
        )

    def _on_clear(self) -> None:
        if not self._excluded:
            return
        if not _confirm_action(
            "Confirm clear all",
            f"Remove all {len(self._excluded)} excluded channels? "
            f"This cannot be undone.",
            parent=self,
        ):
            return
        self._excluded.clear()
        self._refresh_list()
        clear_storage_file()
        self.lbl_feedback.config(text="All exclusions cleared.")

    def _refresh_list(self) -> None:
        self.list_widget.delete(0, tk.END)
        for channel in self._excluded:
            freq = RF_BASE_FREQUENCY_MHZ + channel
            self.list_widget.insert(tk.END, f"{channel}  —  {freq} MHz")
        self._update_remove_state()

    def _update_remove_state(self, *_args) -> None:
        self.btn_remove.configure(
            state=tk.NORMAL if self.list_widget.curselection() else tk.DISABLED
        )

    def _set_feedback(self, text: str) -> None:
        self.lbl_feedback.config(text=text)

    # ------------------------------------------------------------------ API
    def excluded_channels(self) -> list[int]:
        """Return a copy of the excluded channel list (software-level)."""
        return list(self._excluded)
