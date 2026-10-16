"""Tests for Blocker persistence: save/load, corruption recovery, invalid data."""

from __future__ import annotations

import json
import os

import pytest

from rf_spectrum_visualizer.utils.persistence import (
    save_excluded_channels,
    load_excluded_channels,
    clear_storage_file,
    blocker_storage_path,
)
from rf_spectrum_visualizer.constants import RF_CHANNEL_MIN, RF_CHANNEL_MAX


_STORAGE_FILE = blocker_storage_path()


def _remove_storage_file() -> None:
    """Remove the storage file if it exists (test cleanup)."""
    try:
        if os.path.exists(_STORAGE_FILE):
            os.remove(_STORAGE_FILE)
    except OSError:
        pass


class TestPersistenceSaveLoad:
    def setup_method(self):
        _remove_storage_file()

    def teardown_method(self):
        _remove_storage_file()

    def test_save_and_load_roundtrip(self):
        save_excluded_channels([5, 10, 100])
        loaded = load_excluded_channels()
        assert loaded == {5, 10, 100}

    def test_save_empty_list(self):
        save_excluded_channels([])
        loaded = load_excluded_channels()
        assert loaded == set()

    def test_load_missing_file_returns_empty(self):
        _remove_storage_file()
        assert load_excluded_channels() == set()

    def test_load_duplicate_channels_deduplicated(self):
        save_excluded_channels([5, 5, 10, 10, 5])
        loaded = load_excluded_channels()
        assert loaded == {5, 10}

    def test_load_out_of_range_channels_dropped(self):
        # Manually write a file with out-of-range channels.
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"excluded_channels": [5, -1, 126, 200, 10]}, f)
        loaded = load_excluded_channels()
        assert loaded == {5, 10}

    def test_load_non_integer_channels_dropped(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"excluded_channels": [5, "abc", 3.5, None, True, 10]}, f)
        loaded = load_excluded_channels()
        assert loaded == {5, 10}

    def test_storage_file_created(self):
        save_excluded_channels([7])
        assert os.path.exists(_STORAGE_FILE)

    def test_clear_storage_file_removes_file(self):
        save_excluded_channels([3, 8])
        assert os.path.exists(_STORAGE_FILE)
        clear_storage_file()
        assert not os.path.exists(_STORAGE_FILE)


class TestPersistenceCorruptionRecovery:
    def setup_method(self):
        _remove_storage_file()

    def teardown_method(self):
        _remove_storage_file()

    def test_corrupted_json_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            f.write("{not valid json!!!")
        assert load_excluded_channels() == set()

    def test_empty_file_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            f.write("")
        assert load_excluded_channels() == set()

    def test_whitespace_only_file_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            f.write("   \n\t  ")
        assert load_excluded_channels() == set()

    def test_json_array_instead_of_object_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump([5, 10], f)
        assert load_excluded_channels() == set()

    def test_json_missing_channels_key_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"other_key": [5]}, f)
        assert load_excluded_channels() == set()

    def test_channels_key_not_a_list_returns_empty(self):
        with open(_STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"excluded_channels": "not a list"}, f)
        assert load_excluded_channels() == set()


class TestPersistenceStoragePath:
    def test_storage_path_returns_string(self):
        path = blocker_storage_path()
        assert isinstance(path, str)
        assert path == "blocker_exclusions.json"
