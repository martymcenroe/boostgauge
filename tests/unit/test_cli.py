"""Unit tests for CLI argument parsing and override merging.

Issue #7: Configuration File and CLI Arguments
"""

import pytest
from boostgauge.config import get_default_config
from boostgauge.cli import build_cli_parser, parse_cli_args, merge_cli_overrides


def test_parse_cli_args_defaults():
    args = parse_cli_args([])
    assert args.theme is None
    assert args.size is None
    assert args.poll is None
    assert args.opacity is None
    assert args.no_topmost is False
    assert args.config is None
    assert args.reset_config is False


def test_parse_cli_args_theme_dark():
    args = parse_cli_args(["--theme", "dark"])
    assert args.theme == "dark"


def test_parse_cli_args_theme_light():
    args = parse_cli_args(["--theme", "light"])
    assert args.theme == "light"


def test_parse_cli_args_invalid_theme_raises():
    with pytest.raises(SystemExit):
        parse_cli_args(["--theme", "cyberpunk"])


def test_parse_cli_args_size():
    args = parse_cli_args(["--size", "400"])
    assert args.size == 400


def test_parse_cli_args_size_invalid_type_raises():
    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "big"])


def test_parse_cli_args_poll():
    args = parse_cli_args(["--poll", "5"])
    assert args.poll == 5


def test_parse_cli_args_poll_invalid_type_raises():
    with pytest.raises(SystemExit):
        parse_cli_args(["--poll", "fast"])


def test_parse_cli_args_opacity():
    args = parse_cli_args(["--opacity", "0.8"])
    assert args.opacity == pytest.approx(0.8)


def test_parse_cli_args_opacity_invalid_type_raises():
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "full"])


def test_parse_cli_args_no_topmost():
    args = parse_cli_args(["--no-topmost"])
    assert args.no_topmost is True


def test_parse_cli_args_config_path():
    args = parse_cli_args(["--config", "/tmp/my_config.json"])
    assert args.config == "/tmp/my_config.json"


def test_parse_cli_args_reset_config():
    args = parse_cli_args(["--reset-config"])
    assert args.reset_config is True


def test_parse_cli_args_all_valid_values():
    args = parse_cli_args([
        "--theme", "light",
        "--size", "400",
        "--poll", "1",
        "--opacity", "0.8",
        "--no-topmost",
        "--reset-config",
    ])
    assert args.theme == "light"
    assert args.size == 400
    assert args.poll == 1
    assert args.opacity == pytest.approx(0.8)
    assert args.no_topmost is True
    assert args.reset_config is True


def test_build_cli_parser_returns_parser():
    import argparse
    parser = build_cli_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_merge_cli_overrides_theme():
    config = get_default_config()
    args = parse_cli_args(["--theme", "light"])
    merged = merge_cli_overrides(config, args)
    assert merged.theme == "light"


def test_merge_cli_overrides_size():
    config = get_default_config()
    args = parse_cli_args(["--size", "500"])
    merged = merge_cli_overrides(config, args)
    assert merged.size == 500


def test_merge_cli_overrides_poll():
    config = get_default_config()
    args = parse_cli_args(["--poll", "3"])
    merged = merge_cli_overrides(config, args)
    assert merged.polling_interval_seconds == 3


def test_merge_cli_overrides_opacity():
    config = get_default_config()
    args = parse_cli_args(["--opacity", "0.5"])
    merged = merge_cli_overrides(config, args)
    assert merged.opacity == pytest.approx(0.5)


def test_merge_cli_overrides_no_topmost():
    config = get_default_config()
    assert config.always_on_top is True
    args = parse_cli_args(["--no-topmost"])
    merged = merge_cli_overrides(config, args)
    assert merged.always_on_top is False


def test_merge_cli_overrides_no_topmost_false_leaves_always_on_top():
    config = get_default_config()
    args = parse_cli_args([])
    merged = merge_cli_overrides(config, args)
    assert merged.always_on_top is True


def test_merge_cli_overrides_all_options():
    config = get_default_config()
    args = parse_cli_args([
        "--theme", "light",
        "--size", "500",
        "--no-topmost",
    ])
    merged = merge_cli_overrides(config, args)
    assert merged.theme == "light"
    assert merged.size == 500
    assert merged.always_on_top is False
    assert merged.opacity == pytest.approx(0.9)


def test_merge_cli_overrides_no_args_leaves_config_unchanged():
    config = get_default_config()
    args = parse_cli_args([])
    merged = merge_cli_overrides(config, args)
    assert merged.theme == "dark"
    assert merged.size == 300
    assert merged.polling_interval_seconds == 2
    assert merged.opacity == pytest.approx(0.9)
    assert merged.always_on_top is True


def test_merge_cli_overrides_does_not_alter_unrelated_fields():
    config = get_default_config()
    config.show_driver_label = False
    args = parse_cli_args(["--theme", "light"])
    merged = merge_cli_overrides(config, args)
    assert merged.show_driver_label is False


def test_merge_cli_overrides_config_flag_not_applied_to_config_object():
    config = get_default_config()
    args = parse_cli_args(["--config", "/tmp/some_path.json"])
    merged = merge_cli_overrides(config, args)
    assert merged.theme == "dark"