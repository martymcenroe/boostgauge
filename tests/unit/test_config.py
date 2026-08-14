import json
import pytest
from pathlib import Path
from boostgauge.config import load_config, apply_threshold_updates, save_session_changes, mitigate_invalid_config


def test_req_010(tmp_path):
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    assert config_file.exists()
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300
    assert active_config["size"] == 300


def test_req_020(tmp_path):
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump({"size": 200}, f)
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={"size": 400})
    assert active_config["size"] == 400
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 200


def test_req_030(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "w") as f:
        json.dump({"size": 200, "position": {"x": 120, "y": 120}}, f)
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    assert active_config["size"] == 200
    assert active_config["position"] == {"x": 120, "y": 120}


def test_req_040(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "w") as f:
        json.dump({"size": 200}, f)
    active_config = load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    assert active_config["size"] == 500
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300


def test_req_050(tmp_path):
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["thresholds"]["conpty"]["red"] = 70
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    new_config = apply_threshold_updates(str(config_file), active_config)
    assert new_config["thresholds"]["conpty"]["red"] == 70


def test_req_060(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["theme"] = "light"
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data2 = json.load(f)
    assert disk_data2["size"] == 400
    assert disk_data2["theme"] == "light"


def test_req_070(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["size"] = 500
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data2 = json.load(f)
    assert disk_data2["size"] == 400


def test_req_080(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "rb") as f:
        b1 = f.read()
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "rb") as f:
        b2 = f.read()
    assert b1 == b2


def test_req_090(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 100, "y": 100}


def test_req_100(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position={"x": 150, "y": 150}, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 150, "y": 150}


def test_req_110(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 100, "y": 100}


def test_req_120(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position={"x": 150, "y": 150}, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 150, "y": 150}


def test_req_130(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300


def test_req_140(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400


def test_req_150(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300


def test_req_160(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400


def test_req_170(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300


def test_req_180(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400


def test_req_190(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300


def test_req_200(tmp_path):
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400


def test_req_210(tmp_path):
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        f.write('{"polling_interval_seconds": "fast"')
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config(str(config_file), reset_flag=False, cli_overrides={})


def test_req_220(tmp_path):
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["theme"] = "light"
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    new_config = apply_threshold_updates(str(config_file), active_config)
    assert new_config["theme"] == "dark"


import json
import os
import pytest
from unittest import mock
from pathlib import Path
from boostgauge.config import (
    load_config,
    apply_threshold_updates,
    save_session_changes,
    mitigate_invalid_config,
)


def test_atomic_write_failure_cleans_temp_file(tmp_path):
    """Lines 85-87, 90: os.replace failure during config write cleans up temp and re-raises."""
    config_file = tmp_path / "config.json"

    real_replace = os.replace

    def fail_for_config(src, dst):
        if str(dst) == str(config_file):
            raise PermissionError("disk full")
        return real_replace(src, dst)

    with mock.patch("os.replace", side_effect=fail_for_config):
        with pytest.raises(PermissionError, match="disk full"):
            load_config(str(config_file), reset_flag=False, cli_overrides={})


def test_atomic_write_failure_unlink_also_fails(tmp_path):
    """Lines 88-89: temp file cleanup also fails after os.replace failure; original exception propagates."""
    config_file = tmp_path / "config.json"

    real_replace = os.replace

    def fail_for_config(src, dst):
        if str(dst) == str(config_file):
            raise PermissionError("disk full")
        return real_replace(src, dst)

    with mock.patch("os.replace", side_effect=fail_for_config):
        with mock.patch("os.unlink", side_effect=OSError("unlink blocked")):
            with pytest.raises(PermissionError, match="disk full"):
                load_config(str(config_file), reset_flag=False, cli_overrides={})


def test_mitigate_invalid_config_removes_old_corrupt_backup(tmp_path):
    """Line 109: when a .corrupt backup already exists, it is removed before renaming."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{bad json")
    corrupt_backup = Path(str(config_file) + ".corrupt")
    corrupt_backup.write_text("previous corrupt")

    with pytest.raises(Exception):
        mitigate_invalid_config(str(config_file))


def test_mitigate_invalid_config_remove_old_corrupt_oserror(tmp_path):
    """Lines 111-112: os.remove on old .corrupt fails with OSError; error is logged."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{bad json")
    corrupt_backup = Path(str(config_file) + ".corrupt")
    corrupt_backup.write_text("previous corrupt")

    real_remove = os.remove

    def fail_on_corrupt(path):
        if str(path).endswith(".corrupt"):
            raise OSError("access denied")
        return real_remove(path)

    with mock.patch("os.remove", side_effect=fail_on_corrupt):
        with pytest.raises(Exception):
            mitigate_invalid_config(str(config_file))


def test_apply_threshold_updates_no_disk_changes(tmp_path):
    """Line 149: returns current_config unchanged when on-disk thresholds match in-memory."""
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})

    result = apply_threshold_updates(str(config_file), active_config)
    assert result is active_config


def test_apply_threshold_updates_corrupt_json_on_disk(tmp_path):
    """Lines 155-157: JSONDecodeError on reload logs error and returns current_config."""
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})

    config_file.write_text("{{{not json")

    result = apply_threshold_updates(str(config_file), active_config)
    assert result == active_config


def test_apply_threshold_updates_file_deleted(tmp_path):
    """Lines 155-157: OSError when config file is missing; returns current_config."""
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})

    config_file.unlink()

    result = apply_threshold_updates(str(config_file), active_config)
    assert result == active_config


def test_save_session_changes_corrupt_json(tmp_path):
    """Lines 177-179: JSONDecodeError reading config prevents save; returns silently."""
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})

    config_file.write_text("{{{broken")

    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=500)

    # File not overwritten — still contains the broken content
    assert config_file.read_text() == "{{{broken"


def test_save_session_changes_file_deleted(tmp_path):
    """Lines 177-179: OSError when config file is missing; returns silently without creating file."""
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})

    config_file.unlink()

    save_session_changes(
        str(config_file), hand_changed_position={"x": 50, "y": 50}, hand_changed_size=200
    )

    assert not config_file.exists()
