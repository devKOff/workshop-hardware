# rf_spectrum_visualizer.gui.pages.blocker - Blocker Page
# Channel input, Add/Remove controls, and temporary exclusion list

import customtkinter as ctk
from tk import Frame, Label, Entry, Button, messagebox, ttk
from rf_spectrum_visualizer.config import validate_channel, get_frequency_mhz
from rf_spectrum_visualizer.gui.theme import (
    get_crimon_accent_style,
    get_font,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
    COLOR_WHITE,
    COLOR_TEXT_DARK,
    COLOR_NAVY_SIDEBAR,
    get_table_row_style,
)


class BlockerPage(Frame):
    """Blocker page with channel input, Add/Remove controls, and temporary exclusion list."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **get_workspace_style())

        # --- Channel Input Section ---
        self.input_frame = LabelFrame(
            self,
            text="Add Channel to Blocker",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_NAVY_SIDEBAR,
            background=COLOR_WHITE,
        )
        self.input_frame.pack(fill="x", padx=20, pady=10)

        # Channel number input
        self.channel_label = Label(
            self.input_frame,
            text="Channel Number (0-125):",
            font=get_font(FONT_SIZE_SMALL),
            foreground=COLOR_TEXT_DARK,
            background=COLOR_WHITE,
        )
        self.channel_label.pack(anchor="w", padx=10, pady=(10, 0))

        self.channel_entry = Entry(
            self.input_frame,
            font=get_font(FONT_SIZE_DEFAULT),
            width=15,
            justify=CENTER,
        )
        self.channel_entry.pack(anchor="w", padx=10, pady=5)

        # Add button
        self.add_btn = Button(
            self.input_frame,
            text="Add Channel",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_WHITE,
            background=COLOR_CRIMON_ACCENT,
            activeforeground=COLOR_CRIMON_ACCENT,
            activebackground=COLOR_WHITE,
            cursor="hand2",
            relief="flat",
            command=self._on_add_channel,
        )
        self.add_btn.pack(anchor="w", padx=10, pady=5)

        # Remove button
        self.remove_btn = Button(
            self.input_frame,
            text="Remove Selected",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_WHITE,
            background="#505050",
            state="disabled",
            cursor="hand2",
            relief="flat",
            command=self._on_remove_channel,
        )
        self.remove_btn.pack(anchor="w", padx=10, pady=5)

        # --- Temporary Exclusion List ---
        self.list_label = Label(
            self,
            text="Temporary Exclusion List",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_NAVY_SIDEBAR,
            background=COLOR_WHITE,
        )
        self.list_label.pack(anchor="w", padx=20, pady=(15, 5))

        # Treeview for blocked channels
        self.blocked_table = ttk.Treeview(self, columns=("channel", "frequency"), show="headings", height=6)
        self.blocked_table.pack(fill="x", padx=20, pady=5)

        self.blocked_table.heading("channel", text="Channel")
        self.blocked_table.heading("frequency", text="Frequency (MHz)")

        self.blocked_table.column("channel", width=100, anchor=CENTER)
        self.blocked_table.column("frequency", width=150, anchor=CENTER)

        # Populate initial empty list
        self._populate_blocked_list()

        # --- Instruction Label ---
        self.instruction = Label(
            self,
            text="Channels added here are temporarily excluded from scanning.\nNo persistent storage is implemented yet.",
            font=get_font(FONT_SIZE_SMALL),
            foreground="#606060",
            background=COLOR_WHITE,
            justify=LEFT,
        )
        self.instruction.pack(anchor="w", padx=20, pady=10)

    def _populate_blocked_list(self):
        """Refresh the blocked channels list (currently empty placeholder)."""
        # Clear existing items
        for item in self.blocked_table.get_children():
            self.blocked_table.delete(item)
        # No blocked channels yet - placeholder message
        self.blocked_table.insert("", "end", values=("—", "—"))

    def _on_add_channel(self):
        """Handle Add Channel button click."""
        raw = self.channel_entry.get().strip()
        try:
            channel_num = int(raw)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid integer channel number.")
            return

        if not validate_channel(channel_num):
            messagebox.showerror("Channel Out of Range", f"Channel must be between {RF_CHANNEL_MIN} and {RF_CHANNEL_MAX}.")
            return

        freq = get_frequency_mhz(channel_num)
        label = get_channel_label(channel_num)

        # Add to the blocked list table
        self.blocked_table.insert("", "end", values=(label, f"{freq} MHz"))

        # Clear input
        self.channel_entry.delete(0, "end")

        # Remove button stays disabled until there's a selection (simple state)
        self.remove_btn.configure(state="disabled")

    def _on_remove_channel(self):
        """Handle Remove Selected channel click."""
        selected = self.blocked_table.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a channel to remove from the list.")
            return
        for item in selected:
            self.blocked_table.delete(item)
        # Re-enable (or keep disabled if list is empty)
        remaining = len(self.blocked_table.get_children())
        if remaining == 0:
            self.remove_btn.configure(state="disabled")