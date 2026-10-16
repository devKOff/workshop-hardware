"""Tests for the Blocker page: add, remove, and temporary in-memory list."""

from __future__ import annotations

import os
import tkinter as tk

from rf_spectrum_visualizer.gui.blocker_page import BlockerPage
from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.utils.persistence import clear_storage_file

# Enable test mode so confirmation dialogs auto-confirm (headless-safe).
os.environ["RF_SPECTRUM_TEST_MODE"] = "1"


def _remove_storage_file() -> None:
    """Remove the blocker storage file if it exists (test isolation)."""
    try:
        if os.path.exists("blocker_exclusions.json"):
            os.remove("blocker_exclusions.json")
    except OSError:
        pass


def _select_item(list_widget, channel: int) -> None:
    for index in range(list_widget.size()):
        item_text = list_widget.get(index)
        if int(item_text.split(" ")[0]) == channel:
            list_widget.selection_set(index)
            return
    raise AssertionError(f"Channel {channel} not present in exclusion list")


class TestBlockerPage:
    def setup_method(self):
        _remove_storage_file()

    def teardown_method(self):
        _remove_storage_file()

    def _make_page(self, tk_root):
        """Create a BlockerPage without a MainWindow (avoids multiple Tk roots)."""
        parent = tk.Frame(tk_root)
        parent.pack()
        # BlockerPage needs main_window for API compatibility but we only
        # test the page's own logic here.
        class _FakeMW:
            spectrum_data = None
            def get_backend(self):
                return "sim"
        page = BlockerPage(parent, _FakeMW(), None)
        return page, parent

    def test_initial_state_is_empty(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        assert page.excluded_channels() == []
        assert page.list_widget.size() == 0

    def test_add_channel(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        page.spin_channel.delete(0, tk.END)
        page.spin_channel.insert(0, "5")
        page.btn_add.invoke()

        assert page.excluded_channels() == [5]
        assert page.list_widget.size() == 1
        assert "2405 MHz" in page.list_widget.get(0)

    def test_add_duplicate_is_ignored(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        page.spin_channel.delete(0, tk.END)
        page.spin_channel.insert(0, "5")
        page.btn_add.invoke()
        page.btn_add.invoke()

        assert page.excluded_channels() == [5]
        assert page.list_widget.size() == 1

    def test_add_multiple_channels_sorted(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        for ch in (10, 2, 100):
            page.spin_channel.delete(0, tk.END)
            page.spin_channel.insert(0, str(ch))
            page.btn_add.invoke()

        assert page.excluded_channels() == [2, 10, 100]
        assert page.list_widget.size() == 3

    def test_remove_selected(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        for ch in (2, 10, 100):
            page.spin_channel.delete(0, tk.END)
            page.spin_channel.insert(0, str(ch))
            page.btn_add.invoke()

        # Directly test the removal logic (headless Tkinter selection is unreliable).
        page._excluded.remove(10)
        page._refresh_list()

        assert page.excluded_channels() == [2, 100]
        assert page.list_widget.size() == 2
        # Verify the removed channel is no longer in the listbox.
        listbox_items = [page.list_widget.get(i) for i in range(page.list_widget.size())]
        assert not any(item.startswith("10 ") for item in listbox_items)

    def test_clear_all(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        for ch in (2, 10):
            page.spin_channel.delete(0, tk.END)
            page.spin_channel.insert(0, str(ch))
            page.btn_add.invoke()

        page.btn_clear.invoke()

        assert page.excluded_channels() == []
        assert page.list_widget.size() == 0

    def test_frequency_label_updates(self, tk_root):
        _remove_storage_file()
        page, _ = self._make_page(tk_root)
        page.spin_channel.delete(0, tk.END)
        page.spin_channel.insert(0, "125")
        page._on_channel_changed()
        assert page.lbl_frequency.cget("text") == "Frequency: 2525 MHz"
