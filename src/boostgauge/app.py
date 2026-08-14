"""Main application entry point.

Issue #7: Feature: configuration file and CLI arguments
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from boostgauge.config import (
    get_default_config_path,
    get_default_config,
    load_config,
    write_full_config,
    apply_exit_write,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    config_file_path: Path
    in_memory_config: dict[str, Any] = field(default_factory=dict)
    hand_changed_keys: dict[str, Any] = field(default_factory=dict)


def parse_args(args: list[str]) -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="BoostGauge")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--reset-config", action="store_true", help="Reset config to defaults")
    parser.add_argument("--size", type=int, help="Override gauge size")
    return parser.parse_args(args)


def update_thresholds_from_file(path: Path, current_state: SessionState) -> None:
    """Reads file and updates ONLY the thresholds object in current_state.in_memory_config."""
    try:
        disk_data = load_config(path)
        if "thresholds" in disk_data:
            current_state.in_memory_config["thresholds"] = disk_data["thresholds"]
    except (FileNotFoundError, ValueError):
        logger.warning("Could not reload thresholds from %s", path)


def init_session(args: list[str]) -> SessionState:
    """Initializes and returns the session state from CLI args."""
    parsed = parse_args(args)
    config_path = parsed.config if parsed.config else get_default_config_path()

    if parsed.reset_config:
        write_full_config(config_path, get_default_config())
    elif not config_path.exists():
        write_full_config(config_path, get_default_config())

    in_memory_config = load_config(config_path)

    if parsed.size is not None:
        in_memory_config["size"] = parsed.size

    return SessionState(config_file_path=config_path, in_memory_config=in_memory_config)


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        state = init_session(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # GUI and main loop would go here.

    apply_exit_write(state.config_file_path, state.hand_changed_keys)
    return 0


if __name__ == "__main__":
    sys.exit(main())