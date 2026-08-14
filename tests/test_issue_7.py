"""Test file for Issue #7.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

import json
import argparse
from pathlib import Path
import pytest
from boostgauge.config import get_default_config, write_full_config, load_config, apply_exit_write
from boostgauge.app import main, SessionState, update_thresholds_from_file, parse_args, init_session


def test_req_1(tmp_path):
    # First run with no config file creates one with defaults (REQ-1)
    # Expected output: File exists and matches get_default_config()
    config_path = tmp_path / "config.json"
    init_session(["--config", str(config_path)])
    assert config_path.exists()
    assert load_config(config_path) == get_default_config()


def test_req_2(tmp_path):
    # Launch order and CLI overrides (REQ-2)
    # Expected output: Session size is 400, file remains default size (300)
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    state = init_session(["--config", str(config_path), "--size", "400"])
    
    assert state.in_memory_config["size"] == 400
    assert load_config(config_path)["size"] == 300


def test_req_3(tmp_path):
    # Base launch window props (REQ-3)
    # Expected output: Memory size and position match file
    config_path = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["size"] = 250
    custom_cfg["position"] = {"x": 10, "y": 20}
    write_full_config(config_path, custom_cfg)
    
    state = init_session(["--config", str(config_path)])
    assert state.in_memory_config["size"] == 250
    assert state.in_memory_config["position"] == {"x": 10, "y": 20}


def test_req_4_no_size(tmp_path):
    # Reset config flag effects without CLI size (REQ-4)
    # Expected output: File size is 300, memory size is 300
    config_path = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["size"] = 250
    write_full_config(config_path, custom_cfg)
    
    state = init_session(["--config", str(config_path), "--reset-config"])
    assert load_config(config_path)["size"] == 300
    assert state.in_memory_config["size"] == 300


def test_req_4_with_size(tmp_path):
    # Reset config flag effects with CLI size (REQ-4)
    # Expected output: File size is 300, memory size is 500
    config_path = tmp_path / "config.json"
    state = init_session(["--config", str(config_path), "--reset-config", "--size", "500"])
    assert load_config(config_path)["size"] == 300
    assert state.in_memory_config["size"] == 500


def test_req_5(tmp_path):
    # Threshold live reload (REQ-5)
    # Expected output: Memory threshold is 40, file is unmodified by read
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    state = SessionState(config_file_path=config_path, in_memory_config=get_default_config())
    
    disk_cfg = load_config(config_path)
    disk_cfg["thresholds"]["conpty"]["yellow"] = 40
    write_full_config(config_path, disk_cfg)
    
    update_thresholds_from_file(config_path, state)
    assert state.in_memory_config["thresholds"]["conpty"]["yellow"] == 40


def test_req_6(tmp_path):
    # Exit write patch logic (REQ-6)
    # Expected output: File size is 999 and position is updated
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # Direct edit mid-session
    disk_cfg = load_config(config_path)
    disk_cfg["size"] = 999
    write_full_config(config_path, disk_cfg)
    
    # Hand change position
    apply_exit_write(config_path, {"position": {"x": 5, "y": 5}})
    
    final_cfg = load_config(config_path)
    assert final_cfg["size"] == 999
    assert final_cfg["position"] == {"x": 5, "y": 5}


def test_req_7(tmp_path):
    # Exit write collision logic (REQ-7)
    # Expected output: File size is 600
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # Direct edit mid-session
    disk_cfg = load_config(config_path)
    disk_cfg["size"] = 999
    write_full_config(config_path, disk_cfg)
    
    # Hand change size collision
    apply_exit_write(config_path, {"size": 600})
    
    assert load_config(config_path)["size"] == 600


def test_req_8(tmp_path):
    # Untouched session (REQ-8)
    # Expected output: File hash before matches file hash after
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    content_before = config_path.read_bytes()
    
    apply_exit_write(config_path, {})
    assert config_path.read_bytes() == content_before


def test_req_9(tmp_path):
    # Position: no reset, not moved, no direct edits (REQ-9)
    # Expected output: File position matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["position"] == {"x": 100, "y": 100}


def test_req_10(tmp_path):
    # Position: no reset, moved, no direct edits (REQ-10)
    # Expected output: File position is {"x": 5, "y": 5}
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {"position": {"x": 5, "y": 5}})
    assert load_config(config_path)["position"] == {"x": 5, "y": 5}


def test_req_11(tmp_path):
    # Position: reset, not moved, no direct edits (REQ-11)
    # Expected output: File position is {"x": 100, "y": 100}
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["position"] == {"x": 100, "y": 100}


def test_req_12(tmp_path):
    # Position: reset, moved, no direct edits (REQ-12)
    # Expected output: File position matches hand-changed pos
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {"position": {"x": 50, "y": 50}})
    assert load_config(config_path)["position"] == {"x": 50, "y": 50}


def test_req_13(tmp_path):
    # Size: no reset, no size, not resized, no edits (REQ-13)
    # Expected output: File size matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_14(tmp_path):
    # Size: no reset, no size, resized, no edits (REQ-14)
    # Expected output: File size is 700
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    apply_exit_write(config_path, {"size": 700})
    assert load_config(config_path)["size"] == 700


def test_req_15(tmp_path):
    # Size: no reset, size given, not resized, no edits (REQ-15)
    # Expected output: File size matches initial, not 450
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    # CLI size 450 happens via init_session() but user doesn't hand-resize
    init_session(["--config", str(config_path), "--size", "450"])
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_16(tmp_path):
    # Size: no reset, size given, resized, no edits (REQ-16)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    
    init_session(["--config", str(config_path), "--size", "450"])
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_17(tmp_path):
    # Size: reset, no size, not resized, no edits (REQ-17)
    # Expected output: File size is 300
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_18(tmp_path):
    # Size: reset, no size, resized, no edits (REQ-18)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config"])
    
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_19(tmp_path):
    # Size: reset, size given, not resized, no edits (REQ-19)
    # Expected output: File size is 300
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config", "--size", "450"])
    
    apply_exit_write(config_path, {})
    assert load_config(config_path)["size"] == 300


def test_req_20(tmp_path):
    # Size: reset, size given, resized, no edits (REQ-20)
    # Expected output: File size is 800
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    main(["--config", str(config_path), "--reset-config", "--size", "450"])
    
    apply_exit_write(config_path, {"size": 800})
    assert load_config(config_path)["size"] == 800


def test_req_21(tmp_path):
    # Invalid config values (REQ-21)
    # Expected output: ValueError raised
    config_path = tmp_path / "config.json"
    config_path.write_text("{invalid json")
    
    with pytest.raises(ValueError):
        load_config(config_path)


def test_req_22(tmp_path):
    # Non-threshold live edit ignored (REQ-22)
    # Expected output: Memory telltale_windows.short matches initial
    config_path = tmp_path / "config.json"
    write_full_config(config_path, get_default_config())
    state = SessionState(config_file_path=config_path, in_memory_config=get_default_config())
    
    disk_cfg = load_config(config_path)
    disk_cfg["telltale_windows"]["short"] = 999
    write_full_config(config_path, disk_cfg)
    
    update_thresholds_from_file(config_path, state)
    assert state.in_memory_config["telltale_windows"]["short"] == 60
