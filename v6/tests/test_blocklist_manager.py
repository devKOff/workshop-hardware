"""Tests for blocklist_manager module."""

import pytest
import json
import tempfile
import os
from pathlib import Path
from v6.blocklist_manager import BlocklistManager, BlocklistEntry
from v6.config import BlocklistConfig
from v6.exceptions import BlocklistError, InvalidChannelError


class TestBlocklistManager:
    @pytest.fixture
    def temp_blocklist(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('[]')
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)
    
    @pytest.fixture
    def manager(self, temp_blocklist):
        config = BlocklistConfig(file_path=temp_blocklist)
        return BlocklistManager(config)
    
    def test_block_channel(self, manager):
        entry = manager.block_channel(122, "Test reason")
        assert entry.channel == 122
        assert entry.frequency_mhz == 2522
        assert entry.reason == "Test reason"
        assert manager.is_blocked(122)
    
    def test_block_duplicate(self, manager):
        manager.block_channel(122, "First")
        entry = manager.block_channel(122, "Second")
        assert entry.reason == "Second"
        entries = manager.get_blocked_entries()
        assert len(entries) == 1
    
    def test_unblock_channel(self, manager):
        manager.block_channel(122)
        assert manager.unblock_channel(122) is True
        assert manager.is_blocked(122) is False
        assert manager.unblock_channel(122) is False
    
    def test_is_blocked(self, manager):
        assert manager.is_blocked(122) is False
        manager.block_channel(122)
        assert manager.is_blocked(122) is True
    
    def test_get_blocked_channels(self, manager):
        manager.block_channel(10)
        manager.block_channel(5)
        manager.block_channel(122)
        channels = manager.get_blocked_channels()
        assert channels == [5, 10, 122]
    
    def test_get_blocked_entries(self, manager):
        manager.block_channel(122, "Reason 1")
        manager.block_channel(10, "Reason 2")
        entries = manager.get_blocked_entries()
        assert len(entries) == 2
        assert entries[0].channel == 10
        assert entries[1].channel == 122
    
    def test_get_entry(self, manager):
        manager.block_channel(122, "Test reason")
        entry = manager.get_entry(122)
        assert entry is not None
        assert entry.channel == 122
        assert entry.reason == "Test reason"
        
        assert manager.get_entry(123) is None
    
    def test_clear(self, manager):
        manager.block_channel(10)
        manager.block_channel(20)
        count = manager.clear()
        assert count == 2
        assert manager.get_blocked_channels() == []
    
    def test_persistence(self, temp_blocklist):
        config = BlocklistConfig(file_path=temp_blocklist)
        manager1 = BlocklistManager(config)
        manager1.block_channel(122, "Test")
        
        manager2 = BlocklistManager(config)
        assert manager2.is_blocked(122)
        entry = manager2.get_entry(122)
        assert entry.reason == "Test"
    
    def test_invalid_channel(self, manager):
        with pytest.raises(InvalidChannelError):
            manager.block_channel(-1)
        with pytest.raises(InvalidChannelError):
            manager.block_channel(126)
        with pytest.raises(InvalidChannelError):
            manager.unblock_channel(-1)
        with pytest.raises(InvalidChannelError):
            manager.is_blocked(-1)
    
    def test_corrupted_file_recovery(self, temp_blocklist):
        # Write corrupted JSON
        with open(temp_blocklist, 'w') as f:
            f.write('{ not valid json }')
        
        config = BlocklistConfig(file_path=temp_blocklist)
        with pytest.raises(BlocklistError):
            BlocklistManager(config)
        
        # Check backup was created
        backups = list(Path(temp_blocklist).parent.glob(f"{Path(temp_blocklist).stem}.corrupted.*.bak"))
        assert len(backups) == 1
    
    def test_invalid_entries_skipped(self, temp_blocklist):
        # Write JSON with some invalid entries
        with open(temp_blocklist, 'w') as f:
            json.dump([
                {"channel": 10, "frequency_mhz": 2410, "blocked_at": "2024-01-01T00:00:00", "reason": "OK"},
                {"channel": "invalid", "frequency_mhz": 2411, "blocked_at": "2024-01-01T00:00:00"},
                {"channel": 122, "frequency_mhz": 2522, "blocked_at": "2024-01-01T00:00:00", "reason": "OK"},
            ], f)
        
        config = BlocklistConfig(file_path=temp_blocklist)
        manager = BlocklistManager(config)
        assert manager.is_blocked(10)
        assert manager.is_blocked(122)
        assert len(manager.get_blocked_entries()) == 2
    
    def test_export_import_json(self, manager):
        manager.block_channel(10, "Reason 1")
        manager.block_channel(122, "Reason 2")
        
        json_str = manager.export_json()
        data = json.loads(json_str)
        assert len(data["blocklist"]) == 2
        
        manager.clear()
        imported = manager.import_json(json_str)
        assert imported == 2
        assert manager.is_blocked(10)
        assert manager.is_blocked(122)
    
    def test_get_stats(self, manager):
        manager.block_channel(10)
        manager.block_channel(122)
        stats = manager.get_stats()
        assert stats["total_blocked"] == 2
        assert stats["channels"] == [10, 122]
        assert stats["file_path"] is not None


class TestBlocklistEntry:
    def test_to_dict(self):
        entry = BlocklistEntry(122, 2522, "2024-01-01T00:00:00", "Test")
        d = entry.to_dict()
        assert d["channel"] == 122
        assert d["frequency_mhz"] == 2522
        assert d["reason"] == "Test"
    
    def test_from_dict(self):
        data = {"channel": 122, "frequency_mhz": 2522, "blocked_at": "2024-01-01T00:00:00", "reason": "Test"}
        entry = BlocklistEntry.from_dict(data)
        assert entry.channel == 122
        assert entry.reason == "Test"
    
    def test_from_dict_missing_reason(self):
        data = {"channel": 122, "frequency_mhz": 2522, "blocked_at": "2024-01-01T00:00:00"}
        entry = BlocklistEntry.from_dict(data)
        assert entry.reason == "User blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
