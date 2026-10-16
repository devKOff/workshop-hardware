#!/usr/bin/env python
import sys
import os
import tempfile
import json

# Add the source directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rf_spectrum_visualizer_v3', 'src'))

# Test channel model
from rf_spectrum_visualizer.models.channel import (
    channel_to_frequency, validate_channel, CHANNEL_MIN, CHANNEL_MAX
)
from rf_spectrum_visualizer.exceptions import InvalidChannelError

print("=== Channel Model Tests ===")
print(f"CHANNEL_MIN={CHANNEL_MIN}, CHANNEL_MAX={CHANNEL_MAX}")
print(f"channel_to_frequency(0)={channel_to_frequency(0)}")
print(f"channel_to_frequency(122)={channel_to_frequency(122)}")
print(f"channel_to_frequency(125)={channel_to_frequency(125)}")
validate_channel(0)
validate_channel(125)
validate_channel(62)
print("Channel validation: OK")
try:
    validate_channel(126)
    print("ERROR: should have raised")
except InvalidChannelError as e:
    print(f"Invalid channel rejected: {e}")

# Test blocklist service
print("\n=== Blocklist Service Tests ===")
from v6.blocklist_manager import BlocklistManager as V6BlocklistManager
from v6.config import BlocklistConfig

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    f.write('[]')
    temp_path = f.name

try:
    config = BlocklistConfig(file_path=temp_path)
    bl = V6BlocklistManager(config)
    
    # Block channel 122
    entry = bl.block_channel(122, 'Test reason')
    print(f"Blocked channel 122: frequency={entry.frequency_mhz} MHz")
    assert entry.frequency_mhz == 2522, f"Expected 2522, got {entry.frequency_mhz}"
    assert bl.is_blocked(122), "Channel 122 should be blocked"
    
    # Check blocked channels list
    blocked = bl.get_blocked_channels()
    print(f"Blocked channels: {blocked}")
    assert 122 in blocked, "122 should be in blocked list"
    
    # Unblock channel 122
    result = bl.unblock_channel(122)
    print(f"Unblocked channel 122: {result}")
    assert result is True, "Should have been unblocked"
    assert not bl.is_blocked(122), "Channel 122 should no longer be blocked"
    
    # Test invalid channel
    try:
        bl.block_channel(126)
        print("ERROR: should have raised")
    except Exception as e:
        print(f"Invalid channel correctly rejected: {type(e).__name__}")
    
    # Test persistence
    print(f"Blocklist file exists: {os.path.exists(temp_path)}")
    with open(temp_path) as f:
        data = json.load(f)
    print(f"Blocklist file content: {data}")
    
    print("All blocklist service tests passed!")
finally:
    os.unlink(temp_path)

print("\n=== All Tests Passed ===")