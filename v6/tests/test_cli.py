"""Tests for CLI module."""

import pytest
import subprocess
import sys
import json
import tempfile
import os
from pathlib import Path


@pytest.fixture
def cli_env():
    """Environment for CLI tests."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    return env


def run_cli(args, env=None, cwd=None):
    """Run CLI command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "v6.cli_scan"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIBasic:
    def test_help(self, cli_env):
        code, out, err = run_cli(["help"], env=cli_env)
        assert code == 0
        assert "usage" in out.lower() or "commands" in out.lower()
    
    def test_help_no_args(self, cli_env):
        code, out, err = run_cli([], env=cli_env)
        assert code == 0
        assert "usage" in out.lower() or "commands" in out.lower()
    
    def test_simulate_quiet(self, cli_env):
        code, out, err = run_cli(["simulate", "--scenario", "quiet"], env=cli_env)
        assert code == 0
        assert "SIMULATION MODE" in out
        assert "quiet" in out.lower()
    
    def test_simulate_channel_122_high(self, cli_env):
        code, out, err = run_cli(["simulate", "--scenario", "channel_122_high"], env=cli_env)
        assert code == 0
        assert "channel_122_high" in out
    
    def test_simulate_deterministic(self, cli_env):
        code1, out1, err1 = run_cli(["simulate", "--scenario", "mixed", "--seed", "42"], env=cli_env)
        code2, out2, err2 = run_cli(["simulate", "--scenario", "mixed", "--seed", "42"], env=cli_env)
        
        assert code1 == 0
        assert code2 == 0
        # Should produce identical output with same seed
        assert out1 == out2


class TestCLIBlocklist:
    def test_block_channel(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        code, out, err = run_cli([
            "block", "122", "--reason", "Test block",
            "--blocklist-file", str(blocklist_file)
        ], env=cli_env)
        
        assert code == 0
        assert "Blocked" in out
        assert blocklist_file.exists()
        
        # Verify content
        with open(blocklist_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["channel"] == 122
        assert data[0]["reason"] == "Test block"
    
    def test_unblock_channel(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        
        # First block
        run_cli(["block", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        # Then unblock
        code, out, err = run_cli(["unblock", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "Unblocked" in out
        
        with open(blocklist_file) as f:
            data = json.load(f)
        assert len(data) == 0
    
    def test_unblock_not_blocked(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        code, out, err = run_cli(["unblock", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "not blocked" in out
    
    def test_blocklist_show(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        
        run_cli(["block", "10", "--blocklist-file", str(blocklist_file)], env=cli_env)
        run_cli(["block", "20", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        code, out, err = run_cli(["blocklist", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "10" in out
        assert "20" in out
        assert "Total:" in out
    
    def test_blocklist_empty(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "empty_blocklist.json"
        code, out, err = run_cli(["blocklist", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "empty" in out.lower()
    
    def test_channel_check(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        
        run_cli(["block", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        code, out, err = run_cli(["channel", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "BLOCKED" in out
    
    def test_channel_not_blocked(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "test_blocklist.json"
        
        code, out, err = run_cli(["channel", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "NOT blocked" in out
    
    def test_channels_list(self, cli_env):
        code, out, err = run_cli(["channels"], env=cli_env)
        
        assert code == 0
        assert "Ch   0" in out
        assert "Ch 125" in out
    
    def test_recommend(self, cli_env):
        code, out, err = run_cli(["recommend", "--count", "3"], env=cli_env)
        
        assert code == 0
        assert "RECOMMENDATIONS" in out or "NO ELIGIBLE" in out
    
    def test_export_json(self, cli_env):
        code, out, err = run_cli(["export", "--format", "json"], env=cli_env)
        
        assert code == 0
        data = json.loads(out)
        assert "metadata" in data
        assert "channel_assessments" in data
    
    def test_export_csv(self, cli_env):
        code, out, err = run_cli(["export", "--format", "csv"], env=cli_env)
        
        assert code == 0
        lines = out.strip().split("\n")
        assert len(lines) > 1  # Header + data
        assert "channel" in lines[0]
    
    def test_diagnostic(self, cli_env):
        code, out, err = run_cli(["diagnostic"], env=cli_env)
        
        assert code == 0
        assert "Hardware Diagnostic" in out


class TestCLIScan:
    def test_single_scan(self, cli_env):
        code, out, err = run_cli(["scan", "--single", "--format", "json"], env=cli_env)
        
        assert code == 0
        data = json.loads(out)
        assert "metadata" in data
    
    def test_single_scan_csv(self, cli_env):
        code, out, err = run_cli(["scan", "--single", "--format", "csv"], env=cli_env)
        
        assert code == 0
        lines = out.strip().split("\n")
        assert len(lines) > 1
        assert "channel" in lines[0]


class TestCLIErrors:
    def test_invalid_channel(self, cli_env):
        code, out, err = run_cli(["block", "999"], env=cli_env)
        assert code != 0
        assert "out of range" in err.lower() or "error" in err.lower()
    
    def test_invalid_frequency(self, cli_env):
        code, out, err = run_cli(["block", "3000 MHz"], env=cli_env)
        assert code != 0


class TestCLIPersistence:
    def test_persistence_across_invocations(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "persist_test.json"
        
        # Block in first invocation
        run_cli(["block", "122", "--reason", "Persist test", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        # Check in second invocation
        code, out, err = run_cli(["channel", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "BLOCKED" in out
        assert "Persist test" in out
    
    def test_persistence_unblock(self, cli_env, tmp_path):
        blocklist_file = tmp_path / "persist_test.json"
        
        run_cli(["block", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        run_cli(["unblock", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        code, out, err = run_cli(["channel", "122", "--blocklist-file", str(blocklist_file)], env=cli_env)
        
        assert code == 0
        assert "NOT blocked" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
