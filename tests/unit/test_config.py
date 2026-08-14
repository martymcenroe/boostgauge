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